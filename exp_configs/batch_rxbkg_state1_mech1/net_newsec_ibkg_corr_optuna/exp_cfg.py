import json
import os
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
from batch_params import (
    FIXED_SEED_MAIN,
    IBKG_CORR_RANGES,
    N_SEEDS,
    get_ibkg_corr_param_name,
)
import diagnostics as diag


PYR_POPS = ['IT2', 'IT3', 'ITP4', 'ITS4', 'IT5A', 'IT5B', 'IT6',
            'CT5A', 'CT5B', 'CT6', 'PT5B']
PV_POPS = ['PV2', 'PV3', 'PV4', 'PV5A', 'PV5B', 'PV6']
SOM_POPS = ['SOM2', 'SOM3', 'SOM4', 'SOM5A', 'SOM5B', 'SOM6']
VIP_POPS = ['VIP2', 'VIP3', 'VIP4', 'VIP5A', 'VIP5B', 'VIP6']
NGF_POPS = ['NGF1', 'NGF2', 'NGF3', 'NGF4', 'NGF5A', 'NGF5B', 'NGF6']

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
T0_CALC = 10 * 1e3

EXP_LABEL = 'a1_ibkg_corr_optuna'

POPS_USED = CTX_POPS + THAL_POPS

CONNS_FROZEN = CONNS_EE

# Background spiking input
XBKG_NAME = 'rx_bkg_mid_sm_ctx21_thal41'

# Constant input to set Vrest
USE_IBKG = 1
IBKG_JSON_NAME = 'ibkg_mech1_verest_-70_thal_spkthr'

# Surrogate inputs
SURR_INP_ON = 1

REC_TRACES = 0
PLOT_TRACES = 0
PLOT_RATE_DYNAMICS = 0

NEED_RUN = 0
TEST_MODE = 'surrogate_loss'
DIAG = 0

INVALID_RATE_PENALTY = 100.0
SURROGATE_TARGET_BY_POP = {
    'HTC': 0.25,
    'TC': -0.20,
    'TCM': 0.15,
    'IRE': 0.04,
    'IREM': -0.03,
    'TI': 0.004,
    'TIM': -0.006,
}


def gen_exp_name_sub(cfg):
    t_limits = (cfg.t0_calc / 1000, cfg.duration / 1000)
    exp_name_sub = f'exp_{EXP_LABEL}'
    if not SURR_INP_ON:
        exp_name_sub += '_nosurr'
    if TEST_MODE is not None:
        exp_name_sub += f'_{TEST_MODE}'
    #exp_name_sub += f'_nseed_{N_SEEDS}'
    exp_name_sub += f'_t_{t_limits[0]}_{t_limits[1]}'
    #exp_name_sub += '_icorr'
    """ for pop_name in IBKG_CORR_RANGES:
        par_name = get_ibkg_corr_param_name(pop_name)
        exp_name_sub += f'_{pop_name}_{getattr(cfg, par_name)}' """
    exp_name_sub += f'_wmult_{cfg.wmult}_ee_{cfg.EEGain}'
    return exp_name_sub


def _build_bkg_spike_inputs(xbkg_info, pops_used, stim_seed):
    # Background spiking input
    bkg_spike_inputs = {}
    for n, pop in enumerate(pops_used):
        x = xbkg_info[pop]
        bkg_spike_inputs[pop] = {
            'exc': {
                'r': x['rxe'],
                'w': x['wxe'],
                'sec': x['xe_sec'],
                'noise': 1,
                'seed': stim_seed + 10000 + n,
            },
            'inh': {
                'r': x['rxi'],
                'w': x['wxi'],
                'sec': x['xi_sec'],
                'noise': 1,
                'seed': stim_seed + 20000 + n,
            },
        }
    return bkg_spike_inputs


