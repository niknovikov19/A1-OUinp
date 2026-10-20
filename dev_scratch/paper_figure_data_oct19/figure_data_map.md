# Results figure data map

Paper: `doc/paper/Bkg_paper_Oct19_v2.pdf`, 39 pages, created 2026-10-19. Page numbers below are PDF page numbers. Notebook cell numbers are zero based.

## Coverage

All four figures in scope are mapped to their data. The two original mounts plus the subsequently mounted `net_newsec_ctrl_var_seed` provide every rate-error series, the exported learned corrections, and the illustrative raw-file path. All rate summaries and representative saved configurations are preserved locally. The illustrative raw spike file was identified but left unread to limit remote I/O.

“Verified” below means source selection is supported by notebook code, saved configurations/results where accessible, and visual/numerical agreement with the paper. It does not mean the complete assembled figure was regenerated pixel for pixel. No complete figure assembly/export script was found in the inspected code.

## Figure and panel inventory

All result roots below are relative to `exp_results/batch_rxbkg_state1_mech1/`. Exact experiment subfolders are in the next section and in [experiment_manifest.json](data/inventories/experiment_manifest.json).

| PDF page / figure | Panel / series | Source alias | Measurement / selection | Status |
|---|---|---|---|---|
| 8, FIG_CMP_SURR_FULL | A | `ctx_surr` | All-surrogate cortex schematic | Saved cfg verifies all connections frozen |
| 8, FIG_CMP_SURR_FULL | B | `ctx_full` | Recurrent cortex, surrogate thalamus schematic | Saved cfg verifies 36 active cortical populations |
| 8, FIG_CMP_SURR_FULL | C, blue “Surr.” | `ctx_surr` | Population rate minus target, 7–10 s, 15 seeds | Verified, all summaries preserved locally |
| 8, FIG_CMP_SURR_FULL | C, orange “Full” | `ctx_full` | Population rate minus target, 7–10 s, 15 seeds | Verified, all summaries preserved locally |
| 9, FIG_CMP_EE_SURR_FADE | A | `ctx_ee_surr` | All 11 × 11 cortical E–E population pairs frozen | Saved cfg verifies the 121 pairs |
| 9, FIG_CMP_EE_SURR_FADE | B | `ctx_ee_fade` | Same 121 pairs split into surrogate/recurrent inputs; fading 3–5 s | Split pairs verified in cfg; timing supported by saved modulation figure |
| 9, FIG_CMP_EE_SURR_FADE | C, green “ee_surr” | `ctx_ee_surr` | Rate error, 7–10 s, 15 seeds | Verified, all summaries preserved locally |
| 9, FIG_CMP_EE_SURR_FADE | C, red “ee_fade” | `ctx_ee_fade` | Rate error, 7–10 s, 15 seeds | Verified, all summaries preserved locally |
| 11, FIG_THAL | A / D blue “Surr.” | `thal_surr` | All-surrogate thalamus; rate error 7–10 s, 15 seeds | Verified, all summaries preserved locally |
| 11, FIG_THAL | B / D orange “Full” | `thal_orig` | Recurrent thalamus with surrogate cortex; rate error 200–220 s | Verified, all summaries preserved locally |
| 11, FIG_THAL | C / D green “corr_own” | `thal_own` | Learned per-realization constant correction; rate error 200–220 s after feedback locks at 160 s | Verified, all summaries and representative controller cfg preserved |
| 11, FIG_THAL | C / D red “corr_med” | `thal_med` | Same median constant correction for all realizations; rate error 200–220 s | Verified, all summaries and median IClamp cfg preserved |
| 11, FIG_THAL | E, green distributions and points | `thal_own/ibkg_ctrl_1.json` | Final locked controller output `z` for each of 15 trials | Source export preserved; controller files inventoried but not loaded |
| 11, FIG_THAL | E, red horizontal marks | Local correction JSON | Per-population median of those 15 values | Numerically verified locally |
| 12, FIG_A1 | A | `a1_errors` | Rate error, 15–20 s, seeds 1000–1014 | Verified, all summaries preserved locally |
| 12, FIG_A1 | B, left / right | `a1_example` | Seed 1000 spike raster, 6–7.5 s / 13–14.5 s | Explicit notebook path and saved raster; raw file exists, contents not loaded |
| 12, FIG_A1 | C, left / right | `a1_example` | Same seed and intervals, IT3 rate; 5 ms bins, Gaussian smoothing σ = 5 ms | Explicit notebook path/settings and saved left trace; raw file not loaded |

## Exact experiment folders

