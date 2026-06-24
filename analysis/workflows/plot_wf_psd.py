"""Compute and plot workflow-level rate/LFP PSDs and mean rates."""

import importlib.util
import json
import os
import sys
from pathlib import Path


# Set import paths before importing local packages
DIR_REPO = Path(__file__).resolve().parents[2]
DIR_EXTERNAL = DIR_REPO / 'external'
for path in (DIR_REPO, DIR_EXTERNAL):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


WORKFLOW_NAME = 'ibkg_adj__fullsim__var_wmult_list_1d'
RUN_ID = (
    'ibkg_adj__fullsim__var_wmult_list_1d_L2_wmult_list_ee_efb_1_5_10_nseeds_3_ibkg_-1_0.2_10_tdw_5.0_15.0_tfull_5.0_15.0'
)
DIR_COMBINED = DIR_REPO / 'exp_results_local' / 'workflows' / WORKFLOW_NAME / RUN_ID / 'combined'
DIR_OUT = DIR_REPO / 'exp_results_local' / 'workflows' / WORKFLOW_NAME / RUN_ID / 'psd'

NEED_RECALC = 0
DO_RATES_PSD = 1
DO_LFP_PSD = 1
DO_MEAN_RATES = 1

ANALYSIS_T_WIN = (5, None)
PSD_N_CYCLES = 5
PSD_CYCLE_F_REF = 5
PSD_WIN_OVERLAP = 0.5
PSD_FMIN = 0
PSD_FMAX = 50
PSD_WINDOW = 'hann'
PSD_DETREND = 'constant'
PSD_SCALING = 'density'
PSD_AVERAGE = 'median'

POP_VALUES = None
Y_VALUES = [100, 200]

LFP_INTERP_OUTLIERS = 1
OUTLIER_Z_THRESH = 8
OUTLIER_REL_NEIGHBOR_THRESH = 5

PLOT_LOG_Y = 0
FIG_DPI = 150

TIME_DIM = 'time'
SEED_DIM = 'seed_main'
ITER_DIM = 'iteration'
POP_DIM = 'pop'
Y_DIM = 'y'

OPEN_CHUNKS = {
    ITER_DIM: 1,
    SEED_DIM: 1,
}

os.environ.setdefault('MPLCONFIGDIR', str(DIR_OUT / 'mpl_cache'))

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import xarray as xr

from sim_data_analyzer.xr_cache import encode_xr_attrs_json
from sim_data_analyzer.xr_io import load_xr, save_xr
from sim_data_analyzer.xr_signal import interp_time_outliers
from sim_data_analyzer.xr_spect import calc_xr_welch


TARGETS = {
    'rates': {
        'enabled': DO_RATES_PSD,
        'input_name': 'rvec_xr.nc',
        'output_name': 'rates_psd.nc',
        'plot_dir': 'rates',
        'trace_dim': POP_DIM,
        'selector': POP_VALUES,
        'interp_outliers': 0,
    },
    'lfp': {
        'enabled': DO_LFP_PSD,
        'input_name': 'lfp_xr.nc',
        'output_name': 'lfp_psd.nc',
        'plot_dir': 'lfp',
        'trace_dim': Y_DIM,
        'selector': Y_VALUES,
        'interp_outliers': LFP_INTERP_OUTLIERS,
    },
}


def _has_dask():
    """Return whether xarray chunking can use dask."""
    return importlib.util.find_spec('dask') is not None


def _json_dumps(value):
    """Return a compact stable JSON string."""
    return json.dumps(value, sort_keys=True, default=str)


def _as_list(values):
    """Return a plain list or None."""
    if values is None:
        return None
    if isinstance(values, str):
        return [values]
    return list(values)


def _format_value(value):
    """Format one coordinate value for filenames and labels."""
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float):
        return f'{value:g}'
    return str(value)


def _safe_value(value):
    """Format one coordinate value for safe filenames."""
    text = _format_value(value)
    return text.replace('.', 'p').replace('-', 'm').replace('/', '_')


def _get_psd_win_len():
    """Return the PSD window length derived from cycles."""
    return PSD_N_CYCLES / PSD_CYCLE_F_REF


def _get_input_path(target):
    """Return one combined workflow xarray path."""
    return DIR_COMBINED / TARGETS[target]['input_name']


def _get_psd_path(target):
    """Return one saved PSD xarray path."""
    return DIR_OUT / TARGETS[target]['output_name']


def _get_mean_rates_path():
    """Return the saved mean-rate xarray path."""
    return DIR_OUT / 'mean_rates.nc'


