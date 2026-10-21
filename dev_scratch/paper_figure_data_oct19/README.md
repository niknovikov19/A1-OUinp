# Paper figure data investigation

Start with [figure_data_map.md](figure_data_map.md) for the panel-by-panel sources, exact experiment paths, measurement definitions, and verification limits. All four figures and required result batches are accounted for.

The follow-up [supplementary simulation inventory](supplementary_simulations.md) assesses the six relevant “Simulations (TODO)” items, existing controls, missing numerical traces, and optional acquisition/rerun plans.

Saved seed-1000 raster examples with readable filenames are collected in
[evidence/rasters/](evidence/rasters/README.md), with a CSV source manifest.

## Folder layout

| Folder | Contents |
|---|---|
| [code/](code/) | Bounded snapshot reader and offline regeneration script |
| [data/tables/](data/tables/) | Figure inventory, population rates, error statistics, and thalamic corrections |
| [data/inventories/](data/inventories/) | Experiment/file inventories, validation results, saved cfg summary, and read audits |
| [data/inputs/](data/inputs/) | Copies of local simulation input files |
| [data/snapshots/](data/snapshots/) | Small result summaries, representative saved cfgs, and source correction export |
| [evidence/paper/](evidence/paper/) | Extracted PDF text and rendered figure pages |
| [evidence/notebooks/](evidence/notebooks/) | Extracted notebook source/text, saved plot images, and original grouped-plot code |
| [evidence/simulation/](evidence/simulation/) | Saved cortex modulation image |
| [evidence/rasters/](evidence/rasters/README.md) | One saved seed-1000 raster per selected supplementary condition and source manifest |
| [plots/](plots/) | Offline cortex and thalamus comparison plots |
| [notes/](notes/) | Original task and incremental findings log |
| `.runtime/` | Task-local Python dependencies and Matplotlib caches; ignored by Git |

## Key files

- [Figure inventory](data/tables/figure_inventory.csv): 17 panel/series entries.
- [Population rates](data/tables/population_rates.csv): 3,354 records with seeds, windows, targets, errors, and original source paths.
- [Thalamic corrections](data/tables/thalamic_corrections.csv): 105 values in controller-output and current units.
- Per-population error table: [cortical panel](data/tables/population_error_table_cortex.csv), [thalamic panel](data/tables/population_error_table_thalamus.csv), and [caption](notes/population_error_table_caption.md).
- Uncorrected thalamic fading comparison: [population-rate table](data/tables/population_rate_table_thalamus_fading.csv) and [caption and source documentation](notes/thalamus_fading_table_caption.md); two unavailable fading conditions remain blank.
- [Parameter-only thalamic fading pilot](notes/thalamus_parameter_pilot.md): sequential two-seed runs using the existing experiment functions, with saved configurations and per-population rate summaries.
- [Full IREM→TI fading run](notes/thalamus_irem_ti_full_run.md): 15 seeds and the archived `thal_all_fade` duration, population order, and background-seed mapping.
- [Validation](data/inventories/validation.json): checks for all ten experiments.
- [Findings log](notes/findings_log.md): investigation history and organization notes.
- [Original task](notes/task.md): scope and remote-filesystem constraints.
- [Artifact relocation map](data/inventories/artifact_locations.json): previous top-level names mapped to current locations.
- [Supplementary simulation inventory CSV](data/tables/supplementary_simulations_inventory.csv) and [data-readiness evidence](data/inventories/supplementary_data_readiness.json).

## Offline regeneration

Run from the repository root:

```bash
/home/nnovikov/conda_env/netpyne/bin/python dev_scratch/paper_figure_data_oct19/code/build_offline_inventory.py
```

This uses local snapshots and writes tables, validation results, and plots into their respective folders. [snapshot_summaries.py](code/snapshot_summaries.py), [inventory_supplementary_data.py](code/inventory_supplementary_data.py), and [collect_supplementary_rasters.py](code/collect_supplementary_rasters.py) access mounted results; do not rerun them just to inspect cached data.

Regenerate the formatted per-population table panels with `python3 dev_scratch/paper_figure_data_oct19/code/build_population_error_table.py`.

Regenerate the uncorrected thalamic fading table from local caches with
`/home/nnovikov/conda_env/netpyne/bin/python dev_scratch/paper_figure_data_oct19/code/build_thalamus_fading_table.py`.

PyMuPDF is preserved under `.runtime/python_deps/`. Illustrative A1 raw spikes and controller traces remain in their original locations and were deliberately left unread; the figure data map documents their paths and the available evidence.