### First mounted root: `net_newsec_ee_fade_var_seed`

| Alias | Experiment subfolder |
|---|---|
| `ctx_surr` | `exp_ctx_unconn_nseed_15_t_7.0_10.0_wmult_0.25_ee_0.5` |
| `ctx_full` | `exp_ctx_ee_1_nseed_15_t_7.0_10.0_wmult_0.25_ee_0.5` |
| `ctx_ee_surr` | `exp_ctx_ee_0_nseed_15_t_7.0_10.0_wmult_0.25_ee_0.5` |
| `ctx_ee_fade` | `exp_ctx_ee_fade_nseed_15_t_7.0_10.0_wmult_0.25_ee_0.5` |
| `thal_surr` | `exp_thal_unconn_nseed_15_t_7.0_10.0_wmult_0.25_ee_0.5` |

Each selected 15-seed experiment has `results/result_00000_seed_1000.json` through `results/result_00014_seed_1014.json`, and corresponding `cfg/cfg_00000_seed_1000.json` etc. Rate summaries are in `rates`; `t_limits_r` gives the averaging interval in seconds. Every selected result file was read, but only the seed-1000 cfg was read per experiment.

The first root also has 5-seed versions and many exploratory thalamic freezes/fades. They are not the sources selected for these main figures. In particular, do not replace `thal_orig` with `exp_thal_ee_1_nseed_15_t_7.0_10.0_wmult_0.25_ee_0.5`: the thalamus figure notebook explicitly chooses the 220 s experiment instead.

### Second mounted root: `net_newsec_var_seed`

| Alias | Experiment subfolder |
|---|---|
| `a1_errors` | `exp_a1_ee_fade_nseed_15_t_15.0_20.0_ictrl_wmult_0.25_ee_0.5` |
| `a1_example` | `exp_a1_ee_fade_nseed_3_t_15.0_20.0_ictrl_wmult_0.25_ee_0.5` |

Panel A uses all 15 `results/result_{job:05d}_seed_{seed}.json` files from `a1_errors`. Panels B/C use this specific file:

```
exp_results/batch_rxbkg_state1_mech1/net_newsec_var_seed/
  exp_a1_ee_fade_nseed_3_t_15.0_20.0_ictrl_wmult_0.25_ee_0.5/
    pkl/data_00000_seed_1000.pkl
```

The pickle is 78,647,384 bytes; only its existence and size were checked. The `rvec_xr` directory in this 3-seed experiment is empty, so it offers no smaller cached numerical replacement for the illustrative rate trace. Saved notebook PNGs preserve the left trace and right raster for reference. The right trace and left raster require rerunning the plotting cells with their alternate time limits, or locating earlier saved outputs.

The representative cfg summaries of the 3-seed and 15-seed runs agree, including the 8–10 s fade and median thalamic currents, but their same-seed rate summaries differ by up to 0.8862069 Hz. Treat these as distinct runs. The reason for the numerical differences was not investigated.

### Additional root, mounted during investigation: `net_newsec_ctrl_var_seed`

| Alias | Experiment subfolder |
|---|---|
| `thal_orig` | `exp_thal_nseed_15_t_200.0_220.0_wmult_0.25_ee_0.5` |
| `thal_own` | `exp_thal_nseed_15_t_200.0_220.0_kmu_0.005_ksigma_0.0_taur_100_taum_2500_tauu_100_tc0_10000_tlock_160000_ks_0.0001_ku_0.001_epsm_0.1_wmult_0.25_ee_0.5` |
| `thal_med` | `exp_thal_nseed_15_t_200.0_220.0_ictrl_wmult_0.25_ee_0.5` |

All three exact paths are now accessible. Each has 15 result JSONs and 15 cfg files, with the same job/seed naming pattern as the other batches. All 45 summaries and three seed-1000 cfgs were snapshotted. They confirm a 220 s duration, 200–220 s averaging, seven active thalamic populations, and no frozen intrathalamic connections.

The learned-correction cfg confirms `RateController2`, gain 0.005, adaptation start 10 s, lock time 160 s, rate-estimation time constant 100 ms, error-filter time constant 2500 ms, transient time constant 100 ms, ks 0.0001, ku 0.001, and dead zone 0.1 Hz. The median-correction cfg contains the seven exported median currents as additional IClamp entries. The uncorrected cfg has only baseline currents.

The 8,407-byte `thal_own/ibkg_ctrl_1.json` was also preserved and its arrays/medians exactly match the local A1 input JSON. The 15 `ctrl/` filenames were inventoried; the first controller pickle is 4,437,798 bytes and was left unread. Original controller traces would only be needed to independently recompute locked corrections and their time courses, rather than use the existing export.