def _open_dataarray(path):
    """Open one DataArray lazily when the environment supports chunks."""
    open_kwargs = {}
    if _has_dask():
        open_kwargs['chunks'] = OPEN_CHUNKS
    return xr.open_dataarray(path, **open_kwargs)


def _select_analysis_window(X):
    """Crop the signal to the configured PSD analysis window."""
    t0, t1 = ANALYSIS_T_WIN
    time = X.coords[TIME_DIM]
    if t1 is None:
        return X.sel({TIME_DIM: slice(t0, None)})
    return X.sel({TIME_DIM: slice(t0, t1)})


def _validate_time_window(X, target):
    """Validate that the selected time range can support one PSD window."""
    if TIME_DIM not in X.dims:
        raise ValueError(f'{target}: missing {TIME_DIM!r} dimension')
    if X.sizes[TIME_DIM] < 2:
        raise ValueError(f'{target}: analysis window has fewer than two samples')
    time = np.asarray(X.coords[TIME_DIM].values, dtype=float)
    fs = round(1 / float(time[1] - time[0]), 5)
    win_len = _get_psd_win_len()
    nperseg = round(win_len * fs)
    if X.sizes[TIME_DIM] < nperseg:
        raise ValueError(
            f'{target}: analysis window has {X.sizes[TIME_DIM]} samples, '
            f'but PSD window needs {nperseg}'
        )


def _validate_nonempty_time_window(X, target):
    """Validate that the selected time range has samples."""
    if TIME_DIM not in X.dims:
        raise ValueError(f'{target}: missing {TIME_DIM!r} dimension')
    if X.sizes[TIME_DIM] < 1:
        raise ValueError(f'{target}: analysis window has no samples')


def _select_traces(X, target):
    """Select configured populations or LFP depths."""
    trace_dim = TARGETS[target]['trace_dim']
    values = _as_list(TARGETS[target]['selector'])
    if values is None:
        return X
    if trace_dim not in X.dims:
        raise ValueError(f'{target}: missing trace dimension {trace_dim!r}')
    return X.sel({trace_dim: values})


def _prepare_signal(X, target):
    """Select, crop, and preprocess one target signal."""
    X = _select_traces(X, target)
    X = _select_analysis_window(X)
    _validate_time_window(X, target)

    # Interpolate isolated LFP spikes before PSD when requested
    if TARGETS[target]['interp_outliers']:
        X = interp_time_outliers(
            X,
            time_dim=TIME_DIM,
            z_thresh=OUTLIER_Z_THRESH,
            rel_neighbor_thresh=OUTLIER_REL_NEIGHBOR_THRESH,
        )

    # Keep time last for scipy Welch
    dim_order = [dim for dim in X.dims if dim != TIME_DIM] + [TIME_DIM]
    return X.transpose(*dim_order)


def _build_attrs(target, source_path):
    """Build NetCDF-safe PSD metadata."""
    return {
        'workflow_name': WORKFLOW_NAME,
        'run_id': RUN_ID,
        'target': target,
        'source_path': str(source_path),
        'analysis_t_win_json': _json_dumps(ANALYSIS_T_WIN),
        'psd_n_cycles': PSD_N_CYCLES,
        'psd_cycle_f_ref': PSD_CYCLE_F_REF,
        'psd_win_len': _get_psd_win_len(),
        'psd_win_overlap': PSD_WIN_OVERLAP,
        'psd_fmin': PSD_FMIN,
        'psd_fmax': PSD_FMAX,
        'psd_window': PSD_WINDOW,
        'psd_detrend': PSD_DETREND,
        'psd_scaling': PSD_SCALING,
        'psd_average': PSD_AVERAGE,
        'selector_json': _json_dumps(_as_list(TARGETS[target]['selector'])),
        'lfp_interp_outliers': int(bool(TARGETS[target]['interp_outliers'])),
        'outlier_z_thresh': OUTLIER_Z_THRESH,
        'outlier_rel_neighbor_thresh': OUTLIER_REL_NEIGHBOR_THRESH,
    }


def _build_mean_rate_attrs(source_path):
    """Build NetCDF-safe mean-rate metadata."""
    return {
        'workflow_name': WORKFLOW_NAME,
        'run_id': RUN_ID,
        'target': 'mean_rates',
        'source_path': str(source_path),
        'analysis_t_win_json': _json_dumps(ANALYSIS_T_WIN),
        'selector_json': _json_dumps(_as_list(POP_VALUES)),
    }


