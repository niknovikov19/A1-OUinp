# Grid search regions

`grid_regions.csv` summarizes the search regions in
`exp_configs/batch_rxbkg_unconn_state1_mech1/pops_inpsur_newsec_var_drxe_rxi/regions`.
Each row describes one neuronal population. The regions were fitted to firing-rate
maps produced by the earlier rectangular `(rxe, rxi)` sweeps and are then used to
define smaller, population-specific parallelogram grids.

Here, `rxe` and `rxi` are the rates of the excitatory and inhibitory background
spike inputs, respectively. Region coordinates are stored in the raw input-rate
units used by the simulation (Hz). The firing-rate contour levels are output
population rates in Hz.

## Source rectangular search

The source experiment is
`exp_configs/batch_rxbkg_unconn_state1_mech1/pops_inpsur_newsec_var_rxe_rxi`.
Its `batch_params.py` constructs independent, linearly spaced `rxe` and `rxi`
axes. A simulation is run for every pair. Its `exp_cfg.py` assigns that pair to
the excitatory and inhibitory background inputs of every population selected for
the run. Post-processing calculates population firing rates, CVs, and voltage
statistics over the configured time window.

In `proc_batch.ipynb`, the saved job configurations are used to reconstruct the
mapping from `(rxe, rxi)` to job ID. The corresponding result JSON files are read
into an xarray dataset, producing a two-dimensional firing-rate map for each
population.

The source experiment and result subdirectory are recorded in each region JSON as
`params.exp_name` and `params.exp_name_sub`. The latter is copied verbatim to the
CSV as `exp_name_sub`.

## Fitting a region

The notebook fits two firing-rate contours to each population map:

- A low-rate contour, normally `r_left = 0.5` Hz.
- A high-rate contour given by the selected tuning level. In the current notebook
  this is `target_rates[pop]`, loaded from `target_state_1.csv`.

The current procedure applies a Gaussian filter with `smooth_sigma = 1` grid cell
for contour extraction only; the displayed and saved simulation measurements are
not replaced by the smoothed values. For each level, the longest contour segment
with at least four points is retained. If either contour is absent, the population
is skipped.

The high-rate contour is approximated by the line connecting its points with the
smallest and largest `rxe`. Its slope is

```text
q = (rxi2 - rxi1) / (rxe2 - rxe1)
```

and is rounded to three decimal places. This is saved as `rxi_rxe_slope`.
The corresponding line can be written as

```text
rxe(rxi) = rxe1 + (rxi - rxi1) / q
```

For every point on the low-rate contour, the notebook computes the horizontal
distance to that line and takes the largest value as `d0`. The fitted strip is
expanded according to `r_margins = [marg_l, marg_r]`:

```text
strip width = d0 * (1 + marg_l)
right-edge shift = d0 * marg_r
```

Thus, `marg_l` adds space on the low-rate side and `marg_r` moves the high-rate
edge farther into the high-rate side. The lower inhibitory coordinate initially
comes from the bottom of the source grid, and the upper coordinate comes from the
high-rate contour endpoint. If the fitted lower-right point has negative `rxe`,
the edge is clipped at `rxe = 0` and its `rxi` is adjusted along the fitted line.

Before saving, `rxe0`, `rxi0`, `drxe`, and `drxi` are converted back from the
notebook's plotting scale (`k = 1e-3`) to Hz and truncated to a precision of 10 Hz.
The slope is dimensionless because both axes use the same scale.

The checked-in JSON files reflect two versions of this exploratory procedure.
The cortical, NGF, and IT2 files store manually selected fixed high-rate levels
and margins and do not record `smooth_sigma`; the earlier notebook procedure used
the unsmoothed map and selected the leftmost contour segment. The newer thalamic
files store population-specific target levels, `smooth_sigma = 1`, and use the
longest contour segment. Consequently, the `params` object in each JSON is the
authoritative provenance for that saved region; rerunning the current notebook
with the current target-rate table need not reproduce every older region exactly.

## CSV columns

