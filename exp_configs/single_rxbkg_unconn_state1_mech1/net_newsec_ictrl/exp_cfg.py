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
import diagnostics as diag


PV_POPS = ['PV2', 'PV3', 'PV4', 'PV5A', 'PV5B', 'PV6']
SOM_POPS = ['SOM2', 'SOM3', 'SOM4', 'SOM5A', 'SOM5B', 'SOM6']
VIP_POPS = ['VIP2', 'VIP3', 'VIP4', 'VIP5A', 'VIP5B', 'VIP6']
NGF_POPS = ['NGF1', 'NGF2', 'NGF3', 'NGF4', 'NGF5A', 'NGF5B', 'NGF6']

""" EXP_LABEL = 'it246_ictx_unconn'
POPS_USED = (
    ['IT2', 'ITP4', 'ITS4', 'IT6'] + 
    PV_POPS + SOM_POPS + VIP_POPS + NGF_POPS
) """

EXP_LABEL = 'pv_unconn'
POPS_USED = PV_POPS

CONNS_FROZEN = 'all'

# Target firing rates (for surrogate inp. and rate ctrl)
TARGET_STATE_LABEL = 'target_state_1'

# Rate-controlling feedback via tonic current
I_CTRL = 1

CTRL_PARAMS = {
    'mu_gain': 2e-1,
    'sigma_gain': 0.0,
    'tau_ctrl': 1000,
    'taus_ctrl': 10000,
    'target_rates': None,   # set later
    'k_ctrl': 1e-5,
    'kp_ctrl': 0e-2,
    'z0': 0,
    't0': 20000,
    'tlock': 90000
}

# Background spiking input
XBKG_NAME = 'rx_bkg_mid_sm_21'

# Constant input to set Vrest
USE_IBKG = 1
V_REST = -70

# Surrogate inputs
SURR_INP_ON = 1

REC_TRACES = 1
PLOT_TRACES = 0

DIAG = 0


def apply_exp_cfg(cfg):

    # Duration
    cfg.duration = 150 * 1e3

    # Left point (ms) of the calculation time window (r, cv, ...)
    cfg.t0_calc = cfg.duration - 2000

    # Required for rate controller
    cfg.cache_efficient = 0

    # Populations to use
    pops_active = POPS_USED

    # Subnet parameters (surrogate inputs)
    cfg.subnet_build_flag = SURR_INP_ON
    cfg.subnet_params = {
        'pops_active': pops_active,   
        'conns_frozen': CONNS_FROZEN,
        'fpath_frozen_rates': (
            str(dirpath_self / f'{TARGET_STATE_LABEL}.csv')
        )
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
                    'noise': 1, 'seed': cfg.seeds['stim'] + 10000 + n},
            'inh': {'r': x['rxi'], 'w': x['wxi'], 'sec': x['xi_sec'],
                    'noise': 1, 'seed': cfg.seeds['stim'] + 20000 + n}
        }
    
    # Static IClamp that sets the resting voltage
    if USE_IBKG:
        cfg.addIClamp = 1
        fname_ibkg = f'ibkg_mech1_vrest_{V_REST}.json'
        with open(dirpath_self / fname_ibkg, 'r') as fid:
            ibkg = json.load(fid)
        cfg.IClamp = {pop: {'amp': ibkg[pop]}
                      for pop in POPS_USED if pop in ibkg}
    
    # Read target rates
    df = pd.read_csv(dirpath_self / f'{TARGET_STATE_LABEL}.csv')
    target_rates = df.set_index('pop_name')['target_rate'].to_dict()
    cfg.target_rates = target_rates

    # OU inputs controlled by a rate feedback
    if I_CTRL:
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
    

def post_run(sim):
    """Called in the end of a job (after runnig and saving). """

    cfg = sim.cfg
    exp_name = cfg.simLabel

    # Metric calculation time interval in seconds
    t_limits = (cfg.t0_calc / 1000, cfg.duration / 1000)

    exp_name_sub = f'exp_{EXP_LABEL}'
    if not SURR_INP_ON:
        exp_name_sub += '_nosurr'
    exp_name_sub += f'_t_{t_limits[0]}_{t_limits[1]}'
    exp_name_sub += f'_wmult_{cfg.wmult}_ee_{cfg.EEGain}'
    if I_CTRL:
        par = cfg.ou_ctrl_params
        exp_name_sub += (
            f'_kmu_{par["mu_gain"]}_ksigma_{par["sigma_gain"]}'
            f'_tau_{par["tau_ctrl"]}_taus_{par["taus_ctrl"]}'
            f'_tc0_{par["t0"]}_tlock_{par["tlock"]}'
            f'_kci_{par["k_ctrl"]}_kcp_{par["kp_ctrl"]}'
        )

    # Create a subfolder to put the results
    dirpath_res = Path(cfg.saveFolder)
    dirpath_res_sub = dirpath_res / exp_name_sub
    os.makedirs(dirpath_res_sub, exist_ok=True)

    # Move results to the subfolder
    res_names = ['cfg.json', 'netParams.json', 'raster.png', 'ctrl.pkl']
    for res_name in res_names:
        fname = f'{exp_name}_{res_name}'
        if (dirpath_res / fname).exists():
            (dirpath_res / fname).rename(dirpath_res_sub / fname)
        
    # Move traces to the subfodler
    os.makedirs(dirpath_res_sub / 'traces', exist_ok=True)
    for fpath in dirpath_res.glob(f'{exp_name}_*traces*.png'):
        fpath.rename(dirpath_res_sub / 'traces' / fpath.name)
    
    # Save rates, CVs, voltage stats, and timings to a json file
    res = {}
    res['timing'] = sim.timingData
    res |= proc.calc_rates_and_cvs(sim, t_limits, nspikes_min=3)
    if REC_TRACES:
        res |= proc.calc_v_stats(sim, t_limits, med_win=0.05)
    fpath_res = dirpath_res_sub / f'{exp_name}_result.json'
    with open(fpath_res, 'w') as fid:
        json.dump(res, fid, indent=4)
    
    # Plot and save rate dynamics
    os.makedirs(dirpath_res_sub / 'rvec_figs', exist_ok=True)
    r_data = proc.calc_rate_dynamics(
        sim, t_limits=(1, None), tau_smooth=1.5, pops_used=POPS_USED)
    colors = plt.rcParams['axes.prop_cycle'].by_key()['color']
    plt.figure()
    for n, pop in enumerate(POPS_USED):
        tt, rr = r_data[pop]
        r0 = cfg.target_rates[pop]
        plt.plot(tt, rr, label=pop, color=colors[n])
        plt.plot([tt[0], tt[-1]], [r0, r0], '--', color=colors[n])
    plt.xlabel('Time')
    plt.ylabel('Firing rate')
    plt.legend(bbox_to_anchor=(1, 1))
    #plt.yscale('log')
    #plt.ylim(0.05, None)
    plt.savefig(dirpath_res_sub / 'rvec_figs' / f'{exp_name}.png',
                bbox_inches='tight', dpi=300)


def final(sim):
    if not DIAG:
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
