# Experiment registry: static L2 response prediction

This is the single catalogue of local datasets and their scientific relevance.
All listed runs/analyses are complete, not future plans. [Current contracts](../doc/README.md)
define interfaces; [open work](../doc/plans/open_work.md) lists undecided branches.
Local paths below are relative to this data/ directory. Binary data are ignored
by git; this registry is tracked. pA = 0.001 nA. No data were discarded.

## Which results should I use?

| ID / role | Local directory | Measurement and use | Main limitation |
| --- | --- | --- | --- |
| **Q-L2: selected predictor input** | [l2_current_sweep_5seeds_pm100pa_t40s/](l2_current_sweep_5seeds_pm100pa_t40s) | Fully decoupled direct current response; five seeds, ±100 pA, 40-s triangle, 85 s total; pooled derivative at h = 0 | NGF2 rising/falling gains still differ |
| **J-L2: selected derived analysis** | [l2_rate_sweep_j_5seeds/](l2_rate_sweep_j_5seeds) | Refit existing five-seed L2 presynaptic-rate sweep; all 25 input/output pairs, derivative at target rates | Primary fit is 23/25 finite; two provisional zeros in prediction copy |
| **STEP-L2-5: main connected result** | [l2_connected_steps_5seeds_15_30pa_100s/](l2_connected_steps_5seeds_15_30pa_100s) | Five seeds; IT2/PV2/control × ±15/±30 pA; 100 s, 60 jobs; amplitude scaling and fixed J–Q test | Unmatched control noise, operating-point mismatch, nonlinear negative IT2 branch |
| **STEP-L2-2: archived comparison/reference** | [_old/l2_connected_steps_2seeds_30pa_100s/](_old/l2_connected_steps_2seeds_30pa_100s) | Two seeds; IT2/PV2/control × ±30 pA; same 100-s timing, 12 jobs; predecessor of STEP-L2-5 and frozen predictor reference | Superseded as main evidence; retained provenance dependency |

## Q-L2: selected direct current gains

Question: how much does each decoupled population's rate change per added
somatic current? All active recurrence, including within-population coupling,
is frozen. All five populations receive triangular currents simultaneously;
seed 1000–1004 is the only batch axis. Range −0.1 to +0.1 nA, T = 40 s,
5-s baseline plus two cycles = 85 s.

- Run: hsweep-l2-sym-slow-pilot-001, controller 118003.
- Inputs: input/hvec_xr/ and input/rvec_xr/, five pairs copied once from HPC.
- Selected Q: processed/tau_0.2/qmat.nc; pooled gains in Hz/nA are
  IT2 20.77, PV2 188.13, SOM2 122.93, VIP2 151.78, NGF2 54.77.
- Figures: processed/tau_0.2/fits/<population>.png. Additional 0.1/0.4-s and
  rising/falling fits are sensitivity diagnostics, not interchangeable primaries.
- [Result/caveat](../doc/results/l2_current_sweep_q.md),
  [processing](../doc/processing/current_sweep_to_q.md).

HPC source under /ddn/niknovikov19/repo/A1_OUinp/exp_results/:

```text
batch_rxbkg_unconn_state1_mech1/net_inpsur_hsweep_newsec_var_seed/
exp_L2_pilot5_nseed_5_t_5.0_85.0_tri_t0_5000_T_40000_h_-0.1_0.1_ictrl_wmult_0.25_ee_0.5/
```

## J-L2: selected presynaptic-rate gain analysis

This is a derived local analysis, not a new simulation. Source: clean L2 r-r
sweep, five seeds × five presynaptic populations, 20 s, 7.5-s triangle after
5 s. The input cache has raw 2-ms bins plus historical 10-ms smoothing.
Fitting uses 5–20 s, additional 0.2-s smoothing, 64 weighted input bins,
pooled branches, target rates [2, 12, 6, 7, 1] Hz.

- input/rates.nc and input/cfg.json are verified local copies of historical inputs.
- Original fit: processed/tau_0.2_bins_64/jmat_pooled.nc, with two non-finite
  gains, SOM2→SOM2 and NGF2→NGF2.
- Selected prediction copy: analysis/jmat_pooled_zero_filled.nc. Exactly those
  two entries are provisionally zeroed, not inferred absent. Further fitting
  was explicitly stopped. Primary J is pooled across five seeds.
- Figures: processed/tau_0.2_bins_64/fits/; old candidates/failed fits and
  branch/smoothing alternatives remain for audit.
- analysis/ also contains the historical quick prediction of the small-step
  preliminary run; that is not the current connected result.