## Analysis code and measurement definitions

### Cortex and full circuit

Starting notebook:

`exp_configs/batch_rxbkg_state1_mech1/net_newsec_ee_fade_var_seed/compare_rates.ipynb`

- Cells 1–2: experiment mapping and `results/*.json` loading. Cortex selections are now commented; active selections are the 3-seed and 15-seed A1 fading runs.
- Cell 4: grouped boxplot function used for the cortex figures. Each datum is one trial's population mean rate, not a single neuron's rate. The plot subtracts `target_state_1.csv` when `center=True`; it does not normalize by target rate.
- Cells 8–12: horizontal boxplots, population groups and colors, and the active FIG_A1(A) selection `a1_ee_fade` (15 seeds).
- Cell 14: loads the exact 3-seed seed-1000 pickle listed above.
- Cell 15: IT3 rate via `analysis.ou_tuning.sim_res_proc_utils.calc_rate_dynamics`, `t_limits=(0, None)`, `tau_smooth=0.005`, default `dt_bin=0.005` seconds. Full-record filtering precedes selection of the displayed interval. Current x limits are 6–7.5 s; 13–14.5 s is commented.
- Cell 16: NetPyNE raster, layer ordering L1, L2, L3, L4, L5A, L5B, L6, then `IRE, TC, HTC, TI, IREM, TCM, TIM`; `orderBy='pop'`, `orderInverse=1`, dot markers. Current interval is 13–14.5 s; 6–7.5 s is commented. Only genuine modeled populations are included.

The current `net_newsec_var_seed/compare_rates.ipynb` is older exploratory material whose selected inputs span other batches. Its location is not evidence that it produced FIG_A1.

### Thalamus

Notebook:

`exp_configs/batch_rxbkg_state1_mech1/net_newsec_ctrl_var_seed/compare_ctrl_res.ipynb`

- Cells 1–2: exact four-series source mapping, summary loading, and saved 15-trial counts.
- Cells 3–5: population groups and rate-error boxplots. Population order is `TC, HTC, TI, IRE, TCM, TIM, IREM`.
- Cells 7–9: final controller outputs from each population's `zvec[-1]`, plotted as individual points plus boxes. This is the source representation for FIG_THAL(E).
- Cell 10: multiplies locked `z` by `simConfig.ou_ctrl_params.mu_gain` (= 0.005) to export current corrections, then takes the per-population median over trials.

Recovered local source:

`exp_configs/batch_rxbkg_state1_mech1/net_newsec_var_seed/ibkg_ctrl_1.json`

This file retains original HPC provenance, all 105 locked outputs, all 105 current corrections, and seven median currents. Copies are in [inputs/](data/inputs/); the source-run export is in [snapshots/thal_own/ibkg_ctrl_1.json](data/snapshots/thal_own/ibkg_ctrl_1.json), and a tidy export is in [thalamic_corrections.csv](data/tables/thalamic_corrections.csv). Trial index follows the notebook's sorted controller files. Their names are now verified as `ctrl_00000_seed_1000.pkl` through `ctrl_00014_seed_1014.pkl`; the tidy table records seed and original controller path for each value.

| Population | Median correction, nA |
|---|---:|
| TC | -0.23506264738553814 |
| HTC | -0.15799162850300966 |
| TI | -0.0004659604456170393 |
| IRE | -0.019262143816851655 |
| TCM | -0.20883876990917746 |
| TIM | -0.0008936951682445695 |
| IREM | -0.03076673928626604 |

The FIG_THAL(E) plotting code uses `z` (controller output, Hz); physical current is `I = 0.005 × z` nA. The paper figure labels the axis only “Correction” and removes numerical ticks. Preserve both representations when reusing this data. The caption's green-series parenthesis says `corr_med`, whereas its description and the code identify those distributions as per-trial corrections (`corr_own`). The code examined does not contain the final red-median overlay/figure assembly step.

### Rates, boxes, and displayed populations

Historical rate summaries were computed by `analysis/ou_tuning/sim_res_proc_utils.py::calc_rates_and_cvs` and `analysis/ou_tuning/data_proc_utils.py::calc_pop_rate`: spike count in the inclusive interval divided by duration in seconds and the population's number of neurons, including silent neurons in that denominator. The notebook uses the saved summaries directly. `sim_data_analyzer/data_proc_utils.py` has the corresponding shared rate and Gaussian-smoothed dynamics definitions; no new raw-spike analysis was needed here.

