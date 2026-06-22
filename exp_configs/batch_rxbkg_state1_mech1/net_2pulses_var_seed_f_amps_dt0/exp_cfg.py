import json
import os
from copy import deepcopy
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

from analysis.model_utils.net_utils import get_2pop_conns
from analysis.ou_tuning import sim_res_proc_utils as proc
from analysis.ou_tuning.netpyne_res_parse_utils import prepare_sim_result
from batch_params import (
    AMP1_VALUES,
    AMP2_VALUES,
    DT0_VALUES,
    F_VALUES,
    N_SEEDS,
    PULSE_T0
)
from conn_fader import ConnFader
import diagnostics as diag
from external.sim_data_analyzer.xr_adapters import get_lfp_xr, get_net_rate_dynamics_xr
from syn_mech_relabel import _rule_kind_and_base_pops, _relabel_conn_synmech


PYR_POPS = ['IT2', 'IT3', 'ITP4', 'ITS4', 'IT5A', 'IT5B', 'IT6',
            'CT5A', 'CT5B', 'CT6', 'PT5B']
PV_POPS = ['PV2', 'PV3', 'PV4', 'PV5A', 'PV5B', 'PV6']
SOM_POPS = ['SOM2', 'SOM3', 'SOM4', 'SOM5A', 'SOM5B', 'SOM6']
VIP_POPS = ['VIP2', 'VIP3', 'VIP4', 'VIP5A', 'VIP5B', 'VIP6']
NGF_POPS = ['NGF1', 'NGF2', 'NGF3', 'NGF4', 'NGF5A', 'NGF5B', 'NGF6']

L2_POPS = ['IT2', 'PV2', 'SOM2', 'VIP2', 'NGF2']
L4_POPS = ['ITP4', 'ITS4', 'PV4', 'SOM4', 'VIP4', 'NGF4']
CTX_POPS = PYR_POPS + PV_POPS + SOM_POPS + VIP_POPS + NGF_POPS

THAL_E_POPS = ['TC', 'HTC', 'TCM']
THAL_I_POPS = ['TI', 'TIM', 'IRE', 'IREM']
CORE_POPS = ['TC', 'HTC', 'TI', 'IRE']
MATX_POPS = ['TCM', 'TIM', 'IREM']
THAL_POPS = CORE_POPS + MATX_POPS

E_POPS = PYR_POPS + THAL_E_POPS
CONNS_EE = [(p1, p2) for p1 in E_POPS for p2 in E_POPS]


# Duration and rate calculation window
SIM_DURATION = 15 * 1e3
T0_CALC = 5 * 1e3

EXP_LABEL = 'L2'
POPS_USED = L2_POPS

WMAT_MULTIPLIERS = []
WMAT_MULT_LABEL = ''

#CONNS_FROZEN = 'all'
#CONNS_FROZEN = CONNS_EE
CONNS_FROZEN = []

EE_FADER_ON = 1

#CONNS_SPLIT = []
CONNS_SPLIT = [(p1, p2) for p1, p2 in CONNS_EE
               if (p1 in POPS_USED) and (p2 in POPS_USED)]

# Surr->recurrent fader timecourse (time, rec:surr ratio)
FADER_PTS = [(0, 0), (3000, 0), (5000, 1), (SIM_DURATION, 1)]

# Background spiking input
XBKG_NAME = 'rx_bkg_mid_sm_ctx21_thal41'

# Constant input to set Vrest
USE_IBKG = 1
IBKG_JSON_NAME = 'ibkg_mech1_verest_-70_thal_spkthr'

# Constant input correction from rate-control experiment
USE_IBKG_CTRL = 1
IBKG_CTRL_JSON_NAME = 'ibkg_ctrl_1'

# W-modification current corrections
IBKG_WCORR_JSON_NAME = None

# Surrogate inputs
SURR_INP_ON = 1

# Recording time step for traces and LFP
DT_REC = 2

REC_TRACES = 0
PLOT_TRACES = 0

NCELLS_REC = 5
NCELLS_PLOT = 2

REC_LFP = 0
LFP_Y_MIN = 0
LFP_Y_MAX = 300
LFP_Y_STEP = 50

PLOT_CSD = 0
CSD_VIS_T0 = 10000

LAYER_BOUNDS = {'L1': 100, 'L2': 160, 'L3': 950, 'L4': 1250,
                'L5A': 1334, 'L5B': 1550, 'L6': 2000}

PLOT_RATE_DYNAMICS = 1
RVEC_TAU_SMOOTH = 0.02
SAVE_RATE_XR = 0
SAVE_LFP_XR = 0
SAVE_PKL = 1

NEED_RUN = 1
DIAG = 0

