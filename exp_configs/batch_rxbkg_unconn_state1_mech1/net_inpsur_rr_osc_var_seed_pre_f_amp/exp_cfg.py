import json
from pathlib import Path
import sys

dirpath_repo_root = Path(__file__).resolve().parents[3]
dirpath_self = Path(__file__).resolve().parent
sys.path.append(str(dirpath_repo_root))
sys.path.append(str(dirpath_self))

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from analysis.ou_tuning import sim_res_proc_utils as proc
from analysis.ou_tuning.netpyne_res_parse_utils import prepare_sim_result
from batch_params import (
    N_SEEDS, POPS_PRE, OSC_F_VALUES, OSC_AMP_VALUES,
    PYR_POPS, PV_POPS, SOM_POPS, VIP_POPS, NGF_POPS,
    THAL_E_POPS, THAL_I_POPS,
    CTX_POPS, L2_POPS
)
import diagnostics as diag
from external.sim_data_analyzer.xr_adapters import get_net_rate_dynamics_xr
from utils.inh_poisson import generate_trains
from workflow_result_utils import (
    move_if_present,
    organize_standard_outputs,
    relative_output,
)


SIM_DURATION = 20 * 1e3
T0_CALC = 5 * 1e3

EXP_LABEL = 'rr_osc_pre_post_L2'
POPS_USED = L2_POPS

OSC_T0 = 5000

XBKG_NAME = 'rx_bkg_mid_sm_ctx21_thal41'

USE_IBKG = 1
IBKG_JSON_NAME = 'ibkg_mech1_verest_-70_thal_spkthr'

USE_IBKG_CTRL = 1
IBKG_CTRL_JSON_NAME = 'ibkg_ctrl_1'

SURR_INP_ON = 1

DT_REC = 1
REC_TRACES = 0
PLOT_TRACES = 0

NCELLS_REC = 5
NCELLS_PLOT = 0

REC_LFP = 0
LFP_Y_MIN = 0
LFP_Y_MAX = 3000
LFP_Y_STEP = 100

PLOT_CSD = 0
CSD_VIS_T0 = 5000

LAYER_BOUNDS = {'L1': 100, 'L2': 160, 'L3': 950, 'L4': 1250,
                'L5A': 1334, 'L5B': 1550, 'L6': 2000}

PLOT_RATE_DYNAMICS = 1
RVEC_TAU_SMOOTH = 0.01
RVIS_POP_GROUPS = {
    #'PYR': PYR_POPS, 'PV': PV_POPS, 'SOM': SOM_POPS, 'VIP': VIP_POPS,
    #'NGF': NGF_POPS, 'THAL_E': THAL_E_POPS, 'THAL_I': THAL_I_POPS
    'L2': L2_POPS,
    'L2frz': [pop + 'frz' for pop in L2_POPS]
}

NEED_RUN = 1
DIAG = 0

ADD_PULSES = 0
N_PULSES = 10
PULSE_PARAMS = {
    'name': 'PulseSeq',
    'pop': None,
    't0': 5000,
    'width': 150,
    'period': 500,
    'n_pulses': N_PULSES,
    'rates': np.linspace(100, 5000, N_PULSES).round().tolist(),
    'weight': 0.1,
    'n_cells': 100,
    'convergence': 25,
    'jitter': 0,
    'rand_type': 'norm'
}


def _append_iclamp_entry(iclamp_dict, pop_name, entry):
    """Append an IClamp entry without replacing existing entries."""
    if pop_name not in iclamp_dict:
        iclamp_dict[pop_name] = entry
        return

    existing = iclamp_dict[pop_name]
    if isinstance(existing, dict):
        iclamp_dict[pop_name] = [existing, entry]
    elif isinstance(existing, list):
        iclamp_dict[pop_name] = existing + [entry]
    else:
        raise TypeError(f'Unsupported IClamp data type: {type(existing)!r}')


