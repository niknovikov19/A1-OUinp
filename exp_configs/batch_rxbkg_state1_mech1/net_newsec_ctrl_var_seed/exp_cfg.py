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

from analysis.model_utils.net_utils import get_2pop_conns
from analysis.ou_tuning import sim_res_proc_utils as proc
from batch_params import N_SEEDS
from conn_fader import ConnFader
import diagnostics as diag
from syn_mech_relabel import _rule_kind_and_base_pops, _relabel_conn_synmech


PYR_POPS = ['IT2', 'IT3', 'ITP4', 'ITS4', 'IT5A', 'IT5B', 'IT6',
            'CT5A', 'CT5B', 'CT6', 'PT5B']
PV_POPS = ['PV2', 'PV3', 'PV4', 'PV5A', 'PV5B', 'PV6']
SOM_POPS = ['SOM2', 'SOM3', 'SOM4', 'SOM5A', 'SOM5B', 'SOM6']
VIP_POPS = ['VIP2', 'VIP3', 'VIP4', 'VIP5A', 'VIP5B', 'VIP6']
NGF_POPS = ['NGF1', 'NGF2', 'NGF3', 'NGF4', 'NGF5A', 'NGF5B', 'NGF6']
THAL_E_POPS = ['TC', 'HTC', 'TCM']
THAL_I_POPS = ['TI', 'TIM', 'IRE', 'IREM']

L2_POPS = ['IT2', 'PV2', 'SOM2', 'VIP2', 'NGF2']
L4_POPS = ['ITP4', 'ITS4', 'PV4', 'SOM4', 'VIP4', 'NGF4']

CORE_POPS = ['TC', 'HTC', 'TI', 'IRE']
MATX_POPS = ['TCM', 'TIM', 'IREM']

E_POPS = PYR_POPS + THAL_E_POPS
CONNS_EE = [(p1, p2) for p1 in E_POPS for p2 in E_POPS]


# Duration and rate calculation window
SIM_DURATION = 220 * 1e3
T0_CALC = 200 * 1e3

#EXP_LABEL = 'ctx_ee_fade'
#EXP_LABEL = 'ctx_ee_fade_0'
#EXP_LABEL = 'L2_ee_0_ceff_nomod'
#EXP_LABEL = 'L2_unconn'
EXP_LABEL = 'thal'
#EXP_LABEL = 'thal_ee_0'

#POPS_USED = PYR_POPS + PV_POPS + SOM_POPS + VIP_POPS + NGF_POPS
#POPS_USED = L2_POPS
#POPS_USED = THAL_E_POPS + THAL_I_POPS
#POPS_USED = ['IRE']
POPS_USED = CORE_POPS + MATX_POPS

#CONNS_FROZEN = 'all'
#CONNS_FROZEN = CONNS_EE
CONNS_FROZEN = []

EE_FADER_ON = 0

#CONNS_SPLIT = []
CONNS_SPLIT = [(p1, p2) for p1, p2 in CONNS_EE
               if (p1 in POPS_USED) and (p2 in POPS_USED)]

# Surr->recurrent fader timecourse (time, rec:surr ratio)
FADER_PTS = [(0, 0), (3000, 0), (5000, 1), (SIM_DURATION, 1)]
#FADER_PTS = [(0, 1), (SIM_DURATION, 1)]

# Rate-controlling feedback via tonic current
CTRL_ON = 0
CTRL_PARAMS = {
    # Controller type
    'controller_mod': 'RateController2',
    # Activity interval
    't0': 10000,
    'tlock': 160000,
    # Controller time scales
    'tau_rate_ctrl': 100,     # rate estimation from spikes
    'taum_ctrl': 2500,        # slow mean-error estimate m
    'tauu_ctrl': 100,         # fast helper u
    # Controller gains
    'ks_ctrl': 1e-4,           # slow tonic branch: s' = ks * phi(m)
    'ku_ctrl': 1e-3,           # fast branch: u' = (-u + ku*q)/tauu
    'epsm_ctrl': 0.1,          # dead zone on m; 0 -> linear
    # Other
    'target_rates': None,      # set later
    'z0': 0,
    # Actuator params
    'mu_gain': 0.005,
    'sigma_gain': 0.0,
}

