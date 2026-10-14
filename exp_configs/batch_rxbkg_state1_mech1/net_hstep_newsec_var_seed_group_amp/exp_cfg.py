import json
from pathlib import Path
import sys


dirpath_repo_root = Path(__file__).resolve().parents[3]
dirpath_self = Path(__file__).resolve().parent
# Resolve companion repositories explicitly in both local and HPC checkouts
for path in (dirpath_repo_root, dirpath_repo_root.parent, dirpath_repo_root / 'external'):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xarray as xr

from analysis.ou_tuning.netpyne_res_parse_utils import prepare_sim_result
from exp_configs.batch_rxbkg_state1_mech1.net_hstep_newsec_var_seed_group_amp import batch_params as batch
from sim_data_analyzer.netpyne_res_parse_utils import get_pop_size, get_pop_spikes
from sim_data_analyzer.xr_adapters import get_net_rate_dynamics_xr


# Define the connected circuit and step timing in milliseconds
EXP_LABEL = 'L2'
POPS_USED = batch.L2_POPS
SIM_DURATION = 40 * 1e3
T0_CALC = 10 * 1e3
H_STEP_T0 = 20 * 1e3
H_STEP_TRESP = 30 * 1e3
H_STIM_PREFIX = 'hstep'

# Derive half-open windows in seconds and split the response interval in half
RATE_WINDOWS = {
    'baseline': (T0_CALC / 1000, H_STEP_T0 / 1000),
    'response': (H_STEP_TRESP / 1000, SIM_DURATION / 1000),
    'response_early': (H_STEP_TRESP / 1000, (H_STEP_TRESP + SIM_DURATION) / 2000),
    'response_late': ((H_STEP_TRESP + SIM_DURATION) / 2000, SIM_DURATION / 1000),
}

# Preserve the calibrated baseline from the h-sweep experiment
XBKG_NAME = 'rx_bkg_mid_sm_ctx21_thal41'
USE_IBKG = 1
IBKG_JSON_NAME = 'ibkg_mech1_verest_-70_thal_spkthr'
USE_IBKG_CTRL = 1
IBKG_CTRL_JSON_NAME = 'ibkg_ctrl_1'

# Save unsmoothed rates and apply smoothing only to figures
RVEC_DT_BIN = 0.005
PLOT_RATE_DYNAMICS = 1
PLOT_RATE_SMOOTH_S = 0.2
NEED_RUN = 1


def _format_time_s(time_ms):
    """Format milliseconds as seconds with at most two decimal places. """
    return f'{time_ms / 1000:.2f}'.rstrip('0').rstrip('.')


def gen_exp_name_sub(cfg):
    """Name the complete protocol independently of the current batch subset. """
    # Format path timings in seconds without trailing zeros
    duration_label = _format_time_s(cfg.duration)
    step_t0_label = _format_time_s(cfg.h_step_t0)
    tresp_label = _format_time_s(cfg.h_step_tresp)

    # Name the complete configured grid
    name = f'exp_{EXP_LABEL}'
    if batch.PILOT:
        name += f'_pilot{batch.PILOT_ATTEMPT}'
    name += f'_nseed_{batch.N_SEEDS}'
    name += f'_ngroup_{len(cfg.step_group_names)}_namp_{len(cfg.step_amp_values)}'
    name += f'_dur_{duration_label}_step_t0_{step_t0_label}_tresp_{tresp_label}'
    name += f'_gset_{cfg.step_group_set_label}'
    name += f'_amin_{min(cfg.step_amp_values):g}_amax_{max(cfg.step_amp_values):g}'
    if USE_IBKG_CTRL:
        name += '_ictrl'
    name += f'_wmult_{cfg.wmult}_ee_{cfg.EEGain}'
    return name


def _get_job_postfix(child_key, parameters):
    """Name one output using the job ID and all three batch coordinates. """
    if set(parameters) != {'seed_main', 'step_group', 'amp'}:
        raise ValueError('Unexpected h-step batch parameters')
    group = parameters['step_group']
    amp = float(parameters['amp'])
    if group not in batch.STEP_GROUPS or not np.isfinite(amp):
        raise ValueError('Invalid h-step group or amplitude')
    amp_label = '0' if amp == 0 else str(amp)
    child_id = child_key.rsplit('_', 1)[-1]
    return (
        f'{child_id}_seed_{parameters["seed_main"]}'
        f'_group_{group}_amp_{amp_label}'
    )


