# Per-population error table caption

**Table Sx. Population-specific firing-rate errors across model configurations.** (A) Cortical populations; (B) thalamic populations. Target firing rates are shown in Hz. Each setup column reports the mean signed firing-rate error ± sample standard deviation across 15 model realizations (random seeds 1000–1014). For each realization, the error is the population's mean firing rate minus its target rate; positive values indicate firing above target. All errors and standard deviations are in Hz and are rounded to two decimal places. All 36 cortical and seven thalamic populations are included.

In the isolated cortical and thalamic models, inputs from the other subcircuit were replaced by fixed-rate Poisson surrogates. The all-surrogate setup also replaced recurrent inputs within the evaluated subcircuit. The fully recurrent setup retained recurrent connectivity within that subcircuit. For cortex, the E–E surrogate setup replaced excitatory-to-excitatory connections with surrogates, and the faded setup restored those recurrent connections after settling with surrogate inputs. For thalamus, own correction denotes constant current corrections learned separately for each realization, and median correction denotes the same population-specific median corrections applied across realizations. The full thalamocortical circuit column reports the corresponding populations in the coupled model, using E–E fading and median thalamic corrections.

Firing rates were averaged over 7–10 s for all isolated cortical setups and the all-surrogate thalamic setup, 200–220 s for the other isolated thalamic setups, and 15–20 s for the full thalamocortical circuit. In the own-correction setup, feedback was locked at 160 s, before the evaluation interval.

## Files and reproduction

- Panel A: [Cortex CSV](../data/tables/population_error_table_cortex.csv).
- Panel B: [Thalamus CSV](../data/tables/population_error_table_thalamus.csv).
- Source: [cached per-seed rates](../data/tables/population_rates.csv). The full-circuit column uses the 15-seed `a1_errors` experiment, not the separate illustrative 3-seed run.
- Regenerate both panels from the repository root with `python3 dev_scratch/paper_figure_data_oct19/code/build_population_error_table.py`.
- The CSVs contain formatted mean ± SD cells. Unrounded per-seed values and numeric mean/SD columns remain available in `population_rates.csv` and `rate_error_statistics.csv` under `data/tables/`.