def apply_runtime_overrides(cfg, overrides):
    """Apply workflow-only single-job experiment overrides."""
    overrides = dict(overrides)
    if 'wmat_multipliers' in overrides:
        cfg.wmat_multipliers = list(overrides.pop('wmat_multipliers'))
    if 'ibkg_corrections' in overrides:
        corrections = dict(overrides.pop('ibkg_corrections'))
        missing = sorted(set(POPS_USED) - set(corrections))
        if missing:
            raise ValueError(f'Missing ibkg corrections: {missing}')
        unknown = sorted(set(corrections) - set(POPS_USED))
        if unknown:
            raise ValueError(f'Unknown ibkg correction populations: {unknown}')
        cfg.ibkg_corrections = corrections
        cfg.addIClamp = 1
        if not hasattr(cfg, 'IClamp') or cfg.IClamp is None:
            cfg.IClamp = {}
        for pop, amp in corrections.items():
            entry = {'amp': amp, 'dur': SIM_DURATION}
            _append_iclamp_entry(cfg.IClamp, pop, entry)

    # Other settings must already be defined by apply_exp_cfg()
    for name, value in overrides.items():
        if not hasattr(cfg, name):
            raise KeyError(f'Unknown experiment override: {name}')
        setattr(cfg, name, value)


def _get_single_pop_cond(conds):
    """Return one pop name from scalar or singleton-list conditions."""
    pop_name = conds.get('pop', None)
    if isinstance(pop_name, (list, tuple)):
        if len(pop_name) != 1:
            return None
        return pop_name[0]
    return pop_name


def _get_conn_pop_pair(conn):
    """Return one exact pre/post pop pair or None for broad rules."""
    pop_pre = _get_single_pop_cond(conn['preConds'])
    pop_post = _get_single_pop_cond(conn['postConds'])
    if (pop_pre is None) or (pop_post is None):
        return None
    return (pop_pre, pop_post)


def gen_exp_name_sub(cfg):
    """Generate the result subfolder name."""
    if hasattr(cfg, 'workflow_result_subdir'):
        return cfg.workflow_result_subdir

    exp_name_sub = f'exp_{EXP_LABEL}'
    if not SURR_INP_ON:
        exp_name_sub += '_nosurr'

    npre = len(POPS_PRE)
    exp_name_sub += (
        f'_nseed_{N_SEEDS}_npre_{npre}_nf_{len(OSC_F_VALUES)}'
        f'_namp_{len(OSC_AMP_VALUES)}'
    )

    t_limits = (cfg.t0_calc / 1000, cfg.duration / 1000)
    exp_name_sub += f'_t_{t_limits[0]}_{t_limits[1]}'

    if REC_LFP:
        exp_name_sub += f'_lfp_{LFP_Y_MIN}_{LFP_Y_MAX}_{LFP_Y_STEP}'

    exp_name_sub += f'_osc_t0_{int(OSC_T0)}'

    if USE_IBKG_CTRL:
        exp_name_sub += '_ictrl'

    exp_name_sub += f'_wmult_{cfg.wmult}_ee_{cfg.EEGain}'

    if ADD_PULSES:
        pulse_par = cfg.pulse_seq_params
        pt0, pT, pdur, pjit, pr, pw, pc = (
            pulse_par['t0'],
            pulse_par['period'], pulse_par['width'], pulse_par['jitter'],
            pulse_par['rates'], pulse_par['weight'],
            pulse_par['convergence'])
        if np.isscalar(pr):
            pr0, dpr = pr, 0
        else:
            pr0, dpr = pr[0], np.round(pr[1] - pr[0])
        exp_name_sub += (
            f'_pulse_d_{pdur}_T_{pT}_c_{pc}_'
            f'w_{pw}_r_{pr0}_{dpr}_t0_{pt0}_jit_{pjit}')

    return exp_name_sub