ADD_PULSES = 1
PULSE_T_LAST = None
PULSE_PARAMS = [
    {
        'name': 'PulseSeq1',
        'pop': ['NGF'],
        't0': PULSE_T0,
        't_last': PULSE_T_LAST,
        'width': 50,
        'period': None,
        'n_pulses': None,
        #'rates': 1250,
        'rates': [500],
        'weight': None,
        'n_cells': 100,
        'convergence': 25,
        'jitter': 0,
        'rand_type': 'norm',
    },
    {
        'name': 'PulseSeq2',
        'pop': ['NGF'],
        't0': PULSE_T0,
        't_last': PULSE_T_LAST,
        'width': 50,
        'period': None,
        'n_pulses': None,
        #'rates': 1250,
        'rates': [500],
        'weight': None,
        'n_cells': 100,
        'convergence': 25,
        'jitter': 0,
        'rand_type': 'norm',
    },
]


def _get_default_runtime_params():
    """Return the default runtime parameter tree."""
    return {
        'time': {
            'duration': SIM_DURATION,
            't0_calc': T0_CALC,
        },
        'pops_used': list(POPS_USED),
        'conn': {
            'wmat_multipliers': deepcopy(WMAT_MULTIPLIERS),
            'ee_fader_on': EE_FADER_ON,
            'fader_pts': list(FADER_PTS),
        },
        'inp': {
            'ibkg_corrections': {},
            'add_pulses': ADD_PULSES,
        },
        'rec': {
            'traces': REC_TRACES,
            'lfp': REC_LFP,
        },
        'proc': {
            'rate_t_limits': None,
            'rate_dt_bin': 0.005,
            'rate_tau_smooth': RVEC_TAU_SMOOTH,
        },
        'out': {
            'plot_traces': PLOT_TRACES,
            'plot_csd': PLOT_CSD,
            'plot_rate_dynamics': PLOT_RATE_DYNAMICS,
            'save_rate_xr': bool(SAVE_RATE_XR),
            'save_lfp_xr': bool(SAVE_LFP_XR),
            'save_pkl': bool(SAVE_PKL),
        },
    }