# Background spiking input
XBKG_NAME = 'rx_bkg_mid_sm_ctx21_thal41'

# Constant input to set Vrest
USE_IBKG = 1
IBKG_JSON_NAME = 'ibkg_mech1_verest_-70_thal_spkthr'
#V_REST = -70

# Surrogate inputs
SURR_INP_ON = 1

REC_TRACES = 0
PLOT_TRACES = 0

PLOT_RATE_DYNAMICS = 0
PLOT_CTRL_TRACES = 0

NEED_RUN = 1
DIAG = 0


def gen_exp_name_sub(cfg):
    t_limits = (cfg.t0_calc / 1000, cfg.duration / 1000)
    exp_name_sub = f'exp_{EXP_LABEL}'
    if not SURR_INP_ON:
        exp_name_sub += '_nosurr'
    exp_name_sub += f'_nseed_{N_SEEDS}'
    exp_name_sub += f'_t_{t_limits[0]}_{t_limits[1]}'
    if CTRL_ON:
        par = CTRL_PARAMS
        exp_name_sub += (
            f'_kmu_{par["mu_gain"]}_ksigma_{par["sigma_gain"]}'
            f'_taur_{par["tau_rate_ctrl"]}_taum_{par["taum_ctrl"]}_tauu_{par["tauu_ctrl"]}'
            f'_tc0_{par["t0"]}_tlock_{par["tlock"]}'
            f'_ks_{par["ks_ctrl"]}_ku_{par["ku_ctrl"]}_epsm_{par["epsm_ctrl"]}'
        )
    exp_name_sub += f'_wmult_{cfg.wmult}_ee_{cfg.EEGain}'
    return exp_name_sub