def apply_exp_cfg(cfg):
    # Duration
    cfg.duration = SIM_DURATION

    # Left point (ms) of the calculation time window (r, cv, ...)
    cfg.t0_calc = T0_CALC

    cfg.need_run = NEED_RUN
    cfg.test_mode = TEST_MODE

    # Populations to use
    pops_active = POPS_USED

    # Random seeds
    cfg.seed_main = FIXED_SEED_MAIN
    cfg.seeds['stim'] = cfg.seed_main
    cfg.seeds['conn'] = cfg.seed_main * 2

    # Subnet parameters
    cfg.subnet_build_flag = SURR_INP_ON
    cfg.subnet_params = {
        'pops_active': pops_active,
        'conns_frozen': CONNS_FROZEN,
        'fpath_frozen_rates': str(dirpath_self / 'target_state_1.csv'),   # surrogate input
        'global_seed': cfg.seed_main * 3,
    }

    if not SURR_INP_ON:
        cfg.pops_active = POPS_USED
        cfg.addConn = 0

    # Weight multipliers
    cfg.wmult = 0.25
    cfg.EEGain = 0.5

    # Connectivity params
    cfg.addSubConn = 0
    cfg.connRandomSecFromList = 1
    cfg.connWeightSecByLength = 0

    if DIAG:
        cfg.createNEURONObj = True      # Create NEURON hoc objects
        cfg.createPyStruct = True       # Create Python structure
        cfg.saveCellSecs = True         # Save section data (includes hObj)
        cfg.saveCellConns = True        # Save connection data
        cfg.compactConnFormat = False   # Keep full dict format for conns
        cfg.includeParamsLabel = True

    # Load bkg spiking input info
    fpath_xbkg = dirpath_self / f'{XBKG_NAME}.csv'
    df = pd.read_csv(fpath_xbkg).set_index('pop')
    df.drop(columns=['Unnamed: 0'], errors='ignore')
    df['rxe'] = np.maximum(df['rxe'], 1e-3)
    df['rxi'] = np.maximum(df['rxi'], 1e-3)
    xbkg_info = df.T.to_dict()

    # Background spiking input
    cfg.add_bkg_spike_input = 1
    cfg.replace_bkg_spikes_by_ou = 0   # use NetStim's
    cfg.bkg_spike_inputs = _build_bkg_spike_inputs(
        xbkg_info=xbkg_info,
        pops_used=POPS_USED,
        stim_seed=cfg.seeds['stim'],
    )

    # Static IClamp that sets the resting voltage
    if USE_IBKG:
        cfg.addIClamp = 1
        fname_ibkg = f'{IBKG_JSON_NAME}.json'
        with open(dirpath_self / fname_ibkg, 'r') as fid:
            ibkg = json.load(fid)
        cfg.IClamp = {
            pop: {'amp': ibkg[pop], 'dur': SIM_DURATION}
            for pop in POPS_USED if pop in ibkg
        }

    if not hasattr(cfg, 'IClamp') or cfg.IClamp is None:
        cfg.IClamp = {}

    for pop_name in IBKG_CORR_RANGES:
        par_name = get_ibkg_corr_param_name(pop_name)
        if not hasattr(cfg, par_name):
            setattr(cfg, par_name, 0.0)   # set by cfg.update()

    # Read target rates
    df = pd.read_csv(dirpath_self / 'target_state_1.csv')
    cfg.target_rates = df.set_index('pop_name')['target_rate'].to_dict()

    # Conductance changes
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
        ncells_rec = 5
        ncells_plot = 2
        cfg.recordCells = [(pop, list(range(ncells_rec))) for pop in POPS_USED]
        cfg.recordTraces = {'V_soma': {'sec': 'soma', 'loc': 0.5, 'var': 'v'}}
        cfg.recordStep = 0.1
        if PLOT_TRACES:
            cfg.analysis['plotTraces'] = {
                'include': [(pop, list(range(ncells_plot))) for pop in cfg.allpops],
                'timeRange': [1000, cfg.duration],
                'oneFigPer': 'cell', 'overlay': True,
                'saveFig': True, 'showFig': False, 'figSize': (18, 12),
            }


def modify_net_params(cfg, params):
    """Applied after netParams creation. """

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
        for ts in target_sec.values():
            if (pop_pre in ts['pops_pre']) and (pop_post in ts['pops_post']):
                conn['sec'] = ts['sec']
                break
        if conn['sec'] is None:
            raise ValueError(f'No target sec info found for conn {cname}')


def _calc_result_summary(sim):
    # Metric calculation time interval in seconds
    cfg = sim.cfg
    t_limits = (cfg.t0_calc / 1000, cfg.duration / 1000)

    # Summary metrics
    res = {'timing': sim.timingData}
    res |= proc.calc_rates_and_cvs(sim, t_limits, nspikes_min=3)
    if REC_TRACES:
        res |= proc.calc_v_stats(sim, t_limits, med_win=0.05)
    return res


def _get_surrogate_target_by_param():
    return {
        get_ibkg_corr_param_name(pop_name): target
        for pop_name, target in SURROGATE_TARGET_BY_POP.items()
    }


def _get_result_summary(sim):
    # Cache metrics so post_run() and get_batch_metrics() share one calculation
    if not hasattr(sim, '_exp_result_summary'):
        sim._exp_result_summary = _calc_result_summary(sim)
    return sim._exp_result_summary


def _calc_surrogate_batch_metrics(cfg):
    # Deterministic test objective with a known nonzero optimum
    target_by_param = _get_surrogate_target_by_param()
    abs_errors = []
    sq_errors = []

    for par_name, target in target_by_param.items():
        value = float(getattr(cfg, par_name))
        err = value - target
        abs_errors.append(abs(err))
        sq_errors.append(err ** 2)

    return {
        'loss_rate_mae': float(np.mean(abs_errors)),
        'loss_l2': float(np.mean(sq_errors)),
        'loss_max_abs': float(np.max(abs_errors)),
        'num_valid_pops': len(target_by_param),
        'num_penalized_pops': 0,
        'num_surrogate_params': len(target_by_param),
    }


