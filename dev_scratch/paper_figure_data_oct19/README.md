# Paper figure data investigation

Start with [figure_data_map.md](figure_data_map.md) for the panel-by-panel sources, exact experiment paths, measurement definitions, and verification limits. All four figures and required result batches are accounted for.

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
| [plots/](plots/) | Offline cortex and thalamus comparison plots |
| [notes/](notes/) | Original task and incremental findings log |
| `.runtime/` | Task-local Python dependencies and Matplotlib caches; ignored by Git |

## Key files

- [Figure inventory](data/tables/figure_inventory.csv): 17 panel/series entries.
- [Population rates](data/tables/population_rates.csv): 3,354 records with seeds, windows, targets, errors, and original source paths.
- [Thalamic corrections](data/tables/thalamic_corrections.csv): 105 values in controller-output and current units.
- Per-population error table: [cortical panel](data/tables/population_error_table_cortex.csv), [thalamic panel](data/tables/population_error_table_thalamus.csv), and [caption](notes/population_error_table_caption.md).
- [Validation](data/inventories/validation.json): checks for all ten experiments.
- [Findings log](notes/findings_log.md): investigation history and organization notes.
- [Original task](notes/task.md): scope and remote-filesystem constraints.
- [Artifact relocation map](data/inventories/artifact_locations.json): previous top-level names mapped to current locations.

## Offline regeneration

Run from the repository root:

```bash
/home/nnovikov/conda_env/netpyne/bin/python dev_scratch/paper_figure_data_oct19/code/build_offline_inventory.py
```

This uses local snapshots and writes tables, validation results, and plots into their respective folders. Only [snapshot_summaries.py](code/snapshot_summaries.py) accesses mounted results; do not rerun it just to inspect cached data.

Regenerate the formatted per-population table panels with `python3 dev_scratch/paper_figure_data_oct19/code/build_population_error_table.py`.

PyMuPDF is preserved under `.runtime/python_deps/`. Illustrative A1 raw spikes and controller traces remain in their original locations and were deliberately left unread; the figure data map documents their paths and the available evidence.
