# Supplementary raster examples

One saved raster per selected condition, all **seed 1000**, copied unchanged from
the mounted results. Filenames describe the intervention; `10s`, `15s`, `20s`, and
`220s` distinguish total simulation durations. The images are previews of existing
runs, not regenerated paper panels or newly cropped figures.

Collected 2026-10-20: **21 PNGs, none missing; 32,170,125 bytes (30.7 MiB)**.

[manifest.csv](manifest.csv) records each exact source path, local cfg snapshot,
condition, seed, simulation duration, rate-summary window, configured raster time
range, image dimensions, byte count, and SHA-256. A `null` configured raster time
range means no explicit interval was saved in that cfg; consult the image axes.
**The rate-summary window is not a claim about the raster's displayed interval.**

## Cortex — S1

All four runs last 10 s; rate summaries use 7–10 s.

| Image | Condition |
|---|---|
| [cortex_no_fading.png](cortex_no_fading.png) | Naive recurrent cortex |
| [cortex_ee_faded.png](cortex_ee_faded.png) | E–E inputs faded from surrogate to recurrence |
| [cortex_ee_surrogate.png](cortex_ee_surrogate.png) | Static E–E surrogate reference |
| [cortex_all_surrogate.png](cortex_all_surrogate.png) | All-surrogate reference |

## Thalamic correction — S2

The first three runs last 220 s; rate summaries use 200–220 s. The short
all-surrogate reference is listed with S3 below and uses a different protocol.

| Image | Condition |
|---|---|
| [thalamus_uncorrected_220s.png](thalamus_uncorrected_220s.png) | No second-stage correction |
| [thalamus_own_correction_220s.png](thalamus_own_correction_220s.png) | Realization-specific feedback correction |
| [thalamus_median_correction_220s.png](thalamus_median_correction_220s.png) | Fixed median correction |

## Thalamic freeze/fade protocols — S3

All seven runs last 10 s; rate summaries use 7–10 s. In these filenames,
`i_to_e` means **TI/TIM → TC/HTC/TCM**, and `e_to_i` means the reverse six
requested population pairs. They do not refer to every inhibitory/excitatory
projection. “Frozen” means replaced by surrogate input; “faded” means restored
gradually to recurrent input. Requested pairs can include nonexistent projections.

| Image | Condition |
|---|---|
| [thalamus_all_surrogate_10s.png](thalamus_all_surrogate_10s.png) | All-surrogate reference; also relevant to S2 |
| [thalamus_recurrent_10s.png](thalamus_recurrent_10s.png) | Short uncorrected recurrent reference |
| [thalamus_all_faded_10s.png](thalamus_all_faded_10s.png) | All 49 requested thalamic pairs faded |
| [thalamus_i_to_e_frozen_10s.png](thalamus_i_to_e_frozen_10s.png) | Selected I → E pairs remain surrogate |
| [thalamus_i_to_e_faded_10s.png](thalamus_i_to_e_faded_10s.png) | Selected I → E pairs faded to recurrence |
| [thalamus_e_to_i_frozen_10s.png](thalamus_e_to_i_frozen_10s.png) | Selected E → I pairs remain surrogate |
| [thalamus_e_to_i_faded_10s.png](thalamus_e_to_i_faded_10s.png) | Selected E → I pairs faded to recurrence |

## Historical full-A1 controls — S4

All six runs last 15 s; rate summaries use 10–15 s. “Correction” means fixed
median thalamic current correction. The first four form the historical 2×2
comparison. The last two are static E–E surrogate references.

| Image | Condition |
|---|---|
| [a1_no_fading_no_correction_15s.png](a1_no_fading_no_correction_15s.png) | Neither intervention |
| [a1_no_fading_with_correction_15s.png](a1_no_fading_with_correction_15s.png) | Correction only |
| [a1_fading_no_correction_15s.png](a1_fading_no_correction_15s.png) | E–E fading only |
| [a1_fading_with_correction_15s.png](a1_fading_with_correction_15s.png) | Both interventions |
| [a1_ee_surrogate_no_correction_15s.png](a1_ee_surrogate_no_correction_15s.png) | Static E–E surrogate, no correction |
| [a1_ee_surrogate_with_correction_15s.png](a1_ee_surrogate_with_correction_15s.png) | Static E–E surrogate, with correction |

## Exact FIG_A1 illustrative cohort — S5

[a1_paper_example_20s.png](a1_paper_example_20s.png) comes from the **three-seed**
experiment used for the main figure's illustrative traces. It lasts 20 s and has
15–20 s summaries. It is distinct from both the historical 15 s controls and the
later 15-seed error-summary cohort. This is the existing saved raster, not a
reconstruction of the paper's selected time-window panels.

## Fading conductance examples — S6

These use simulations already represented above: `cortex_ee_faded.png`,
`thalamus_all_faded_10s.png`, the historical A1 fading controls, and
`a1_paper_example_20s.png`. A conductance trace is a different output from its
simulation's raster. This collection does not resolve the separate numerical
conductance-export gap documented in [the inventory](../../supplementary_simulations.md).

## Retrieval and limits

Selection follows [the supplementary inventory](../../supplementary_simulations.md):
four cortex conditions, three long thalamic correction conditions, seven short
thalamic protocols, six historical A1 controls/references, and one exact A1 example.
The excluded “without 50% E–E decrease” proposal is not included. Static E–E
surrogate references are different interventions.

Only one raster PNG per condition was read remotely; no spike pickle or network
file was opened. [copy_audit.json](copy_audit.json) records payload and missing
images. The CSV preserves checksums of the copied bytes without rereading remote
PNGs. Same numeric seeds across interventions do not guarantee identical realized
connectivity or noise. These examples should be interpreted alongside the seed
distributions, not as paired causal comparisons.

Rerun from the repository root with:

```bash
python3 dev_scratch/paper_figure_data_oct19/code/collect_supplementary_rasters.py
```

Existing verified local copies are reused. The script only probes the explicitly
selected source file paths and enforces per-file and total read limits. PNGs are
ignored by the existing root `.gitignore`; this README, manifest, and audit remain
versionable.