def apply_exp_cfg(cfg):
    """Apply experiment config to the base cfg."""

    cfg.duration = SIM_DURATION
    cfg.t0_calc = T0_CALC
    cfg.need_run = NEED_RUN

    pops_active = POPS_USED

    cfg.seed_main = None
    cfg.pop_pre = None
    cfg.osc_f = None
    cfg.osc_amp = None

    cfg.seeds['stim'] = None
    cfg.seeds['conn'] = None

    cfg.includeParamsLabel = True
    cfg.cache_efficient = 0

    cfg.subnet_build_flag = SURR_INP_ON
    cfg.subnet_params = {
        'pops_active': pops_active,
        'conns_frozen': 'all',
        'fpath_frozen_rates': str(dirpath_self / 'target_state_1.csv'),
        'global_seed': None
    }

    if not SURR_INP_ON:
        cfg.pops_active = POPS_USED
        cfg.addConn = 0

    cfg.wmult = 0.25
    cfg.EEGain = 0.5
    cfg.wmat_multipliers = []
    cfg.ibkg_corrections = {}

    cfg.addSubConn = 0
    cfg.connRandomSecFromList = 1
    cfg.connWeightSecByLength = 0

    if DIAG:
        cfg.createNEURONObj = True
        cfg.createPyStruct = True
        cfg.saveCellSecs = True
        cfg.saveCellConns = True
        cfg.compactConnFormat = False
        cfg.includeParamsLabel = True

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
            'exc': {'r': x['rxe'], 'w': x['wxe'], 'sec': x['xe_sec'],
                    'noise': 1, 'seed': None},
            'inh': {'r': x['rxi'], 'w': x['wxi'], 'sec': x['xi_sec'],
                    'noise': 1, 'seed': None},
        }

    if USE_IBKG:
        cfg.addIClamp = 1
        fname_ibkg = f'{IBKG_JSON_NAME}.json'
        with open(dirpath_self / fname_ibkg, 'r') as fid:
            ibkg = json.load(fid)
        cfg.IClamp = {pop: {'amp': ibkg[pop], 'dur': SIM_DURATION}
                      for pop in POPS_USED if pop in ibkg}

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

    if 'plotRaster' in cfg.analysis:
        cfg.analysis['plotRaster']['include'] = POPS_USED
    if 'plotSpikeStats' in cfg.analysis:
        cfg.analysis['plotSpikeStats']['include'] = POPS_USED
    if 'plotTraces' in cfg.analysis:
        cfg.analysis['plotTraces']['include'] = POPS_USED

    cfg.analysis['plotSpikeStats'] = False

    if REC_TRACES:
        cfg.recordCells = [(pop, list(range(NCELLS_REC))) for pop in POPS_USED]
        cfg.recordTraces = {'V_soma': {'sec': 'soma', 'loc': 0.5, 'var': 'v'}}
        cfg.recordStep = DT_REC

    if REC_TRACES and PLOT_TRACES:
        cfg.analysis['plotTraces'] = {
            'include': [(pop, list(range(NCELLS_PLOT))) for pop in cfg.allpops],
            'timeRange': [1000, cfg.duration],
            'oneFigPer': 'cell', 'overlay': True,
            'saveFig': True, 'showFig': False, 'figSize': (18, 12)
        }

    if REC_LFP:
        cfg.recordTime = True
        cfg.recordStep = DT_REC
        cfg.recordLFP = [[100, y, 100]
                         for y in range(LFP_Y_MIN, LFP_Y_MAX, LFP_Y_STEP)]

    if REC_LFP and PLOT_CSD:
        csd_t0 = CSD_VIS_T0 if CSD_VIS_T0 is not None else 2000
        cfg.analysis['plotCSD'] = {
            'spacing_um': LFP_Y_STEP, 'LFP_overlay': 1, 'layer_lines': 1,
            'layer_bounds': LAYER_BOUNDS, 'saveFig': 1, 'showFig': 0,
            'timeRange': (csd_t0, cfg.duration)
        }

    cfg.add_pulses = int(ADD_PULSES)
    if ADD_PULSES:
        cfg.pulse_seq_params = PULSE_PARAMS


