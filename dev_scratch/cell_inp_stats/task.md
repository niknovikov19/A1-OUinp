# Task

For each pair of populations `P1` and `P2`, analyze distributions of input metrics across cells belonging to `P2`. The metrics describe `P1 -> P2` inputs and should be computed without saving or gathering the full connectivity matrix.

# Metric definitions

For a postsynaptic cell `c2` belonging to `P2`, group all included incoming NetPyNE connection records by presynaptic GID `g` belonging to `P1`.

If several connection records exist for the same cell pair, including separate receptor components or multiple contacts, define their aggregate weight as:

$$
W_{g,c2} = \sum_{k \in g \rightarrow c2} w_k
$$

Calculate:

- `n_pre`: number of unique presynaptic GIDs with at least one included `P1 -> c2` connection;
- `r_pre_mean`: unweighted mean rate of those presynaptic cells;
- `w_sum`: sum of all instantiated connection-record weights;
- `wr_sum`: sum of connection-record weights multiplied by the corresponding presynaptic-cell rates;
- `r_pre_wmean`: weight-averaged presynaptic rate, `wr_sum / w_sum`.

Equivalently:

$$
\mathrm{r\_pre\_mean}_{c2} =
\frac{1}{N}\sum_g r_g
$$

$$
\mathrm{w\_sum}_{c2} =
\sum_g W_{g,c2}
$$

$$
\mathrm{wr\_sum}_{c2} =
\sum_g W_{g,c2}r_g
$$

$$
\mathrm{r\_pre\_wmean}_{c2} =
\frac{\mathrm{wr\_sum}_{c2}}{\mathrm{w\_sum}_{c2}}
$$

For cells with no `P1` inputs, use `n_pre = 0`, `w_sum = 0`, `wr_sum = 0`, and `NaN` for both rate means. Also use `NaN` for `r_pre_wmean` whenever `w_sum == 0`.

# Receptor-weight aggregation

Do not store a separate synaptic-mechanism dimension in the first prototype. Receptor-specific records may be summed because this analysis is primarily concerned with normalized distribution shapes across cells.

This aggregation is valid only when the receptor-weight mixture is constant within each `(pop_pre, pop_post)` pair. When it can be done cheaply, check that assumption using the instantiated weights:

1. For each logical `(pre_gid, post_gid)` pair, sum its records by synaptic mechanism to obtain `W_m`.
2. Form the normalized receptor-weight vector `q_m = W_m / sum_m(W_m)`, filling missing mechanisms with zero.
3. Verify that `q_m` is constant across all cell pairs belonging to the same `(pop_pre, pop_post)` pair, within a small numerical tolerance.
4. Perform this check across MPI ranks by exchanging only small per-population-pair summaries, such as minima, maxima, counts, and a few failing GID examples.
5. Raise an informative error when the constant-ratio assumption fails. Report the affected population pair, mechanisms, ratio ranges, and representative cell pairs.

The validation must reuse the cell-pair grouping and instantiated connection records already needed for the metric calculation. Update compact ratio minima/maxima and example accumulators while finalizing those groups; do not scan all connections a second time or retain ratios for every cell pair. If a separate pass or other significant unavoidable computation or memory is required, omit the validation from the first prototype and record that it was skipped. Metric calculation takes priority over this guardrail.

The check should naturally detect receptor-specific section weight-normalization differences. Co-location can also be reported as a diagnostic, but constant instantiated-weight ratios are the required invariant.

Synaptic time constants are intentionally not included in `w_sum` or `wr_sum`. When receptor ratios and kinetics are constant within a population pair, kinetics contribute only a common multiplicative factor and therefore do not change normalized distribution shapes. They also cancel from the consistently weighted ratio `r_pre_wmean`.

# Weight semantics

Use the instantiated nominal `conn['weight']` values. These include the scaling and section weight normalization already applied during NetPyNE network construction.

Ignore connection fading in the first prototype. Do not attempt to calculate time-dependent or interval-effective weights. Record clearly in the dataset metadata that the metrics use nominal instantiated weights and ignore dynamic modulation.

# Rates and CVs

Use the same calculation interval and conventions as the other experiment metrics:

- interval: `cfg.t0_calc / 1000` through `cfg.duration / 1000`, in seconds;
- CV minimum: `nspikes_min = 3`;
- per-cell CV is `NaN` when there are too few spikes.

Store each analyzed cell's firing rate and CV as `rate(gid)` and `cv(gid)`.

# Frozen populations

Support a `CELL_INP_STATS_USE_FRZ` flag:

