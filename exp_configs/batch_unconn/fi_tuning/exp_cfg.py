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
import fi_utils

from batch_params import (
    AMP_VALS, RX_VALS, WX_VALS,
    BKG_SEC, I_SEC
)


EXP_NAME = 'ti'
POPS_USED = ['TI']

CELL_TYPES = {'IRE': 'RE', 'PV3': 'PV', 'SOM3': 'SOM',
              'VIP3': 'VIP', 'NGF3': 'NGF'}

# Constant input increasing across the cells ("I" of the f-I curve)
#I_RANGE = [-0.002, 0.01]
I_RANGE = [-0.02, 0.03]

# Mechanism changes
GKDR_MULT = 1
GKAP_MULT = 1
GLEAK_MULT = 1
GCAT_MULT = 1
GCAL_MULT = 1
GCAN_MULT = 1
GKBK_MULT = 1
GIH_MULT = 1
GNAX_MULT = 1


def get_mech_changes():
    mech_change_info = {
        'gkdr': ('kdr', 'gbar', GKDR_MULT),
        'gkap': ('kap', 'gbar', GKAP_MULT),
        'gleak': ('pas', 'g', GLEAK_MULT),
        'gcat': ('cat', 'gcatbar', GCAT_MULT),
        'gcal': ('cal', 'gcalbar', GCAL_MULT),
        'gcan': ('can', 'gcanbar', GCAN_MULT),
        'gkbk': ('kBK', 'gpeak', GKBK_MULT),
        'gih': ('ih', 'gbar', GIH_MULT),
        'gnax': ('nax', 'gbar', GNAX_MULT)
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
    cfg.duration = 7 * 1e3
    
    # Turn off the connections
    cfg.addConn = 0

    # Turn on/off bkg inputs (old ones, unused now)
    cfg.addBkgConn = 0

    # Populations to use
    cfg.pops_active = POPS_USED
    cfg.allpops = cfg.pops_active
    if 'plotRaster' in cfg.analysis:
        cfg.analysis['plotRaster']['include'] = cfg.pops_active
    if 'plotSpikeStats' in cfg.analysis:
        cfg.analysis['plotSpikeStats']['include'] = cfg.pops_active
    if 'plotTraces' in cfg.analysis:
        cfg.analysis['plotTraces']['include'] = cfg.pops_active
    
    cfg.analysis['plotSpikeStats'] = False
    
    # Tonic current input (I)
    cfg.add_ou_current = 1
    cfg.ou_common = 1    # all pops receive the same OU input
    cfg.ou_noise_duration = cfg.duration
    cfg.ou_tau = 10
    cfg.OUamp = list(I_RANGE)
    cfg.OUstd = 0
    cfg.ou_sec = I_SEC

    # Strong ramp-up pulse for switching between the steady-states
    cfg.ou_ramp_dur = 1000   # duration
    cfg.ou_ramp_t0 = 3500    # start time
    cfg.ou_ramp_offset = 0   # amplitude, from batch
    cfg.ou_ramp_mult = 0
    cfg.ou_ramp_type = 'up'

    # NetStim input
    cfg.add_bkg_spike_input = 1
    cfg.bkg_r = 0   # from batch
    cfg.bkg_w = 0   # from batch

    # Cell mechanisms to modify
    cfg.mech_changes = get_mech_changes()
    
    # Load a table of pop sizes
    fpath_csv = dirpath_self / 'pops_sz.csv'
    pops_sz_df = pd.read_csv(fpath_csv)
    pops_sz = pops_sz_df.set_index('pop')['ncells'].to_dict()

    # Choose the cells to record voltages for each active pop.
    ncells_rec = 500
    cfg.pop_cells_rec = {}
    for pop in cfg.allpops:
        N = np.minimum(pops_sz[pop], ncells_rec)
        cfg.pop_cells_rec[pop] = np.linspace(0, pops_sz[pop] - 1, N, dtype=int)

    # Record voltage traces
    cfg.recordCells = [(pop, list(cfg.pop_cells_rec[pop]))
                       for pop in cfg.allpops]
    cfg.recordTraces = {
        'V_soma': {'sec': 'soma', 'loc': 0.5, 'var': 'v'}
    }
    cfg.recordStep =  0.1
    """ cfg.analysis['plotTraces'] = {
        'include': [(pop, cells_rec) for pop in cfg.allpops],
        'timeRange': [0, cfg.duration],
        'oneFigPer': 'cell', 'overlay': False,
        'saveFig': True, 'showFig': False, 'figSize': (18, 12)
    } """


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
            if v['mech'] in sec['mechs']:
                sec['mechs'][v['mech']][v['par']] *= v['mult']
                #sec['mechs'][v['mech']][v['par']] += v['add']


def post_run(sim):
    """Called in the end of a job (after runnig and saving). """

    cfg = sim.cfg
    job_name = cfg.simLabel
    dirpath_res = Path(cfg.saveFolder)

    # Main subfolder name
    exp_name_sub = f'exp_{EXP_NAME}'
    exp_name_sub += f'_gkdr_{GKDR_MULT}'
    mechs = {'gkap': GKAP_MULT, 'gl': GLEAK_MULT, 
             'gcat': GCAT_MULT, 'gcal': GCAL_MULT,
             'gcan': GCAN_MULT, 'gkbk': GKBK_MULT,
             'gih': GIH_MULT, 'gnax': GNAX_MULT}
    for name, mult in mechs.items():
        if mult != 1:
            exp_name_sub += f'_{name}_{mult}'
    exp_name_sub += f'_amp_{np.min(AMP_VALS)}_{np.max(AMP_VALS)}'
    exp_name_sub += f'_rx_{np.min(RX_VALS)}_{np.max(RX_VALS)}'
    exp_name_sub += f'_wx_{np.min(WX_VALS)}_{np.max(WX_VALS)}'
    exp_name_sub += f'_sz_{len(AMP_VALS)}_{len(RX_VALS)}_{len(WX_VALS)}'
    exp_name_sub += f'_xsec_{BKG_SEC}'
    exp_name_sub += f'_isec_{I_SEC}'
    exp_name_sub += f'_irange_{cfg.OUamp[0]}_{cfg.OUamp[1]}'

    # Will be added to file names
    postfix = (f'stim_{cfg.ou_ramp_offset}'
               f'_rx_{cfg.bkg_r}_wx_{cfg.bkg_w}')
    
    # New filename base
    job_id = job_name.split('_')[-1]
    job_name_new = f'{job_id}_{postfix}'
    
    # Create the main subfolder
    dirpath_res_sub = dirpath_res / exp_name_sub
    os.makedirs(dirpath_res_sub, exist_ok=True)

    # Create subfolders to move the files
    dirnames_sub = ['cfg', 'params', 'pkl', 'res_json', 'rasters', 
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
        fpath_old = dirpath_res / f'{job_name}_{rt[0]}'
        fpath_new = dirpath_res_sub / rt[1] / f'{job_name_new}_{rt[0]}'
        if fpath_old.exists():
            fpath_old.rename(fpath_new)

    # Collect sim result
    sim_result = parse_utils.prepare_sim_result(sim)

    # Time intervals to compute avg. rates and voltage stats
    time_ranges = [(2.5, 3.5), (6, 7)]   # before and after the stimulus

    # Compute avg. rates and voltage stats, save as xarrays, plot fi- and vi-curves
    for pop in cfg.pops_active:
        # Create and save xarray with avg. firing rates
        r_data = fi_utils.calc_avg_rates(sim, sim_result, pop, time_ranges)
        fname_out = f'{job_name_new}_rates_{pop}.nc'
        r_data.to_netcdf(dirpath_res_sub / 'rates_xr' / fname_out)
    
        # Plot and save pre-/post-ramp firing rate vs. input current
        plt.figure(111, figsize=(12, 6)); plt.clf()
        fi_utils.plot_fi_curve(r_data, pop)
        fname_out = f'{job_name_new}_fi_{pop}.png'
        plt.savefig(dirpath_res_sub / 'fi_figs' / fname_out)

        # Create and save xarray with voltage stats
        vstats_data = fi_utils.calc_voltage_stats(sim, sim_result, pop, time_ranges)
        fname_out = f'{job_name_new}_vstats_{pop}.nc'
        vstats_data.to_netcdf(dirpath_res_sub / 'vstats_xr' / fname_out)

        # Plot and save pre-/post-ramp voltage stats vs. input current
        plt.figure(111, figsize=(12, 6)); plt.clf()
        fi_utils.plot_vi_curve(vstats_data, pop)
        fname_out = f'{job_name_new}_vi_{pop}.png'
        plt.savefig(dirpath_res_sub / 'vi_figs' / fname_out)
