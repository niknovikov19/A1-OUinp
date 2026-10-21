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

## 2026-10-20 — Supplementary simulation inventory started

- User requested an inventory and data/code-readiness assessment for Supplementary → “Simulations (TODO)”, excluding “Without 50% E-E decrease”. Scope and I/O constraints are recorded in `supplementary_simulations_task.md`.
- Existing paper text, main-figure manifests, and mounted-root listings are available locally. Additional relevant local investigations exist under `dev_scratch/thal_frz/` and `dev_scratch/thal_frz_2/`; inspect these before accessing more remote data.
- No simulation submission or production-configuration edit is part of this assessment.

## Supplementary list and first code findings

- PDF page 27 lists six relevant items: cortex without fading; thalamus without correction; lack of bistability in thalamus; full A1 without fading / thalamic corrections; firing-rate traces for other FIG_A1 populations; fading g traces. “Without 50% E-E decrease” is excluded.
- First two items reuse already verified main-figure experiments (`ctx_full` and `thal_orig`). New simulation is not needed merely to tabulate their rate errors.
- Local `dev_scratch/thal_frz/` contains archived cfgs, collected rate/CV datasets, and per-cell rate caches for the thalamic freeze/fade experiments. Existing freeze analyses explicitly distinguish requested from effective projections; these caches should be assessed before any remote reads.
- `ConnFader.setup_recording()` actually records a representative synapse's `_ref_g`, although its docstring and figure ylabel say modulation/`pmod`. Thus existing `wmod_figs` can be conductance traces, not just the deterministic fade coefficient. Existing post-run code must be checked for whether numerical traces were persisted or only plotted.
- A separate five-seed/14-condition thalamic loop cache exists under `dev_scratch/thal_frz_2/`; its 10–15 s window and live-source-only input statistics differ from the older 15-seed, 7–10 s fade experiments. It cannot silently replace the corresponding main-paper cohort or supply dynamic conductance traces.

## Matched A1 controls located

- Targeted top-level listings of the three mounted batches are saved as `data/inventories/supplementary_remote_experiments.json`.
- The controller batch contains all four full-A1 combinations: naive recurrent without correction (`exp_a1_ee_full_ictrl_0...`), naive recurrent with correction (`exp_a1_full..._ictrl...`), faded without correction (`exp_a1_ee_fade_ictrl_0...`), and faded with correction (`exp_a1_ee_fade..._ictrl...`). Each is labeled 15 seeds and a 10–15 s window; exact counts will be checked next.
- Representative saved cfgs verify 43 active populations and no permanently frozen pairs in all four, 196 split E–E pairs only in faded variants, and the exact extra TC/HTC median currents only in corrected variants. Thus the full-A1 TODO is not intrinsically a missing-experiment problem.
- These older A1 controls use 15 s total / 10–15 s measurement, while FIG_A1 uses 20 s total / 15–20 s measurement. Use the older matched cohort for its own comparison; do not treat it as an identical control cohort for the later figure without checking timing and settings.
- Historical thalamic cfgs verify 49 split pairs for all-connection fading and six for each E→interneuron/interneuron→E fading condition. Their fade schedules are not saved as cfg fields, so current module constants alone cannot establish the historical transition times.
- The current full-A1 runtime `inp.ibkg_corrections` dictionary adds currents after the baseline and median currents; an empty dictionary does not disable the existing median correction. For reruns, the controller-capable experiment's `USE_IBKG_CTRL` switch is the direct existing parameter for turning that correction on/off.

## Supplementary data verification