def _deep_update_runtime_params(base, patch):
    """Deep-merge a runtime parameter patch with key validation."""
    result = deepcopy(base)
    for key, value in dict(patch).items():
        if key not in result:
            raise KeyError(f'Unknown runtime_params root: {key}')
        if isinstance(result[key], dict):
            if not result[key]:
                result[key] = deepcopy(value)
                continue
            if not isinstance(value, dict):
                raise TypeError(f'runtime_params[{key!r}] should be a dict')
            result[key] = _deep_update_runtime_params(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


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


def _get_conns_split(pops_used):
    """Select recurrent excitatory pairs present in active populations."""
    return [
        (p1, p2)
        for p1, p2 in CONNS_EE
        if (p1 in pops_used) and (p2 in pops_used)
    ]


def _validate_runtime_params(runtime_params):
    """Validate runtime params before deriving cfg fields."""
    pops_used = list(runtime_params['pops_used'])
    if len(set(pops_used)) != len(pops_used):
        raise ValueError('Duplicate entries in pops_used')
    unknown = sorted(set(pops_used) - set(POPS_USED))
    if unknown:
        raise ValueError(f'Unknown populations in pops_used: {unknown}')

    # Validate connection multipliers against the active populations
    weights = list(runtime_params['conn']['wmat_multipliers'])
    pairs = [(item['pre'], item['post']) for item in weights]
    if len(set(pairs)) != len(pairs):
        raise ValueError('Duplicate entries in wmat_multipliers')
    unknown = sorted(set(pop for pair in pairs for pop in pair) - set(pops_used))
    if unknown:
        raise ValueError(f'Unknown weight-multiplier populations: {unknown}')

    # Require explicit correction values when corrections are supplied
    corrections = dict(runtime_params['inp']['ibkg_corrections'])
    if corrections:
        missing = sorted(set(pops_used) - set(corrections))
        if missing:
            raise ValueError(f'Missing ibkg corrections: {missing}')
        unknown = sorted(set(corrections) - set(pops_used))
        if unknown:
            raise ValueError(f'Unknown ibkg correction populations: {unknown}')

    # Require LFP recording when compact LFP output is requested
    if runtime_params['out']['save_lfp_xr'] and not runtime_params['rec']['lfp']:
        raise ValueError('save_lfp_xr requires runtime_params["rec"]["lfp"]')


def _build_bkg_spike_inputs(pops_used):
    """Build background spike-input settings for active populations."""
    fpath_xbkg = dirpath_self / f'{XBKG_NAME}.csv'
    df = pd.read_csv(fpath_xbkg).set_index('pop')
    df.drop(columns=['Unnamed: 0'], errors='ignore', inplace=True)
    df['rxe'] = np.maximum(df['rxe'], 1e-3)
    df['rxi'] = np.maximum(df['rxi'], 1e-3)
    xbkg_info = df.T.to_dict()

    # Leave seeds empty until batch_params.post_update()
    return {
        pop: {
            'exc': {
                'r': xbkg_info[pop]['rxe'],
                'w': xbkg_info[pop]['wxe'],
                'sec': xbkg_info[pop]['xe_sec'],
                'noise': 1,
                'seed': None,
            },
            'inh': {
                'r': xbkg_info[pop]['rxi'],
                'w': xbkg_info[pop]['wxi'],
                'sec': xbkg_info[pop]['xi_sec'],
                'noise': 1,
                'seed': None,
            },
        }
        for pop in pops_used
    }


def _load_ibkg_wcorr(pops_used):
    """Load optional W-correction currents from a flat JSON file."""
    if IBKG_WCORR_JSON_NAME is None:
        return {}

    # Read the correction file from this experiment folder
    fname = str(IBKG_WCORR_JSON_NAME)
    if not fname.endswith('.json'):
        fname = f'{fname}.json'
    with open(dirpath_self / fname, 'r') as fid:
        corrections = json.load(fid)
    if not isinstance(corrections, dict):
        raise TypeError('IBKG_WCORR_JSON_NAME should point to a flat dict JSON')

    # Require one explicit correction per active population
    missing = sorted(set(pops_used) - set(corrections))
    if missing:
        raise ValueError(f'Missing ibkg W-corrections: {missing}')
    unknown = sorted(set(corrections) - set(pops_used))
    if unknown:
        raise ValueError(f'Unknown ibkg W-correction populations: {unknown}')
    return {
        pop: corrections[pop]
        for pop in pops_used
    }


def _build_iclamp(runtime_params):
    """Build baseline, control, and runtime correction IClamps."""
    pops_used = list(runtime_params['pops_used'])
    duration = runtime_params['time']['duration']
    corrections = dict(runtime_params['inp']['ibkg_corrections'])
    iclamp = {}

    # Add static resting-voltage currents
    if USE_IBKG:
        fname_ibkg = f'{IBKG_JSON_NAME}.json'
        with open(dirpath_self / fname_ibkg, 'r') as fid:
            ibkg = json.load(fid)
        iclamp = {
            pop: {'amp': ibkg[pop], 'dur': duration}
            for pop in pops_used
            if pop in ibkg
        }

    # Add control-derived DC offsets
    if USE_IBKG_CTRL:
        with open(dirpath_self / f'{IBKG_CTRL_JSON_NAME}.json', 'r') as fid:
            ibkg_ctrl = json.load(fid)
        I_median = ibkg_ctrl['I_median']
        for pop in pops_used:
            if pop not in I_median:
                continue
            entry = {'amp': I_median[pop], 'dur': duration}
            _append_iclamp_entry(iclamp, pop, entry)

    # Add connectivity-W correction currents before runtime patches
    for pop, amp in _load_ibkg_wcorr(pops_used).items():
        entry = {'amp': amp, 'dur': duration}
        _append_iclamp_entry(iclamp, pop, entry)

    # Add runtime correction currents last so they are easy to inspect
    for pop, amp in corrections.items():
        entry = {'amp': amp, 'dur': duration}
        _append_iclamp_entry(iclamp, pop, entry)
    return iclamp


def _set_analysis_includes(cfg, pops_used):
    """Set analysis population filters while preserving disabled entries."""
    for analysis_name in ('plotRaster', 'plotSpikeStats', 'plotTraces'):
        analysis_cfg = cfg.analysis.get(analysis_name)
        if isinstance(analysis_cfg, dict):
            analysis_cfg['include'] = pops_used
    cfg.analysis['plotSpikeStats'] = False


def _apply_runtime_params_to_cfg(cfg):
    """Derive ordinary cfg fields from cfg.runtime_params."""
    runtime_params = deepcopy(cfg.runtime_params)
    _validate_runtime_params(runtime_params)
    cfg.runtime_params = runtime_params

    # Derive timing and active population fields before subnet creation
    cfg.duration = runtime_params['time']['duration']
    cfg.t0_calc = runtime_params['time']['t0_calc']
    cfg.pops_used = list(runtime_params['pops_used'])
    cfg.ee_fader_on = bool(runtime_params['conn']['ee_fader_on'])
    cfg.conns_split = _get_conns_split(cfg.pops_used)

    # Derive subnet parameters consumed by common net construction
    cfg.subnet_build_flag = SURR_INP_ON
    cfg.subnet_params = {
        'pops_active': cfg.pops_used,
        'conns_frozen': CONNS_FROZEN,
        'fpath_frozen_rates': str(dirpath_self / 'target_state_1.csv'),
        'global_seed': None,
    }
    if cfg.ee_fader_on:
        cfg.subnet_params['conns_split'] = {
            f'{c[0]}, {c[1]}': 0.5
            for c in cfg.conns_split
        }
        cfg.includeParamsLabel = True
        cfg.cache_efficient = 0

    if not SURR_INP_ON:
        cfg.pops_active = cfg.pops_used
        cfg.addConn = 0

    # Derive inputs after active populations and duration are known
    cfg.add_bkg_spike_input = 1
    cfg.replace_bkg_spikes_by_ou = 0
    cfg.bkg_spike_inputs = _build_bkg_spike_inputs(cfg.pops_used)
    cfg.IClamp = _build_iclamp(runtime_params)
    cfg.addIClamp = int(bool(cfg.IClamp))

    # Derive recording, plotting, and pulse controls
    cfg.rec_traces = bool(runtime_params['rec']['traces'])
    cfg.rec_lfp = bool(runtime_params['rec']['lfp'])
    cfg.plot_traces = bool(runtime_params['out']['plot_traces'])
    cfg.plot_csd = bool(runtime_params['out']['plot_csd'])
    cfg.plot_rate_dynamics = bool(runtime_params['out']['plot_rate_dynamics'])
    cfg.savePickle = bool(runtime_params['out']['save_pkl'])
    cfg.add_pulses = int(bool(runtime_params['inp']['add_pulses']))
    _set_analysis_includes(cfg, cfg.pops_used)

    # Rebuild trace recording fields from scratch
    cfg.recordCells = []
    cfg.recordTraces = {}
    if cfg.rec_traces:
        cfg.recordCells = [
            (pop, list(range(NCELLS_REC)))
            for pop in cfg.pops_used
        ]
        cfg.recordTraces = {
            'V_soma': {'sec': 'soma', 'loc': 0.5, 'var': 'v'}
        }
        cfg.recordStep = DT_REC

    # Rebuild trace plotting fields from scratch
    cfg.analysis.pop('plotTraces', None)
    if cfg.rec_traces and cfg.plot_traces:
        cfg.analysis['plotTraces'] = {
            'include': [
                (pop, list(range(NCELLS_PLOT)))
                for pop in cfg.pops_used
            ],
            'timeRange': [1000, cfg.duration],
            'oneFigPer': 'cell',
            'overlay': True,
            'saveFig': True,
            'showFig': False,
            'figSize': (18, 12),
        }

    # Rebuild LFP recording and CSD plotting fields from scratch
    cfg.recordTime = False
    cfg.recordLFP = []
    cfg.analysis.pop('plotCSD', None)
    if cfg.rec_lfp:
        cfg.recordTime = True
        cfg.recordStep = DT_REC
        cfg.recordLFP = [
            [100, y, 100]
            for y in range(LFP_Y_MIN, LFP_Y_MAX, LFP_Y_STEP)
        ]
    if cfg.rec_lfp and cfg.plot_csd:
        csd_t0 = CSD_VIS_T0 if CSD_VIS_T0 is not None else 2000
        cfg.analysis['plotCSD'] = {
            'spacing_um': LFP_Y_STEP,
            'LFP_overlay': 0,
            'layer_lines': 1,
            'layer_bounds': LAYER_BOUNDS,
            'saveFig': 1,
            'showFig': 0,
            'timeRange': (csd_t0, cfg.duration),
        }

    # Rebuild optional pulse stimulus fields
    cfg.pulse_seq_params = {}
    if cfg.add_pulses:
        cfg.pulse_seq_params = deepcopy(PULSE_PARAMS)


def apply_runtime_overrides(cfg, overrides):
    """Apply a generic runtime_params patch."""
    overrides = dict(overrides)
    if 'runtime_params' in overrides:
        cfg.runtime_params = _deep_update_runtime_params(
            cfg.runtime_params,
            overrides.pop('runtime_params'),
        )
        _apply_runtime_params_to_cfg(cfg)
    if overrides:
        raise KeyError(f'Unknown experiment overrides: {sorted(overrides)}')


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


def _apply_wmat_multipliers(params, wmat_multipliers):
    """Apply pairwise connection-weight multipliers."""
    weights_by_pair = {
        (item['pre'], item['post']): item['mult']
        for item in wmat_multipliers
    }
    if len(weights_by_pair) != len(wmat_multipliers):
        raise ValueError('Duplicate entries in wmat_multipliers')

    matched_pairs = set()
    for conn in params.connParams.values():
        pair = _get_conn_pop_pair(conn)
        if pair not in weights_by_pair:
            continue
        conn['weight'] *= weights_by_pair[pair]
        matched_pairs.add(pair)
    
    missing_pairs = set(weights_by_pair) - matched_pairs
    if missing_pairs:
        raise ValueError(
            f'No connParams found for wmat multipliers: {missing_pairs}'
        )


def _get_pulse_rate_label(rates):
    """Return a compact label for static pulse-rate settings."""
    if np.isscalar(rates):
        return rates, 0

    rates = list(rates)
    if len(rates) == 0:
        raise ValueError('PULSE_PARAMS["rates"] cannot be empty')
    if len(rates) == 1:
        return rates[0], 0
    return rates[0], np.round(rates[1] - rates[0])


def _get_pulse_pop_label(pop_names):
    """Return a compact label for pulse target populations."""
    if isinstance(pop_names, str):
        return pop_names
    return '_'.join(pop_names)


def _get_pulse_param_list(pulse_seq_params):
    """Return pulse params as a list."""
    if isinstance(pulse_seq_params, dict):
        return [pulse_seq_params]
    return list(pulse_seq_params)


def gen_exp_name_sub(cfg):
    """Generate the result subfolder name."""
    if hasattr(cfg, 'workflow_result_subdir'):
        return cfg.workflow_result_subdir

    runtime_params = getattr(
        cfg,
        'runtime_params',
        _get_default_runtime_params(),
    )
    t_limits = (cfg.t0_calc / 1000, cfg.duration / 1000)
    exp_name_sub = f'exp_{EXP_LABEL}'
    if not SURR_INP_ON:
        exp_name_sub += '_nosurr'
    exp_name_sub += (
        f'_nseed_{N_SEEDS}'
        f'_f_{"_".join(str(f) for f in F_VALUES)}'
        f'_amp1_{AMP1_VALUES[0]}_{AMP1_VALUES[-1]}_{len(AMP1_VALUES)}'
        f'_amp2_{AMP2_VALUES[0]}_{AMP2_VALUES[-1]}_{len(AMP2_VALUES)}'
        f'_dt0_{"_".join(str(dt0) for dt0 in DT0_VALUES)}'
    )
    exp_name_sub += f'_t_{t_limits[0]}_{t_limits[1]}'
    if runtime_params['rec']['lfp']:
        exp_name_sub += f'_lfp_{LFP_Y_MIN}_{LFP_Y_MAX}_{LFP_Y_STEP}'
    if USE_IBKG_CTRL:
        exp_name_sub += '_ictrl'
    if WMAT_MULT_LABEL:
        exp_name_sub += f'_{WMAT_MULT_LABEL}'
    exp_name_sub += f'_wmult_{cfg.wmult}_ee_{cfg.EEGain}'
    if runtime_params['inp']['add_pulses']:
        pulse_params = _get_pulse_param_list(cfg.pulse_seq_params)
        pulse_par = pulse_params[0]
        ppop, pt0, pt_last, pdur, pjit, pr, pc = (
            pulse_par['pop'],
            pulse_par['t0'],
            pulse_par.get('t_last', None),
            pulse_par['width'],
            pulse_par['jitter'],
            pulse_par['rates'],
            pulse_par['convergence'],
        )
        ppop = _get_pulse_pop_label(ppop)
        pr0, dpr = _get_pulse_rate_label(pr)
        exp_name_sub += (
            f'_{len(pulse_params)}pulse_{ppop}_d_{pdur}_c_{pc}_'
            f'r_{pr0}_{dpr}_t0_{pt0}_jit_{pjit}'
        )
        if pt_last is not None:
            exp_name_sub += f'_tlast_{pt_last}'
    return exp_name_sub


def apply_exp_cfg(cfg):
    """Apply default experiment config values."""
    cfg.need_run = NEED_RUN

    # Random seeds are filled by the batch layer after cfg.update()
    cfg.seed_main = None   # batch param
    cfg.f = None   # batch param
    cfg.amp1 = None   # batch param
    cfg.amp2 = None   # batch param
    cfg.dt0 = None   # batch param
    cfg.seeds['stim'] = None   # set in batch_params.py
    cfg.seeds['conn'] = None   # set in batch_params.py

    # Common connection scaling defaults
    cfg.wmult = 0.25
    cfg.EEGain = 0.5

    # Connectivity params shared by standalone and runtime-patched runs
    cfg.addSubConn = 0
    cfg.connRandomSecFromList = 1
    cfg.connWeightSecByLength = 0

    # Runtime params are the generic external override surface
    cfg.runtime_params = _get_default_runtime_params()
    _apply_runtime_params_to_cfg(cfg)

    if DIAG:
        cfg.createNEURONObj = True      # Create NEURON hoc objects
        cfg.createPyStruct = True       # Create Python structure
        cfg.saveCellSecs = True         # Save section data (includes hObj)
        cfg.saveCellConns = True        # Save connection data
        cfg.compactConnFormat = False   # Keep full dict format for conns
        cfg.includeParamsLabel=True

    # Read target rates
    df = pd.read_csv(dirpath_self / 'target_state_1.csv')
    target_rates = df.set_index('pop_name')['target_rate'].to_dict()
    cfg.target_rates = target_rates
    
    # Cell mechanisms to modify
    with open(dirpath_self / 'mech_changes_1.json', 'r') as fid:
        cfg.mech_changes = json.load(fid)


def modify_net_params(cfg, params):
    """Apply experiment changes after netParams creation."""

    # Modify membrane mechanisms
    for v in cfg.mech_changes.values():
        secs_all = params.cellParams[v['pop']]['secs']
        if v['sec'] == 'all':
            secs = list(secs_all.values())
        else:
            secs = [secs_all[v['sec']]]
        for sec in secs:
            sec['mechs'][v['mech']][v['par']] *= v['mult']
            sec['mechs'][v['mech']][v['par']] += v['add']
    
    # Set target sections from json file
    with open(dirpath_self / 'target_sec_1.json', 'r') as fid:
        target_sec = json.load(fid)
    for cname, conn in params.connParams.items():
        pop_pre = conn['preConds'].get('pop', None)
        pop_post = conn['postConds'].get('pop', None)
        if (pop_pre is None) or (pop_post is None):
            raise ValueError(f'Pre or post pop is not specified for conn {cname}')
        conn['sec'] = None
        for ts_name, ts in target_sec.items():
            if (pop_pre in ts['pops_pre']) and (pop_post in ts['pops_post']):
                #print(f'Sec info: {cname} {ts_name}')
                conn['sec'] = ts['sec']
                break
        if conn['sec'] is None:
            #print(f'{pop_pre} -> {pop_post}')
            #raise ValueError(f'No target sec info found for conn {cname}')  
            print(f'WARNING: No target sec info found for conn {cname}')  

    # Apply optional runtime connection-weight multipliers
    wmat_multipliers = cfg.runtime_params['conn']['wmat_multipliers']
    _apply_wmat_multipliers(params, wmat_multipliers)


def modify_net_params_2(cfg, params):
    """Apply experiment changes after subnet netParams creation."""
    if not cfg.runtime_params['conn']['ee_fader_on']:
        return

    # Set distinct synMech labels for surrogate and recurrent inputs
    split_pairs = set(cfg.conns_split)
    rank = int(h.ParallelContext().id())
    for cname, conn in params.connParams.items():
        kind, pops_pre_base, pops_post = _rule_kind_and_base_pops(
            conn  #, verbose=(rank == 0)
        )
        if kind is None:
            continue
        needs_split = any(
            (p_pre, p_post) in split_pairs
            for p_pre in pops_pre_base
            for p_post in pops_post
        )
        if needs_split:
           _relabel_conn_synmech(params, conn, kind)


def modify_network(sim):
    """Add recurrent-connection faders after network creation."""
    if not sim.cfg.runtime_params['conn']['ee_fader_on']:
        return

    # Fader object
    fader = ConnFader(
        sim, T=sim.cfg.duration, dt=sim.cfg.dt
    )

    # Find recurrent/surrogate conns for positive/inverse modulation
    conns_pos, conns_neg = [], []
    for pop_pre, pop_post in sim.cfg.conns_split:
        conns_pos_ = get_2pop_conns(sim, pop_pre, pop_post)   # recurrent conns
        conns_neg_ = get_2pop_conns(sim, pop_pre + 'frz', pop_post)   # surrogate inputs
        conns_pos += conns_pos_
        conns_neg += conns_neg_
    
    fader.add_conn_group(
        group_name='ee',
        conns_pos=conns_pos,
        conns_neg=conns_neg,
        pts=sim.cfg.runtime_params['conn']['fader_pts']
    )

    fader.create_modulators()
    fader.connect_modulators()
    fader.setup_recording(rec_dt=1)

    sim.ee_fader = fader


def _relative_output(cfg, fpath):
    """Return a result path relative to cfg.saveFolder."""
    return Path(fpath).relative_to(Path(cfg.saveFolder)).as_posix()


def _get_rate_t_limits(cfg):
    """Resolve rate-dynamics processing limits in seconds."""
    t_limits = cfg.runtime_params['proc']['rate_t_limits']
    if t_limits is not None:
        return tuple(t_limits)
    return (cfg.t0_calc / 1000, cfg.duration / 1000)


def _save_rate_xr(sim, dirpath_res_sub, postfix):
    """Save compact population-rate dynamics as NetCDF."""
    cfg = sim.cfg
    proc_params = cfg.runtime_params['proc']
    t_limits = _get_rate_t_limits(cfg)
    sim_result = prepare_sim_result(sim)
    rvec_xr = get_net_rate_dynamics_xr(
        sim_result,
        t_limits=t_limits,
        dt_bin=proc_params['rate_dt_bin'],
        tau_smooth=proc_params['rate_tau_smooth'],
        pop_names=cfg.pops_used,
    )
    rvec_xr.attrs['t_limits'] = list(t_limits)
    rvec_xr.attrs['dt_bin'] = float(proc_params['rate_dt_bin'])
    rvec_xr.attrs['tau_smooth'] = float(proc_params['rate_tau_smooth'])
    rvec_xr.attrs['seed_main'] = int(cfg.seed_main)
    fpath_rvec = dirpath_res_sub / 'rvec_xr' / f'rvec_{postfix}.nc'
    rvec_xr.to_netcdf(fpath_rvec)
    return fpath_rvec


def _save_lfp_xr(sim, dirpath_res_sub, postfix):
    """Save compact total LFP dynamics as NetCDF."""
    cfg = sim.cfg
    sim_result = prepare_sim_result(sim)
    lfp_xr = get_lfp_xr(sim_result)
    lfp_xr.attrs['seed_main'] = int(cfg.seed_main)
    lfp_xr.attrs['f'] = float(cfg.f)
    lfp_xr.attrs['amp1'] = float(cfg.amp1)
    lfp_xr.attrs['amp2'] = float(cfg.amp2)
    lfp_xr.attrs['dt0'] = float(cfg.dt0)
    lfp_xr.attrs['dt_rec'] = float(DT_REC)
    fpath_lfp = dirpath_res_sub / 'lfp_xr' / f'lfp_{postfix}.nc'
    lfp_xr.to_netcdf(fpath_lfp)
    return fpath_lfp


def _get_job_postfix(cfg, exp_name):
    """Generate a compact postfix from the batch coordinates."""
    exp_id = exp_name.split('_')[-1]
    return (
        f'{exp_id}_seed_{cfg.seed_main}_f_{cfg.f:g}_'
        f'amp1_{cfg.amp1:g}_amp2_{cfg.amp2:g}_dt0_{cfg.dt0:g}'
    )


def post_run(sim):
    """Process and organize one completed simulation job."""
    cfg = sim.cfg
    exp_name = cfg.simLabel
    outputs = []

    # Metric calculation time interval in seconds
    t_limits = (cfg.t0_calc / 1000, cfg.duration / 1000)

    # Experiment sub-name
    exp_name_sub = gen_exp_name_sub(cfg)

    # Generate filename postfix with batch param values
    postfix = _get_job_postfix(cfg, exp_name)

    # Create subfolders to put the results
    dirpath_res = Path(cfg.saveFolder)
    dirpath_res_sub = dirpath_res / exp_name_sub
    os.makedirs(dirpath_res_sub, exist_ok=True)
    dirnames_sub = ['rasters', 'results', 'cfg', 'pkl', 'netpar', 
                    'traces', 'wmod_figs', 'rvec_figs', 'csd_figs',
                    'rvec_xr', 'lfp_xr']
    for dirname in dirnames_sub:
        os.makedirs(dirpath_res_sub / dirname, exist_ok=True)

    # Move results to a subfolder
    data_info = [
        ('raster', 'png', 'rasters'),
        ('cfg', 'json', 'cfg'),
        ('netParams', 'json', 'netpar'),
        ('CSD', 'png', 'csd_figs')
    ]
    if cfg.savePickle:
        data_info.insert(1, ('data', 'pkl', 'pkl'))
    for di in data_info:
        data_name, ext, dirname_sub = di
        fpath_old = dirpath_res / f'{exp_name}_{data_name}.{ext}'
        fpath_new = dirpath_res_sub / dirname_sub / f'{data_name}_{postfix}.{ext}'
        if fpath_old.exists():
            fpath_old.rename(fpath_new)
        else:
            print('RESULT NOT FOUND: ', fpath_old)

    # Move NetPyNE-generated traces to a subfolder
    trace_files = list(dirpath_res.glob(f'{exp_name}_traces*.png'))
    for fpath_old in trace_files:
        fpath_new = dirpath_res_sub / 'traces' / f'{fpath_old.stem}_{postfix}{fpath_old.suffix}'
        fpath_old.rename(fpath_new)
    
    # Move NetPyNE-generated CSD figures to a subfolder
    if cfg.rec_lfp and cfg.plot_csd:
        csd_files = list(dirpath_res.glob(f'{exp_name}_CSD*.png'))
        for fpath_old in csd_files:
            fpath_new = dirpath_res_sub / 'csd_figs' / f'{fpath_old.stem}_{postfix}{fpath_old.suffix}'
            fpath_old.rename(fpath_new)
    
    # Save rates, CVs, voltage stats, and timings to a json file
    if NEED_RUN:
        res = {}
        res['timing'] = sim.timingData
        res |= proc.calc_rates_and_cvs(sim, t_limits, nspikes_min=3)
        if cfg.rec_traces:
            res |= proc.calc_v_stats(sim, t_limits, med_win=0.05)
        fpath_res = dirpath_res_sub / 'results' / f'result_{postfix}.json'
        with open(fpath_res, 'w') as fid:
            json.dump(res, fid, indent=4)
        outputs.append(_relative_output(cfg, fpath_res))
    
    # Plot weight modulation signals
    if cfg.runtime_params['conn']['ee_fader_on'] and NEED_RUN:
        #gathered = sim.ee_fader.gather_recs()
        sim.ee_fader.plot_recs()
        fpath_wmod = (dirpath_res_sub / 'wmod_figs' / f'wmod_{postfix}.png')
        plt.savefig(fpath_wmod, dpi=300)

    # Save optional compact rate dynamics for downstream processing
    if NEED_RUN and cfg.runtime_params['out']['save_rate_xr']:
        fpath_rvec = _save_rate_xr(sim, dirpath_res_sub, postfix)
        outputs.append(_relative_output(cfg, fpath_rvec))

    # Save optional compact LFP dynamics for downstream processing
    if NEED_RUN and cfg.runtime_params['out']['save_lfp_xr']:
        fpath_lfp = _save_lfp_xr(sim, dirpath_res_sub, postfix)
        outputs.append(_relative_output(cfg, fpath_lfp))

    # Plot and save rate dynamics
    if cfg.plot_rate_dynamics:
        pop_groups = {'PYR': PYR_POPS, 'PV': PV_POPS, 'SOM': SOM_POPS,
                      'VIP': VIP_POPS, 'NGF': NGF_POPS,
                      'THAL_E': THAL_E_POPS, 'THAL_I': THAL_I_POPS}
        colors = plt.rcParams['axes.prop_cycle'].by_key()['color']
        for pop_group_name, pops in pop_groups.items():
            pops = [p for p in pops if p in cfg.pops_used]
            if len(pops) == 0:
                continue

            # Compute rate dynamics
            r_data = proc.calc_rate_dynamics(
                sim,
                t_limits=_get_rate_t_limits(cfg),
                tau_smooth=cfg.runtime_params['proc']['rate_tau_smooth'],
                pops_used=pops)

            plt.figure(111); plt.clf()

            for n, pop in enumerate(pops):
                tt, rr = r_data[pop]
                r0 = cfg.target_rates[pop]
                col = colors[n % len(colors)]
                plt.plot(tt, rr, label=pop, color=col)
                plt.plot([tt[0], tt[-1]], [r0, r0], '--', color=col)

            plt.xlabel('Time')
            plt.ylabel('Firing rate')
            plt.legend(bbox_to_anchor=(1, 1))
            #plt.yscale('log')
            #plt.ylim(0.05, None)

            fname_out = f'{pop_group_name}_{postfix}.png'
            plt.savefig(dirpath_res_sub / 'rvec_figs' / fname_out,
                        bbox_inches='tight', dpi=300)

    return outputs


def final(sim):
    if not DIAG or not NEED_RUN:
        return

    diag.count_conns(sim)
    diag.count_synmechs(sim)
    diag.count_netcons_neuron(sim)
    #diag.count_pointprocesses(sim)
    diag.report_min_delay(sim)
    #diag.conn_distance_percentiles(sim)

    # Count post-synaptic sections
    pops_pre = ['ITP4frz']
    pops_post = ['ITP4']
    sec_groups = {
        'soma': ['soma'],
        #'Adend': ['Adend1', 'Adend2', 'Adend3'],
        'Bdend': ['Bdend'],
        'Adend1': ['Adend1'],
        'Adend2': ['Adend2'],
        'Adend3': ['Adend3']
    }
    sec_counts = diag.count_conn_target_secs(
        sim, sec_groups, pops_pre, pops_post)
    if sim.rank == 0:
        print('Conn targets by sec group:', sec_counts)
        #diag.print_cell_nseg(sim, 'IT2')
