import json
from pathlib import Path
import sys

# Set import paths
dirpath_repo_root = Path(__file__).resolve().parents[3]
dirpath_self = Path(__file__).resolve().parent
sys.path.append(str(dirpath_repo_root))
sys.path.append(str(dirpath_self))

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from analysis.ou_tuning import sim_res_proc_utils as proc
from batch_params import (
    N_SEEDS,
    IBKG_MIN, IBKG_MAX, IBKG_NUM,
    IBKG_DW_ADJ_VALUES,
    PYR_POPS, PV_POPS, SOM_POPS, VIP_POPS, NGF_POPS, 
    L2_POPS, 
)
from workflow_result_utils import (
    move_if_present,
    organize_standard_outputs,
    relative_output,
)


# Timing constants
SIM_DURATION = 15 * 1e3
T0_CALC = 5 * 1e3

# Experiment name
EXP_LABEL = 'dw_adj_L2_ee_2'

# Active populations
POPS_USED = L2_POPS

# Weight adjustment
WMAT_MULTIPLIERS = {
    ('IT2', 'IT2'): 2
}

# Background e/i Poisson inputs
XBKG_NAME = 'rx_bkg_mid_sm_ctx21_thal41'

# Bkg current: correction 1
USE_IBKG = 1
IBKG_JSON_NAME = 'ibkg_mech1_verest_-70_thal_spkthr'

# Bkg current: correction 2
USE_IBKG_CTRL = 1
IBKG_CTRL_JSON_NAME = 'ibkg_ctrl_1'

SURR_INP_ON = 1

# Recording flags
DT_REC = 1
REC_TRACES = 0
PLOT_TRACES = 0

NCELLS_REC = 5
NCELLS_PLOT = 0

REC_LFP = 0
LFP_Y_MIN = 0
LFP_Y_MAX = 3000
LFP_Y_STEP = 100

# CSD plotting flags
PLOT_CSD = 0
CSD_VIS_T0 = 5000

LAYER_BOUNDS = {'L1': 100, 'L2': 160, 'L3': 950, 'L4': 1250,
                'L5A': 1334, 'L5B': 1550, 'L6': 2000}

PLOT_RATE_DYNAMICS = 1
RVEC_TAU_SMOOTH = 0.1
RVIS_POP_GROUPS = {
    #'PYR': PYR_POPS, 'PV': PV_POPS, 'SOM': SOM_POPS, 
    #'VIP': VIP_POPS, 'NGF': NGF_POPS,
    'L2': L2_POPS
    #'ALL': POPS_USED
}

# Run flag
NEED_RUN = 1


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

    # Other settings must already be defined by apply_exp_cfg()
    for name, value in overrides.items():
        if not hasattr(cfg, name):
            raise KeyError(f'Unknown experiment override: {name}')
        setattr(cfg, name, value)


def gen_exp_name_sub(cfg):
    """Generate the result subfolder name."""
    if hasattr(cfg, 'workflow_result_subdir'):
        return cfg.workflow_result_subdir

    exp_name_sub = f'exp_{EXP_LABEL}'
    # Surrogate input flag
    if not SURR_INP_ON:
        exp_name_sub += '_nosurr'
    # Batch params
    exp_name_sub += (
        f'_nseed_{N_SEEDS}_ibkg_{IBKG_MIN}_{IBKG_MAX}_{IBKG_NUM}'
    )
    # Time window tag
    t_limits = (cfg.t0_calc / 1000, cfg.duration / 1000)
    exp_name_sub += f'_t_{t_limits[0]}_{t_limits[1]}'
    # LFP tag
    if REC_LFP:
        exp_name_sub += f'_lfp_{LFP_Y_MIN}_{LFP_Y_MAX}_{LFP_Y_STEP}'
    # Control-derived static correction
    if USE_IBKG_CTRL:
        exp_name_sub += '_ictrl'
    # Weight tag
    exp_name_sub += f'_wmult_{cfg.wmult}_ee_{cfg.EEGain}'
    return exp_name_sub