- All six historical A1 setups (four fading/correction combinations plus two static E–E-surrogate controls) have complete 15-seed result/cfg filename sets, seeds 1000–1014, and summaries over 10–15 s. Snapshotted 90 result summaries and six representative cfgs; copied one additional 141,582-byte thalamic fade image. Distinct remote payload is 1,080,927 bytes across 97 files, recorded in `supplementary_read_audit.json`.
- All six A1 representative cfgs match on a hash of target rates, background-input definitions/seeds, mechanism changes, weight gains, section-selection settings, and global seeds. Fade variants differ in split connections and `cache_efficient` (0 versus True), so shared numeric seeds alone are not evidence of identical realized connectivity/noise.
- `inventory_supplementary_data.py` inspected all 22 local thalamic rate/CV datasets via `sim_data_analyzer.xr_io.load_xr`. The all-surrogate mean absolute population bias is 0.545 Hz, naive full thalamus 5.443 Hz, and three faded conditions about 5.16–5.32 Hz. Frozen interneuron→relay input improves bias to 2.710 Hz, which returns to 5.174 Hz after that input is faded back to recurrence. These are finite-protocol comparisons, not proof of global monostability.
- Representative raw files exist for the thalamic reference/fades (about 9.6–14.1 MB), cortex without fading (32.4 MB), and all historical A1 controls (46–66 MB). No raw pickle was opened. Exact per-experiment output filenames/sizes are saved in `supplementary_data_readiness.json`.
- The exact FIG_A1 3-seed seed-1000 source has 21 saved rate-figure PNGs and three conductance/fade PNGs; its compact `rvec_xr/` folder is empty. The later 15-seed cohort also has no compact rate NetCDFs. Additional exact rate traces require extracting/filtering existing spikes, not simulating again.
- The inspected historical all-thalamus conductance image supports a 3–5 s fade. The current and historical `ConnFader` implementation records `_ref_g` in µS, stores it only on the fader object, and the inspected post-run hooks save a PNG without a numerical fader export. Numerical g curves are therefore not yet located; a small recording/export change would be needed for a rerun if original traces cannot be recovered elsewhere.

## Supplementary inventory written

- Wrote `supplementary_simulations.md` and the six-row `data/tables/supplementary_simulations_inventory.csv`, with code parameters, exact existing A1 control paths, data limits, and acquisition routes.
- Distinguished 15-seed historical A1 controls (10–15 s) from FIG_A1 (15–20 s). The historical 2×2 needs no new run. A strict later 15-seed factorial would need its three missing cells if the existing faded/corrected reference can be retained; a new common implementation might instead justify all four.
- Flagged misleading legacy rate-image counts: several thalamic `rvec_figs/` folders contain only cortical-class filenames. Their presence is not sufficient evidence for useful thalamic time courses; use existing raw spikes for the required plots.
- Acquisition priority is compact post-processing of existing spikes for thalamic fade dynamics and additional FIG_A1 population traces, followed by deciding whether existing g images suffice or a numerical recording export is required. No new model implementation is needed for the listed scientific controls; numerical g persistence is a small output/metadata exception to parameter-only changes.
- Final checks passed: six inventory rows; six complete 15-seed/43-population A1 cohorts; 3,870 unique numerical rows; all 97 snapshotted artifact hashes; selected-input fingerprints including subnet seed; freeze/split flags; 10–15 s windows; and all seven median-current on/off settings in all six representative cfgs. Script syntax, report links, and tracked-file whitespace checks pass.
- No raw simulation pickle was opened, no production config edited, and no simulation/HPC job submitted. Newly produced artifacts are organized under the existing paper task folder and were not committed or pushed by this inventory task.
# Supplementary raster collection — 2026-10-20

## Follow-up: single-projection thalamic fading table

Run-organization correction: the user clarified that parameter-only differences
should not create new `exp_configs/` experiment folders. Both missing conditions
will reuse `net_newsec_ee_fade_var_seed`, with changed parameter values and distinct
`EXP_LABEL`/result names. The run plan now records this; no simulation code or
experiment directory has been changed or created.

Proposed the next-run procedure in `notes/thalamus_missing_fades_run_plan.md`:
two dedicated single-projection restoration configurations, seed-1000 pilots,
then 15 seeds each, explicit proposed 3–5 s fading and 7–10 s summaries, full-record
compact rate exports, and existing tracked HPC requests/preflight. Inspection
confirmed that the old fader hooks read module-level settings, so cfg overrides
alone cannot select the new pair/schedule; present defaults are full A1 and a
permanent freeze and must not be launched unchanged. No jobs or experiment edits
were made in response to the planning question.

Prepared the requested seven-population table as
`data/tables/population_rate_table_thalamus_fading.csv`: target rates and seven
condition columns in the agreed order, with mean rate ± sample SD to two decimal
places for the five available conditions. The IREM→TI and IREM→IRE fading
columns are explicit empty placeholders (14 blank cells). Unlike the prior error
tables, these cells contain firing rates. Sources contain both modeled and `frz`
surrogate-source populations; only the seven modeled populations are selected.
The local-only generator uses `sim_data_analyzer`, validates all 15 seeds and
saved protocol/intervention metadata, and preserves 525 unrounded per-seed rates
plus source hashes and numerical summaries. Caption, source mapping, limitations,
and regeneration are in `notes/thalamus_fading_table_caption.md`. No mounted
result files were read and no experiments were launched for this export.
Verification confirmed seven population rows, five populated condition columns,
14 empty cells, and 525 per-seed source values. Every displayed mean and sample
SD matches an independent recomputation from the exported per-seed CSV.