- [Short J hand-off](../doc/results/l2_rate_sweep_j.md),
  [matrix contract/hashes](../doc/contracts/static_prediction.md).

HPC source under /ddn/niknovikov19/repo/A1_OUinp/exp_results/:

```text
batch_rxbkg_unconn_state1_mech1/net_inpsur_rsweep_newsec_var_seed_pre/
exp_pre_L2_post_L2_nseed_5_npre_5_t_5.0_20.0_tri_t0_5000_T_7500_rmax_10xbkg_500_ictrl_wmult_0.25_ee_0.5/
```

The local original is under exp_results/batch_rxbkg_unconn_state1_mech1/
net_inpsur_rsweep_newsec_var_seed_pre/exp_pre_L2_post_L2/combined/data_proc/;
input/rates.nc preserves its source/hash. Other historical rate-sweep runs
(L4, full cortex, legacy duplicate-artifact L2) are audited in
[the source reference](../doc/reference/rate_sweep_sources.md). They are not
additional selected J inputs, and full-cortex J is not silently spliced into L2.

## STEP-L2-5: main five-seed connected amplitude test

Question: do the fixed open-loop J/Q predict connected static changes, and do
responses scale with amplitude? All L2 recurrent projections remain active;
external surrogates/calibration are unchanged. Seeds 1000–1004, IT2/PV2/empty
control, amplitudes −0.03/−0.015/+0.015/+0.03 nA: 40 step jobs plus 20 redundant
zero-input controls. 100 s total; onset 40 s; baseline 10–40 s; response 60–100 s.

- Run hstep-l2-amplitude5-001; controller 118098, children 118099–118158.
- All 60 children completed; about 36½ min to completed observation.
  Compact handoff: 8.51-MB archive, 119.81 MB unpacked, 241 verified files.
- input/ is a symlink to the verified local helper cache in
  exp_results_local/hpc_codex/hstep-l2-amplitude5-001/compact/. No duplicate copy.
- Best overview: [analysis/jq/amplitude_summary/drift_adjusted_hz.png](l2_connected_steps_5seeds_15_30pa_100s/analysis/jq/amplitude_summary/drift_adjusted_hz.png).
- Alternative subtraction: analysis/jq/amplitude_summary/matched_post_hz.png.
- Absolute rate overlays: analysis/jq/rate_dynamics/, eight group/amp figures,
  five seed traces/population and baseline-shifted static predictions.
- Numbers: analysis/response_estimates.csv, analysis/jq/comparison_errors.csv,
  and analysis/jq/amplitude_summary/{response_summary,half_amplitude_checks}.csv.
- [Short results hand-off](../doc/results/connected_steps_5seeds_15_30pa.md).
  [Full historical log](../doc/archive/connected_steps_5seeds_15_30pa_log.md)
  is optional provenance/reproduction reference, not a work request.

Main finding: before/after control-subtracted vector error averages 0.403 Hz
for J–Q versus 0.799 Hz for Q-only. Negative IT2→PV2 suppression is weaker than
predicted and not proportional between amplitudes. This is descriptive evidence,
not complete validation; preserve alternative response definitions and seed SD.

HPC source under /ddn/niknovikov19/repo/A1_OUinp_codex/exp_results/:

```text
batch_rxbkg_state1_mech1/net_hstep_newsec_var_seed_group_amp/
exp_L2_pilot3_nseed_5_ngroup_3_namp_4_dur_100_step_t0_40_tresp_60_gset_1pop_v1_amin_-0.03_amax_0.03_ictrl_wmult_0.25_ee_0.5/
```

## STEP-L2-2: two-seed larger-step comparison

Same 100-s timing/circuit as STEP-L2-5, but seeds 1000/1001 and only ±0.03 nA:
eight steps/four controls, 12 jobs. Run hstep-l2-long-pilot-001/controller 118074;
all 49 completion files verified. Copied once: 49 compact files, 23.96 MB.

Use analysis/jq/amplitude_summary/ and analysis/jq/rate_dynamics/ for the
four-condition comparisons under _old/l2_connected_steps_2seeds_30pa_100s/.
Results have much larger measurement-definition sensitivity and only two seeds.
Archived because STEP-L2-5 supersedes it as experimental evidence. Its saved
manifest still identifies the frozen reference selected before the five-seed
batch; this dependency does not make it an active experiment. Do not pool it
with the new batch without an explicit choice.
[Findings and symbols](../doc/archive/connected_steps_2seeds_30pa_results.md).

HPC source under /ddn/niknovikov19/repo/A1_OUinp_codex/exp_results/:

