# Findings log

Artifact names in the historical entries below reflect the original layout. See [the README](../README.md) and [relocation map](../data/inventories/artifact_locations.json) for current locations.

## 2026-10-19 — Initial scope

- User supplied two mounted HPC result roots and a starting analysis notebook; these are candidate sources, not yet verified provenance.
- The requested scope is the figures in the Results subsections Cortex, Thalamus, and Thalamocortical circuit.
- All task artifacts will be kept in `dev_scratch/paper_figure_data_oct19/`.
- Initial repository filename search excluded mounted results and scratch folders. Both candidate batches have `compare_rates.ipynb` notebooks under `exp_configs/batch_rxbkg_state1_mech1/`.

## Local code and first bounded directory listings

- Extracted the source and textual saved outputs of both notebooks into `*_notebook.txt`; cell numbers are zero based.
- `net_newsec_ee_fade_var_seed/compare_rates.ipynb` is the strongest lead: commented experiment selections cover cortex, isolated thalamus, core/matrix disconnections, and whole A1. Its current active boxplots use `net_newsec_var_seed/exp_a1_ee_fade_nseed_15_t_15.0_20.0_ictrl_wmult_0.25_ee_0.5/results/*.json`.
- That notebook's current raster and rate example instead load seed 1000 from the **3-seed** version of the same experiment. These are different source directories and must be documented separately.
- The other batch's `compare_rates.ipynb` contains older single-run and unrelated exploratory selections; its location alone does not establish figure provenance.
- Both current `batch_params.py` files define seeds 1000–1014, with stim seed = main seed, conn seed = 2 × main seed, subnet/global seed = 3 × main seed.
- Current `net_newsec_ee_fade_var_seed/exp_cfg.py` selects `a1_irem_ire_0`, duration 15 s, summary window 10–15 s; it is not a frozen configuration for all historical runs. Saved per-run cfg files will be preferred for verification.
- Two nonrecursive top-level listings were saved in `remote_top_level.txt`. They show the expected cortex and thalamus variants in the first root and whole-circuit/controller variants in the second. No large result contents have been read.
- PDF command-line tools and base Python PDF modules are absent; checking existing environments before adding a local PDF parser.
- Existing unrelated working-tree edits were observed and are being left untouched.

## Paper inventory and additional provenance

- Parsed the 39-page local PDF using PyMuPDF installed under `python_deps/`; no remote simulation files were involved. `paper.txt` preserves page boundaries, and pages 8, 9, 11, 12 were rendered for inspection.
- Four figures are in scope: `FIG_CMP_SURR_FULL` (p. 8), `FIG_CMP_EE_SURR_FADE` (p. 9), `FIG_THAL` (p. 11), and `FIG_A1` (p. 12). Schematic panels carry configuration provenance rather than measured data.
- Cortex: blue/orange compare all-surrogate and recurrent cortex; green/red compare E–E-surrogate and faded cortex. Paper describes 15 seeds and last 3 s; the named candidates use 7–10 s summaries.
- Whole circuit: panel A uses 15 seeds and final 5 s. Panels B/C show 6–7.5 s and 13–14.5 s, with E–E fading at 8–10 s. The notebook specifies seed 1000 from the 3-seed run, Gaussian smoothing 5 ms for IT3, default rate bins 5 ms.
- **Additional batch required for thalamus:** `exp_configs/batch_rxbkg_state1_mech1/net_newsec_ctrl_var_seed/compare_ctrl_res.ipynb` explicitly selects the all-surrogate 7–10 s run from the first mounted root plus three 200–220 s experiments in `exp_results/batch_rxbkg_state1_mech1/net_newsec_ctrl_var_seed/`: uncorrected, realization-specific feedback-learned correction, and common median correction. Thus the orange thalamus series should not automatically be assigned to the short `exp_thal_ee_1...` run.
- `compare_ctrl_res.ipynb` cells 1–6 identify FIG_THAL(D) and cells 7–10 identify FIG_THAL(E). Saved text outputs report 15 trials for all four error series and 15 controller files for learned corrections.
- Local `net_newsec_var_seed/ibkg_ctrl_1.json` includes explicit original HPC source experiment/cfg paths, gain 0.005, `z_per_job`, `I_per_job`, and `I_median` for seven thalamic populations. It preserves the correction data without needing controller pickle reads.
- FIG_THAL(E) notebook plotting uses final controller output `zvec[-1]`; conversion to current is `I = 0.005 * z` nA. Units and scaling must be recorded explicitly because the figure axis is only labeled “Correction”.

## Small-summary verification

