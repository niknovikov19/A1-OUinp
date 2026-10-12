import json
import os
from pathlib import Path
import sys

dirpath_repo_root = Path(__file__).resolve().parents[3]
dirpath_self = Path(__file__).resolve().parent
sys.path.append(str(dirpath_repo_root))
sys.path.append(str(dirpath_self))

import matplotlib.pyplot as plt
from neuron import h
import numpy as np
import pandas as pd
import xarray as xr

from analysis.ou_tuning import sim_res_proc_utils as proc
from analysis.ou_tuning.netpyne_res_parse_utils import prepare_sim_result
from batch_params import L2_POPS, N_SEEDS, PILOT
from sim_data_analyzer.xr_adapters import get_net_rate_dynamics_xr


SIM_DURATION = 20 * 1e3
T0_CALC = 5 * 1e3

EXP_LABEL = 'L2'
POPS_USED = L2_POPS

# Direct-current identification waveform
H_SWEEP_TYPE = 'tri'
H_SWEEP_T0 = 5000
H_SWEEP_PERIOD = 7500
H_SWEEP_AMPS = {pop: 0.1 for pop in POPS_USED}
H_STIM_PREFIX = 'hsweep'

# Calibrated baseline inputs
XBKG_NAME = 'rx_bkg_mid_sm_ctx21_thal41'
USE_IBKG = 1
IBKG_JSON_NAME = 'ibkg_mech1_verest_-70_thal_spkthr'
USE_IBKG_CTRL = 1
IBKG_CTRL_JSON_NAME = 'ibkg_ctrl_1'
SURR_INP_ON = 1

RVEC_TAU_SMOOTH = 0.02
PLOT_RATE_DYNAMICS = 1
NEED_RUN = 1


def _get_h_source(pop):
    """Return the NetPyNE source label for one population's h clamp."""
    return f'{H_STIM_PREFIX}_{pop}'


def _triangle_scale(t_ms, t0, period):
    """Evaluate a zero-centered unit triangle after its onset."""
    t_ms = np.asarray(t_ms, dtype=float)
    scale = np.zeros_like(t_ms)
    active = t_ms >= t0
    phase = ((t_ms[active] - t0) / period) % 1
    scale[active] = np.interp(
        phase,
        [0, 0.25, 0.5, 0.75, 1],
        [0, 1, 0, -1, 0],
    )
    return scale


def get_hsweep_corners(duration, amp, t0=H_SWEEP_T0,
                       period=H_SWEEP_PERIOD):
    """Return sparse time and current knots for one triangular h sweep."""
    if not 0 < t0 < duration:
        raise ValueError(f'Expected 0 < t0 < duration, got {t0}, {duration}')
    if period <= 0:
        raise ValueError(f'Expected a positive period, got {period}')
    if amp < 0:
        raise ValueError(f'Expected a non-negative amplitude, got {amp}')

    # Start from the unperturbed operating point
    times = [0, float(t0)]
    currents = [0, 0]
    n_cycles = int(np.ceil((duration - t0) / period))

    # Add the four linear segments of every required cycle
    fractions = [0.25, 0.5, 0.75, 1]
    scales = [1, 0, -1, 0]
    for cycle in range(n_cycles):
        cycle_t0 = t0 + cycle * period
        for fraction, scale in zip(fractions, scales):
            time = cycle_t0 + fraction * period
            if time <= duration:
                times.append(float(time))
                currents.append(float(amp * scale))

    # Close a partial final segment exactly at simulation end
    if times[-1] < duration:
        scale = _triangle_scale([duration], t0, period)[0]
        times.append(float(duration))
        currents.append(float(amp * scale))
    return np.asarray(times), np.asarray(currents)