```text
batch_rxbkg_state1_mech1/net_hstep_newsec_var_seed_group_amp/
exp_L2_pilot2_nseed_2_ngroup_3_namp_2_dur_100_step_t0_40_tresp_60_gset_1pop_v1_amin_-0.03_amax_0.03_ictrl_wmult_0.25_ee_0.5/
```

## Superseded datasets in _old/

These are retained for diagnostics/history. The two-seed ±30-pA dataset also
retains the frozen predictor reference manifest; the others are not predictor inputs.
They were moved locally, not deleted; HPC source names were not changed.

| Directory under _old/ | What it tested | Why not primary now |
| --- | --- | --- |
| l2_current_sweep_1seed_pm100pa_t7p5s/ | ±0.1-nA triangle, T = 7.5 s, 20 s total, one seed | Initial delivery/fitter test; substantial branch split |
| l2_current_sweep_2seeds_pm100pa_t15s/ | ±0.1 nA, T = 15 s, 35 s total, seeds 1000/1001; run hsweep-l2-slow-pilot-001 | Slower probe improved four populations; NGF2 still poorly identified |
| l2_current_sweep_5seeds_m50_p200pa_t20s/ | −0.05 to +0.2 nA, T = 20 s, 45 s total, five seeds; run hsweep-l2-asym-pilot-001 | NGF2 rising flank poorly constrained; replaced by wider negative range/slower Q-L2 |
| l2_connected_steps_2seeds_5pa_40s/ | IT2/PV2/control × ±0.005 nA, 12 jobs, 40 s, onset 20 s; run hstep-l2-first-pilot-002 | Small signal versus variability; response window not uniformly settled; superseded by longer/larger steps |
| l2_connected_steps_2seeds_30pa_100s/ | IT2/PV2/control × ±0.03 nA, 12 jobs, 100 s; run hstep-l2-long-pilot-001 | Superseded by five-seed amplitude test; retained comparison and frozen-manifest reference |

Earlier current-sweep HPC experiment labels share the Q-L2 parent:

```text
exp_L2_pilot2_nseed_1_t_5.0_20.0_tri_t0_5000_T_7500_amp_0.1_ictrl_wmult_0.25_ee_0.5
exp_L2_pilot3_nseed_2_t_5.0_35.0_tri_t0_5000_T_15000_amp_0.1_ictrl_wmult_0.25_ee_0.5
exp_L2_pilot4_nseed_5_t_5.0_45.0_tri_t0_5000_T_20000_h_-0.05_0.2_ictrl_wmult_0.25_ee_0.5
```

The small-step HPC label shares the connected parent above:

```text
exp_L2_pilot1_nseed_2_ngroup_3_namp_2_dur_40_step_t0_20_tresp_30_gset_1pop_v1_amin_-0.005_amax_0.005_ictrl_wmult_0.25_ee_0.5
```

[Current-sweep development](../doc/archive/current_sweep_development.md) and
[small-step results](../doc/archive/connected_steps_2seeds_5pa_results.md)
retain the numerical diagnostics. Their historical next-step proposals are
not current plans.

## Presentation collections

Presentation collection (not another experiment):
[slide_assets/jq_prediction/](slide_assets/jq_prediction/README.md) contains
five selected/replotted J–Q figures with source descriptions and reproduction
command. Original experiment inputs, fits, and comparison outputs are unchanged.

## Local-name migration and provenance

| Former data/ name | Current data/ path |
| --- | --- |
| l2_sym_slow_pilot | l2_current_sweep_5seeds_pm100pa_t40s |
| j_l2_refit | l2_rate_sweep_j_5seeds |
| l2_hstep_amplitude5 | l2_connected_steps_5seeds_15_30pa_100s |
| l2_hstep_pilot2 | _old/l2_connected_steps_2seeds_30pa_100s |
| l2_connected_steps_2seeds_30pa_100s | _old/l2_connected_steps_2seeds_30pa_100s |
| l2_pilot2 | _old/l2_current_sweep_1seed_pm100pa_t7p5s |
| l2_slow_pilot | _old/l2_current_sweep_2seeds_pm100pa_t15s |
| l2_asym_pilot | _old/l2_current_sweep_5seeds_m50_p200pa_t20s |
| l2_hstep_pilot1 | _old/l2_connected_steps_2seeds_5pa_40s |

Saved JSON/NetCDF provenance and hashes were not rewritten to hide old names.
The fixed predictor resolves historical local paths through code/dataset_paths.py,
then performs the same hash checks. All paths describing HPC sources remain
the actual HPC paths, not SSHFS mount paths. No HPC filesystem was scanned
or modified during this local reorganization.
