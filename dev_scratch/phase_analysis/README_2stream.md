# Two-Stream Phase Analysis

`run_2stream.py` analyzes batches with two pulse streams defined by
`f`, `amp1`, `amp2`, and `dt0`.

`precompute_csd_2stream.py` derives `csd_xr_combined.nc` from the active
`run_2stream.py` experiment's `lfp_xr_combined.nc`.

## What It Does

- Reads combined rates from `dev_scratch/artifacts/net_2pulses_var_seed_f_amps_dt0/<EXP_NAME>/rates_xr_combined.nc`.
- Reads precomputed LFP/CSD from `lfp_xr_combined.nc` or `csd_xr_combined.nc`
  when `SIGNAL_KIND` is set to `lfp` or `csd`.
- Reads `PulseSeq1` and `PulseSeq2` from matching copied `dev_scratch/.../netpar` files when available.
- Uses `PulseSeq1` starts for pulse-time phase and coefficient fits.
- Masks both pulse streams before spectra, phase, and coefficient analysis.
- Streams one `(pop, f, dt0)` slice at a time: compute, save NetCDF, save plots, then release.
- If `NEED_RECALC = 0`, existing NetCDF/CSV products are reused and only missing trace slices are recomputed.

The first-run default is `POP_VALUES = ['IT2', 'PV2']`. Set `POP_VALUES = 'all'`
or `None` for all populations.

The script looks for copied `netpar` files under the matching `dev_scratch`
artifact folder. If they are absent, it builds the two pulse schedules from the
batch timing parameters in `run_2stream.py`.

For LFP/CSD analyses:

- Run `precompute_csd_2stream.py` once before `SIGNAL_KIND = 'csd'`.
- Use `Y_VALUES = [100]` or another list of depths to limit analysis.
- `Y_VALUES = None` analyzes all depths.
- Output filenames use the numeric `y` trace value instead of population names.

## Output Layout

Outputs are saved under:

`dev_scratch/phase_analysis/artifacts/<EXP_NAME>/<param_dir>/`

Each `(f, dt0)` slice gets a mid-level folder:

- `f_5_dt0_0/`
- `f_5_dt0_15/`

Each slice contains:

- `params.json`: full run parameters plus the active `f` and `dt0`.
- `block_metrics.csv`: one row per pop, seed, amp pair, and time block.
- `condition_metrics.csv`: seed-balanced summaries for each `(amp1, amp2)`.
- `pooled_amp1_metrics.csv`: summaries by `amp1`, pooled over `amp2 + seed`.
- `pooled_amp2_metrics.csv`: summaries by `amp2`, pooled over `amp1 + seed`.
- `phase_events/<pop>.nc`: pulse-time phases and complex coefficients.
- `complex_spectrogram/<pop>.nc`: time-frequency fitted complex coefficients.
- `epoch_signals/<pop>.nc`: pulse-triggered signal averages around `PulseSeq1` starts.

## Cache And Replotting

`NEED_RECALC` controls whether saved products are reused.

- `NEED_RECALC = 1`: recompute fitted data, CSVs, NetCDFs, and plots.
- `NEED_RECALC = 0`: read existing `phase_events`, `complex_spectrogram`,
  `epoch_signals`, and CSV files when present; recompute only missing trace slices.

Reloaded spectra are rebuilt from saved complex spectrogram coefficients, so they
are intended for practical replotting and may not be byte-identical to the
original block-spectrum summaries.

## CSV Columns

`block_metrics.csv` has one row per population, seed, `(amp1, amp2)`, and
time block.

- `job_id`: source batch job.
- `pop` or `y`: analyzed rate population or future LFP/CSD channel.
- `seed_main`: simulation seed.
- `f`: drive frequency used for fitted spectra and pulse-time phase fits.
- `dt0`: stream-2 offset from stream-1 pulse starts, in the batch units.
- `amp1`, `amp2`: pulse strengths for `PulseSeq1` and `PulseSeq2`.
- `block_idx`, `block_t0`, `block_t1`: nonoverlapping analysis block index and time limits.
- `n_valid_time`: unmasked samples left in the block after masking both streams.
- `p_band`: total fitted power in `BROAD_BAND`.
- `p_target`: fitted power around the drive frequency.
- `concentration`: `p_target / p_band`; larger values mean more power concentrated near the drive.
- `centroid_offset`: spectral centroid minus `f0`; values near zero mean the band is centered near the drive.
- `width`: spectral spread inside `BROAD_BAND`; smaller values mean a narrower spectral concentration.

