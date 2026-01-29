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

from analysis.ou_tuning import sim_res_proc_utils as proc
from analysis.model_utils.split_conn import split_conn_by_sections


#EXP_LABEL = 'it2'
#POPS_USED = ['IT2']
EXP_LABEL = 'pyr'
POPS_USED = ['IT2', 'IT3', 'ITS4', 'ITP4', 'IT5A', 'CT5A',
             'IT5B', 'CT5B', 'PT5B', 'IT6', 'CT6']

#RXE, RXI = 15000, 2000
RXE, RXI = 1, 1

WXE, WXI = 1.25, 5

NOISE = 1
T0_XE, T0_XI = 0, 0
#T0_XE, T0_XI = None, None

USE_IBKG = 1
V_REST = -70

REC_TRACES = 0
PLOT_TRACES = 0

# Use subConn
ADD_SUBCON = 0

# Split conns from sec-list 1-sec form (length-based)
SPLIT_CONNS = 0

# Choose a section from a list: 0=first, 1=random
RAND_SEC = 1

# Uniformly distribute locs within a section
UNI_LOCS = 0

# Number of different loc values (used when UNI_LOCS=0)
N_LOCS = 5


def apply_exp_cfg(cfg):

    # Duration
    cfg.duration = 1 * 1e3

    # Left point (ms) of the calculation time window (r, cv, ...)
    cfg.t0_calc = 200

    # Populations to use
    pops_active = POPS_USED

    # Subnet parameters
    cfg.subnet_build_flag = 1
    cfg.subnet_params = {
        'pops_active': pops_active,   
        'conns_frozen': 'all',   # all inputs are surrogate, no recurrent connections
        'fpath_frozen_rates': str(dirpath_self / 'target_state_1.csv'),   # surrogate input
    }

    # Weight multipliers
    cfg.wmult = 0.25
    cfg.EEGain = 0.5
    #cfg.EEGain = 1

    # Turn subConn on / off
    cfg.addSubConn = ADD_SUBCON

    # Choose a section from a list: 0=first, 1=random
    cfg.connRandomSecFromList = RAND_SEC

    # Background spiking input
    cfg.add_bkg_spike_input = 1
    cfg.bkg_spike_inputs = {}
    for n, pop in enumerate(POPS_USED):
        cfg.bkg_spike_inputs[pop] = {
            'exc': {'r': RXE, 'w': WXE, 'sec': 'apic',
                    'noise': NOISE, #'start': T0_XE,
                    'seed': cfg.seeds['stim'] + 10000 + n},
            'inh': {'r': RXI, 'w': WXI, 'sec': 'soma',
                    'noise': NOISE, #'start': T0_XI,
                    'seed': cfg.seeds['stim'] + 20000 + n},
        }
    
    # Static IClamp that sets the resting voltage
    if USE_IBKG:
        cfg.addIClamp = 1
        fname_ibkg = f'ibkg_mech1_vrest_{V_REST}.json'
        with open(dirpath_self / fname_ibkg, 'r') as fid:
            ibkg = json.load(fid)
        cfg.IClamp = {pop: {'amp': ibkg[pop]} for pop in POPS_USED}

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
        ncells_plot = 3
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

    # Possible loc values
    if UNI_LOCS:
        locs = 'uniform(0, 1)'
    else:
        if N_LOCS == 1:
            locs = 0.5
        else:
            l = 1 / N_LOCS
            locs = f'{l / 2} + {l} * (int({N_LOCS} * uniform(0, 1)))'
    
    # Modify connections
    conn_names = list(params.connParams.keys())
    for cname in conn_names:
        params.connParams[cname]['loc'] = locs
        if SPLIT_CONNS:
            split_conn_by_sections(params, cname)


def post_run(sim):
    """Called in the end of a job (after runnig and saving). """

    cfg = sim.cfg
    exp_name = cfg.simLabel

    # Metric calculation time interval in seconds
    t_limits = (cfg.t0_calc / 1000, cfg.duration / 1000)

    exp_name_sub = f'exp_{EXP_LABEL}'
    exp_name_sub += f'_rx_{RXE}_{RXI}_wx_{WXE}_{WXI}'
    exp_name_sub += f'_noise_{NOISE}'
    #exp_name_sub += f'_tx0_{T0_XE}_{T0_XI}'
    exp_name_sub += f'_t_{t_limits[0]}_{t_limits[1]}'
    if USE_IBKG:
        exp_name_sub += f'_vrest_{V_REST}'
    exp_name_sub += f'_wmult_{cfg.wmult}_ee_{cfg.EEGain}'
    exp_name_sub += f'_subcon_{cfg.addSubConn}'
    exp_name_sub += f'_randsec_{RAND_SEC}'
    exp_name_sub += f'_splitcon_{SPLIT_CONNS}'
    if UNI_LOCS:
        exp_name_sub += '_loc_uni'
    else:
        exp_name_sub += f'_loc_{N_LOCS}'
    exp_name_sub += f'_vrec_{REC_TRACES}'

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
    res = proc.calc_rates_and_cvs(sim, t_limits, nspikes_min=3)
    if REC_TRACES:
        res |= proc.calc_v_stats(sim, t_limits, med_win=0.05)
    res['timing'] = sim.timingData
    fpath_res = dirpath_res_sub / f'{exp_name}_result.json'
    with open(fpath_res, 'w') as fid:
        json.dump(res, fid, indent=4)