def gen_exp_name_sub(cfg):
    """Generate the result subdirectory name."""
    exp_name_sub = f'exp_{EXP_LABEL}'
    if PILOT:
        exp_name_sub += '_pilot'
    if not SURR_INP_ON:
        exp_name_sub += '_nosurr'

    exp_name_sub += f'_nseed_{N_SEEDS}'
    t_limits = (cfg.t0_calc / 1000, cfg.duration / 1000)
    exp_name_sub += f'_t_{t_limits[0]}_{t_limits[1]}'
    exp_name_sub += (
        f'_{cfg.h_sweep_type}_t0_{int(cfg.h_sweep_t0)}'
        f'_T_{int(cfg.h_sweep_period)}'
    )

    # Record all fixed population amplitudes in stable population order
    amp_label = '_'.join(
        f'{pop}_{cfg.h_sweep_amps[pop]:g}' for pop in POPS_USED
    )
    exp_name_sub += f'_amp_{amp_label}'
    if USE_IBKG_CTRL:
        exp_name_sub += '_ictrl'
    exp_name_sub += f'_wmult_{cfg.wmult}_ee_{cfg.EEGain}'
    return exp_name_sub


def get_batch_completion_files(child_key, parameters):
    """Return the compact outputs owned by one h-sweep child."""
    if set(parameters) != {'seed_main'}:
        raise ValueError('Unexpected h-sweep batch parameters')
    child_id = child_key.rsplit('_', 1)[-1]
    postfix = f'{child_id}_seed_{parameters["seed_main"]}'
    return [
        f'cfg/cfg_{postfix}.json',
        f'results/result_{postfix}.json',
        f'rvec_xr/rvec_{postfix}.nc',
        f'hvec_xr/hvec_{postfix}.nc',
    ]


def apply_exp_cfg(cfg):
    """Apply the L2 h-sweep configuration to the calibrated base model."""
    cfg.duration = SIM_DURATION
    cfg.t0_calc = T0_CALC
    cfg.need_run = NEED_RUN

    cfg.seed_main = None
    cfg.seeds['stim'] = None
    cfg.seeds['conn'] = None
    cfg.includeParamsLabel = True
    cfg.cache_efficient = 0

    # Save the exact identification waveform in every job configuration
    cfg.h_sweep_type = H_SWEEP_TYPE
    cfg.h_sweep_t0 = H_SWEEP_T0
    cfg.h_sweep_period = H_SWEEP_PERIOD
    cfg.h_sweep_amps = dict(H_SWEEP_AMPS)

    # Keep all active-to-active inputs frozen at their calibrated target rates
    cfg.subnet_build_flag = SURR_INP_ON
    cfg.subnet_params = {
        'pops_active': POPS_USED,
        'conns_frozen': 'all',
        'fpath_frozen_rates': str(dirpath_self / 'target_state_1.csv'),
        'global_seed': None,
    }
    if not SURR_INP_ON:
        cfg.pops_active = POPS_USED
        cfg.addConn = 0

    cfg.wmult = 0.25
    cfg.EEGain = 0.5
    cfg.addSubConn = 0
    cfg.connRandomSecFromList = 1
    cfg.connWeightSecByLength = 0

    # Restore the calibrated stochastic background without changing its values
    fpath_xbkg = dirpath_self / f'{XBKG_NAME}.csv'
    df = pd.read_csv(fpath_xbkg).set_index('pop')
    df.drop(columns=['Unnamed: 0'], errors='ignore')
    df['rxe'] = np.maximum(df['rxe'], 1e-3)
    df['rxi'] = np.maximum(df['rxi'], 1e-3)
    xbkg_info = df.T.to_dict()

    cfg.add_bkg_spike_input = 1
    cfg.replace_bkg_spikes_by_ou = 0
    cfg.bkg_spike_inputs = {}
    for pop in POPS_USED:
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

    # Preserve both established baseline-current components
    if USE_IBKG:
        cfg.addIClamp = 1
        fname_ibkg = f'{IBKG_JSON_NAME}.json'
        with open(dirpath_self / fname_ibkg, 'r') as fid:
            ibkg = json.load(fid)
        cfg.IClamp = {
            pop: {'amp': ibkg[pop], 'dur': SIM_DURATION}
            for pop in POPS_USED if pop in ibkg
        }

    if USE_IBKG_CTRL:
        cfg.addIClamp = 1
        with open(dirpath_self / f'{IBKG_CTRL_JSON_NAME}.json', 'r') as fid:
            ibkg_ctrl = json.load(fid)
        I_median = ibkg_ctrl['I_median']
        if not hasattr(cfg, 'IClamp') or cfg.IClamp is None:
            cfg.IClamp = {}
        for pop in POPS_USED:
            if pop not in I_median:
                continue
            ctrl_entry = {'amp': I_median[pop], 'dur': SIM_DURATION}
            if pop in cfg.IClamp:
                existing = cfg.IClamp[pop]
                cfg.IClamp[pop] = (
                    [existing, ctrl_entry]
                    if isinstance(existing, dict)
                    else existing + [ctrl_entry]
                )
            else:
                cfg.IClamp[pop] = ctrl_entry

    df = pd.read_csv(dirpath_self / 'target_state_1.csv')
    cfg.target_rates = df.set_index('pop_name')['target_rate'].to_dict()
    with open(dirpath_self / 'mech_changes_1.json', 'r') as fid:
        cfg.mech_changes = json.load(fid)

    # Restrict standard plots to the active L2 populations
    if 'plotRaster' in cfg.analysis:
        cfg.analysis['plotRaster']['include'] = POPS_USED
    if 'plotSpikeStats' in cfg.analysis:
        cfg.analysis['plotSpikeStats']['include'] = POPS_USED
    if 'plotTraces' in cfg.analysis:
        cfg.analysis['plotTraces']['include'] = POPS_USED
    cfg.analysis['plotSpikeStats'] = False