Boxplots use quartiles, median, mean as a white circle, and whiskers at the most extreme samples within 1.5 IQR; remaining samples are outliers. Trial rates are unweighted across the 15 realizations. Frozen surrogate population entries (`*frz`) are excluded by aligning rates to genuine population names in the target CSV.

Both cortex figures display 32 of 36 cortical populations:

- Top: `IT2, IT3, ITP4, ITS4, IT5A, IT5B, IT6, CT5A, CT5B, CT6, PT5B, NGF1, NGF2, NGF3, NGF4, NGF5A, NGF5B, NGF6`.
- Bottom left: `PV2, PV3, PV4, PV5A, PV5B, PV6, SOM2, SOM3, SOM4, SOM5A, SOM5B, SOM6`.
- Bottom right: `VIP2, VIP3`.

FIG_A1(A) displays 39 of 43 populations, in groups:

- PYR: `IT2, IT3, ITP4, ITS4, IT5A, CT5A, IT5B, CT5B, PT5B, IT6, CT6`.
- PV, SOM, NGF as above; VIP only `VIP2, VIP3`.
- Thalamus: `TC, HTC, TI, IRE, TCM, TIM, IREM`.

Thus `VIP4, VIP5A, VIP5B, VIP6` were simulated but omitted from these rate-error panels. They are retained in `data/tables/population_rates.csv`; the A1 raster includes them.

## Inputs and saved configurations

Across all ten experiments, the representative saved cfg's targets match the corresponding local `target_state_1.csv`, and its background excitatory/inhibitory rates, weights, and target sections match `rx_bkg_mid_sm_ctx21_thal41.csv` (rates clipped below at 0.001 as in the simulation code). [validation.json](data/inventories/validation.json) records these checks.

Other associated local configuration files are `ibkg_mech1_verest_-70_thal_spkthr.json`, `mech_changes_1.json`, and `target_sec_1.json`; copies are preserved in `data/inputs/`. Filename membership alone does not independently verify their complete historical use. The saved cfg snapshots preserve actual `IClamp`, `mech_changes`, background inputs, and connectivity settings for seed 1000. The A1 IClamp entries explicitly include the seven median correction currents above.

Both batch parameter scripts use `seed_main = 1000…1014`, `stim = seed_main`, `conn = 2 × seed_main`, and surrogate global seed `3 × seed_main`; representative saved cfgs agree. Current source cfg files are mutable and should not replace saved historical cfgs for reproduction. In particular, the current first-root cfg selects a different `a1_irem_ire_0` experiment and a different timing window.

## Evidence, limitations, and next action

- Full numerical evidence for the accessible boxes: [population_rates.csv](data/tables/population_rates.csv), [rate_error_statistics.csv](data/tables/rate_error_statistics.csv), and exact [snapshots/](data/snapshots/).
- Cortex comparisons were regenerated offline with the notebook's own grouped-boxplot function. `plots/check_cortex_*.png` agrees visually with paper box locations and distributions; colors in these review plots use default blue/orange for both comparisons.
- A1's six saved horizontal boxplot images agree visually with the respective paper panels. Thalamic error distributions and learned correction distributions were additionally reconstructed offline from the newly snapshotted summaries/export (`plots/check_thalamus_errors.png`, `plots/check_thalamus_corrections.png`).
- The saved cortex modulation image `evidence/simulation/ctx_fader_seed1000.png` supports a 3–5 s transition. Its numerical modulation trace was not read. A1's 8–10 s transition is explicitly preserved in `runtime_params.conn.fader_pts`.
- Raw raster/spike values were not re-extracted, to avoid reading the 78.6 MB illustrative simulation pickle. Its exact provenance is documented, but numerical spike-by-spike validation remains outstanding.
- No required result batch remains missing after the additional mount. Rate-error series are preserved numerically; controller time courses and A1 spike trains remain in their original files and were not loaded.
- Supplementary thalamic disconnection/fading figures are outside the requested subsection-figure inventory; the first root contains candidate data, but the draft still uses supplementary placeholders.

Remote content read for this task: 148 small cfg/result JSON files (1,258,067 bytes), one correction export JSON (8,407 bytes), and one cortex modulation PNG (156,891 bytes), **1,423,365 bytes total**. Some representative JSONs were read once during inspection and again during snapshotting, so this is the distinct-file payload total rather than a wire-traffic measurement. Directory listings were nonrecursive and targeted; no large simulation pickle, netParams file, archive, or controller trace was loaded. Read manifests/hashes are in `data/inventories/remote_read_audit.json` and `data/inventories/additional_remote_reads.json`.