def get_batch_completion_files(child_key, parameters):
    """Return the compact outputs owned by one connected h-step job. """
    postfix = _get_job_postfix(child_key, parameters)
    return [
        f'cfg/cfg_{postfix}.json',
        f'results/result_{postfix}.json',
        f'rvec_xr/rvec_{postfix}.nc',
        f'hvec_xr/hvec_{postfix}.nc',
    ]


def _validate_timing(cfg):
    """Check that measurement windows belong to the intended step phases. """
    onset = cfg.h_step_t0 / 1000
    duration = cfg.duration / 1000
    if not 0 < onset < duration:
        raise ValueError('The step onset must lie inside the simulation')
    for name, (start, stop) in cfg.rate_windows.items():
        if not 0 <= start < stop <= duration:
            raise ValueError(f'Invalid measurement window: {name}')
        if name == 'baseline' and stop > onset:
            raise ValueError('The baseline window must precede the step')
        if name != 'baseline' and start < onset:
            raise ValueError(f'The {name} window must follow the step')


def apply_exp_cfg(cfg):
    """Configure the calibrated connected L2 model with additive step inputs. """
    cfg.duration = SIM_DURATION
    cfg.t0_calc = T0_CALC
    cfg.need_run = NEED_RUN
    cfg.pops_used = list(POPS_USED)
    cfg.seed_main = None
    cfg.step_group = None
    cfg.amp = None
    cfg.seeds['stim'] = None
    cfg.seeds['conn'] = None
    cfg.includeParamsLabel = True
    cfg.cache_efficient = 0

    # Store the complete amplitude-independent group table in every job
    cfg.step_groups = batch.get_step_groups(cfg.pops_used)
    cfg.step_group_names = list(batch.STEP_GROUPS)
    cfg.step_group_set_label = batch.GROUP_SET_LABEL
    cfg.step_amp_values = batch.AMP_VALUES.copy()
    cfg.h_step_t0 = H_STEP_T0
    cfg.h_step_tresp = H_STEP_TRESP
    cfg.rate_windows = dict(RATE_WINDOWS)
    cfg.h_step = {pop: 0 for pop in cfg.pops_used}
    _validate_timing(cfg)

    # Restore recurrent L2 projections while retaining external surrogates
    cfg.subnet_build_flag = 1
    cfg.subnet_params = {
        'pops_active': cfg.pops_used,
        'conns_frozen': [],
        'fpath_frozen_rates': str(dirpath_self / 'target_state_1.csv'),
        'global_seed': None,
    }
    cfg.wmult = 0.25
    cfg.EEGain = 0.5
    cfg.addSubConn = 0
    cfg.connRandomSecFromList = 1
    cfg.connWeightSecByLength = 0

    # Reuse the calibrated stochastic background and its targeting
    df = pd.read_csv(dirpath_self / f'{XBKG_NAME}.csv').set_index('pop')
    df['rxe'] = np.maximum(df['rxe'], 1e-3)
    df['rxi'] = np.maximum(df['rxi'], 1e-3)
    xbkg_info = df.T.to_dict()
    cfg.add_bkg_spike_input = 1
    cfg.replace_bkg_spikes_by_ou = 0
    cfg.bkg_spike_inputs = {}
    for pop in cfg.pops_used:
        x = xbkg_info[pop]
        cfg.bkg_spike_inputs[pop] = {
            'exc': {
                'r': x['rxe'],
                'w': x['wxe'],
                'sec': x['xe_sec'],
                'noise': 1,
                'seed': None,
            },
            'inh': {
                'r': x['rxi'],
                'w': x['wxi'],
                'sec': x['xi_sec'],
                'noise': 1,
                'seed': None,
            },
        }

    # Keep the two baseline-current components as separate ordinary clamps
    cfg.IClamp = {}
    if USE_IBKG:
        with open(dirpath_self / f'{IBKG_JSON_NAME}.json', 'r') as fid:
            ibkg = json.load(fid)
        cfg.IClamp = {
            pop: {'amp': ibkg[pop], 'dur': cfg.duration}
            for pop in cfg.pops_used if pop in ibkg
        }
    if USE_IBKG_CTRL:
        with open(dirpath_self / f'{IBKG_CTRL_JSON_NAME}.json', 'r') as fid:
            ibkg_ctrl = json.load(fid)
        for pop in cfg.pops_used:
            if pop not in ibkg_ctrl['I_median']:
                continue
            entry = {'amp': ibkg_ctrl['I_median'][pop], 'dur': cfg.duration}
            if pop in cfg.IClamp:
                cfg.IClamp[pop] = [cfg.IClamp[pop], entry]
            else:
                cfg.IClamp[pop] = entry
    cfg.addIClamp = int(bool(cfg.IClamp))

    # Retain calibration metadata and the established membrane changes
    df = pd.read_csv(dirpath_self / 'target_state_1.csv')
    cfg.target_rates = df.set_index('pop_name')['target_rate'].to_dict()
    with open(dirpath_self / 'mech_changes_1.json', 'r') as fid:
        cfg.mech_changes = json.load(fid)
    for name in ('plotRaster', 'plotSpikeStats', 'plotTraces'):
        if isinstance(cfg.analysis.get(name), dict):
            cfg.analysis[name]['include'] = cfg.pops_used
    cfg.analysis['plotSpikeStats'] = False