def modify_net_params(cfg, params):
    """Apply calibrated mechanisms and declare the additional h clamps."""
    # Preserve the calibrated membrane-mechanism changes
    for change in cfg.mech_changes.values():
        secs_all = params.cellParams[change['pop']]['secs']
        if change['sec'] == 'all':
            secs = list(secs_all.values())
        else:
            secs = [secs_all[change['sec']]]
        for sec in secs:
            mech = sec['mechs'][change['mech']]
            mech[change['par']] *= change['mult']
            mech[change['par']] += change['add']

    # Preserve the newsec connection targets used for J identification
    with open(dirpath_self / 'target_sec_1.json', 'r') as fid:
        target_sec = json.load(fid)
    for cname, conn in params.connParams.items():
        pop_pre = conn['preConds'].get('pop', None)
        pop_post = conn['postConds'].get('pop', None)
        if pop_pre is None or pop_post is None:
            raise ValueError(f'Pre or post pop is not specified for conn {cname}')
        conn['sec'] = None
        for target in target_sec.values():
            if pop_pre in target['pops_pre'] and pop_post in target['pops_post']:
                conn['sec'] = target['sec']
                break
        if conn['sec'] is None:
            print(f'WARNING: No target sec info found for conn {cname}')

    # Let NetPyNE create, target, and retain one extra h clamp per active cell
    for pop in POPS_USED:
        source = _get_h_source(pop)
        target = f'{source}->{pop}'
        params.stimSourceParams[source] = {
            'type': 'IClamp',
            'delay': 0,
            'dur': cfg.duration,
            'amp': 0,
        }
        params.stimTargetParams[target] = {
            'source': source,
            'conds': {'pop': pop},
            'sec': 'soma',
            'loc': 0.5,
        }