def _calc_batch_metrics(cfg, res):
    # Optuna objective is calculated against all active pops with target rates
    rates = res.get('rates', {})
    pops_metric = [pop for pop in POPS_USED if pop in cfg.target_rates]

    loss_terms = []
    num_valid_pops = 0
    num_penalized_pops = 0

    # Penalize missing or invalid rates so every trial returns a numeric loss
    for pop in pops_metric:
        rate = rates.get(pop)
        target_rate = cfg.target_rates.get(pop)
        is_valid = (
            rate is not None and
            target_rate is not None and
            np.isfinite(rate) and
            np.isfinite(target_rate)
        )
        if is_valid:
            loss_terms.append(abs(float(rate) - float(target_rate)))
            num_valid_pops += 1
        else:
            loss_terms.append(INVALID_RATE_PENALTY)
            num_penalized_pops += 1

    if not loss_terms:
        loss_terms = [INVALID_RATE_PENALTY]
        num_penalized_pops = 1

    return {
        'loss_rate_mae': float(np.mean(loss_terms)),
        'num_valid_pops': num_valid_pops,
        'num_penalized_pops': num_penalized_pops,
    }


def post_run(sim):
    """Called in the end of a job (after runnig and saving). """

    cfg = sim.cfg
    exp_name = cfg.simLabel

    # Experiment sub-name
    exp_name_sub = gen_exp_name_sub(cfg)

    # Generate filename postfix with batch param values
    exp_id = exp_name.split('_')[-1]
    postfix = f'{exp_id}_seed_{cfg.seed_main}'

    # Create subfolders to put the results
    dirpath_res = Path(cfg.saveFolder)
    dirpath_res_sub = dirpath_res / exp_name_sub
    os.makedirs(dirpath_res_sub, exist_ok=True)
    dirnames_sub = ['rasters', 'results', 'cfg', 'pkl', 'netpar', 'traces', 'rvec_figs']
    for dirname in dirnames_sub:
        os.makedirs(dirpath_res_sub / dirname, exist_ok=True)

    # Move results to a subfolder
    data_info = [
        ('raster', 'png', 'rasters'),
        ('data', 'pkl', 'pkl'),
        ('cfg', 'json', 'cfg'),
        ('netParams', 'json', 'netpar'),
    ]
    for data_name, ext, dirname_sub in data_info:
        fpath_old = dirpath_res / f'{exp_name}_{data_name}.{ext}'
        fpath_new = dirpath_res_sub / dirname_sub / f'{data_name}_{postfix}.{ext}'
        if fpath_old.exists():
            fpath_old.rename(fpath_new)
        else:
            print('RESULT NOT FOUND: ', fpath_old)

    trace_files = list(dirpath_res.glob(f'{exp_name}_traces*.png'))
    for fpath_old in trace_files:
        fpath_new = dirpath_res_sub / 'traces' / f'{fpath_old.stem}_{postfix}{fpath_old.suffix}'
        fpath_old.rename(fpath_new)

    # Save scalar results
    if NEED_RUN:
        res = _get_result_summary(sim)
        res |= _calc_batch_metrics(cfg, res)
        sim._exp_result_summary = res
        fpath_res = dirpath_res_sub / 'results' / f'result_{postfix}.json'
        with open(fpath_res, 'w') as fid:
            json.dump(res, fid, indent=4)

    # Plot rate vectors
    if PLOT_RATE_DYNAMICS:
        pop_groups = {'PYR': PYR_POPS, 'PV': PV_POPS, 'SOM': SOM_POPS,
                      'VIP': VIP_POPS, 'NGF': NGF_POPS,
                      'THAL_E': THAL_E_POPS, 'THAL_I': THAL_I_POPS}
        colors = plt.rcParams['axes.prop_cycle'].by_key()['color']
        for pop_group_name, pops in pop_groups.items():
            pops = [p for p in pops if p in POPS_USED]
            if len(pops) == 0:
                continue

            r_data = proc.calc_rate_dynamics(
                sim, t_limits=(2, None), tau_smooth=0.2, pops_used=pops)

            plt.figure(111)
            plt.clf()

            for n, pop in enumerate(pops):
                tt, rr = r_data[pop]
                r0 = cfg.target_rates[pop]
                col = colors[n % len(colors)]
                plt.plot(tt, rr, label=pop, color=col)
                plt.plot([tt[0], tt[-1]], [r0, r0], '--', color=col)

            plt.xlabel('Time')
            plt.ylabel('Firing rate')
            plt.legend(bbox_to_anchor=(1, 1))

            fname_out = f'{pop_group_name}_{postfix}.png'
            plt.savefig(dirpath_res_sub / 'rvec_figs' / fname_out,
                        bbox_inches='tight', dpi=300)


def get_batch_metrics(sim):
    # Used by run_exp.py to report metrics back to batchtools/Optuna
    if not getattr(sim.cfg, 'need_run', True):
        test_mode = getattr(sim.cfg, 'test_mode', None)
        if test_mode == 'surrogate_loss':
            return _calc_surrogate_batch_metrics(sim.cfg)
        raise ValueError(f'Unsupported no-run test_mode: {test_mode!r}')

    res = _get_result_summary(sim)
    return _calc_batch_metrics(sim.cfg, res)


def final(sim):
    if not DIAG or not NEED_RUN:
        return

    diag.count_conns(sim)
    diag.count_synmechs(sim)
    diag.count_netcons_neuron(sim)
    diag.report_min_delay(sim)