def _get_cond_pops(conditions):
    """Read explicit population labels from a connection condition. """
    pops = conditions['pop']
    return [pops] if isinstance(pops, str) else list(pops)


def _count_recurrent_rules(params, pops_used):
    """Count connection rules for each existing active-population pair. """
    counts = {}
    for conn in params.connParams.values():
        for pre in _get_cond_pops(conn['preConds']):
            for post in _get_cond_pops(conn['postConds']):
                if pre in pops_used and post in pops_used:
                    pair = f'{pre}->{post}'
                    counts[pair] = counts.get(pair, 0) + 1
    return counts


def modify_net_params(cfg, params):
    """Apply calibrated targeting and declare ordinary NetPyNE step clamps. """
    # Preserve the calibrated membrane-mechanism changes
    for change in cfg.mech_changes.values():
        secs_all = params.cellParams[change['pop']]['secs']
        secs = list(secs_all.values()) if change['sec'] == 'all' else [secs_all[change['sec']]]
        for sec in secs:
            mech = sec['mechs'][change['mech']]
            mech[change['par']] *= change['mult']
            mech[change['par']] += change['add']

    # Keep newsec targets identical to the open-loop identification
    with open(dirpath_self / 'target_sec_1.json', 'r') as fid:
        target_sec = json.load(fid)
    for cname, conn in params.connParams.items():
        pop_pre = conn['preConds'].get('pop')
        pop_post = conn['postConds'].get('pop')
        if pop_pre is None or pop_post is None:
            raise ValueError(f'Pre or post pop is not specified for conn {cname}')
        conn['sec'] = None
        for target in target_sec.values():
            if pop_pre in target['pops_pre'] and pop_post in target['pops_post']:
                conn['sec'] = target['sec']
                break
        if conn['sec'] is None:
            raise ValueError(f'No target section specified for conn {cname}')
    cfg.hstep_expected_recurrent_rules = _count_recurrent_rules(params, cfg.pops_used)

    # Declare an additive step source for every active population, including controls
    for pop in cfg.pops_used:
        source = f'{H_STIM_PREFIX}_{pop}'
        params.stimSourceParams[source] = {
            'type': 'IClamp',
            'delay': cfg.h_step_t0,
            'dur': cfg.duration - cfg.h_step_t0,
            'amp': cfg.h_step[pop],
        }
        params.stimTargetParams[f'{source}->{pop}'] = {
            'source': source,
            'conds': {'pop': pop},
            'sec': 'soma',
            'loc': 0.5,
        }


