import json
import os
from pathlib import Path
import sys

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xarray as xr

dirpath_self = Path(__file__).resolve().parent
dirpath_repo_root = Path(__file__).resolve().parents[3]
sys.path.append(str(dirpath_self))
sys.path.append(str(dirpath_repo_root))

import analysis.ou_tuning.netpyne_res_parse_utils as parse_utils
#import analysis.ou_tuning.data_proc_utils as proc_utils
import fi_utils


EXP_NAME = 'tim'
POPS_USED = ['TIM']

CELL_TYPES = {'IRE': 'RE', 'PV3': 'PV', 'SOM3': 'SOM',
              'VIP3': 'VIP', 'NGF3': 'NGF'}

# Duration and rate calculation window
SIM_DURATION = 15 * 1e3
T0_CALC = 10 * 1e3   # irrelevant

# Length of time window for metrics calculation (in seconds)
TCALC_WIN = 3

# Mean input increasing across the cells ("I" of the f-I curve)
#I_RANGE = [-0.002, 0.01]
I_RANGE = [-0.01, 0.03]
I_SEC = 'soma'

# Input std.
#I_STD = 0.002
I_STD = 0

# Strong ramp-up pulse for switching between the steady-states
STIM_T0 = 6000
STIM_DUR = 1000
STIM_AMP = -0.5

# Weak NetStim to randomly jitter the cells between steady-states
RX = 0
WX = 1
BKG_SEC = 'soma'

# Surrogate inputs
SURR_INP_ON = 1

PLOT_TRACES = 1

# Load mech multipliers from json
MECH_FROM_JSON = 1

# Mechanism changes (for MECH_FROM_JSON=0)
GKDR_MULT = 1
GKAP_MULT = 1
GLEAK_MULT = 1
GCAT_MULT = 1
GCAL_MULT = 1
GCAN_MULT = 1


def gen_exp_name_sub(cfg):

    t_limits = (cfg.t0_calc / 1000, cfg.duration / 1000)

    exp_name_sub = f'exp_{EXP_NAME}'
    if not SURR_INP_ON:
        exp_name_sub += '_nosurr'
    exp_name_sub += f'_isec_{I_SEC}'
    #exp_name_sub += f'_rx_{RX}_wx_{WX}'   # will be in filename postfix
    exp_name_sub += f'_t_{t_limits[0]}_{t_limits[1]}'
    exp_name_sub += f'_irange_{cfg.OUamp[0]}_{cfg.OUamp[1]}'
    exp_name_sub += f'_istd_{I_STD}'
    exp_name_sub += f'_xsec_{BKG_SEC}'
    exp_name_sub += f'_tstim_{STIM_T0}_{STIM_DUR}'
    # Puse amplitude will be in filename postfix

    if not MECH_FROM_JSON:
        mechs = {'gkdr': GKDR_MULT, 'gkap': GKAP_MULT, 'gl': GLEAK_MULT}
                 #'gih': GIH_MULT, 'gnax': GNAX_MULT, 'gkbk': GKBK_MULT}
        if (GCAT_MULT == 0) and (GCAL_MULT == 0) and (GCAN_MULT == 0):
            mechs |= {'gca': 0}
        else:
            mechs |= {'gcat': GCAT_MULT, 'gcal': GCAL_MULT,
                      'gcan': GCAN_MULT}                 
        for name, mult in mechs.items():
            if mult != 1:
                exp_name_sub += f'_{name}_{mult}'

    return exp_name_sub


