# TC loops 1: per-cell firing rates

## Input

The analysis uses
`data/tc_loops_1/cell_inp_stats_xr_combined.nc`, collected from:

`exp_results/batch_rxbkg_state1_mech1/net_newsec_var_seed_frzconns/exp_thal_nseed_5_nfrz_14_t_10.0_15.0_wmult_0.25_ee_0.5`

The dataset contains five seeds, 14 frozen-connection conditions, and 721
cells from the seven thalamic populations. The analyzed `rate` field covers
10-15 s of simulation time.

## Analysis

`code/plot_cell_rates.py` pools finite per-cell rates over seeds for each
condition and population. It plots normalized rate histograms in four panels:

- Reference
- Single loops
- TC combinations
- IREM combinations

The editable parameters at the top of the script follow the previous
cell-rate analysis. In particular, `SHARE_BINS = 0` gives every condition its
own bins, while `SHARE_BINS = 1` uses common bins across conditions within a
population. The default plot uses logarithmic rate bins. Zero-rate cells are
excluded from those log histograms and summarized separately in
`artifacts/tc_loops_1/silent_frac.csv`.

Figures are written to a parameter-named folder under
`artifacts/tc_loops_1/`, with one `rate_distribution_<POP>.png` file per
population.

`code/make_rate_err.py` writes `artifacts/tc_loops_1/pop_rate_err.csv`.
Each population entry is the signed population-rate error relative to target
state 1, shown as mean `+-` sample standard deviation over seeds. Rates are
first averaged over the cells in each population for each seed. Silent cells
are included. The first two columns give the freezing-group name and its
active projections.

`code/plot_cell_scatter.py` draws one single-panel cell-rate scatter per
selected population. Each freezing group has its own color. Seeds are placed
in nearby point columns separated by `DX`; setting `DX = 0` stacks all seed
columns. `JITTER_STD` adds reproducible Gaussian horizontal point jitter.
`SHOW_SEED_MEAN` controls the short seed-level mean dashes, while
`SHOW_SEED_AVG` controls the wider mean-over-seeds dash. The black dashed line
marks the target rate. `PLOT_ALL_POPS` switches between one figure per
population and a shared multi-panel figure. `LOG_YSCALE` and `Y_LIMITS`
control the vertical axis. Zero-rate points cannot appear on a log axis, but
they remain included in both kinds of means.

## Run

From the repository root:

```bash
conda activate netpyne
python dev_scratch/thal_frz_2/code/plot_cell_rates.py
python dev_scratch/thal_frz_2/code/make_rate_err.py
python dev_scratch/thal_frz_2/code/plot_cell_scatter.py
```