def modify_net_params(cfg, params):
    """Applied after netParams creation."""

    for v in cfg.mech_changes.values():
        secs_all = params.cellParams[v['pop']]['secs']
        if v['sec'] == 'all':
            secs = list(secs_all.values())
        else:
            secs = [secs_all[v['sec']]]
        for sec in secs:
            sec['mechs'][v['mech']][v['par']] *= v['mult']
            sec['mechs'][v['mech']][v['par']] += v['add']

    with open(dirpath_self / 'target_sec_1.json', 'r') as fid:
        target_sec = json.load(fid)
    for cname, conn in params.connParams.items():
        pop_pre = conn['preConds'].get('pop', None)
        pop_post = conn['postConds'].get('pop', None)
        if (pop_pre is None) or (pop_post is None):
            raise ValueError(f'Pre or post pop is not specified for conn {cname}')
        conn['sec'] = None
        for ts in target_sec.values():
            if (pop_pre in ts['pops_pre']) and (pop_post in ts['pops_post']):
                conn['sec'] = ts['sec']
                break
        if conn['sec'] is None:
            print(f'WARNING: No target sec info found for conn {cname}')

    # Weight multipliers
    wmat_multipliers = {
        (item['pre'], item['post']): item['mult']
        for item in cfg.wmat_multipliers
    }
    if len(wmat_multipliers) != len(cfg.wmat_multipliers):
        raise ValueError('Duplicate entries in cfg.wmat_multipliers')

    matched_pairs = set()
    for conn in params.connParams.values():
        pair = _get_conn_pop_pair(conn)
        if pair not in wmat_multipliers:
            continue
        conn['weight'] *= wmat_multipliers[pair]
        matched_pairs.add(pair)

    missing_pairs = set(wmat_multipliers) - matched_pairs
    if missing_pairs:
        raise ValueError(
            f'No connParams found for wmat multipliers: {missing_pairs}'
        )


def modify_net_params_2(cfg, params):
    """Replace cfg.pop_pre surrogate with a baseline-centered oscillatory VecStim."""
    if cfg.pop_pre is None:
        raise ValueError('cfg.pop_pre is not set in modify_net_params_2')
    if cfg.osc_f is None or cfg.osc_amp is None:
        raise ValueError('cfg.osc_f and cfg.osc_amp must be set in modify_net_params_2')

    pop_name = cfg.pop_pre + 'frz'
    if pop_name not in params.popParams:
        raise ValueError(
            f'Pop {pop_name} not found in popParams in modify_net_params_2'
        )

    pop = params.popParams[pop_name]

    target_rate = float(pop['rate'])
    ynorm_range = pop['ynormRange']
    base_seed = int(np.random.RandomState(int(pop['seed'])).randint(0, 2**31))

    # Number of cells from the pre-computed population-size table
    pops_sz = pd.read_csv(dirpath_self / 'pops_sz.csv').set_index('pop')['ncells'].to_dict()
    n_cells = int(pops_sz[cfg.pop_pre])

    # Generate oscillatory rate dynamics
    t_vec = np.arange(0.0, cfg.duration, 1.0)
    rate_vec = np.full_like(t_vec, target_rate, dtype=float)
    osc_mask = t_vec >= OSC_T0
    phase = (
        2 * np.pi * float(cfg.osc_f) *
        (t_vec[osc_mask] - OSC_T0) / 1000.0
    )
    rate_vec[osc_mask] = np.maximum(
        0.0,
        target_rate + float(cfg.osc_amp) * np.sin(phase)
    )

    # Generate modulated spike trains
    spk_times = generate_trains(rate_vec, t_vec, cfg.duration, n_cells, base_seed)

    params.popParams[pop_name] = {
        'cellModel': 'VecStim',
        'numCells': n_cells,
        'spkTimes': spk_times,
        'ynormRange': ynorm_range,
    }