def apply_exp_cfg(cfg):

    # Duration
    cfg.duration = SIM_DURATION

    # Left point (ms) of the calculation time window (r, cv, ...)
    cfg.t0_calc = T0_CALC

    cfg.need_run = NEED_RUN

    # Populations to use
    pops_active = POPS_USED

    # Random seeds
    cfg.seed_main = None   # batch param
    cfg.seeds['stim'] = None   # set in batch_params.py
    cfg.seeds['conn'] = None   # set in batch_params.py

    # Add labels to conns
    if EE_FADER_ON:
        cfg.includeParamsLabel = True

    # Required for reference broadcasting
    if EE_FADER_ON or CTRL_ON:
        cfg.cache_efficient = 0

    # Subnet parameters
    cfg.subnet_build_flag = SURR_INP_ON
    cfg.subnet_params = {
        'pops_active': pops_active,   
        'conns_frozen': CONNS_FROZEN,
        'fpath_frozen_rates': str(dirpath_self / 'target_state_1.csv'),   # surrogate input
        'global_seed': None   # set in batch_params.py
    }
    if EE_FADER_ON:
        cfg.subnet_params['conns_split'] = {
            f'{c[0]}, {c[1]}': 0.5 for c in CONNS_SPLIT
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
        cfg.includeParamsLabel=True

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
    cfg.bkg_spike_inputs = {}
    for n, pop in enumerate(POPS_USED):
        x = xbkg_info[pop]
        cfg.bkg_spike_inputs[pop] = {
            'exc': {'r': x['rxe'], 'w': x['wxe'], 'sec': x['xe_sec'],
                    'noise': 1, 'seed': None},   # set in batch_params.py
            'inh': {'r': x['rxi'], 'w': x['wxi'], 'sec': x['xi_sec'],
                    'noise': 1, 'seed': None},   # set in batch_params.py
        }
    
    # Static IClamp that sets the resting voltage
    if USE_IBKG:
        cfg.addIClamp = 1
        fname_ibkg = f'{IBKG_JSON_NAME}.json'
        with open(dirpath_self / fname_ibkg, 'r') as fid:
            ibkg = json.load(fid)
        cfg.IClamp = {pop: {'amp': ibkg[pop], 'dur': SIM_DURATION}
                      for pop in POPS_USED if pop in ibkg}

    # Read target rates
    df = pd.read_csv(dirpath_self / 'target_state_1.csv')
    target_rates = df.set_index('pop_name')['target_rate'].to_dict()
    cfg.target_rates = target_rates

    # OU inputs controlled by a rate feedback
    if CTRL_ON:
        # Add the inputs
        cfg.add_ou_current = 1
        cfg.ou_common = 0
        cfg.ou_noise_duration = cfg.duration
        cfg.ou_tau = 10
        cfg.ou_pop_inputs = {}
        for pop in POPS_USED:
            cfg.ou_pop_inputs[pop] = {'ou_mean': 0, 'ou_std': 0}
        
        # Controller params
        cfg.ou_ctrl_params = CTRL_PARAMS
        cfg.ou_ctrl_params['target_rates'] = target_rates
    
    # Cell mechanisms to modify
    with open(dirpath_self / 'mech_changes_1.json', 'r') as fid:
        cfg.mech_changes = json.load(fid)

    if 'plotRaster' in cfg.analysis:
        cfg.analysis['plotRaster']['include'] = POPS_USED
    if 'plotSpikeStats' in cfg.analysis:
        cfg.analysis['plotSpikeStats']['include'] = POPS_USED
    if 'plotTraces' in cfg.analysis:
        cfg.analysis['plotTraces']['include'] = POPS_USED
    
    #cfg.analysis['plotRaster'] = False
    cfg.analysis['plotSpikeStats'] = False

    cfg.plot_ctrl_traces = PLOT_CTRL_TRACES

    # Record voltage traces
    if REC_TRACES:
        ncells_rec = 5
        ncells_plot = 2
        cfg.recordCells = [(pop, list(range(ncells_rec))) for pop in POPS_USED]
        cfg.recordTraces = {'V_soma': {'sec': 'soma', 'loc': 0.5, 'var': 'v'}}
        cfg.recordStep =  0.1
        if PLOT_TRACES:
            cfg.analysis['plotTraces'] = {
                'include': [(pop, list(range(ncells_plot))) for pop in cfg.allpops],
                'timeRange': [1000, cfg.duration],
                'oneFigPer': 'cell', 'overlay': True,
                'saveFig': True, 'showFig': False, 'figSize': (18, 12)
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
        for ts_name, ts in target_sec.items():
            if (pop_pre in ts['pops_pre']) and (pop_post in ts['pops_post']):
                #print(f'Sec info: {cname} {ts_name}')
                conn['sec'] = ts['sec']
                break
        if conn['sec'] is None:
            raise ValueError(f'No target sec info found for conn {cname}')  


def modify_net_params_2(cfg, params):
    """Applied after subnet netParams creation. """
    if not EE_FADER_ON:
        return

    # Set distinct synMech labels for surrogate and recurrent inputs
    split_pairs = set(CONNS_SPLIT)
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
    if not EE_FADER_ON:
        return

    # Fader object
    fader = ConnFader(
        sim, T=sim.cfg.duration, dt=sim.cfg.dt    
    )

    # Find recurrent/surrogate conns for positive/inverse modulation
    conns_pos, conns_neg = [], []
    for pop_pre, pop_post in CONNS_SPLIT:
        conns_pos_ = get_2pop_conns(sim, pop_pre, pop_post)   # recurrent conns
        conns_neg_ = get_2pop_conns(sim, pop_pre + 'frz', pop_post)   # surrogate inputs
        conns_pos += conns_pos_
        conns_neg += conns_neg_
    
    fader.add_conn_group(
        group_name='ee',
        conns_pos=conns_pos,
        conns_neg=conns_neg,
        pts=FADER_PTS
    )

    fader.create_modulators()
    fader.connect_modulators()
    fader.setup_recording(rec_dt=1)

    sim.ee_fader = fader


def post_run(sim):
    """Called in the end of a job (after runnig and saving). """

    cfg = sim.cfg
    exp_name = cfg.simLabel

    # Metric calculation time interval in seconds
    t_limits = (cfg.t0_calc / 1000, cfg.duration / 1000)

    # Experiment sub-name
    exp_name_sub = gen_exp_name_sub(cfg)

    # Generate filename postfix with batch param values
    exp_id = exp_name.split('_')[-1]
    postfix = (f'{exp_id}_seed_{cfg.seed_main}')

    # Create subfolders to put the results
    dirpath_res = Path(cfg.saveFolder)
    dirpath_res_sub = dirpath_res / exp_name_sub
    os.makedirs(dirpath_res_sub, exist_ok=True)
    dirnames_sub = ['rasters', 'results', 'cfg', 'pkl', 'netpar', 
                    'traces', 'wmod_figs', 'rvec_figs',
                    'ctrl', 'ctrl_figs']
    for dirname in dirnames_sub:
        os.makedirs(dirpath_res_sub / dirname, exist_ok=True)

    # Move results to a subfolder
    data_info = [
        ('raster', 'png', 'rasters'),
        ('data', 'pkl', 'pkl'),
        ('cfg', 'json', 'cfg'),
        ('netParams', 'json', 'netpar'),
        ('ctrl', 'pkl', 'ctrl')
    ]
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

    # Move controller-related traces to a separate subfolder
    ctrl_trace_files = list(dirpath_res.glob(f'{exp_name}_ctrl_traces*.png'))
    for fpath_old in ctrl_trace_files:
        pop_name = fpath_old.stem.replace(f'{exp_name}_ctrl_traces_', '')
        fpath_new = dirpath_res_sub / 'ctrl_figs' / f'ctrl_{pop_name}_{postfix}{fpath_old.suffix}'
        fpath_old.rename(fpath_new)
    
    # Save rates, CVs, voltage stats, and timings to a json file
    if NEED_RUN:
        res = {}
        res['timing'] = sim.timingData
        res |= proc.calc_rates_and_cvs(sim, t_limits, nspikes_min=3)
        if REC_TRACES:
            res |= proc.calc_v_stats(sim, t_limits, med_win=0.05)
        fpath_res = dirpath_res_sub / 'results' / f'result_{postfix}.json'
        with open(fpath_res, 'w') as fid:
            json.dump(res, fid, indent=4)
    
    # Plot weight modulation signals
    if EE_FADER_ON and NEED_RUN:
        #gathered = sim.ee_fader.gather_recs()
        sim.ee_fader.plot_recs()
        fpath_wmod = (dirpath_res_sub / 'wmod_figs' / f'wmod_{postfix}.png')
        plt.savefig(fpath_wmod, dpi=300)

    # Plot and save rate dynamics
    if PLOT_RATE_DYNAMICS:
        pop_groups = {'PYR': PYR_POPS, 'PV': PV_POPS, 'SOM': SOM_POPS,
                      'VIP': VIP_POPS, 'NGF': NGF_POPS,
                      'THAL_E': THAL_E_POPS, 'THAL_I': THAL_I_POPS}
        colors = plt.rcParams['axes.prop_cycle'].by_key()['color']
        for pop_group_name, pops in pop_groups.items():
            pops = [p for p in pops if p in POPS_USED]
            if len(pops) == 0:
                continue

            # Compute rate dynamics
            r_data = proc.calc_rate_dynamics(
                sim, t_limits=(2, None), tau_smooth=0.2, pops_used=pops)

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