The user confirmed intended improving projections **IREM→TI** and **IREM→IRE**.
Their frozen conditions exist (`irem_ti_0`, `irem_ire_0`), alongside all-surrogate,
naive recurrence, and all-surrogate-to-recurrence fading: five of seven proposed
condition columns, all 15 seeds and 7–10 s. No matching single-projection fading
cohorts were found in fresh nonrecursive experiment-name listings of the three
mounted batches. This follow-up read no remote file contents. The existing I→E/E→I
fades and full-A1 E–E fades are different interventions. Two parameter-only
thalamus conditions (15 seeds each) would fill the gaps. Exact evidence, proposed
table organization, interpretation limits, and parameter choices are preserved in
`notes/thalamus_branch_fading_table_assessment.md`; the fresh name audit is
`data/inventories/thalamus_branch_fading_name_check.json`. No paper table or runs
were created.

## Raster collection

Targeted, nonrecursive listings of 21 selected experiment `rasters/` folders found
`raster_00000_seed_1000.png` in every folder. Selection covers four cortex
conditions, three long thalamic correction conditions, the seven short thalamic
protocols in the supplementary inventory, six historical A1 controls/references,
and the exact three-seed FIG_A1 illustrative cohort. Image sizes are approximately
0.48–2.49 MB each. Only one PNG per condition will be copied; no raw simulation
pickle is needed. The 10 s versus 220 s thalamic cohorts and 15 s versus 20 s A1
cohorts must remain distinguishable in filenames and documentation.

Completed collection: 21 seed-1000 PNGs, none missing, 32,170,125 bytes (30.7 MiB)
read remotely. All local images passed PNG verification and match their recorded
SHA-256 and byte counts; each is 2500×2500 px. The saved cfgs specify no explicit
raster `timeRange`, so summary windows are recorded separately and are not treated
as raster axis limits. Visual inspection of `thalamus_all_faded_10s.png` confirms
a 0–10000 ms raster with the seven thalamic populations. Images remain byte-for-byte
copies, with short descriptive filenames under `evidence/rasters/`. That folder's
README, manifest CSV, and copy audit preserve provenance; the existing root ignore
rule excludes its PNGs. No pickle was opened or new simulation launched.

## Experiment rollback — 2026-10-20

Restored `net_newsec_ee_fade_var_seed` to its pre-pilot version (`0612925`),
retaining only `get_batch_completion_files()` for HPC compatibility. Removed
the added `fade_post` batch axis, dynamic projection selection, diagnostics,
and changed simulation hooks; restored the original parameter values too.
Verified that `batch_params.py` matches the original exactly and that the
experiment's Python syntax tree differs only by the compatibility function.
Checked the original 15-seed batch and its declared output filenames. Removed
the obsolete staged `_pilot_v2` label edit; unrelated staged files are unchanged.
Existing pilot data remain associated with their original simulation commit;
the old pilot request does not describe the restored configuration. No HPC
checkout, job, or result file was changed. The user subsequently requested that
this rollback be committed, pushed, and fetched on lethe without updating its
checked-out commit.

## Pilot analysis resumed — 2026-10-20

- The completion-list repair recovered attempt B and released its checkout;
  all four simulations had completed. The installed `hpc-result` inventory now
  works. Retrieved three missing result JSONs and verified the existing fourth
  cache copy through that helper. Each JSON is about 116 kB; only 347 kB of new
  scientific payload was transferred. No raw pickle or raster was retrieved.
- The existing analysis script passed the saved protocol, population, finite-rate,
  contact-count, coefficient-schedule, and eight-rank endpoint checks for all
  four runs. Maximum recurrent-coefficient discrepancy is 0.000025; recurrent
  and surrogate coefficients sum to one for every recorded sample after t=0.
  The t=0 sample has both shared coefficients zero and is explicitly excluded;
  terminal representative synaptic coefficients are 1/0 on every rank.
- Read four existing local NetCDF reference caches with `sim_data_analyzer`.
  Preserved checksummed pilot snapshots, 84 population/phase rows, a numerical
  analysis report, and full/cropped rate plots. These operations read no mounted
  simulation data.