def apply_exp_cfg(cfg):
    """Apply experiment config to the base cfg."""
    # Timing and run flags
    cfg.duration = SIM_DURATION
    cfg.t0_calc = T0_CALC
    cfg.need_run = NEED_RUN

    # Active populations
    pops_active = POPS_USED

    # Batch-controlled params
    cfg.seed_main = None
    cfg.ibkg_dw_adj = None

    # Random seeds (set in batch)
    cfg.seeds['stim'] = None
    cfg.seeds['conn'] = None

    # Save and cache flags
    cfg.includeParamsLabel = True
    cfg.cache_efficient = 0

    # Subnet setup
    cfg.subnet_build_flag = SURR_INP_ON
    cfg.subnet_params = {
        'pops_active': pops_active,
        'conns_frozen': 'all',
        'fpath_frozen_rates': str(dirpath_self / 'target_state_1.csv'),
        'global_seed': None,   # set in batch
    }

    if not SURR_INP_ON:
        cfg.pops_active = POPS_USED
        cfg.addConn = 0

    # Weight metadata
    cfg.wmult = 0.25
    cfg.EEGain = 0.5
    cfg.wmat_multipliers = [
        {'pre': pre, 'post': post, 'mult': mult}
        for (pre, post), mult in WMAT_MULTIPLIERS.items()
    ]

    # Connectivity flags
    cfg.addSubConn = 0
    cfg.connRandomSecFromList = 1
    cfg.connWeightSecByLength = 0

    # Background input table
    fpath_xbkg = dirpath_self / f'{XBKG_NAME}.csv'
    df = pd.read_csv(fpath_xbkg).set_index('pop')
    df.drop(columns=['Unnamed: 0'], errors='ignore')
    df['rxe'] = np.maximum(df['rxe'], 1e-3)
    df['rxi'] = np.maximum(df['rxi'], 1e-3)
    xbkg_info = df.T.to_dict()

    # Background spiking inputs
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

    # Baseline IClamps
    if USE_IBKG:
        cfg.addIClamp = 1
        fname_ibkg = f'{IBKG_JSON_NAME}.json'
        with open(dirpath_self / fname_ibkg, 'r') as fid:
            ibkg = json.load(fid)
        cfg.IClamp = {pop: {'amp': ibkg[pop], 'dur': SIM_DURATION}
                      for pop in POPS_USED if pop in ibkg}

    # Control-derived IClamps
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

    # Adjustable IClamp (to compensate WMAT_MULTIPLIERS)
    cfg.addIClamp = 1
    if not hasattr(cfg, 'IClamp') or cfg.IClamp is None:
        cfg.IClamp = {}
    cfg.IClamp_ibkg_dw_adj = {}
    for pop in POPS_USED:
        adj_entry = {'amp': 0, 'dur': SIM_DURATION}
        cfg.IClamp_ibkg_dw_adj[pop] = adj_entry
        _append_iclamp_entry(cfg.IClamp, pop, adj_entry)

    # Target rates
    df = pd.read_csv(dirpath_self / 'target_state_1.csv')
    cfg.target_rates = df.set_index('pop_name')['target_rate'].to_dict()

    # Mechanism changes
    with open(dirpath_self / 'mech_changes_1.json', 'r') as fid:
        cfg.mech_changes = json.load(fid)

    # Analysis pop filters
    if 'plotRaster' in cfg.analysis:
        cfg.analysis['plotRaster']['include'] = POPS_USED
    if 'plotSpikeStats' in cfg.analysis:
        cfg.analysis['plotSpikeStats']['include'] = POPS_USED
    if 'plotTraces' in cfg.analysis:
        cfg.analysis['plotTraces']['include'] = POPS_USED

    cfg.analysis['plotSpikeStats'] = False

    # Voltage recording
    if REC_TRACES:
        cfg.recordCells = [(pop, list(range(NCELLS_REC))) for pop in POPS_USED]
        cfg.recordTraces = {'V_soma': {'sec': 'soma', 'loc': 0.5, 'var': 'v'}}
        cfg.recordStep = DT_REC

    # Voltage plotting
    if REC_TRACES and PLOT_TRACES:
        cfg.analysis['plotTraces'] = {
            'include': [(pop, list(range(NCELLS_PLOT))) for pop in POPS_USED],
            'timeRange': [1000, cfg.duration],
            'oneFigPer': 'cell', 'overlay': True,
            'saveFig': True, 'showFig': False, 'figSize': (18, 12)
        }

    # LFP recording
    if REC_LFP:
        cfg.recordTime = True
        cfg.recordStep = DT_REC
        cfg.recordLFP = [[100, y, 100]
                         for y in range(LFP_Y_MIN, LFP_Y_MAX, LFP_Y_STEP)]

    # CSD plotting
    if REC_LFP and PLOT_CSD:
        csd_t0 = CSD_VIS_T0 if CSD_VIS_T0 is not None else 2000
        cfg.analysis['plotCSD'] = {
            'spacing_um': LFP_Y_STEP, 'LFP_overlay': 1, 'layer_lines': 1,
            'layer_bounds': LAYER_BOUNDS, 'saveFig': 1, 'showFig': 0,
            'timeRange': (csd_t0, cfg.duration)
        }