def modify_net_params_2(cfg, params):
    """Verify the connected subnet and record its connection-rule summary. """
    counts = _count_recurrent_rules(params, cfg.pops_used)
    if not counts or counts != cfg.hstep_expected_recurrent_rules:
        raise ValueError('The subnet did not preserve the recurrent L2 rules')
    frozen = {pop: par for pop, par in params.popParams.items() if pop.endswith('frz')}
    if any(pop[:-3] in cfg.pops_used for pop in frozen):
        raise ValueError('The connected subnet contains duplicated L2 surrogates')
    cfg.hstep_topology = {
        'pops_active': cfg.pops_used,
        'recurrent_rules_by_pair': counts,
        'surrogate_rates_hz': {pop: par['rate'] for pop, par in frozen.items()},
        'summary_type': 'connection rules, not realized synapse counts',
    }


def modify_network(sim):
    """Check instantiated step clamps and count them across MPI ranks. """
    cfg = sim.cfg
    counts = {pop: 0 for pop in cfg.pops_used}
    for cell in sim.net.cells:
        pop = cell.tags['pop']
        if pop not in counts:
            continue
        source = f'{H_STIM_PREFIX}_{pop}'
        stims = [stim for stim in cell.stims if stim.get('source') == source]
        if len(stims) != 1 or stims[0].get('hObj') is None:
            raise ValueError(f'Expected one instantiated {source} on gid={cell.gid}')
        clamp = stims[0]['hObj']
        actual = [clamp.delay, clamp.dur, clamp.amp]
        expected = [cfg.h_step_t0, cfg.duration - cfg.h_step_t0, cfg.h_step[pop]]
        if not np.allclose(actual, expected, rtol=0, atol=1e-12):
            raise ValueError(f'Unexpected step parameters on gid={cell.gid}')
        counts[pop] += 1

    # Retain all-rank clamp counts for the compact result summary
    all_counts = sim.pc.py_allgather(counts)
    sim.hstep_clamp_counts = {
        pop: sum(rank_counts[pop] for rank_counts in all_counts)
        for pop in cfg.pops_used
    }


def _get_window_stats(sim_result, cfg):
    """Compute window rates from half-open spike counts without smoothing. """
    stats = {name: {} for name in cfg.rate_windows}
    for pop in cfg.pops_used:
        ncells = get_pop_size(sim_result, pop)
        if ncells <= 0:
            raise ValueError(f'No active cells in population {pop}')
        spikes = get_pop_spikes(sim_result, pop, subtract_t0=False, ms=False)[0]
        for name, (start, stop) in cfg.rate_windows.items():
            count = int(np.sum((spikes >= start) & (spikes < stop)))
            stats[name][pop] = {
                'n_cells': ncells,
                'n_spikes': count,
                'rate_hz': count / (ncells * (stop - start)),
            }
    return stats


def _build_hvec_xr(rvec_xr, cfg):
    """Evaluate the declared current step at the saved population-rate times. """
    times = np.asarray(rvec_xr.time.values)
    active = (times >= cfg.h_step_t0 / 1000) & (times < cfg.duration / 1000)
    values = np.asarray([cfg.h_step[pop] * active for pop in cfg.pops_used])
    hvec = xr.DataArray(
        values,
        dims=('pop', 'time'),
        coords={'pop': cfg.pops_used, 'time': times},
        name='h',
    )
    hvec.attrs.update(rvec_xr.attrs)
    hvec.attrs['units'] = 'nA'
    hvec.attrs['waveform'] = 'step'
    return hvec


def _plot_rate_dynamics(rvec, hvec, cfg, fpath):
    """Plot smoothed rates and declared currents without axes grids. """
    n_smooth = max(1, int(round(PLOT_RATE_SMOOTH_S / RVEC_DT_BIN)))
    rates_plot = rvec.rolling(time=n_smooth, center=True, min_periods=1).mean()
    fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
    for n, pop in enumerate(cfg.pops_used):
        color = f'C{n % 10}'
        axes[0].plot(rvec.time, rates_plot.sel(pop=pop), label=pop, color=color)
        axes[1].step(hvec.time, hvec.sel(pop=pop), where='post', color=color)
    for axis in axes:
        axis.axvline(cfg.h_step_t0 / 1000, color='0.5', linestyle='--')
        axis.grid(False)
    axes[0].set_title(f'{cfg.step_group}, amp={cfg.amp:g} nA, seed={cfg.seed_main}')
    axes[0].set_ylabel('Firing rate (Hz)')
    axes[0].legend(bbox_to_anchor=(1, 1))
    axes[1].set_ylabel('h (nA)')
    axes[1].set_xlabel('Time (s)')
    fig.tight_layout()
    fig.savefig(fpath, bbox_inches='tight', dpi=150)
    plt.close(fig)


