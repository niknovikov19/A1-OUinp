from matplotlib.lines import Line2D
import matplotlib.pyplot as plt
import numpy as np
import xarray as xr


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