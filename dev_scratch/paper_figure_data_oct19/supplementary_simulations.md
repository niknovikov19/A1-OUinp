# Supplementary simulation inventory and readiness

Scope: Supplementary → “Simulations (TODO)”, PDF page 27 of `doc/paper/Bkg_paper_Oct19_v2.pdf`. Assessed 2026-10-20. “Without 50% E-E decrease” is excluded as requested. No simulations were launched, production configurations changed, or raw simulation pickles opened.

## Assessment

Most items need selection, analysis, and plotting of existing data. In particular, a complete historical full-A1 comparison of fading × thalamic correction already exists. The main gap is a numerical export of the illustrative synaptic conductance traces: the existing code records and plots them, but the inspected save hooks only retain PNGs.

| ID | Draft item | Evidence available | Remaining work | New simulation? |
|---|---|---|---|---|
| S1 | Ctx without fading | Verified 15-seed recurrent cortex and faded cortex; cached rates/errors, saved rate plots, raw spike files | Select a supplementary presentation; extract higher-quality time courses if desired | No |
| S2 | Thalamus without correction | Verified 15-seed uncorrected thalamus over 200–220 s, plus own/median-correction comparisons | Existing main-figure boxes already cover rate errors; add time courses or cell distributions if useful | No for rate errors; existing raw files support further analysis |
| S3 | Lack of bistability in the thalamic subcircuit | Local 15-seed all-surrogate, full, frozen, and three faded-condition summaries; raw spike files and conductance PNGs exist | Extract pre/during/post-fade rates and frame the conclusion as failure of the tested fading protocols to sustain a near-target state | No for the existing protocol comparisons; optional longer/protocol-sensitivity tests use existing parameters |
| S4 | Full A1 without fading / thalamic corrections | Complete 15-seed 2×2 historical comparison, plus static E–E controls, all over 10–15 s | Plot the matched historical cohort separately from the later FIG_A1 cohort; optional reruns only if identical later timing is required | No for a standalone historical control figure |
| S5 | Firing-rate traces from other FIG_A1 populations | Exact illustrative seed-1000 raw file and 21 saved rate-plot PNGs; no compact rate NetCDF | Extract rates for the desired populations using the original smoothing and intervals | No |
| S6 | Fading g traces | Recorded representative synaptic g is shown in existing `wmod_figs` PNGs; no numerical export located | Reuse original figures if sufficient, otherwise recover numeric recordings or add a small export and rerun one example | Conditional: needed only if numerical traces cannot be recovered |

A machine-readable version is [supplementary_simulations_inventory.csv](data/tables/supplementary_simulations_inventory.csv). Exact source files, counts, and representative cfg settings are in [supplementary_data_readiness.json](data/inventories/supplementary_data_readiness.json).

Follow-up: [21 local seed-1000 raster examples](evidence/rasters/README.md) now
cover the selected conditions below, with readable filenames and an exact-source
CSV manifest. All requested example PNGs existed; the additional raster transfer
was 32,170,125 bytes, recorded separately from this assessment's original read audit.

## S1 — Cortex without fading

Use the existing main-figure aliases:

- `ctx_full`: `net_newsec_ee_fade_var_seed/exp_ctx_ee_1_nseed_15_t_7.0_10.0_wmult_0.25_ee_0.5`.
- `ctx_ee_fade`: `net_newsec_ee_fade_var_seed/exp_ctx_ee_fade_nseed_15_t_7.0_10.0_wmult_0.25_ee_0.5`.
- `ctx_ee_surr` and `ctx_surr` are available as initialization/tuning references.

Paths above are relative to `exp_results/batch_rxbkg_state1_mech1/`. Both principal conditions have 15 realizations, 36 active cortical populations, and rate summaries over 7–10 s. Their rates/errors are already in [population_rates.csv](data/tables/population_rates.csv); they are the full/recurrent and faded comparisons in the main figures.