def post_run(sim):
    """Organize simulation artifacts and save compact step-response outputs. """
    cfg = sim.cfg
    parameters = {name: getattr(cfg, name) for name in ('seed_main', 'step_group', 'amp')}
    postfix = _get_job_postfix(cfg.simLabel, parameters)
    dirpath_res = Path(cfg.saveFolder)
    dirpath_sub = dirpath_res / gen_exp_name_sub(cfg)
    expected = get_batch_completion_files(cfg.simLabel, parameters)
    if any((dirpath_sub / name).exists() for name in expected):
        raise FileExistsError(f'H-step outputs already exist for {postfix}')
    for name in ('rasters', 'results', 'cfg', 'pkl', 'netpar', 'rvec_figs', 'rvec_xr', 'hvec_xr'):
        (dirpath_sub / name).mkdir(parents=True, exist_ok=True)

    # Move the ordinary NetPyNE artifacts into typed output subdirectories
    artifacts = [
        ('raster', 'png', 'rasters'),
        ('data', 'pkl', 'pkl'),
        ('cfg', 'json', 'cfg'),
        ('netParams', 'json', 'netpar'),
    ]
    for label, ext, dirname in artifacts:
        source = dirpath_res / f'{cfg.simLabel}_{label}.{ext}'
        destination = dirpath_sub / dirname / f'{label}_{postfix}.{ext}'
        if source.exists():
            source.rename(destination)
        elif label == 'cfg':
            raise FileNotFoundError(f'Missing job configuration: {source}')

    # Extract unsmoothed compact rates using sim_data_analyzer
    sim_result = prepare_sim_result(sim)
    rvec = get_net_rate_dynamics_xr(
        sim_result,
        t_limits=(0, cfg.duration / 1000),
        dt_bin=RVEC_DT_BIN,
        tau_smooth=None,
        pop_names=cfg.pops_used,
    )
    rvec.attrs = {
        'units': 'Hz',
        'seed_main': int(cfg.seed_main),
        'step_group': cfg.step_group,
        'amp_nA': float(cfg.amp),
        'exp_label': EXP_LABEL,
        'h_step_t0_ms': cfg.h_step_t0,
        'h_step_tresp_ms': cfg.h_step_tresp,
        'h_step_nA_json': json.dumps(cfg.h_step, sort_keys=True),
        'dt_bin_s': RVEC_DT_BIN,
        'tau_smooth_s': 0,
    }
    rvec.to_netcdf(dirpath_sub / 'rvec_xr' / f'rvec_{postfix}.nc')
    hvec = _build_hvec_xr(rvec, cfg)
    hvec.to_netcdf(dirpath_sub / 'hvec_xr' / f'hvec_{postfix}.nc')

    # Save counts, window means, and topology evidence for local comparison
    result = {
        'timing': sim.timingData,
        'parameters': parameters,
        'h_step_nA': cfg.h_step,
        'step_pops': cfg.step_pops,
        'rate_windows_s': cfg.rate_windows,
        'window_boundary_convention': 'start <= spike time < stop',
        'window_stats': _get_window_stats(sim_result, cfg),
        'topology': cfg.hstep_topology,
        'h_clamp_count_by_pop': sim.hstep_clamp_counts,
    }
    with open(dirpath_sub / 'results' / f'result_{postfix}.json', 'w') as fid:
        json.dump(result, fid, indent=2)
    if PLOT_RATE_DYNAMICS:
        fpath = dirpath_sub / 'rvec_figs' / f'{EXP_LABEL}_{postfix}.png'
        _plot_rate_dynamics(rvec, hvec, cfg, fpath)
    if not all((dirpath_sub / name).is_file() for name in expected):
        raise FileNotFoundError('Connected h-step completion files were not produced')
    return expected