def get_mech_changes():
    if MECH_FROM_JSON:
        with open(dirpath_self / 'mech_changes_1.json', 'r') as fid:
            mech_changes = json.load(fid)
    else:
        mech_change_info = {
            'gkdr': ('kdr', 'gbar', GKDR_MULT),
            'gkap': ('kap', 'gbar', GKAP_MULT),
            'gleak': ('pas', 'g', GLEAK_MULT),
            'gcat': ('cat', 'gcatbar', GCAT_MULT),
            'gcal': ('cal', 'gcalbar', GCAL_MULT),
            'gcan': ('can', 'gcanbar', GCAN_MULT),
            #'gkbk': ('kBK', 'gpeak', GKBK_MULT),
            #'gih': ('ih', 'gbar', GIH_MULT),
            #'gnax': ('nax', 'gbar', GNAX_MULT)
        }
        mech_changes = {}
        for pop in POPS_USED:
            ct = CELL_TYPES[pop] if pop in CELL_TYPES else pop
            for name, ch in mech_change_info.items():
                mech_changes[f'{name}_{pop}'] = {
                    'pop': f'{ct}_reduced', 'sec': 'all',
                    'mech': ch[0], 'par': ch[1], 'mult': ch[2]
                }
    return mech_changes


def apply_exp_cfg(cfg):
    """Applied after default cfg creation and before netParams creation. """

    # Duration
    cfg.duration = SIM_DURATION

    # Left point (ms) of the calculation time window (r, cv, ...)
    cfg.t0_calc = T0_CALC

    # Subnet parameters
    cfg.subnet_build_flag = SURR_INP_ON
    cfg.subnet_params = {
        'pops_active': POPS_USED,   
        'conns_frozen': 'all',   # all inputs are surrogate, no recurrent connections
        'fpath_frozen_rates': str(dirpath_self / 'target_state_1.csv'),   # surrogate input
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
    
    # Tonic current input (I)
    cfg.add_ou_current = 1
    cfg.ou_common = 1    # all pops receive the same OU input
    cfg.ou_noise_duration = cfg.duration
    cfg.ou_tau = 10
    cfg.OUamp = list(I_RANGE)
    cfg.OUstd = I_STD
    cfg.ou_sec = I_SEC

    # Strong ramp-up pulse for switching between the steady-states
    cfg.ou_ramp_dur = STIM_DUR   # duration
    cfg.ou_ramp_t0 = STIM_T0    # start time
    cfg.ou_ramp_offset = STIM_AMP   # amplitude (current to soma)
    cfg.ou_ramp_mult = 0
    cfg.ou_ramp_type = 'up'

    # Additional NetStim input to promote inter-branch jitter
    cfg.add_bkg_spike_input = 1 if (RX != 0) else 0
    cfg.bkg_r = RX
    cfg.bkg_w = WX
    cfg.bkg_spike_inputs = {
        pop: {'exc': {'r': cfg.bkg_r, 'w': cfg.bkg_w, 'sec': BKG_SEC}}
        for pop in POPS_USED
    }

    # Read target rates
    df = pd.read_csv(dirpath_self / 'target_state_1.csv')
    target_rates = df.set_index('pop_name')['target_rate'].to_dict()
    cfg.target_rates = target_rates

    # Cell mechanisms to modify
    cfg.mech_changes = get_mech_changes()

    if 'plotRaster' in cfg.analysis:
        cfg.analysis['plotRaster']['include'] = POPS_USED
    if 'plotSpikeStats' in cfg.analysis:
        cfg.analysis['plotSpikeStats']['include'] = POPS_USED
    if 'plotTraces' in cfg.analysis:
        cfg.analysis['plotTraces']['include'] = POPS_USED
    
    #cfg.analysis['plotRaster'] = False
    cfg.analysis['plotSpikeStats'] = False
    
    # Load a table of pop sizes
    fpath_csv = dirpath_self / 'pops_sz.csv'
    pops_sz_df = pd.read_csv(fpath_csv)
    pops_sz = pops_sz_df.set_index('pop')['ncells'].to_dict()

    # Choose the cells to record and plot voltages for each population
    ncells_rec = 500
    ncells_plot = 10
    cfg.pop_cells_rec = {}
    cfg.pop_cells_plot = {}
    for pop in cfg.allpops:
        N = np.minimum(pops_sz[pop], ncells_rec)
        cfg.pop_cells_rec[pop] = np.linspace(0, pops_sz[pop] - 1, N, dtype=int)
        N_plot = np.minimum(N, ncells_plot)
        idx = np.linspace(0, N - 1, N_plot, dtype=int).astype(np.intp)
        cfg.pop_cells_plot[pop] = cfg.pop_cells_rec[pop][idx]

    # Record voltage traces
    cfg.recordCells = [(pop, list(cfg.pop_cells_rec[pop]))
                       for pop in cfg.allpops]
    cfg.recordTraces = {
        'V_soma': {'sec': 'soma', 'loc': 0.5, 'var': 'v'}
    }
    cfg.recordStep = 0.1
    if PLOT_TRACES:
        cfg.analysis['plotTraces'] = {
            'include': [(pop, list(cfg.pop_cells_plot[pop]))
                        for pop in cfg.allpops],
            'timeRange': [0, cfg.duration],
            'oneFigPer': 'cell', 'overlay': False,
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

    # Main subfolder name
    exp_name_sub = gen_exp_name_sub(cfg)

    # Will be added to file names
    postfix = (f'stim_{cfg.ou_ramp_offset}'
               f'_rx_{cfg.bkg_r}_wx_{cfg.bkg_w}')
    
    # Create the main subfolder
    dirpath_res = Path(cfg.saveFolder)
    dirpath_res_sub = dirpath_res / exp_name_sub
    os.makedirs(dirpath_res_sub, exist_ok=True)

    # Create subfolders to move the files
    dirnames_sub = [
        'cfg', 'params', 'pkl', 'res_json', 'rasters', 'traces',
        'rates_xr', 'vstats_xr', 'fi_figs', 'vi_figs']
    for dirname in dirnames_sub:
        os.makedirs(dirpath_res_sub / dirname, exist_ok=True)

    # Rename files and move them to subfolders
    res_types = [
        ('cfg.json', 'cfg'), ('netParams.json', 'params'),
        ('data.pkl', 'pkl'), ('result.json', 'res_json'),
        ('raster.png', 'rasters')
    ]
    for rt in res_types:
        fpath_old = dirpath_res / f'{exp_name}_{rt[0]}'
        fpath_new = dirpath_res_sub / rt[1] / f'{postfix}_{rt[0]}'
        if fpath_old.exists():
            fpath_old.rename(fpath_new)
    
    # Move traces to the subfodler
    for fpath in dirpath_res.glob(f'{exp_name}_*traces*.png'):
        fpath.rename(dirpath_res_sub / 'traces' / fpath.name)

    # Collect sim result
    sim_result = parse_utils.prepare_sim_result(sim)

    # Time intervals to compute avg. rates and voltage stats
    #time_ranges = [(2.5, 3.5), (6, 7)]   # before and after the stimulus
    T = cfg.duration / 1000
    tstim = STIM_T0 / 1000
    time_ranges = [
        (tstim - TCALC_WIN, tstim), (T - TCALC_WIN, T)   # before and after the stimulus
    ]

    # Compute avg. rates and voltage stats, save as xarrays, plot fi- and vi-curves
    for pop in POPS_USED:
        # Create and save xarray with avg. firing rates
        r_data = fi_utils.calc_avg_rates(sim, sim_result, pop, time_ranges)
        fname_out = f'{postfix}_rates_{pop}.nc'
        r_data.to_netcdf(dirpath_res_sub / 'rates_xr' / fname_out)
    
        # Plot and save pre-/post-ramp firing rate vs. input current
        plt.figure(111, figsize=(12, 6)); plt.clf()
        fi_utils.plot_fi_curve(r_data, pop)
        fname_out = f'{postfix}_fi_{pop}.png'
        plt.savefig(dirpath_res_sub / 'fi_figs' / fname_out)

        # Create and save xarray with voltage stats
        vstats_data = fi_utils.calc_voltage_stats(sim, sim_result, pop, time_ranges)
        fname_out = f'{postfix}_vstats_{pop}.nc'
        vstats_data.to_netcdf(dirpath_res_sub / 'vstats_xr' / fname_out)

        # Plot and save pre-/post-ramp voltage stats vs. input current
        plt.figure(111, figsize=(12, 6)); plt.clf()
        fi_utils.plot_vi_curve(vstats_data, pop)
        fname_out = f'{postfix}_vi_{pop}.png'
        plt.savefig(dirpath_res_sub / 'vi_figs' / fname_out)