def _compute_psd(target):
    """Compute and save one target PSD."""
    source_path = _get_input_path(target)
    if not source_path.is_file():
        raise FileNotFoundError(f'Missing combined input: {source_path}')

    X = _open_dataarray(source_path)
    try:
        X = _prepare_signal(X, target)
        psd = calc_xr_welch(
            X,
            win_len=_get_psd_win_len(),
            win_overlap=PSD_WIN_OVERLAP,
            fmin=PSD_FMIN,
            fmax=PSD_FMAX,
            window=PSD_WINDOW,
            detrend=PSD_DETREND,
            scaling=PSD_SCALING,
            average=PSD_AVERAGE,
            time_dim=TIME_DIM,
            compute=False,
            store_proc_info=True,
        )
        psd.attrs.update(_build_attrs(target, source_path))
        psd.name = f'{target}_psd'

        # Save one durable target-level PSD file
        out_path = _get_psd_path(target)
        save_xr(encode_xr_attrs_json(psd), out_path)
        print(f'Saved {target} PSD: {out_path}')
    finally:
        X.close()
    return out_path


def _compute_mean_rates():
    """Compute and save per-seed mean firing rates."""
    source_path = _get_input_path('rates')
    if not source_path.is_file():
        raise FileNotFoundError(f'Missing combined input: {source_path}')

    X = _open_dataarray(source_path)
    try:
        X = _select_traces(X, 'rates')
        X = _select_analysis_window(X)
        _validate_nonempty_time_window(X, 'mean_rates')

        # Keep one value per workflow iteration, seed, and population
        mean_rates = X.mean(TIME_DIM)
        mean_rates.name = 'mean_rates'
        mean_rates.attrs.update(_build_mean_rate_attrs(source_path))

        out_path = _get_mean_rates_path()
        save_xr(encode_xr_attrs_json(mean_rates), out_path)
        print(f'Saved mean rates: {out_path}')
    finally:
        X.close()
    return out_path


def _ensure_psd(target):
    """Return an existing PSD path or compute it when needed."""
    out_path = _get_psd_path(target)
    if out_path.is_file() and not NEED_RECALC:
        print(f'Reusing {target} PSD: {out_path}')
        return out_path
    return _compute_psd(target)


def _ensure_mean_rates():
    """Return an existing mean-rate path or compute it when needed."""
    out_path = _get_mean_rates_path()
    if out_path.is_file() and not NEED_RECALC:
        print(f'Reusing mean rates: {out_path}')
        return out_path
    return _compute_mean_rates()


def _get_trace_values(psd, target):
    """Return selected trace coordinate values from a PSD xarray."""
    trace_dim = TARGETS[target]['trace_dim']
    values = _as_list(TARGETS[target]['selector'])
    if values is not None:
        return values
    return list(psd.coords[trace_dim].values)


def _get_trace_fname(target, value):
    """Return a plot filename for one trace."""
    if target == 'lfp':
        return f'y_{_safe_value(value)}.png'
    return f'{_safe_value(value)}.png'


def _get_iter_label(row):
    """Return a compact label for one iteration curve."""
    iteration = int(row.coords[ITER_DIM].item())
    variant = ''
    if 'wmult_variant' in row.coords:
        variant = str(row.coords['wmult_variant'].item())
    if variant:
        return f'iter {iteration}: {variant}'
    return f'iter {iteration}'


def _plot_trace(psd, target, trace_value, out_path):
    """Plot one population or depth PSD across iterations."""
    trace_dim = TARGETS[target]['trace_dim']
    psd_trace = psd.sel({trace_dim: trace_value}).mean(SEED_DIM).load()
    fig, ax = plt.subplots(1, 1, figsize=(8, 5))

    # Draw one seed-averaged curve per workflow iteration
    for iteration in psd_trace.coords[ITER_DIM].values:
        row = psd_trace.sel({ITER_DIM: iteration})
        label = _get_iter_label(row)
        ax.plot(
            row.coords['freq'].values,
            row.values,
            linewidth=1.4,
            label=label,
        )

    if PLOT_LOG_Y:
        ax.set_yscale('log')
    trace_label = f'{trace_dim}={_format_value(trace_value)}'
    ax.set_xlabel('Frequency (Hz)')
    ax.set_ylabel('PSD')
    ax.set_title(
        f'{target} PSD, {trace_label}\n'
        f't={ANALYSIS_T_WIN[0]}-{ANALYSIS_T_WIN[1]} s; '
        f'win={_get_psd_win_len():g} s ({PSD_N_CYCLES:g} cycles @ {PSD_CYCLE_F_REF:g} Hz)'
    )
    ax.grid(alpha=0.2)
    ax.legend(fontsize=8)
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=FIG_DPI, bbox_inches='tight')
    plt.close(fig)
    print(f'Saved plot: {out_path}')