- The short pilot does not establish convergence to the historical bad outcome.
  IREM→TI seed 1000 is already high before fading (TC/HTC 28.96/28.51 Hz), whereas
  seed 1001 ends at 5.38/6.84 Hz. IREM→IRE endpoints are 14.84/13.08 and
  8.57/11.87 Hz. Historical fully recurrent means are 22.29/18.51 Hz over 7–10 s.
  The pilot measures only 5–6 s, immediately after the fade ends at 5 s.
- Keep both production-table columns blank. Before a production cohort, use a
  longer pilot and a fully recurrent control under the same code. Configure each
  projection through existing parameter values in separate pinned revisions;
  do not restore the removed batch axis. No experiment file or job was changed.

## Parameter-only pilot — 2026-10-20

- The user requested a fresh pilot with experiment changes restricted to existing
  parameter values or HPC compatibility helpers, and required sequential batches.
- Prepared IREM→TI with two seeds, 10 s duration, 3–5 s fading, and 7–10 s rates.
  AST checks confirm that every function, including the existing completion
  helper, is unchanged. Local preflight and archived baseline-input comparisons
  passed. Commit `08e301a`; main 118859 and simulations 118860/118861 completed.
- Normal finalization verified seven files. Downloaded a 12.4 kB compact archive
  containing cfgs, results, and index; analyzed through `sim_data_analyzer` and
  direct saved-cfg checks. TC/HTC endpoints were 29.98/28.11 Hz (seed 1000) and
  7.34/10.15 Hz (seed 1001). Released the batch before changing conditions.
- Changed only the existing projection and result-label values for IREM→IRE,
  repeated preflight/AST checks, committed as `450eb40`, pushed and updated lethe,
  then submitted main 118863. Only this second batch is active.
- Detailed incremental execution log: [thalamus_parameter_pilot.md](thalamus_parameter_pilot.md).
- IREM→IRE main 118863 and children 118864/118865 completed; normal finalization
  verified all seven files, compact retrieval and local analysis passed, and
  release succeeded. Both sequential batches are finished and released.
- The two routes give similar endpoint rates within each seed (largest absolute
  seven-population differences 1.00 and 1.24 Hz). TC/HTC are high for seed 1000
  and much lower for seed 1001 in both conditions. Endpoint data alone cannot
  establish convergence or monostability.
- Confirmed a reference limitation: both frozen references share the pilot's
  population order, whereas archived fully recurrent/all-surrogate-fading runs
  use another order. Existing background seeds depend on that order. Saved these
  order/seed details in both analysis reports; an identically ordered recurrent
  control is needed before interpreting same-numbered historical seeds as matched
  comparisons. The 15-seed table remains unchanged.

## Full IREM→TI fade requested — 2026-10-20

- The user requested the full `thal_all_fade` duration and 15-seed cohort for
  IREM→TI restoration, then waiting without background work once the watcher is
  operating. Execution log: [thalamus_irem_ti_full_run.md](thalamus_irem_ti_full_run.md).
- Set the existing label, projection, population-order, and seed-count values.
  The population order now matches the archived all-thalamus fade, including
  its background-seed assignment. Duration remains 10 s and summary 7–10 s.
  No experiment functions or completion helpers changed.
- The initial concurrency-two attempt (main 118869) was cancelled at the user's
  request; four children completed and two were cancelled. Finalized and released
  it, preserving all partial files. The user then selected concurrency 10,
  30 ranks, and 128 GiB per simulation after the protected 30-core ceiling rejected
  a 32-core request. No protected policy changed.
- Restarted all 15 seeds in fresh label `thal_irem_ti_fade_r2`, source commit
  `cdeb4e10cd2b71e3baa9ffae45395fc626d8df6e`, main 118876. Waited for the
  watcher without parallel task work or background checks. Its terminal report
  confirmed completion of all 15 children. Normal finalization verified 46 files.
- Retrieved the 84,977-byte compact archive, verified its 31 payloads, and checked
  all saved scientific cfgs against the all-thalamus fade reference. All 15 cfgs,
  seed mappings, and 105 finite population rates passed. Saved unrounded rates
  and manifest in `data/inventories/thalamus_irem_ti_full_r2_run.json`. Normal
  release succeeded; pilots and cancelled outputs remain separate.

