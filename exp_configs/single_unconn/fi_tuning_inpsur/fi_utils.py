from pathlib import Path
import sys

dirpath_self = Path(__file__).resolve().parent
dirpath_repo_root = Path(__file__).resolve().parents[3]
sys.path.append(str(dirpath_repo_root))

from matplotlib.lines import Line2D
import matplotlib.pyplot as plt
import numpy as np
import xarray as xr

import analysis.ou_tuning.netpyne_res_parse_utils as parse_utils
import analysis.ou_tuning.data_proc_utils as proc_utils


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


def plot_fi_curve(
        R: xr.DataArray,
        pop: str
        ):
    for n in range(R.sizes['interval']):
        plt.plot(
            R.coords['I'].values,
            R.isel(interval=n).values + n,
            '.',
            label=R.coords['time_range'][n].item()
        )        
    plt.xlabel('Input current')
    plt.ylabel('Avg. rate (Hz)')
    plt.title(f'Pop: {pop}')
    plt.legend()


def plot_vi_curve(
        V_stats: xr.Dataset,
        pop: str,
        v_block=-40,   # depol. block: v_block < v < v_spike
        v_spike=20
        ):
    
    Vmin = V_stats['vmin']
    Vmax = V_stats['vmax']
    Vavg = V_stats['vavg']

    I_vals = V_stats.coords['I'].values
    trange_dim = 'interval'

    # Types of activity
    act_types = {
        'rest': {
            'vmax_range': (-np.inf, v_block),
            'colors': {'min': 'm', 'max': 'm', 'avg': 'r'},
            'show_avg': 1, 'show_minmax': 0
        },
        'block': {
            'vmax_range': (v_block, v_spike),
            'colors': {'min': 'g', 'max': 'g', 'avg': 'b'},
            'show_avg': 1, 'show_minmax': 0
        },
        'spiking': {
            'vmax_range': (20, np.inf),
            'colors': {'min': 'k', 'max': 'k', 'avg': 'k'},
            'show_avg': 0, 'show_minmax': 1
        }
    }
    
    for m, _ in enumerate(Vmax[trange_dim]):
        for act_name, act_par in act_types.items():
            # Choose cells with a given activity type
            cc = {trange_dim: m}
            vmax = Vmax.isel(cc)
            vv = act_par['vmax_range']
            mask = (vmax >= vv[0]) & (vmax < vv[1])

            ii = I_vals[mask]
            vmax = Vmax.isel(cc).values[mask]
            vmin = Vmin.isel(cc).values[mask]
            vavg = Vavg.isel(cc).values[mask]

            if act_par['show_avg']:
                plt.plot(ii, vavg, '.', color=act_par['colors']['avg'])
            if act_par['show_minmax']:
                plt.plot(ii, vmax, '.', color=act_par['colors']['max'])
                plt.plot(ii, vmin, '.', color=act_par['colors']['min'])

    plt.xlabel('Input current (I)')
    plt.ylabel('Voltage')

    # Legend
    legend_elements = [
        Line2D([0], [0], marker='.', color='r', linestyle='None', label='Rest (avg)'),
        Line2D([0], [0], marker='.', color='b', linestyle='None', label='Depol. block (avg)'),
        Line2D([0], [0], marker='.', color='k', linestyle='None', label='Spiking (min, max)'),
    ]
    plt.legend(handles=legend_elements)

    plt.title(pop)