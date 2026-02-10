import json
import os
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import xarray as xr

import analysis.ou_tuning.netpyne_res_parse_utils as parse_utils
import analysis.ou_tuning.data_proc_utils as proc_utils
from plot_fi_vi_curves import plot_fi_curve, plot_vi_curve


dirpath_self = Path(__file__).resolve().parent


def calc_avg_rates(sim, sim_result, pop, time_ranges) -> xr.DataArray:
    """Calculate per-cell avg rates for a pop. over specified time ranges. """

    # Extract spike times from the sim result
    spikes = parse_utils.get_pop_spikes(sim_result, pop, combine_cells=False)

    # Calculate pre- and post-stimulus firing rates
    avg_rates = []
    for _, t_range in enumerate(time_ranges):
        rr = proc_utils.calc_pop_rate(spikes, t_range)
        avg_rates.append(rr)
    
    # Input current values of the neurons
    ncells = len(spikes)
    I_min, I_max = sim.cfg.OUamp
    I_vals = np.linspace(I_min, I_max, ncells)

    time_range_labels = [f't=({t[0]}-{t[1]})' for t in time_ranges]

    data = xr.DataArray(
        data=np.array(avg_rates), 
        dims=['interval', 'cell'], 
        coords={
            'interval': ['pre', 'post'],
            'time_range': ('interval', time_range_labels),
            'cell': np.arange(ncells),
            'I': ('cell', I_vals),
        }
    )
    return data


def calc_voltage_stats(sim, sim_result, pop, time_ranges) -> xr.DataArray:
    """Calculate per-cell V stats for a pop. over specified time ranges. """

    # Extract voltages for each time range
    V0 = []
    for t_limits in time_ranges:
        V_, _ = parse_utils.get_pop_voltages(
            sim_result, pop, np.array(t_limits) * 1000
        )
        V0.append(V_)
    
    # Input current values of the cells
    ncells = parse_utils.get_pop_size(sim_result, pop)
    I_min, I_max = sim.cfg.OUamp
    I_vals = np.linspace(I_min, I_max, ncells)

    # Cells with recorded voltages
    cell_idx = sim.cfg.pop_cells_rec[pop]

    time_range_labels = [f't=({t[0]}-{t[1]})' for t in time_ranges]

    # Create xarray for voltage statistics
    Z = xr.DataArray(
        data=np.full((len(time_ranges), len(cell_idx)), np.nan),
        dims=['interval', 'cell'], 
        coords={
            'interval': ['pre', 'post'],
            'time_range': ('interval', time_range_labels),
            'cell': cell_idx,
            'I': ('cell', I_vals[cell_idx])
        }
    )
    V_stats = xr.Dataset({
        v: Z.copy()
        for v in ['vmin', 'vmax', 'vmed', 'vavg']
    })

    # Compute and save voltage statistics
    for n, _ in enumerate(time_ranges):
        V = V0[n]   # (cell x time)
        cc = {'interval': n}
        V_stats['vmin'][cc] = np.min(V, axis=1)
        V_stats['vmax'][cc] = np.max(V, axis=1)
        V_stats['vmed'][cc] = np.median(V, axis=1)
        V_stats['vavg'][cc] = np.mean(V, axis=1)
    return V_stats


def post_run(sim):
    """Called in the end of a job (after runnig and saving). """

    cfg = sim.cfg
    dirpath_res = Path(cfg.saveFolder)
    exp_name = cfg.simLabel

    # Will be added to file names
    postfix = (f'stim_{cfg.ou_ramp_offset}'
               f'_rx_{cfg.bkg_r}_wx_{cfg.bkg_w}')

    # Create subfolders to move the files
    dirnames_sub = ['cfg', 'params', 'pkl', 'res_json', 'rasters', 
                    'rates_xr', 'vstats_xr', 'fi_figs', 'vi_figs']
    for dirname in dirnames_sub:
        os.makedirs(dirpath_res / dirname, exist_ok=True)

    # Rename files and move them to subfolders
    res_types = [
        ('cfg.json', 'cfg'), ('netParams.json', 'params'),
        ('data.pkl', 'pkl'), ('result.json', 'res_json'),
        ('raster.png', 'rasters')
    ]
    for rt in res_types:
        fpath_old = dirpath_res / f'{exp_name}_{rt[0]}'
        fpath_new = dirpath_res / rt[1] / f'{exp_name}_{postfix}_{rt[0]}'
        fpath_old.rename(fpath_new)

    # Collect sim result
    sim_result = parse_utils.prepare_sim_result(sim)

    # Time intervals to compute avg. rates and voltage stats
    time_ranges = [(2.5, 3.5), (6, 7)]   # before and after the stimulus

    # Compute avg. rates and voltage stats, save as xarrays, 
    # plot fi- and vi-curves
    for pop in cfg.pops_active:

        # Create and save xarray with avg. firing rates
        r_data = calc_avg_rates(sim, sim_result, pop, time_ranges)
        fname_out = f'{exp_name}_{postfix}_rates_{pop}.nc'
        r_data.to_netcdf(dirpath_res / 'rates_xr' / fname_out)
    
        # Plot and save pre-/post-ramp firing rate vs. input current
        plt.figure(111, figsize=(12, 6)); plt.clf()
        plot_fi_curve(r_data, pop)
        fname_out = f'{exp_name}_{postfix}_fi_{pop}.png'
        plt.savefig(dirpath_res / 'fi_figs' / fname_out)

        # Create and save xarray with voltage stats
        vstats_data = calc_voltage_stats(sim, sim_result, pop, time_ranges)
        fname_out = f'{exp_name}_{postfix}_vstats_{pop}.nc'
        vstats_data.to_netcdf(dirpath_res / 'vstats_xr' / fname_out)

        # Plot and save pre-/post-ramp voltage stats vs. input current
        plt.figure(111, figsize=(12, 6)); plt.clf()
        plot_vi_curve(vstats_data, pop)
        fname_out = f'{exp_name}_{postfix}_vi_{pop}.png'
        plt.savefig(dirpath_res / 'vi_figs' / fname_out)
        