def modify_network(sim):
    """Attach sparse triangular vectors to the NetPyNE-declared h clamps."""
    expected_pops = set(POPS_USED)
    if set(sim.cfg.h_sweep_amps) != expected_pops:
        raise ValueError('h_sweep_amps must contain exactly the active populations')
    if sim.cfg.h_sweep_type != 'tri':
        raise ValueError(f'Unsupported h sweep: {sim.cfg.h_sweep_type!r}')

    sim.hsweep_inputs = []
    for cell in sim.net.cells:
        pop = cell.tags['pop']
        if pop not in expected_pops:
            continue

        # Each active cell must have exactly one declared h stimulus
        source = _get_h_source(pop)
        stims = [stim for stim in cell.stims if stim.get('source') == source]
        if len(stims) != 1:
            raise ValueError(
                f'Expected one {source} on gid={cell.gid}, found {len(stims)}'
            )
        clamp = stims[0].get('hObj')
        if clamp is None:
            raise ValueError(f'NetPyNE did not instantiate {source} on gid={cell.gid}')

        times, currents = get_hsweep_corners(
            sim.cfg.duration,
            float(sim.cfg.h_sweep_amps[pop]),
            sim.cfg.h_sweep_t0,
            sim.cfg.h_sweep_period,
        )
        tvec = h.Vector(times)
        ivec = h.Vector(currents)
        ivec.play(clamp._ref_amp, tvec, True)
        sim.hsweep_inputs.append({
            'cell_gid': cell.gid,
            'pop': pop,
            'source': source,
            'tvec': tvec,
            'ivec': ivec,
        })


def _build_hvec_xr(rvec_xr, cfg):
    """Build the exact population current traces at saved rate times."""
    times_sec = np.asarray(rvec_xr.time.values, dtype=float)
    currents = []
    for pop in POPS_USED:
        scale = _triangle_scale(
            times_sec * 1000,
            cfg.h_sweep_t0,
            cfg.h_sweep_period,
        )
        currents.append(float(cfg.h_sweep_amps[pop]) * scale)

    hvec_xr = xr.DataArray(
        np.asarray(currents),
        dims=('pop', 'time'),
        coords={'pop': POPS_USED, 'time': times_sec},
        name='h',
    )
    hvec_xr.attrs['units'] = 'nA'
    hvec_xr.attrs['waveform'] = cfg.h_sweep_type
    hvec_xr.attrs['t0_ms'] = float(cfg.h_sweep_t0)
    hvec_xr.attrs['period_ms'] = float(cfg.h_sweep_period)
    hvec_xr.attrs['amps_nA_json'] = json.dumps(cfg.h_sweep_amps, sort_keys=True)
    return hvec_xr


