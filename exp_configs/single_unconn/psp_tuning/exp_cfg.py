import json
import os
from pathlib import Path
import sys

dirpath_repo_root = Path(__file__).resolve().parents[3]
dirpath_self = Path(__file__).resolve().parent
sys.path.append(str(dirpath_repo_root))
#sys.path.append(str(dirpath_self))

import matplotlib.pyplot as plt
import numpy as np

from analysis.ou_tuning import netpyne_res_parse_utils as parse_utils
from analysis.ou_tuning import sim_res_proc_utils as proc

from neuron import h


""" EXP_NAME = 'all'
POPS_USED = [
    'IT2', 'IT3', 'ITP4', 'ITS4', 'IT5A', 'CT5A',
    'IT5B', 'CT5B', 'PT5B', 'IT6', 'CT6',
    'PV2', 'PV3', 'PV4', 'PV5A', 'PV5B', 'PV6',
    'SOM2', 'SOM3', 'SOM4', 'SOM5A', 'SOM5B', 'SOM6',
    'VIP2', 'VIP3', 'VIP4', 'VIP5A', 'VIP5B', 'VIP6',
    'NGF1', 'NGF2', 'NGF3', 'NGF4', 'NGF5A', 'NGF5B', 'NGF6',
    'TC', 'HTC', 'TCM', 'TI', 'TIM', 'IRE', 'IREM'
] """

EXP_NAME = 'tc_tcm_htc'
POPS_USED = ['TC', 'HTC', 'TCM']

# Duration
TSIM = 20000

# Time range in which spiking input is on
TX_INTERVAL = (5000, TSIM)

# Inter-spike interval (same for XE and XI)
XISI = 2000

# Min/max weight
WXE_RANGE = (0, 1)
WXI_RANGE = (0, 6)

# Target sections of input spikes
SEC_XE = 'soma'
SEC_XI = 'soma'

# Time of the 1st spike after TX_INTERVAL[0]
T0_XE = 0
T0_XI = XISI / 2

# Regular spikes
NOISE = 0

# Tonic currents that set the resting voltages
USE_IBKG = 1
IBKG_LABEL = 'ibkg_mech1_vrest'   # name of a json file

ONE_CELL = 1