def modify_net_params(cfg, params):
    """Applied after netParams creation."""

    # Membrane mechanisms
    for v in cfg.mech_changes.values():
        secs_all = params.cellParams[v['pop']]['secs']
        if v['sec'] == 'all':
            secs = list(secs_all.values())
        else:
            secs = [secs_all[v['sec']]]
        for sec in secs:
            sec['mechs'][v['mech']][v['par']] *= v['mult']
            sec['mechs'][v['mech']][v['par']] += v['add']

    # Target sections
    with open(dirpath_self / 'target_sec_1.json', 'r') as fid:
        target_sec = json.load(fid)
    for cname, conn in params.connParams.items():
        src_pop = conn['preConds'].get('pop', None)
        dst_pop = conn['postConds'].get('pop', None)
        if (src_pop is None) or (dst_pop is None):
            raise ValueError(f'Pre or post pop is not specified for conn {cname}')
        conn['sec'] = None
        for ts in target_sec.values():
            if (src_pop in ts['pops_pre']) and (dst_pop in ts['pops_post']):
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
        pop_pre = conn['preConds'].get('pop', None)
        pop_post = conn['postConds'].get('pop', None)
        pair = (pop_pre, pop_post)
        if pair not in wmat_multipliers:
            continue
        conn['weight'] *= wmat_multipliers[pair]
        matched_pairs.add(pair)

    missing_pairs = set(wmat_multipliers) - matched_pairs
    if missing_pairs:
        raise ValueError(
            f'No connParams found for wmat multipliers: {missing_pairs}'
        )


def post_run(sim):
    """Called in the end of a job (after running and saving)."""
    cfg = sim.cfg
    exp_name = cfg.simLabel

    t_limits = (cfg.t0_calc / 1000, cfg.duration / 1000)
    exp_name_sub = gen_exp_name_sub(cfg)

    # Result naming postfix
    exp_id = exp_name.split('_')[-1]
    postfix = (
        f'{exp_id}_seed_{cfg.seed_main}_ibkg_dw_adj_{cfg.ibkg_dw_adj:g}'
    )

    # Standard output relocation and retention
    dirpath_res = Path(cfg.saveFolder)
    dirpath_res_sub = organize_standard_outputs(
        cfg,
        exp_name_sub,
        postfix,
    )

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

    # Results json
    outputs = []
    if NEED_RUN:
        res = {}
        res['timing'] = sim.timingData
        res |= proc.calc_rates_and_cvs(sim, t_limits, nspikes_min=3)
        res['avg_rates'] = sim.analysis.popAvgRates(
            tranges=[cfg.t0_calc, cfg.duration],
            show=False,
        )
        if REC_TRACES:
            res |= proc.calc_v_stats(sim, t_limits, med_win=0.05)
        fpath_res = dirpath_res_sub / 'results' / f'result_{postfix}.json'
        with open(fpath_res, 'w') as fid:
            json.dump(res, fid, indent=4)
        outputs.append(relative_output(cfg, fpath_res))
    
    # Plot and save rate dynamics
    if PLOT_RATE_DYNAMICS:
        colors = plt.rcParams['axes.prop_cycle'].by_key()['color']
        for pop_group_name, pops in RVIS_POP_GROUPS.items():
            pops = [p for p in pops if p in POPS_USED]
            if len(pops) == 0:
                continue

            # Compute rate dynamics
            r_data = proc.calc_rate_dynamics(
                sim, t_limits=(2, None), tau_smooth=RVEC_TAU_SMOOTH, pops_used=pops)

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
