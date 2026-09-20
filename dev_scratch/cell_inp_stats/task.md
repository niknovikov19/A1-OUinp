# Input dataset structure

The data to process is an xarray dataset with:

```text
dimensions:   gid, pop_pre
coordinates:  gid, pop_pre, pop_post(gid)
variables:    n_pre, r_pre_mean, w_sum, wr_sum, r_pre_wmean,
              rate(gid), cv(gid)
```

Variables describe statistics of the inputs projecting onto a cell belonging to population `pop_post` from the cells belonging to `pop_pre`. Each `(gid, ...)` point corresponds to one post-synaptic cell.

Variables:

- `n_pre`: number of unique presynaptic GIDs with at least one included connection;
- `r_pre_mean`: unweighted mean rate of those presynaptic cells;
- `w_sum`: sum of all instantiated connection-record weights;
- `wr_sum`: sum of connection-record weights multiplied by the corresponding presynaptic-cell rates;
- `r_pre_wmean`: weight-averaged presynaptic rate, `wr_sum / w_sum`;
- `rate`, `cv`: rate and cv of a cell.

Below, the dataset is referred to as `ds`.

For testing, load `ds` from `dev_scratch/cell_inp_stats/test_data/single/cell_inp_stats_00000_seed_1000.nc`.


# Task

Create a CSV table where each row corresponds to a pair of populations. Omit population pairs without connections.

Columns:

- `pop_pre`, `pop_post` — names of pre/post populations.
- `sz_pre`, `sz_post` — sizes of the populations (number of cells).
- `r0_pre_avg`, `r0_pre_std`, `r0_post_avg`, `r0_post_std` — mean and standard deviation of the pre/post firing rates, computed across all cells of the corresponding populations.
- `npre_avg`, `npre_std` — mean and standard deviation of `ds['n_pre']`, computed across postsynaptic cells.
- `rpre_avg`, `rpre_std` — mean and standard deviation of `ds['r_pre_mean']`, computed across postsynaptic cells.
- `rpre_wmean_avg`, `rpre_wmean_std` — mean and standard deviation of `ds['r_pre_wmean']`, computed across postsynaptic cells. This measures the distribution across postsynaptic cells of the connection-weighted mean firing rate of their presynaptic partners.
- `drpre_wmean_avg`, `drpre_wmean_std` — mean and standard deviation across postsynaptic cells of
  `ds['r_pre_wmean'] - r0_pre_avg`.
  This measures how much the connection-weighted presynaptic rate seen by individual postsynaptic cells differs from the mean firing rate of the full presynaptic population.
- `wsum_avg`, `wsum_std` — mean and standard deviation of `ds['w_sum']`, computed across postsynaptic cells.
- `wrsum_avg`, `wrsum_std` — mean and standard deviation of `ds['wr_sum']`, computed across postsynaptic cells.
- `dinput_avg`, `dinput_std` — mean and standard deviation across postsynaptic cells of
  `ds['wr_sum'] - r0_pre_avg * ds['w_sum']`.
  This quantity is the difference between the rate-weighted input in the original connectivity and the input obtained if all presynaptic cells were replaced by cells firing at the population mean rate `r0_pre_avg`, while preserving the same instantiated connections and weights.

Use the same convention for standard deviation consistently for all columns.

Foe each (avg, std) pair, create an additional "cv" column, e.g. `wsum_cv = wsum_std / wsum_avg`