def apply_exp_cfg(cfg):

    # Duration
    cfg.duration = TSIM

    # Left point (ms) of the calculation time window (r, cv, ...)
    #cfg.t0_calc = cfg.duration - 1000
    cfg.t0_calc = 1000

    # Populations to use
    cfg.pops_active = POPS_USED

    # One cell per population
    if ONE_CELL:
        cfg.singleCellPops = 1

    # Unconnected
    cfg.addConn = 0

    cfg.psp_inp_params = {
        'wxe_range': WXE_RANGE,
        'wxi_range': WXI_RANGE,
        'xisi': XISI,
        't_interval': TX_INTERVAL,
        't0_xe': T0_XE,
        't0_xi': T0_XI,
        'sec_xe': SEC_XE,
        'sec_xi': SEC_XI,
    }

    # Background spiking input
    cfg.add_bkg_spike_input = 1
    cfg.bkg_spike_inputs = {}
    for n, pop in enumerate(POPS_USED):
        cfg.bkg_spike_inputs[pop] = {
            'exc': {'r': 1000 / XISI,
                    'w': 1,   # will be replaced by time-dependent signal
                    'sec': SEC_XE,
                    'noise': NOISE,
                    'start': TX_INTERVAL[0] + T0_XE,
                    'seed': cfg.seeds['stim'] + 10000 + n},
            'inh': {'r': 1000 / XISI,
                    'w': 1,   # will be replaced by time-dependent signal
                    'sec': SEC_XI,   
                    'noise': NOISE,
                    'start': TX_INTERVAL[0] + T0_XI,
                    'seed': cfg.seeds['stim'] + 20000 + n},
        }
    
    # Static IClamp that sets the resting voltage
    if USE_IBKG:
        cfg.addIClamp = 1
        fname_ibkg = f'{IBKG_LABEL}.json'
        with open(dirpath_self / fname_ibkg, 'r') as fid:
            ibkg = json.load(fid)
        cfg.IClamp = {pop: {'amp': ibkg[pop]}
                      for pop in cfg.pops_active if pop in ibkg}

    # Cell mechanisms to modify
    with open(dirpath_self / 'mech_changes_1.json', 'r') as fid:
        cfg.mech_changes = json.load(fid)
    
    if 'plotRaster' in cfg.analysis:
        cfg.analysis['plotRaster']['include'] = POPS_USED
    if 'plotSpikeStats' in cfg.analysis:
        cfg.analysis['plotSpikeStats']['include'] = POPS_USED
    if 'plotTraces' in cfg.analysis:
        cfg.analysis['plotTraces']['include'] = POPS_USED
    
    cfg.analysis['plotRaster'] = False
    cfg.analysis['plotSpikeStats'] = False

    # Record voltage traces
    ncells_rec = 300
    ncells_plot = 5
    if ONE_CELL:
        ncells_rec = 1
        ncells_plot = 1
    cfg.recordCells = [(pop, list(range(ncells_rec))) for pop in POPS_USED]
    cfg.recordTraces = {'V_soma': {'sec': 'soma', 'loc': 0.5, 'var': 'v'}}
    cfg.recordStep = 1
    cfg.analysis['plotTraces'] = {
        'include': [(pop, list(range(ncells_plot))) for pop in cfg.allpops],
        'timeRange': [500, cfg.duration],
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


def modify_network(sim):

    if not hasattr(sim, '_weight_play_refs'):
        sim._weight_play_refs = []

    tvec = h.Vector(TX_INTERVAL)

    for cell in sim.net.cells:

        for conn in getattr(cell, "conns", []):
            if conn.get('preGid') != 'NetStim':
                continue
            nc = conn.get('hObj')
            if nc is None:
                continue

            label = conn.get('preLabel')

            # Weights in stimtargetParams were set to 1,
            # so conn['weight'] is the scaling factor we need
            if 'exc' in label:
                w_range = np.array(WXE_RANGE) * conn['weight']
                wvec = h.Vector(w_range)
            elif 'inh' in label:
                w_range = np.array(WXI_RANGE) * conn['weight']
                wvec = h.Vector(w_range)
            else:
                continue
            wvec.play(nc._ref_weight[0], tvec, 1)   # 1 = interpolate

            sim._weight_play_refs.append((tvec, wvec, nc))


def post_run(sim):
    """Called in the end of a job (after runnig and saving). """

    cfg = sim.cfg
    exp_name = cfg.simLabel

    # Metric calculation time interval in seconds
    t_limits = (cfg.t0_calc / 1000, cfg.duration / 1000)

    exp_name_sub = f'exp_{EXP_NAME}'
    exp_name_sub += f'_wxe_{WXE_RANGE[0]}_{WXE_RANGE[1]}'
    exp_name_sub += f'_wxi_{WXI_RANGE[0]}_{WXI_RANGE[1]}'
    exp_name_sub += f'_xisi'
    exp_name_sub += f'_t_{t_limits[0]}_{t_limits[1]}'
    exp_name_sub += f'_xsec_{SEC_XE}_{SEC_XI}'

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
    
    # Save rates, CVs, and voltage stats to a json file
    res = proc.calc_rates_and_cvs(sim, t_limits, nspikes_min=3)
    res |= proc.calc_v_stats(sim, t_limits, med_win=0.05)
    res['timing'] = sim.timingData
    fpath_res = dirpath_res_sub / f'{exp_name}_result.json'
    with open(fpath_res, 'w') as fid:
        json.dump(res, fid, indent=4)
    
    # Extract and save voltages xarray
    dirpath_v = dirpath_res_sub / 'voltages'
    os.makedirs(dirpath_v, exist_ok=True)
    sim_res = parse_utils.prepare_sim_result(sim)
    V_data = parse_utils.get_voltages_xr(sim_res)
    for pop, V_xr in V_data.items():
        if V_xr is None:
            continue
        V_xr.to_netcdf(dirpath_v / f'{pop}.nc')