`condition_metrics.csv` averages block summaries within each seed, then averages
seeds equally for every `(amp1, amp2)`.

- `n_seed`: number of seeds contributing to the condition mean.
- `n_blocks`: total analyzed blocks across contributing seeds.
- `n_pulses`: `PulseSeq1` starts available for phase/coefficient fits.
- `n_valid_phase`: pulse starts with a valid local sinusoid fit.
- `z_mean_re`, `z_mean_im`: real and imaginary parts of mean `z = a - i b` at `PulseSeq1` starts.
- `z_mean_abs`: magnitude of the mean complex coefficient.

`pooled_amp1_metrics.csv` and `pooled_amp2_metrics.csv` use the same metric
columns, but collapse the other amplitude dimension within seed before averaging
seeds. `n_source_conditions` reports how many source amplitude conditions were
pooled.

For phase locking, start with `concentration`, `width`, `centroid_offset`,
`z_mean_abs`, and `n_valid_phase`. Stronger locking usually means higher
`concentration`, lower `width`, `centroid_offset` near zero, and larger
`z_mean_abs` relative to `(amp1=0, amp2=0)`. Use `dt0` to compare whether the
same amplitude pair locks differently when the two streams are shifted. Always
check `n_valid_phase` and `n_valid_time` before trusting a condition.

## Plot Families

Full-combo plots use one curve or panel per `(amp1, amp2)` pair.

- `spectra_raw_logratio/<pop>.png`: raw masked spectra and `log(S / S00)`.
- `band_metrics/<pop>.png`: block points, seed means, and condition means.
- `phase_density/<pop>.png`: phase density and enrichment versus `(0, 0)`.
- `coeff_clouds/<pop>.png`: complex coefficient clouds with null contours.

Pooled plots collapse one amplitude dimension:

- `pooled_amp1/.../<pop>.png`: condition axis is `amp1`, pooled over `amp2 + seed`.
- `pooled_amp2/.../<pop>.png`: condition axis is `amp2`, pooled over `amp1 + seed`.

Grid plots use the `(amp1, amp2)` grid:

- `grid_band_metrics/<pop>.png`: heatmaps for band power, concentration, centroid offset, and width.
- `grid_phase_metrics/<pop>.png`: heatmaps for mean coefficient summaries and valid phase counts.
- `grid_spectra_logratio/<pop>.png`: condition-by-frequency heatmap of `log(S / S00)`.

Epoch plots show pulse-triggered signal averages:

- `epoch_signals/<pop>.png`: seed-balanced epoch means for all `(amp1, amp2)` pairs.
- If `EPOCH_SUBTRACT_GLOBAL_MEAN = 1`, the plotted trace subtracts each job trace's global mean.
- The global mean is computed over the analysis window after erasing peri-stim bins around both streams.

Line colors encode pulse amplitudes by sorted amplitude index:

- black: `(amp1=0, amp2=0)`.
- red scale: increasing `amp1` with `amp2=0`.
- blue scale: increasing `amp2` with `amp1=0`.
- violet: both amplitudes are high.

## How To Read

Use `(amp1=0, amp2=0)` as the null reference within each `(f, dt0)` folder.

- A narrow rise near `f0` in `log(S / S00)` suggests frequency-specific locking.
- Higher concentration with lower width means power is more focused near the drive.
- Phase enrichment shows where pulse-start phases are over- or under-represented relative to null.
- Coefficient clouds shifted away from the null contours suggest a coherent locked component.
- Compare `f_5_dt0_0` and `f_5_dt0_15` to see how stream timing changes the same amplitude grid.