- `0` for the full model analyzed after the full fade;
- `1` when the same analysis is used with surrogate populations.

When included, preserve frozen population names such as `IT2frz` as distinct `pop_pre` values. Do not merge them silently with their base populations. The frozen populations produced by `SubnetParamBuilder2` are NetStim point-cell populations: they have population membership, global GIDs, and spike output, so include them when `CELL_INP_STATS_USE_FRZ` is enabled.

Do not interpret `CELL_INP_STATS_USE_FRZ` as a general instruction to include every NetStim source. Exclude ordinary per-target stimulus NetStims whose connection records use the literal `preGid == 'NetStim'` and cannot be resolved to a presynaptic population cell and GID.

# Distributed computation

The model has 43 biological populations, approximately 10k cells, and normally runs on approximately 60 MPI ranks. Compute the summaries while each rank still owns its instantiated local network. Never gather or save the full connectivity matrix.

Use the following distributed strategy:

1. Immediately after `sim.runSim()`, calculate rates and CVs for cells local to each rank.
2. Exchange only the compact global `gid -> rate` and required `gid -> population` information. Every rank needs rates for remote presynaptic GIDs connected to its local postsynaptic cells.
3. Scan incoming connections only for local postsynaptic cells and calculate their per-cell summaries.
4. Gather only the compact per-cell summaries and receptor-ratio validation summaries to rank 0.
5. Construct the final xarray dataset on rank 0 and leave it available for the existing result-saving stage.

Add a generic all-ranks hook to `run_exp.py`, called after `sim.runSim()` and before `sim.gatherData()`. A suggested interface is:

```python
sim.runSim()
if hasattr(cfg_mod, 'post_run_parallel'):
    cfg_mod.post_run_parallel(sim)
sim.gatherData()
```

Define `post_run_parallel(sim)` in the experiment configuration. The existing rank-0 `post_run(sim)` should save the assembled result using the normal output routine.

# Dataset structure

Save the result as an xarray dataset with:

```text
dimensions:   gid, pop_pre
coordinates:  gid, pop_pre, pop_post(gid)
variables:    n_pre, r_pre_mean, w_sum, wr_sum, r_pre_wmean,
              rate(gid), cv(gid)
```

Use global GIDs, never local within-rank cell indices. Store population names directly as string coordinates; do not introduce numerical population IDs. Encode strings in a NetCDF-compatible fixed-width representation where appropriate.

Include useful metadata such as:

- calculation interval;
- `nspikes_min`;
- `include_frz`;
- weight semantics;
- statement that dynamic modulation was ignored;
- receptor-ratio tolerance and validation summary;
- simulation seed and relevant runtime parameters.

# Integration

Implement the reusable calculation and dataset-building functionality in `utils/cell_inp_stats.py`.

Add the analysis to `exp_configs/batch_rxbkg_state1_mech1/net_newsec_var_seed/exp_cfg.py`. Use two ordinary experiment flag variables:

- `CELL_INP_STATS_ON` enables the analysis and its result saving;
- `CELL_INP_STATS_USE_FRZ` controls whether named `*frz` presynaptic populations are included.

Do not place the analysis-enable flag under the `out` runtime branch. In this full-model configuration, set `CELL_INP_STATS_USE_FRZ = 0`.

Saving should follow the existing directory, filename, metadata, and workflow-output conventions used by the other analyses. Keep `saveCellConns = False`.

The results must be batch-collectable. Copy `collect_batch_results.py` into `net_newsec_var_seed` from a neighboring experiment and adapt it to collect these per-job NetCDF datasets. Rely on `sim_data_analyzer` batch/xarray utilities whenever possible.

# Testing

Full simulations and MPI are not available in this environment. For now, use single-process unit tests and smoke runs with small synthetic or stub networks. Do not claim that rank-local ownership, inter-rank exchange, or multi-rank assembly has been tested here; validate those later when access to the normal simulation environment is available.

Cover at least:

- noncontiguous global GIDs, without assuming that a GID is a positional index;
- separate receptor records with constant ratios;
- if ratio validation is retained, a receptor-ratio violation that produces a useful error;
- repeated records or contacts from the same presynaptic GID;
- cells with no inputs and zero total weight;
- silent cells and cells with too few spikes for CV;
- inclusion and exclusion of `*frz` populations;
- correct final dataset coordinates, shapes, values, metadata, and NetCDF round-trip;
- batch collection of several synthetic per-job datasets.

In the simulation environment, subsequently test the MPI hook, remote presynaptic GID/rate lookup, compact cross-rank assembly, and ratio-summary reduction on multiple ranks.