The supplementary item would be most informative as time courses or rasters illustrating convergence to the alternative state, rather than another copy of the existing boxes. There are 75 rate PNGs per principal experiment, one for each cortical class and seed. Seed-1000 raw files exist (32.4 MB without fading; 48.0 MB with fading). No new model run is needed to reconstruct rate dynamics from those spikes.

Existing code: `exp_configs/batch_rxbkg_state1_mech1/net_newsec_ee_fade_var_seed/{exp_cfg.py,compare_rates.ipynb}`. For an eventual rerun, select cortical populations, `CONNS_FROZEN=[]`, `EE_FADER_ON=0` for naive recurrence or `EE_FADER_ON=1` with the 121 cortical E–E pairs for fading. Preserve the background and resting-current inputs. The current module selects an unrelated IREM freeze, so its current defaults must not be used unchanged.

## S2 — Thalamus without correction

Use `thal_orig` from the main inventory:

`net_newsec_ctrl_var_seed/exp_thal_nseed_15_t_200.0_220.0_wmult_0.25_ee_0.5`.

The 15 summaries and a representative saved cfg are already cached. This is the uncorrected reference used by FIG_THAL, alongside realization-specific and median-correction conditions. The protocol runs for 220 s and evaluates 200–220 s. The uncorrected cfg has baseline thalamic currents but neither feedback corrections nor median offsets.

There are no rate PNGs or rate NetCDFs in this experiment's probed folders. Its seed-1000 raw file exists (143.6 MB); if a time course is needed, process that file where it lives and transfer only the selected rate series. For broad per-cell rate distributions, compact older thalamic caches already exist, but they use 7–10 s and must be labeled as a different cohort.

Existing code: `net_newsec_ctrl_var_seed/exp_cfg.py`. Relevant parameters are `POPS_USED=THAL_POPS`, `CONNS_FROZEN=[]`, `EE_FADER_ON=0`, `CTRL_ON=0`, `USE_IBKG=1`, and `USE_IBKG_CTRL=0`; `SIM_DURATION=220000`, `T0_CALC=200000` reproduce this comparison window. Turning off second-stage corrections does not mean removing the baseline currents used to position the cells on their firing curves.

## S3 — Thalamic fading and the bistability interpretation

The [uncorrected population-rate table](data/tables/population_rate_table_thalamus_fading.csv)
now compares all-surrogate input, the two improving single-projection freezes
(IREM→TI and IREM→IRE), naive full recurrence, and fading from each starting
condition. The two single-projection fading columns remain blank pending data.
See the [caption and source documentation](notes/thalamus_fading_table_caption.md).

There are 22 local thalamic rate/CV datasets under `dev_scratch/thal_frz/analysis/collected/`, with representative historical cfgs under `dev_scratch/thal_frz/cfg/`. The following all use seeds 1000–1014, 10 s total, and 7–10 s summaries:

| Experiment label | Intervention | Mean absolute population bias, Hz |
|---|---|---:|
| `thal_unconn` | All-surrogate | 0.545 |
| `thal_ee_1` | Full recurrent thalamus | 5.443 |
| `thal_all_fade` | All 49 requested thalamic population pairs faded to recurrence | 5.316 |
| `thal_ti_tc_0` | TI/TIM → TC/HTC/TCM frozen | 2.710 |
| `thal_ti_tc_fade` | Those six pairs faded to recurrence | 5.174 |
| `thal_tc_ti_0` | TC/HTC/TCM → TI/TIM frozen | 5.267 |
| `thal_tc_ti_fade` | Those six pairs faded to recurrence | 5.160 |

Bias here means the mean signed rate error over seeds for each population; the listed metric averages its absolute value over the seven populations. It is not the mean of trial-level absolute errors. These values were read from local caches with `sim_data_analyzer`, not recomputed from large raw files.

Exact folders follow `net_newsec_ee_fade_var_seed/exp_<label>_nseed_15_t_7.0_10.0_wmult_0.25_ee_0.5`. Requested pairs can include nonexistent projections; use the saved cfg lists and effective connectivity when interpreting a freeze. The E–E freeze is an existing tested intervention (`thal_ee_0`) and remains relevant here; excluding the separate “Without 50% E-E decrease” TODO does not remove these freezing controls.

