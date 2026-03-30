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


PYR_POPS = ['IT2', 'IT3', 'ITP4', 'ITS4', 'IT5A', 'IT5B', 'IT6',
            'CT5A', 'CT5B', 'CT6', 'PT5B']
PV_POPS = ['PV2', 'PV3', 'PV4', 'PV5A', 'PV5B', 'PV6']
SOM_POPS = ['SOM2', 'SOM3', 'SOM4', 'SOM5A', 'SOM5B', 'SOM6']
VIP_POPS = ['VIP2', 'VIP3', 'VIP4', 'VIP5A', 'VIP5B', 'VIP6']
NGF_POPS = ['NGF1', 'NGF2', 'NGF3', 'NGF4', 'NGF5A', 'NGF5B', 'NGF6']

L2_POPS = ['IT2', 'PV2', 'SOM2', 'VIP2', 'NGF2']
L4_POPS = ['ITP4', 'ITS4', 'PV4', 'SOM4', 'VIP4', 'NGF4']

CONNS_EE = [(p1, p2) for p1 in PYR_POPS for p2 in PYR_POPS]

#EXP_LABEL = 'ctx_unconn_sm_21'
EXP_LABEL = 'ctx_ee_0'
#EXP_LABEL = 'L4_unconn'
#EXP_LABEL = 'L4_ee_0'
#EXP_LABEL = 'L2_ee_0'

POPS_USED = PYR_POPS + PV_POPS + SOM_POPS + VIP_POPS + NGF_POPS
#POPS_USED = L4_POPS
#POPS_USED = L2_POPS

#CONNS_FROZEN = 'all'
CONNS_FROZEN = CONNS_EE
#CONNS_FROZEN = []

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

SEED = 1115


def apply_exp_cfg(cfg):

    # Duration
    cfg.duration = 3 * 1e3

    # Left point (ms) of the calculation time window (r, cv, ...)
    cfg.t0_calc = 2000

    # Populations to use
    pops_active = POPS_USED

    # Random seeds
    cfg.seeds['stim'] = SEED
    cfg.seeds['conn'] = SEED * 2

    # Subnet parameters
    cfg.subnet_build_flag = SURR_INP_ON
    cfg.subnet_params = {
        'pops_active': pops_active,   
        'conns_frozen': CONNS_FROZEN,
        'fpath_frozen_rates': str(dirpath_self / 'target_state_1.csv'),   # surrogate input
        'global_seed': SEED * 3
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
    exp_name_sub += f'_seed_{SEED}'

    # Create a subfolder to put the results
    dirpath_res = Path(cfg.saveFolder)
    dirpath_res_sub = dirpath_res / exp_name_sub
    os.makedirs(dirpath_res_sub, exist_ok=True)

    # Move results to the subfolder
    res_names = ['cfg.json', 'netParams.json', 'raster.png']
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