- `experiment_manifest.json` records exact result/cfg filenames for seven accessible candidate experiments. All six 15-seed selections have complete filenames for seeds 1000–1014; the illustrative A1 selection has 1000–1002.
- The three required `net_newsec_ctrl_var_seed` experiment paths are absent locally. Asked the user asynchronously whether that folder can also be mounted; continued independent work.
- Read/snapshotted only 93 result JSON summaries and seven representative seed-1000 cfg JSON files, totaling **994,876 bytes**. `remote_read_audit.json` records paths, sizes, and SHA-256 hashes for these 100 files. No simulation pickle, netParams file, archive, or controller trace was loaded.
- `population_rates.csv` has 3,039 rows of rates, target rates, errors, windows, seeds, and exact source files. These include all genuine modeled populations with available rates; surrogate `*frz` populations are excluded by aligning to cfg targets.
- Saved cfg verification: cortex runs have 36 active populations, 10 s duration, 7–10 s rate summaries. All-surrogate freezes all connections; full cortex freezes none within the active subcircuit; E–E surrogate freezes 121 = 11² pairs; fading splits those 121 pairs.
- Thalamic all-surrogate cfg has seven active populations and freezes all connections. Saved summaries confirm the 7–10 s window.
- A1 runs have all 43 active populations, 20 s duration, 15–20 s summaries, and 196 = 14² split E–E pairs. Saved `runtime_params.conn.fader_pts` confirms 8–10 s fading. IClamp entries contain the exact seven median corrections preserved in the local JSON, in addition to baseline resting-potential currents.
- The representative saved cfg summaries of the 3-seed and 15-seed A1 runs are identical, but the same-seed rate summaries differ (maximum across the three common seeds/populations: 0.8862069 Hz). Do not substitute the 15-seed seed-1000 raw file for the notebook's 3-seed seed-1000 file.
- The illustrative A1 raw pickle exists and is 78,647,384 bytes. Its path and size were checked only; it was not opened.
- Numerical fingerprints agree with the paper's plotted scales: full cortex IT5A/IT5B mean errors ≈1.91/2.86 Hz and VIP2/VIP3 ≈10.33/10.20 Hz; A1 TC mean error ≈7.65 Hz. More detailed offline comparisons follow.

## Offline checks and panel documentation

- Regenerated cortex comparison plots using the original notebook cell-4 plotting function and only local JSON snapshots. Visually checked agreement of the top groups with the paper; all three groups for each cortex figure are saved as `check_cortex_*.png`.
- Verified representative historical cfg targets against local target CSVs, and all background rates/weights/sections against `rx_bkg_mid_sm_ctx21_thal41.csv`. All checks passed for the seven accessible experiments. Results are in `validation.json`.
- Exported descriptive error statistics (`rate_error_statistics.csv`) and all 105 thalamic corrections with locked output/current units (`thalamic_corrections.csv`). All seven medians and `I = 0.005 × z` relationships pass numerical checks.
- Read one additional 156,891-byte seed-1000 cortex weight-modulation PNG. Its surrogate/recurrent traces support a 3–5 s transition, as described by the paper. Kept it as `ctx_fader_seed1000.png`, with hash/size in `additional_remote_reads.json`. Distinct remote content payload total is now 1,151,767 bytes; some initial representative JSON inspection reads were repeated during snapshotting, so this is not measured wire traffic.
- Extracted relevant saved PNG outputs from the local notebooks. Thalamic error/correction plots and A1 boxplots agree visually with the paper. Saved output is corroborating evidence, not independent verification of the unavailable thalamic raw summaries.
- The figure boxes omit VIP4/VIP5A/VIP5B/VIP6: cortex panels show 32 of 36 cortical populations; A1(A) shows 39 of 43 modeled populations. The cached rate table retains all modeled populations, and the A1 raster includes the omitted VIP populations.
- FIG_THAL(E) has an underspecified axis unit and a likely caption parenthesis typo (green distributions called corr_med instead of corr_own); both are recorded in the map because they affect data interpretation.
- Wrote `figure_data_map.md`, a 17-entry `figure_inventory.csv`, and an artifact README. The map distinguishes accessible/verified source data, code-identified missing result paths, and the deliberately unread illustrative raw spikes.
- Preserved the original grouped-plot source as `notebook_cell4_source.txt` for offline regeneration independent of future notebook edits. Added hashes for the paper and principal source notebooks in `local_source_audit.json`.

## Additional mount pending

- User replied that they will mount `net_newsec_ctrl_var_seed`. The first follow-up path check still found it unavailable. Will extend the same inventory once the mount appears.
- Updated the bounded snapshot reader to reuse existing local snapshots. Extending the manifest will therefore read only the newly available small files, without rereading the original mounted summaries.
- Artifact consistency checks passed: 17 panel/series rows, 3,039 rate rows, 237 population error distributions, 105 correction rows; all README/map links resolve and no simulation pickle was copied.