def _plot_psd(target, psd_path):
    """Plot all selected traces for one target PSD."""
    psd = load_xr(psd_path, data_type='dataarray', load=False)
    try:
        trace_dim = TARGETS[target]['trace_dim']
        if trace_dim not in psd.dims:
            raise ValueError(f'{target}: missing PSD dimension {trace_dim!r}')
        out_dir = DIR_OUT / TARGETS[target]['plot_dir']

        # Load only one trace at a time while plotting
        for trace_value in _get_trace_values(psd, target):
            out_path = out_dir / _get_trace_fname(target, trace_value)
            _plot_trace(psd, target, trace_value, out_path)
    finally:
        psd.close()


def _get_mean_rate_pops(mean_rates):
    """Return selected population values from mean-rate xarray."""
    values = _as_list(POP_VALUES)
    if values is not None:
        return values
    return list(mean_rates.coords[POP_DIM].values)


def _plot_mean_rate_pop(mean_rates, pop, out_path):
    """Plot per-seed mean rates and medians for one population."""
    pop_rates = mean_rates.sel({POP_DIM: pop}).load()
    fig, ax = plt.subplots(1, 1, figsize=(8, 5))
    xticks = []
    xlabels = []

    # Draw each iteration as a vertical seed stack plus median dash
    for n_iter, iteration in enumerate(pop_rates.coords[ITER_DIM].values):
        row = pop_rates.sel({ITER_DIM: iteration})
        values = np.asarray(row.values, dtype=float).ravel()
        values = values[np.isfinite(values)]
        if values.size == 0:
            continue

        label_seed = 'Seeds' if n_iter == 0 else None
        label_median = 'Median' if n_iter == 0 else None
        ax.scatter(
            np.full(values.shape, n_iter, dtype=float),
            values,
            s=34,
            color='C0',
            alpha=0.75,
            label=label_seed,
        )
        ax.hlines(
            np.median(values),
            n_iter - 0.25,
            n_iter + 0.25,
            color='k',
            linewidth=2,
            label=label_median,
        )
        xticks.append(n_iter)
        xlabels.append(_get_iter_label(row))

    ax.set_xticks(xticks)
    ax.set_xticklabels(xlabels, rotation=30, ha='right')
    ax.set_ylabel('Mean firing rate (Hz)')
    ax.set_title(
        f'Mean rate, pop={_format_value(pop)}\n'
        f't={ANALYSIS_T_WIN[0]}-{ANALYSIS_T_WIN[1]} s'
    )
    ax.grid(axis='y', alpha=0.25)
    ax.legend(fontsize=8)
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=FIG_DPI, bbox_inches='tight')
    plt.close(fig)
    print(f'Saved plot: {out_path}')


def _plot_mean_rates(mean_rates_path):
    """Plot all selected population mean rates."""
    mean_rates = load_xr(mean_rates_path, data_type='dataarray', load=False)
    try:
        if POP_DIM not in mean_rates.dims:
            raise ValueError(f'mean_rates: missing dimension {POP_DIM!r}')
        out_dir = DIR_OUT / 'mean_rates'

        # Load and plot one population at a time
        for pop in _get_mean_rate_pops(mean_rates):
            out_path = out_dir / f'{_safe_value(pop)}.png'
            _plot_mean_rate_pop(mean_rates, pop, out_path)
    finally:
        mean_rates.close()


def run_target(target):
    """Compute or reuse one target PSD and rebuild plots."""
    if not TARGETS[target]['enabled']:
        print(f'Skipping disabled target: {target}')
        return
    psd_path = _ensure_psd(target)
    _plot_psd(target, psd_path)


def run_mean_rates():
    """Compute or reuse mean rates and rebuild plots."""
    if not DO_MEAN_RATES:
        print('Skipping disabled target: mean_rates')
        return
    mean_rates_path = _ensure_mean_rates()
    _plot_mean_rates(mean_rates_path)


def main():
    """Run configured workflow PSD analysis."""
    DIR_OUT.mkdir(parents=True, exist_ok=True)
    for target in TARGETS:
        run_target(target)
    run_mean_rates()


if __name__ == '__main__':
    main()