def post_run(sim):
    """Called in the end of a job (after running and saving)."""

    cfg = sim.cfg
    exp_name = cfg.simLabel

    t_limits = (cfg.t0_calc / 1000, cfg.duration / 1000)
    exp_name_sub = gen_exp_name_sub(cfg)

    exp_id = exp_name.split('_')[-1]
    postfix = (
        f'{exp_id}_seed_{cfg.seed_main}_rpre_{cfg.pop_pre}'
        f'_f_{cfg.osc_f:g}_amp_{cfg.osc_amp:g}'
    )

    # Standard output relocation and retention
    dirpath_res = Path(cfg.saveFolder)
    dirpath_res_sub = organize_standard_outputs(
        cfg,
        exp_name_sub,
        postfix,
    )
    (dirpath_res_sub / 'rvec_xr').mkdir(parents=True, exist_ok=True)

    # Trace relocation
    trace_files = list(dirpath_res.glob(f'{exp_name}_traces*.png'))
    for fpath_old in trace_files:
        fpath_new = dirpath_res_sub / 'traces' / (
            f'{fpath_old.stem}_{postfix}{fpath_old.suffix}'
        )
        move_if_present(fpath_old, fpath_new)

    # CSD relocation
    if REC_LFP and PLOT_CSD:
        csd_files = list(dirpath_res.glob(f'{exp_name}_CSD*.png'))
        for fpath_old in csd_files:
            fpath_new = dirpath_res_sub / 'csd_figs' / (
                f'{fpath_old.stem}_{postfix}{fpath_old.suffix}'
            )
            move_if_present(fpath_old, fpath_new)

    # Derived result and rate-dynamics data
    outputs = []
    if NEED_RUN:
        res = {}
        res['timing'] = sim.timingData
        res |= proc.calc_rates_and_cvs(sim, t_limits, nspikes_min=3)
        if REC_TRACES:
            res |= proc.calc_v_stats(sim, t_limits, med_win=0.05)
        fpath_res = dirpath_res_sub / 'results' / f'result_{postfix}.json'
        with open(fpath_res, 'w') as fid:
            json.dump(res, fid, indent=4)
        outputs.append(relative_output(cfg, fpath_res))

        # Compute firing rate dynamics
        sim_result = prepare_sim_result(sim)
        pop_names = POPS_USED + [pop + 'frz' for pop in POPS_PRE]
        rvec_xr = get_net_rate_dynamics_xr(
            sim_result,
            t_limits=(2, None),
            tau_smooth=RVEC_TAU_SMOOTH,
            pop_names=pop_names,
        )
        rvec_xr.attrs['OSC_T0'] = float(OSC_T0)
        rvec_xr.attrs['OSC_F'] = float(cfg.osc_f)
        rvec_xr.attrs['OSC_AMP'] = float(cfg.osc_amp)
        rvec_xr.attrs['t_limits'] = [2.0, float(rvec_xr.time.values[-1])]
        rvec_xr.attrs['tau_smooth'] = float(RVEC_TAU_SMOOTH)
        rvec_xr.attrs['exp_label'] = EXP_LABEL
        rvec_xr.attrs['seed_main'] = int(cfg.seed_main)
        rvec_xr.attrs['pop_pre'] = str(cfg.pop_pre)
        fpath_rvec_xr = dirpath_res_sub / 'rvec_xr' / f'rvec_{postfix}.nc'
        rvec_xr.to_netcdf(fpath_rvec_xr)
        outputs.append(relative_output(cfg, fpath_rvec_xr))

    if PLOT_RATE_DYNAMICS and NEED_RUN:
        colors = plt.rcParams['axes.prop_cycle'].by_key()['color']
        for pop_group_name, pops in RVIS_POP_GROUPS.items():
            pops = [p for p in pops if p in rvec_xr.coords['pop'].values]
            if len(pops) == 0:
                continue

            plt.figure(111)
            plt.clf()

            for n, pop in enumerate(pops):
                pop_base = pop.replace('frz', '')
                pop_r = rvec_xr.sel(pop=pop)
                tt = pop_r['time'].values
                rr = pop_r.values
                r0 = cfg.target_rates[pop_base]
                col = colors[n % len(colors)]
                plt.plot(tt, rr, label=pop, color=col)
                plt.plot([tt[0], tt[-1]], [r0, r0], '--', color=col)

            plt.xlabel('Time')
            plt.ylabel('Firing rate')
            plt.legend(bbox_to_anchor=(1, 1))

            fname_out = f'{pop_group_name}_{postfix}.png'
            plt.savefig(dirpath_res_sub / 'rvec_figs' / fname_out,
                        bbox_inches='tight', dpi=300)

    return outputs


def final(sim):
    """Run optional diagnostics after the simulation."""
    if not DIAG or not NEED_RUN:
        return

    diag.count_conns(sim)
    diag.count_synmechs(sim)
    diag.count_netcons_neuron(sim)
    diag.report_min_delay(sim)

    pops_pre = ['ITP4frz']
    pops_post = ['ITP4']
    sec_groups = {
        'soma': ['soma'],
        'Bdend': ['Bdend'],
        'Adend1': ['Adend1'],
        'Adend2': ['Adend2'],
        'Adend3': ['Adend3']
    }
    sec_counts = diag.count_conn_target_secs(
        sim, sec_groups, pops_pre, pops_post)
    if sim.rank == 0:
        print('Conn targets by sec group:', sec_counts)