The summaries establish that errors return after the tested restorations of recurrence. To show the crucial initial near-target phase, extract time courses from a representative `thal_all_fade` raw file and compare with the all-surrogate and naive recurrent references. The relevant seed-1000 files exist and are only about 9.6–14.1 MB each. Existing `rvec_xr` folders are empty. Most legacy rate PNGs have cortical class names despite these being thalamic experiments, so file counts alone are not evidence of useful thalamic traces; the `thal_tc_ti_*` folders do contain `THAL_...png` files.

Historical cfgs retain the split pairs but not the fade time points. The inspected all-thalamus conductance image supports fading between 3 and 5 s; this is image-level evidence for that example, not a verified numerical schedule for every historical condition. A compact full-record rate extraction would resolve the visible before/after behavior without rerunning.

These finite simulations support “no sustained near-target regime was reached by the tested fading protocols.” They do not prove the absence of every possible second attractor. If stronger evidence is wanted, existing `FADER_PTS`, duration, and seed parameters can specify longer post-fade holds and slower transitions. First assess existing time courses; a new parameter sweep is not yet necessary. The branch-level freeze proposals in `dev_scratch/thal_frz/analysis/exp_frz_key_experiments_and_next.md` answer additional mechanism questions and are not prerequisites for this inventory.

The five-seed, 14-condition `dev_scratch/thal_frz_2/data/tc_loops_1/cell_inp_stats_xr_combined.nc` is additional available evidence, not the same cohort: 10–15 s, 721 cells, and live-source connection/rate statistics. It does not contain dynamic synaptic conductance/current traces.

## S4 — Full A1: fading × thalamic corrections

All six conditions below are in `exp_results/batch_rxbkg_state1_mech1/net_newsec_ctrl_var_seed/`. Each has 15 result files and 15 cfg files for seeds 1000–1014, 43 active populations, 15 s total, and rate summaries over 10–15 s.

| Alias | Fading | Median correction | Exact experiment subfolder |
|---|---|---|---|
| `a1_no_fade_no_corr` | Off; naive recurrent | Off | `exp_a1_ee_full_ictrl_0_nseed_15_t_10.0_15.0_wmult_0.25_ee_0.5` |
| `a1_no_fade_corr` | Off; naive recurrent | On | `exp_a1_full_nseed_15_t_10.0_15.0_ictrl_wmult_0.25_ee_0.5` |
| `a1_fade_no_corr` | On | Off | `exp_a1_ee_fade_ictrl_0_nseed_15_t_10.0_15.0_wmult_0.25_ee_0.5` |
| `a1_fade_corr` | On | On | `exp_a1_ee_fade_nseed_15_t_10.0_15.0_ictrl_wmult_0.25_ee_0.5` |
| `a1_ee_surr_no_corr` | Static E–E surrogate reference | Off | `exp_a1_ee_0_ictrl_0_nseed_15_t_10.0_15.0_wmult_0.25_ee_0.5` |
| `a1_ee_surr_corr` | Static E–E surrogate reference | On | `exp_a1_ee_0_nseed_15_t_10.0_15.0_ictrl_wmult_0.25_ee_0.5` |

For the 2×2 comparison, saved cfgs verify no permanently frozen connections in any condition, 196 split pairs only in the faded conditions, and the exported median currents only in corrected conditions. The two static controls freeze E–E inputs instead of restoring them. Selected background, target, mechanism, gain, section-selection, and seed settings match across all six representative cfgs; the exact fields compared are recorded by the inventory script. This does not certify every possible cfg field or realized network.

All six rate/CV JSON cohorts and seed-1000 cfgs are now in [data/snapshots/supplementary/](data/snapshots/supplementary/). [supplementary_a1_control_rates.csv](data/tables/supplementary_a1_control_rates.csv) contains 3,870 numerical per-population/per-seed records. The 2×2 mean absolute population biases are 2.666 Hz (neither intervention), 1.985 Hz (correction only), 1.413 Hz (fading only), and 0.723 Hz (both). These are descriptive cohort-level summaries, not paired causal effect estimates.