def post_run(sim):
    """Organize outputs and save compact rate and current dynamics."""
    cfg = sim.cfg
    exp_name = cfg.simLabel
    exp_name_sub = gen_exp_name_sub(cfg)
    exp_id = exp_name.split('_')[-1]
    postfix = f'{exp_id}_seed_{cfg.seed_main}'

    # Create the established per-experiment output structure
    dirpath_res = Path(cfg.saveFolder)
    dirpath_res_sub = dirpath_res / exp_name_sub
    dirnames_sub = [
        'rasters', 'results', 'cfg', 'pkl', 'netpar',
        'rvec_figs', 'rvec_xr', 'hvec_xr',
    ]
    for dirname in dirnames_sub:
        os.makedirs(dirpath_res_sub / dirname, exist_ok=True)

    # Move standard NetPyNE artifacts into stable typed subdirectories
    data_info = [
        ('raster', 'png', 'rasters'),
        ('data', 'pkl', 'pkl'),
        ('cfg', 'json', 'cfg'),
        ('netParams', 'json', 'netpar'),
    ]
    outputs = []
    for data_name, ext, dirname_sub in data_info:
        fpath_old = dirpath_res / f'{exp_name}_{data_name}.{ext}'
        fpath_new = dirpath_res_sub / dirname_sub / f'{data_name}_{postfix}.{ext}'
        if fpath_old.exists():
            fpath_old.rename(fpath_new)
            if data_name == 'cfg':
                outputs.append(fpath_new.relative_to(dirpath_res_sub).as_posix())
        else:
            print('RESULT NOT FOUND: ', fpath_old)

    # Retain summary statistics for compatibility with nearby experiments
    t_limits = (cfg.t0_calc / 1000, cfg.duration / 1000)
    result = {'timing': sim.timingData}
    result |= proc.calc_rates_and_cvs(sim, t_limits, nspikes_min=3)
    fpath_result = dirpath_res_sub / 'results' / f'result_{postfix}.json'
    with open(fpath_result, 'w') as fid:
        json.dump(result, fid, indent=4)
    outputs.append(fpath_result.relative_to(dirpath_res_sub).as_posix())

    # Save compact rate dynamics through sim_data_analyzer
    sim_result = prepare_sim_result(sim)
    pop_names = [
        pop for pop in sim_result['net']['pops'] if 'frz' not in pop
    ]
    rvec_xr = get_net_rate_dynamics_xr(
        sim_result,
        t_limits=(2, None),
        tau_smooth=RVEC_TAU_SMOOTH,
        pop_names=pop_names,
    )
    rvec_xr.attrs['H_SWEEP_TYPE'] = cfg.h_sweep_type
    rvec_xr.attrs['H_SWEEP_T0'] = float(cfg.h_sweep_t0)
    rvec_xr.attrs['H_SWEEP_PERIOD'] = float(cfg.h_sweep_period)
    rvec_xr.attrs['H_SWEEP_AMPS_NA_JSON'] = json.dumps(
        cfg.h_sweep_amps,
        sort_keys=True,
    )
    rvec_xr.attrs['t_limits'] = [2, float(rvec_xr.time.values[-1])]
    rvec_xr.attrs['tau_smooth'] = float(RVEC_TAU_SMOOTH)
    rvec_xr.attrs['exp_label'] = EXP_LABEL
    rvec_xr.attrs['seed_main'] = int(cfg.seed_main)
    fpath_rvec = dirpath_res_sub / 'rvec_xr' / f'rvec_{postfix}.nc'
    rvec_xr.to_netcdf(fpath_rvec)
    outputs.append(fpath_rvec.relative_to(dirpath_res_sub).as_posix())

    hvec_xr = _build_hvec_xr(rvec_xr, cfg)
    fpath_hvec = dirpath_res_sub / 'hvec_xr' / f'hvec_{postfix}.nc'
    hvec_xr.to_netcdf(fpath_hvec)
    outputs.append(fpath_hvec.relative_to(dirpath_res_sub).as_posix())

    if PLOT_RATE_DYNAMICS:
        # Plot rates and their applied currents on a shared time axis
        colors = plt.rcParams['axes.prop_cycle'].by_key()['color']
        fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
        for n, pop in enumerate(POPS_USED):
            color = colors[n % len(colors)]
            pop_r = rvec_xr.sel(pop=pop)
            axes[0].plot(pop_r.time, pop_r, label=pop, color=color)
            axes[0].axhline(
                cfg.target_rates[pop],
                linestyle='--',
                color=color,
                alpha=0.5,
            )
            axes[1].plot(
                hvec_xr.time,
                hvec_xr.sel(pop=pop),
                label=pop,
                color=color,
            )
        axes[0].set_ylabel('Firing rate (Hz)')
        axes[0].legend(bbox_to_anchor=(1, 1))
        axes[1].set_xlabel('Time (s)')
        axes[1].set_ylabel('h (nA)')
        fpath_fig = dirpath_res_sub / 'rvec_figs' / f'L2_{postfix}.png'
        fig.savefig(fpath_fig, bbox_inches='tight', dpi=200)
        plt.close(fig)

    expected = get_batch_completion_files(
        exp_id,
        {'seed_main': cfg.seed_main},
    )
    if outputs != expected:
        raise FileNotFoundError('H-sweep child completion files were not produced')
    return outputs
