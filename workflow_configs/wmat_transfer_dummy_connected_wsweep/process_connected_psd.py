from pathlib import Path
import sys

import matplotlib

matplotlib.use('Agg')

import matplotlib.pyplot as plt
import numpy as np


# Set import paths
DIR_REPO = Path(__file__).resolve().parents[2]
DIR_EXTERNAL = DIR_REPO / 'external'
for path in (DIR_REPO, DIR_EXTERNAL):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from sim_data_analyzer.batch_xr import collect_batch_rates_from_pkl
from sim_data_analyzer.xr_cache import encode_xr_attrs_json
from sim_data_analyzer.xr_io import load_xr, save_xr
from sim_data_analyzer.xr_spect import calc_xr_welch
from workflow_utils import build_job_index, load_job_records


def _get_weight_title(stage_spec):
    """Format iteration and weight overrides for figure titles."""
    title = f'Iteration {stage_spec["iteration"]}'
    weights = stage_spec.get(
        'experiment_overrides',
        {},
    ).get('wmat_multipliers', [])
    if not weights:
        return title
    weight_text = ', '.join(
        f'{item["pre"]}->{item["post"]} x{item["mult"]:g}'
        for item in weights
    )
    return f'{title}; {weight_text}'


def _plot_seed_psd(psd_xr, seed, fpath_out, stage_spec, dpi):
    """Plot all active connected populations for one seed."""
    psd_seed = psd_xr.sel(seed_main=seed)
    fig, ax = plt.subplots(figsize=(10, 6))

    # Plot one analyzer-produced PSD curve per active population
    for pop in psd_seed.coords['pop'].values:
        row = psd_seed.sel(pop=pop)
        ax.plot(
            np.asarray(row.coords['freq'].values, dtype=float),
            np.asarray(row.values, dtype=float),
            label=str(pop),
            lw=1.5,
        )

    ax.set_xlabel('Frequency (Hz)')
    ax.set_ylabel('PSD')
    ax.set_title(
        f'Connected L2 rate PSD: seed {int(seed)}\n'
        f'{_get_weight_title(stage_spec)}'
    )
    ax.grid(alpha=0.2)
    ax.legend(ncol=2)
    fig.tight_layout()
    fig.savefig(fpath_out, dpi=dpi, bbox_inches='tight')
    plt.close(fig)


def _plot_psd_batch(psd_xr, stage_dir, stage_spec, dpi):
    """Plot one connected-population PSD figure per seed."""
    dirpath_out = Path(stage_dir) / 'processed' / 'psd'
    dirpath_out.mkdir(parents=True, exist_ok=True)
    outputs = []

    # Keep seed-specific plots separate for direct fixture comparison
    for seed in psd_xr.coords['seed_main'].values:
        fpath_out = dirpath_out / f'psd_seed_{int(seed)}.png'
        _plot_seed_psd(
            psd_xr,
            seed,
            fpath_out,
            stage_spec,
            dpi,
        )
        outputs.append(fpath_out.relative_to(stage_dir).as_posix())
    return outputs


def load_stage_result(stage_dir, stage_spec, **processor_params):
    """Load persisted connected-model PSD output for resume."""
    fpath = Path(stage_dir) / 'processed' / 'psd.nc'
    return load_xr(fpath, data_type='dataarray', load=True)


def process_stage(stage_dir, stage_spec, pop_names, t_limits,
                  dt_bin=0.005, tau_smooth=0.05,
                  psd_win_len=1, psd_win_overlap=0.5,
                  psd_fmin=0, psd_fmax=50,
                  psd_average='median', plot_dpi=200):
    """Collect connected rates, calculate Welch PSD, and plot seeds."""
    stage_dir = Path(stage_dir)
    dirpath_processed = stage_dir / 'processed'
    dirpath_processed.mkdir(parents=True, exist_ok=True)
    records = load_job_records(stage_dir)
    job_idx_xr = build_job_index(records, stage_spec['batch_params'])

    # Collect active-population rates directly through sim_data_analyzer
    fpath_rates = dirpath_processed / 'rate_dynamics.nc'
    rates_xr = collect_batch_rates_from_pkl(
        job_idx_xr,
        stage_dir / 'sim_results' / 'pkl',
        fname_templ='data_{job:05d}_*.pkl',
        t_limits=tuple(t_limits),
        dt_bin=dt_bin,
        tau_smooth=tau_smooth,
        avg_cells=True,
        pop_names=list(pop_names),
        cache_path=fpath_rates,
        lazy=False,
        load=True,
        skip_missing=False,
        overwrite=True,
    )

    # Calculate the canonical PSD through sim_data_analyzer
    psd_xr = calc_xr_welch(
        rates_xr,
        win_len=psd_win_len,
        win_overlap=psd_win_overlap,
        fmin=psd_fmin,
        fmax=psd_fmax,
        average=psd_average,
        compute=True,
        store_proc_info=True,
    )
    psd_xr.attrs['stage_spec_hash'] = stage_spec['stage_spec_hash']
    fpath_psd = dirpath_processed / 'psd.nc'
    save_xr(encode_xr_attrs_json(psd_xr), fpath_psd)

    # Plot seed-specific diagnostics and declare every durable artifact
    outputs = [
        'processed/rate_dynamics.nc',
        'processed/psd.nc',
    ]
    outputs.extend(_plot_psd_batch(
        psd_xr,
        stage_dir,
        stage_spec,
        plot_dpi,
    ))
    return psd_xr, outputs