| Column | Meaning and source |
| --- | --- |
| `pop_name` | Population key under the JSON `regions` object. |
| `rxe_min`, `rxi_min` | Values encoded after `rxmin` in the source `exp_name_sub`. They are the lower bounds of the original rectangular sweep. |
| `rxe_max`, `rxi_max` | Values encoded after `rxmax` in the source `exp_name_sub`. They are the upper bounds of the original rectangular sweep. |
| `n_rxe`, `n_rxi` | Values encoded after `sz`; the numbers of samples on the original rectangular `rxe` and `rxi` axes. |
| `t_start`, `t_end` | Values encoded after `t`; the start and end, in seconds, of the source simulation interval used to calculate rates and other metrics. |
| `rxe0` | Excitatory coordinate of the fitted strip's right edge at its lower inhibitory boundary. It is not the minimum `rxe` of the strip. |
| `rxi0` | Lower inhibitory coordinate of the fitted strip. |
| `drxe` | Horizontal width of the fitted strip. |
| `drxi` | Inhibitory-axis height of the fitted strip. |
| `rxi_rxe_slope` | Slope `q = delta rxi / delta rxe` of the slanted strip edges. |
| `r_levels` | Output firing-rate contour levels used to fit the strip. The first entry is the low level; the second is either one common high level or a list ordered like `params.pops`. |
| `r_margins` | Dimensionless `[marg_l, marg_r]` expansion factors used around the two contours. |
| `exp_name_sub` | Source rectangular-sweep result path, relative to `exp_results/<params.exp_name>`. |

There is an important naming-unit detail. `pops_inpsur_newsec_var_rxe_rxi/exp_cfg.py`
encodes `rxmax` as `RXE_MAX / 1000` and `RXI_MAX / 1000`, but encodes `rxmin`
without that division. The CSV deliberately preserves the path tokens: for
example, `rxe_max = 25` denotes a source maximum of 25,000 Hz, whereas
`rxe_min = 1` denotes a source minimum of 1 Hz. The region geometry columns are
all stored directly in Hz.

The `t_start` and `t_end` values describe the source sweep used to fit the region.
They are not the analysis window of the later parallelogram search. In the current
`pops_inpsur_newsec_var_drxe_rxi/exp_cfg.py`, simulations last 12 seconds and
metrics are calculated over 7--12 seconds.

## Use in `pops_inpsur_newsec_var_drxe_rxi`

The experiment selects a population group through `EXP_LABEL` and `POPS_USED`.
`exp_cfg.py` loads `regions/regions_<EXP_LABEL>.json` into
`cfg.drxe_rxi_regions`. Background input weights come from the separate weight
JSON; the region controls rates, not weights.

`batch_params.py` creates two index parameters, `drxe_num` and `rxi_num`. With the
current `N_DRXE = N_RXI = 20`, this gives a nominal 20 by 20 grid. For each
population, `post_update()` maps those common indices into that population's
physical region. For `N_e = N_DRXE`, `N_i = N_RXI`, indices `m` and `j`, and
`q = rxi_rxe_slope`, the mapping is equivalent to

```text
rxi(j) = rxi0 + j * drxi / (N_i - 1)
rxe_right(j) = rxe0 + (rxi(j) - rxi0) / q
rxe(m, j) = rxe_right(j) - drxe + m * drxe / (N_e - 1)
```

Therefore, `rxi_num` moves from the bottom to the top of the parallelogram, while
`drxe_num` moves horizontally from its left edge to its right edge. A value of
`drxe_num` is an index across the fitted strip, despite its name; it is not itself
an input-rate increment.

The selected `rxe` and `rxi` values are assigned to the population's excitatory
and inhibitory background spike inputs. Exact zeros are replaced by `1e-3` Hz.
A population with either non-positive rate is removed from that job; if no
population remains, `cfg.need_run` is set to zero. For a multi-population run, one
index pair is shared across populations, but each population receives a different
physical rate pair because it has its own fitted geometry.

Only the five geometry fields under `regions[pop]` are used by this mapping.
The source bounds, source grid sizes, source time window, contour levels, margins,
and source path are provenance metadata. `grid_regions.csv` itself is a paper and
inspection artifact and is not read by the simulation.