Do not pool this cohort with the later FIG_A1 15–20 s results. A separate supplementary panel with its own timing caption needs no new simulation. If the intended claim requires controls with precisely the later FIG_A1 duration/fade schedule, prepare the missing 15-seed cells using 20 s total, 15–20 s measurement, the same seeds, and 8–10 s fading. The faded-and-corrected cell already exists; three additional cells would complete that later 2×2 if its source version and saved settings can be retained. A three-seed 20 s naive/corrected candidate is also listed in the modern batch, but it is not the required verified 15-seed cohort. Rerunning all four cells is only necessary if a newly fixed common implementation is chosen.

The existing controller-capable experiment already has the needed `EE_FADER_ON`, `USE_IBKG_CTRL`, `POPS_USED`, `CONNS_FROZEN`, `FADER_PTS`, duration, and seed switches. Keep `CTRL_ON=0` for static median-correction comparisons, preserve baseline currents and input assets, and use distinct reviewed experiment labels so existing outputs are not overwritten.

Two parameter pitfalls matter:

- In the modern `net_newsec_var_seed` experiment, `runtime_params.inp.ibkg_corrections` is additive. An empty dictionary does not remove median offsets already enabled by the module-level `USE_IBKG_CTRL=1`. Use the explicit switch in an isolated reviewed experiment configuration, or expose it deliberately before using runtime-only overrides.
- Fading uses `cache_efficient=0`, whereas naive/static historical controls save `cache_efficient=True`. Matching numeric seeds does not guarantee identical instantiated connectivity or Poisson streams across these construction paths. This is consistent with the already documented same-seed limitation in the step-response work. Use seed distributions; do not assume exact paired-noise cancellation.

## S5 — Additional population rate traces from FIG_A1

Use the same file as the main figure's illustrative IT3 trace and raster:

```
exp_results/batch_rxbkg_state1_mech1/net_newsec_var_seed/
  exp_a1_ee_fade_nseed_3_t_15.0_20.0_ictrl_wmult_0.25_ee_0.5/
    pkl/data_00000_seed_1000.pkl
```

The 78,647,384-byte file exists; it has not been opened in this assessment. Existing saved cfg/output inventories and plotting code identify it as the correct source. It is distinct from the later 15-seed seed-1000 run. Its seven population-group PNGs for this seed cover PYR, PV, SOM, VIP, NGF, THAL_E, and THAL_I; saved plot images are useful previews, but they are not numerical traces with verified FIG_A1 smoothing.

The original figure uses 5 ms bins and Gaussian smoothing with sigma 5 ms, calculated across the full record, then shows 6–7.5 s and 13–14.5 s. Use `sim_data_analyzer.xr_adapters.get_net_rate_dynamics_xr` on the original result, with `t_limits=(0, 20)`, `dt_bin=0.005`, `tau_smooth=0.005`, and the desired genuine modeled population names. Filter first and crop afterward to avoid interval-edge artifacts. Keep target-rate lines and recording units consistent with the main figure.

The least costly retrieval is one post-processing pass where the raw file resides: export a compact population × time NetCDF for the selected intervals, then retrieve that small file. All 43 populations in the two intervals amount to roughly 0.2 MB of float64 rate samples, before metadata/compression. This is analysis of existing spikes, not a new simulation. No compact rate NetCDF currently exists in the probed 3-seed or 15-seed FIG_A1 folders.

For future runs, the modern experiment can already save rates with `runtime_params.out.save_rate_xr=True`. Set `proc.rate_t_limits=[0,20]` explicitly if the initial/fading period is needed: its default export window is only `t0_calc…duration`. Also set `proc.rate_tau_smooth=0.005` if matching FIG_A1; the ordinary plotting/export smoothing default is different.

## S6 — Fading conductance traces

Existing sources include:

- Cortex: `ctx_ee_fade/wmod_figs/wmod_00000_seed_1000.png`, already retained locally as `evidence/simulation/ctx_fader_seed1000.png`.
- Thalamus: `thal_all_fade/wmod_figs/wmod_00000_seed_1000.png`, now retained as `evidence/simulation/supplementary_thal_all_fade_seed1000.png`.
- Full A1: three `wmod_figs` PNGs in the illustrative 3-seed run and 15 in its 15-seed counterpart; the historical A1 fade/correction controls have 15 each.

`conn_fader.py::setup_recording()` records `syn._ref_g`, one representative synapse for each positive/recurrent and negative/surrogate modulator, at a requested 1 ms interval in these experiment hooks. `plot_recs()` nevertheless labels the axis `pmod`, and the record is named `z`. The modulated synapse mechanisms declare `g` in µS. The docstring/axis label therefore cannot be used to identify this variable as the dimensionless coefficient a(t).

The inspected saving path keeps the fader on `sim.ee_fader` and saves the plot PNG. It does not export `_get_local_recs()` numerically or insert those arrays into `simData`. Standard saved-data fields do not include the custom fader object. A separate numerical source may exist outside the inspected folders, but none was identified here. Slides 45–46 were not available as a source file in the inspected local paper/doc tree, so exact matching to those panels is unverified.

There are two distinct routes:

1. **Illustrative conductance panel:** use the existing PNG/original slide graphic, with variable, unit, protocol, and source identified. No new run is needed, but the original figure's `pmod` labeling should not be carried into a scientific g-axis description.
2. **Reusable numerical g(t) curves:** first check whether original numeric recordings were retained elsewhere. Otherwise add a small post-run export of `sim.ee_fader._get_local_recs()` and rerun one illustrative seed using the intended protocol. Export actual g and time plus the dimensionless fade coefficient separately, and identify population, cell gid, synaptic mechanism, source class/projection, rank, units, sampling interval, and seed.

The current representative-synapse choice is “first encountered” for each modulator, and the plotted traces are from rank 0. Positive and negative representatives are not certified as the same postsynaptic cell/mechanism. For a paired illustration, choose both sources on an explicitly identified postsynaptic target. This needs a small recording/metadata/export change, not a new circuit model or optimization method. Changing simulation parameters alone does not supply the missing saved numerical traces.

## Recommended work order

1. Build S4 from the existing complete historical 2×2 cohort, with its own 10–15 s caption. S1/S2 can reuse main-figure summaries and should add information rather than repeat them.
2. Extract compact time courses for S3 and S5 from selected existing raw files where they reside. Inspect S3's initial near-target phase before choosing the final wording or requesting longer runs.
3. Decide whether S6 needs an illustrative existing graphic or numerical g traces. Only the second route may require a recording-enabled rerun.
4. Consider new parameter-only control runs only for a stricter matched later A1 protocol or additional thalamic sensitivity evidence. Those are optional refinements, not missing basic experiment implementations.

## Evidence and I/O limits

New remote payload: **1,080,927 bytes of distinct files** (six cfgs, 90 result JSONs, one conductance PNG). Some representative cfgs were inspected before being snapshotted, so this is distinct payload, not a measured wire-traffic total. The 22 rate/CV NetCDFs were already local. No large raw pickle, network parameter file, archive, or controller trace was loaded. Directory listings were nonrecursive and targeted.

- [Read audit and hashes](data/inventories/supplementary_read_audit.json).
- [Available experiment names](data/inventories/supplementary_remote_experiments.json).
- [Detailed data readiness](data/inventories/supplementary_data_readiness.json).
- [Bounded inventory script](code/inventory_supplementary_data.py), which reuses existing snapshots on subsequent runs.
- [Incremental findings log](notes/findings_log.md) and [task scope](notes/supplementary_simulations_task.md).

The source raw files were checked for presence/size, not revalidated byte by byte. Only representative seed-1000 cfg contents were inspected per new A1 condition; all 15 result summaries were checked. No production config or paper draft was edited, and no new simulation or HPC job was submitted.
