# Phase Analysis Scratch Scripts

This folder contains standalone scripts for masked phase/spectral analysis of pulse-forcing experiments.

## Current script

`run_priority1.py` implements the first analysis pass from `dev_scratch/phase_plan.md`.

- Reads combined xarray outputs from `dev_scratch/artifacts/...`.
- Reads the saved `PulseSeq` schedule from the matching `exp_results/.../netpar` folder.
- Masks each pulse interval plus padding in every condition, including `amp=0`.
- `PULSE_PAD` can be scalar or `(before, after)` in seconds.
- Uses `analysis.phase_utils.spect_proc` for local fitted spectra, phases, and coefficients.
- Defaults to rates; set `POP_VALUES = 'all'` or `None` to analyze all populations.

## Output folders

Each run writes to a parameterized signal folder, for example:

`rates_pop_NGF2_pad_0.02-0.02_blk_5_fmarg_5_h_<hash>`

- The visible pieces are selected by `DIRNAME_PARAM_KEYS` in `run_priority1.py`.
- The short hash is always generated from all run parameters.
- Full parameters are saved in `params.json` inside the result folder.
- Integer-valued parameters are formatted without decimal points in folder names.
- Plot PNGs are grouped by plot type, e.g. `band_metrics/NGF2.png`.
- Analysis arrays are saved as NetCDF files next to the CSV tables.

## Output tables

`block_metrics.csv` has one row per population, seed, amplitude, and time block.

- `job_id`: source batch job.
- `seed_main`: simulation seed.
- `f`: drive frequency used for fitted spectra and pulse-time phase fits.
- `amp`: pulse strength condition.
- `pop` or `y`: analyzed rate population or future LFP/CSD channel.
- `block_idx`, `block_t0`, `block_t1`: nonoverlapping analysis block index and time limits.
- `n_valid_time`: unmasked samples left in the block after pulse masking.
- `p_band`: total fitted power in `BROAD_BAND`.
- `p_target`: fitted power around the drive frequency.
- `concentration`: `p_target / p_band`; larger values mean more power concentrated near the drive.
- `centroid_offset`: spectral centroid minus `f0`; values near zero mean the band is centered near the drive.
- `width`: spectral spread inside `BROAD_BAND`; smaller values mean a narrower spectral concentration.

`condition_metrics.csv` averages block summaries within each seed, then averages seeds equally.

- `n_seed`: number of seeds contributing to the condition mean.
- `n_blocks`: total analyzed blocks across contributing seeds.
- `n_pulses`: pulse starts available for phase/coefficient fits.
- `n_valid_phase`: pulse starts with a valid local sinusoid fit.
- `z_mean_re`, `z_mean_im`: real and imaginary parts of mean `z = a - i b` at pulse starts.
- `z_mean_abs`: magnitude of the mean complex coefficient.

For phase locking, start with `concentration`, `width`, `centroid_offset`,
`z_mean_abs`, and `n_valid_phase`. Stronger locking usually means higher
`concentration`, lower `width`, `centroid_offset` near zero, and larger
`z_mean_abs` relative to `amp=0`. Always check `n_valid_phase` and
`n_valid_time` before trusting a condition.

## NetCDF outputs

`phase_events/<trace>.nc`

- Stores pulse-time fitted phases and complex coefficients at `f0`.
- Main variables: `phase`, `coeff_re`, `coeff_im`, `event_time`.
- Coordinates include signal trace, `seed_main`, `f`, `amp`, and `event`.

`complex_spectrogram/<trace>.nc`

- Stores the time-frequency fitted complex coefficient spectrogram.
- Main variables: `coeff_re`, `coeff_im`, `freq`, `t_fit`.
- `freq` and `t_fit` are stored as variables so the file remains self-describing when different drive frequencies use different grids.
- Both NetCDF files include the full run parameter JSON in `attrs["params_json"]`.

## How to read the plots

`spectra_raw_logratio_*.png`

- Top: raw masked fitted spectra. Use this mainly to see shared mask artifacts and broad condition changes.
- Bottom: `log(S_h / S_0)`, where `S_0` is the seed-balanced zero-amplitude baseline.
- Positive values near `f0` with nearby negative values suggest spectral concentration or locking.
- Broad positive values suggest nonspecific power increase.
- `POWER_F_MARGIN` controls the right-side frequency margin; the left margin is clamped so frequencies stay positive.

`band_metrics_*.png`

- Gray points are block values.
- Colored lines are seed means.
- The thick black line is the seed-balanced condition mean.
- Look for `concentration` increasing, `width` decreasing, and `centroid_offset` moving toward zero.

`phase_density_*.png`

- Top: raw phase-density overlays; the thick dark curve is `amp=0`.
- Bottom: phase enrichment for each amplitude relative to `amp=0`.
- Red means phases enriched relative to baseline; blue means depleted. The color scale is symmetric around zero.

`coeff_clouds_*.png`

- Points are fitted complex coefficients `z = a - i b` at pulse starts.
- The zero-amplitude cloud is shown in gray on every panel.
- Dashed/dotted contours are Gaussian fits to the zero-amplitude cloud at 95% and 99%.
- A shifted mean vector suggests a coherent phase-locked component; radial expansion suggests amplitude increase.