## Additional mount received and thalamus verified

- User confirmed the mount. All three exact thalamic experiment paths now exist, each with 15 result JSONs and 15 cfgs. Extended the manifest and reused the original local snapshots while reading only 45 new result summaries plus three seed-1000 cfgs.
- The small source `thal_own/ibkg_ctrl_1.json` exists (8,407 bytes). Snapshotted it separately and verified exact equality of `I_per_job`, `z_per_job`, and `I_median` against the local A1 input JSON.
- All three thalamic cfgs have 220 s duration, 200–220 s summary windows, seven active thalamic populations, and no frozen recurrent thalamic connections. The learned-correction cfg saves `RateController2`, gain 0.005, adaptation start 10 s, locking at 160 s, tau_rate 100 ms, tau_m 2500 ms, tau_u 100 ms, ks 0.0001, ku 0.001, and dead zone 0.1 Hz. The common-median cfg's additional IClamp currents exactly match the exported medians.
- Controller directory inventory has the expected sorted filenames `ctrl_00000_seed_1000.pkl` through `ctrl_00014_seed_1014.pkl`, supporting the export's trial-index-to-seed mapping. Only the first file's size was checked (4,437,798 bytes); no controller pickle was opened.
- Cached evidence now comprises 148 cfg/result JSON files (1,258,067 bytes), one correction export (8,407 bytes), and one modulation PNG (156,891 bytes): 1,423,365 bytes of distinct remote content. The rate table has 3,354 rows; all four FIG_THAL(D) series can now be reconstructed offline.

## Final verification and handoff

- Rebuilt the offline inventory with all ten experiments. Target, background-input, and representative seed checks pass for all ten. The rate-error statistics table now has 258 experiment/population distributions.
- Visually checked `check_thalamus_errors.png` against the paper and saved notebook plot; all four series agree. `check_thalamus_corrections.png` reproduces the recovered final-output distributions and median marks.
- Updated the main map, README, and 17-entry figure CSV to reflect the completed mount verification. No required result batch remains missing.
- Verified artifact links, table sizes (3,354 rates, 258 distributions, 105 corrections, 17 panel/series entries), and absence of copied simulation pickles.
- Remaining verification limits are explicit: only seed-1000 cfgs were read per experiment; large raw A1 spike and controller time-series files were identified/inventoried but not opened; complete assembled publication figures were not regenerated pixel for pixel.
- All durable task artifacts are under `dev_scratch/paper_figure_data_oct19/`. No production simulation/analysis code was changed.

## Folder organization

- At the user's request, grouped supporting artifacts into `code/`, `data/`, `evidence/`, `notes/`, and `plots/`; kept the README and main figure map at the top level.
- Moved Python dependencies and plotting caches into ignored `.runtime/`. No artifacts were deleted and no mounted result files were accessed during this organization pass.
- Updated report links, script inputs/outputs, the regeneration command, and the correction table's local export path. Original simulation source paths and saved snapshot contents remain intact.
- Preserved a mapping from previous top-level names to new locations in `data/inventories/artifact_locations.json`.
- Verification passed: offline regeneration from the task directory, document links, all 150 audited snapshot/image hashes, script base paths, correction-table export references, and all ten experiment checks. The relocated PDF dependency also imports successfully.

## Per-population supplementary table

- User requested the per-population CSV table and its caption following discussion of setup columns and separate cortical/thalamic blocks.
- Created a generator for two CSV panels of one supplementary table: all 36 cortical populations and seven thalamic populations, with target rate and five setup columns per panel. Each setup cell reports mean signed error ± sample SD (ddof = 1) over seeds 1000–1014, in Hz, to three decimals.
- Used only cached per-seed summaries; no remote filesystem reads or new raw-spike analysis are needed. The full-circuit columns select the 15-seed `a1_errors` run.
- The caption defines signs, variability, circuit configurations, and the different averaging windows. Source/reproduction notes are kept below the caption.
- Generator checks passed for every cell: exactly 15 unique expected seeds, consistent targets, correct averaging windows, rate-minus-target arithmetic, and agreement of unrounded mean/sample SD with the existing cached statistics table.

## Commit preparation

- Root `.gitignore` excludes task dependencies/caches, generated plots, extracted evidence images, and the dated draft PDF. The task-local ignore file was removed by the user.
- Added automatic creation of `plots/` during offline regeneration, so a fresh checkout does not need the ignored output directory to exist.
- Regeneration passed using cached inputs and a new temporary output directory; all eight comparison plots and the correction table were produced. Code/document whitespace checks passed. Original snapshot and extracted evidence formatting was preserved.
- Commit scope is the paper figure-data task folder and its root ignore rules. Unrelated working-tree edits, including the separate step-response ignore change, remain outside this commit.
