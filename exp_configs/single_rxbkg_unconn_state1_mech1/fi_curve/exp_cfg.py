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
sys.path.append(str(dirpath_repo_root))

import analysis.ou_tuning.netpyne_res_parse_utils as parse_utils
import analysis.ou_tuning.data_proc_utils as proc_utils


#EXP_NAME = 'it2'
#POPS_USED = ['IT2'] 
#EXP_NAME = 'pyr'
#POPS_USED = ['IT2', 'IT3', 'ITS4', 'ITP4', 'IT5A', 'CT5A',
#             'IT5B', 'CT5B', 'PT5B', 'IT6', 'CT6']
EXP_NAME = 'tc'
POPS_USED = ['TC', 'HTC', 'TCM'] 

RX = 1
WX = 0.001

# Static IClamp that sets the resting voltage
use_ibkg = 0
v_rest = -70


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
    
    # OU current
    cfg.add_ou_current = 1
    cfg.ou_common = 1    # all pops receive the same OU input
    cfg.ou_noise_duration = cfg.duration
    cfg.ou_tau = 2
    cfg.OUamp = [-0.03, 0.01]
    cfg.OUstd = 0

    # NetStim inputs
    cfg.add_bkg_spike_input = 1
    cfg.bkg_r = RX
    cfg.bkg_w = WX
    cfg.bkg_spike_inputs = {
        pop: {'exc': {'r': cfg.bkg_r, 'w': cfg.bkg_w}}
        for pop in cfg.pops_active
    }

    # Static IClamp that sets the resting voltage
    if use_ibkg:
        cfg.addIClamp = 1
        fname_ibkg = f'ibkg_mech1_vrest_{v_rest}.json'
        with open(dirpath_self / fname_ibkg, 'r') as fid:
            ibkg = json.load(fid)
        cfg.IClamp = {pop: {'amp': ibkg[pop]} for pop in cfg.pops_active}

    # Cell mechanisms to modify
    with open(dirpath_self / 'mech_changes_1.json', 'r') as fid:
        cfg.mech_changes = json.load(fid)
    
    # Load a table of pop sizes
    fpath_csv = dirpath_self / 'pops_sz.csv'
    pops_sz_df = pd.read_csv(fpath_csv)
    pops_sz = pops_sz_df.set_index('pop')['ncells'].to_dict()

    # Choose the cells to record voltages for each active pop.
    ncells_rec = 100
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

    # OU ramp
    cfg.ou_ramp_dur = 1000
    cfg.ou_ramp_t0 = 3500
    cfg.ou_ramp_offset = 1
    cfg.ou_ramp_mult = 0
    cfg.ou_ramp_type = 'up'


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

    exp_name_sub = f'exp_{EXP_NAME}'
    exp_name_sub += f'_rx_{RX}_wx_{WX:.03f}'
    exp_name_sub += f'_ramp_{cfg.ou_ramp_offset:.02f}'
    #if cfg.addIClamp:
    #    exp_name_sub += f'_iclamp_{cfg.IClamp["IT2"]["amp"]:.05f}'
    if use_ibkg:
        exp_name_sub += f'_vrest_{v_rest}'

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

    # Create subfolders to put the results
    dirnames_sub = ['ir_curves', 'iv_curves', 'rates', 'vstats']
    for dirname in dirnames_sub:
        os.makedirs(dirpath_res_sub / dirname, exist_ok=True)

    # Collect sim result
    sim_result = parse_utils.prepare_sim_result(sim)

    # Time intervals before and after the ramp (for averaging r and V)
    time_ranges = [(2.5, 3.5), (6, 7)]

    # Extract voltages
    V0, tt = [], []
    for t_limits in time_ranges:
        V_, tt_ = parse_utils.get_voltages(
            sim_result, np.array(t_limits) * 1000
        )
        V0.append(V_)
        tt.append(tt_)

    for pop in cfg.pops_active:        
        # Extract spike times from the sim result
        spikes = parse_utils.get_pop_spikes(sim_result, pop, combine_cells=False)

        # Calculate pre- and post-ramp firing rates
        avg_rates = []
        for n, t_range in enumerate(time_ranges):
            rr = proc_utils.calc_pop_rate(spikes, t_range)
            avg_rates.append(rr)
        
        # OU amplitudes and std's corresponding to the neurons
        ncells = len(spikes)
        ouamp_min, ouamp_max = sim.cfg.OUamp
        ou_amps = np.linspace(ouamp_min, ouamp_max, ncells)   # TODO: convert to I
    
        # Plot pre- / post-ramp firing rate vs. OU amplitude
        plt.figure(111, figsize=(12, 6))
        plt.clf()
        for n, t_range in enumerate(time_ranges):
            plt.plot(ou_amps, np.array(avg_rates[n]) + n, '.',
                    label=f't=({t_range[0]}-{t_range[1]})')
        plt.xlabel('OU amplitude')
        plt.ylabel('Avg. rate (Hz)')
        plt.title(f'Pop: {pop}')
        plt.legend()
        plt.savefig(dirpath_res_sub / 'ir_curves' / f'ir_{pop}.png', dpi=300)

        # Create and save xarray with avg. firing rates
        time_range_labels = [f't=({t[0]}-{t[1]})' for t in time_ranges]
        data = xr.DataArray(
            data=np.array(avg_rates), 
            dims=['interval', 'cell'], 
            coords={
                'interval': ['pre', 'post'],
                'time_range': ('interval', time_range_labels),
                'cell': np.arange(ncells),
                'ou_mean': ('cell', ou_amps)
            }
        )
        data.attrs = {
            'ramp_offset': cfg.ou_ramp_offset,
            'ramp_mult':  cfg.ou_ramp_mult,
            'rx': cfg.bkg_r,
            'wx': cfg.bkg_w
        }
        data.to_netcdf(dirpath_res_sub / 'rates' / f'rates_{pop}.nc')

        # Create xarray with voltages
        V = [V0_[pop] for V0_ in V0]
        cell_idx = cfg.pop_cells_rec[pop]
        V_data = xr.DataArray(
            data=V, 
            dims=['interval', 'cell', 'time'], 
            coords={
                'interval': ['pre', 'post'],
                'time_range': ('interval', time_range_labels),
                'cell': cell_idx,
                'ou_mean': ('cell', ou_amps[cell_idx]),
                'time': tt[0] / 1000
            }
        )
        V_data.attrs = data.attrs

        # Create and save xarray with voltage statistics
        V_stats = xr.Dataset({
            'vmin': V_data.min(dim='time'),
            'vmax': V_data.max(dim='time'),
            'vmed': V_data.median(dim='time'),
            'vavg': V_data.mean(dim='time')
        })
        V_stats.attrs = V_data.attrs
        V_stats.to_netcdf(dirpath_res_sub / 'vstats' / f'vstats_{pop}.nc')
