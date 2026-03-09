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

from batch_params import N_RXE, N_RXI


EXP_LABEL = 'pv'
POPS_USED = ['PV2', 'PV3', 'PV4', 'PV5A', 'PV5B', 'PV6']
#EXP_LABEL = 'som'
#POPS_USED = ['SOM2', 'SOM3', 'SOM4', 'SOM5A', 'SOM5B', 'SOM6']
#EXP_LABEL = 'it2'
#POPS_USED = ['IT2']
#EXP_LABEL = 'vip'
#POPS_USED = ['VIP2', 'VIP3', 'VIP4', 'VIP5A', 'VIP5B', 'VIP6']
#EXP_LABEL = 'ngf'
#POPS_USED = ['NGF1', 'NGF2', 'NGF3', 'NGF4', 'NGF5A', 'NGF5B', 'NGF6']
#EXP_LABEL = 'pyr'
#POPS_USED = ['IT2', 'IT3', 'ITS4', 'ITP4', 'IT5A', 'CT5A',
#             'IT5B', 'CT5B', 'PT5B', 'IT6', 'CT6']

# Weights of background exc/inh inputs (custom)
WXE, WXI = 1.25, 5

NOISE = 1
T0_XE, T0_XI = 0, 0

# Compensate effects of dKDR change on Vrest by adding const. current
USE_IBKG = 1
V_REST = -70

REC_TRACES = 1
PLOT_TRACES = 0


def apply_exp_cfg(cfg):

    # Duration
    cfg.duration = 5 * 1e3

    # Left point (ms) of the calculation time window (r, cv, ...)
    cfg.t0_calc = 3000

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

    # Turn subConn on / off
    cfg.addSubConn = 1

    # Background spiking input
    cfg.add_bkg_spike_input = 1
    cfg.bkg_spike_inputs = {}
    for n, pop in enumerate(POPS_USED):
        cfg.bkg_spike_inputs[pop] = {
            'exc': {'r': 0, 'w': WXE, 'sec': 'apic',   # r will be set in batch
                    'noise': NOISE, 'start': T0_XE,
                    'seed': cfg.seeds['stim'] + 10000 + n},
            'inh': {'r': 0, 'w': WXI, 'sec': 'soma',   # r will be set in batch
                    'noise': NOISE, 'start': T0_XI,
                    'seed': cfg.seeds['stim'] + 20000 + n},
        }

    # Cell mechanisms to modify
    with open(dirpath_self / 'mech_changes_1.json', 'r') as fid:
        cfg.mech_changes = json.load(fid)
    
    # Static IClamp that sets Vrest (compensates for the cell mech changes)
    if USE_IBKG:
        cfg.addIClamp = 1
        fname_ibkg = f'ibkg_mech1_vrest_{V_REST}.json'
        with open(dirpath_self / fname_ibkg, 'r') as fid:
            ibkg = json.load(fid)
        cfg.IClamp = {pop: {'amp': ibkg[pop]} for pop in POPS_USED}

    if 'plotRaster' in cfg.analysis:
        cfg.analysis['plotRaster']['include'] = pops_active
    if 'plotSpikeStats' in cfg.analysis:
        cfg.analysis['plotSpikeStats']['include'] = pops_active
    if 'plotTraces' in cfg.analysis:
        cfg.analysis['plotTraces']['include'] = pops_active
    
    # Time range for rate and CV calculation
    #cfg.analysis['plotSpikeStats']['timeRange'] = (cfg.t0_calc, cfg.duration)

    cfg.analysis['plotRaster'] = False
    cfg.analysis['plotSpikeStats'] = False

    # Record voltage traces
    if REC_TRACES:
        ncells_rec = 5
        ncells_plot = 3
        cfg.recordCells = [(pop, list(range(ncells_rec))) for pop in pops_active]
        cfg.recordTraces = {'V_soma': {'sec': 'soma', 'loc': 0.5, 'var': 'v'}}
        cfg.recordStep =  1
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


def post_run(sim):
    """Called in the end of a job (after runnig and saving). """

    cfg = sim.cfg
    exp_name = cfg.simLabel

    # Metric calculation time interval in seconds
    t_limits = (cfg.t0_calc / 1000, cfg.duration / 1000)

    exp_name_sub = f'exp_{EXP_LABEL}'
    exp_name_sub += f'_wx_{WXE}_{WXI}'
    exp_name_sub += f'_sz_{N_RXE}_{N_RXI}'
    exp_name_sub += f'_t_{t_limits[0]}_{t_limits[1]}'
    if USE_IBKG:
        exp_name_sub += f'_vrest_{V_REST}'
    exp_name_sub += f'_wmult_{cfg.wmult}_ee_{cfg.EEGain}'
    exp_name_sub += f'_subcon_{cfg.addSubConn}'

    # Generate filename postfix with batch param values
    inp = cfg.bkg_spike_inputs[POPS_USED[0]]
    rxe, rxi = inp['exc']['r'], inp['inh']['r']
    exp_id = exp_name.split('_')[-1]
    postfix = (f'{exp_id}_rxe_{int(rxe)}_rxi_{int(rxi)}')

    # Create subfolders to put the results
    dirpath_res = Path(cfg.saveFolder)
    dirpath_res_sub = dirpath_res / exp_name_sub
    os.makedirs(dirpath_res_sub, exist_ok=True)
    dirnames_sub = ['rasters', 'results', 'cfg', 'pkl', 'netpar']
    for dirname in dirnames_sub:
        os.makedirs(dirpath_res_sub / dirname, exist_ok=True)
    
    # Move results to a subfolder
    data_info = [
        ('raster', 'png', 'rasters'),
        ('data', 'pkl', 'pkl'),
        ('cfg', 'json', 'cfg'),
        ('netParams', 'json', 'netpar')
    ]
    for di in data_info:
        data_name, ext, dirname_sub = di
        fpath_old = dirpath_res / f'{exp_name}_{data_name}.{ext}'
        fpath_new = dirpath_res_sub / dirname_sub / f'{data_name}_{postfix}.{ext}'
        if fpath_old.exists():
            fpath_old.rename(fpath_new)
        else:
            print('NOT FOUND: ', fpath_old)
    
    # Save rates, CVs, and voltage stats to a json file
    res = proc.calc_rates_and_cvs(sim, t_limits, nspikes_min=3)
    res |= proc.calc_v_stats(sim, t_limits, med_win=0.05)
    res['timing'] = sim.timingData
    fpath_res = dirpath_res_sub / 'results' / f'result_{postfix}.json'
    with open(fpath_res, 'w') as fid:
        json.dump(res, fid, indent=4)
