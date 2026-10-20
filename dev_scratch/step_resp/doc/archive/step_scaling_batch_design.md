# L2 amplitude-scaling test: current evidence and next batch

HISTORICAL — retained evidence/proposals, not a current contract or pending run.

Paths written as data/ or code/ are relative to dev_scratch/step_resp/, not this document.

Status: completed and processed as pilot3, run `hstep-l2-amplitude5-001`,
controller 118098; all 60 trials and 241 compact output files verified.
See [the run record](../results/connected_steps_5seeds_15_30pa.md) for execution and processing.
Estimates below use the completed second pilot's
local timing records and compact-input file sizes; no remote filesystem scan
was needed. This note is the current follow-up plan after
[the second-pilot analysis](connected_steps_2seeds_30pa_results.md).

Infrastructure update: [chunked monitoring and compact archives](../../../hpc/helper_src/INSTALL_MONITOR_ARCHIVE.md)
are installed and acceptance-tested. The user requested a total-child cap of
60 and concurrency ten; both policy promotions passed and the limits are installed.
The completed handoff used one checksummed archive transfer followed by local
unpacking: 8.51 MB transferred, 119.81 MB compact outputs unpacked. The estimates
and planned procedure below are retained as the pre-run specification.

## What we have

The connected L2 pilot tested IT2 and PV2 inputs at ±0.03 nA, with two seeds
and ordinary empty-group controls. Each simulation lasted 100 s, with input
starting at 40 s. Baseline rates use 10–40 s and response rates use 60–100 s.
The predictor is fixed: pooled five-seed J and Q with 0.2 s smoothing and the
requested provisional zeros for SOM2→SOM2 and NGF2→NGF2 in J. Q comes from the
slow symmetric current sweep. No fitting to the connected responses was done.

The following measurements subtract the controls' average before/after change
from the step run's before/after change. Values are mean ± seed SD, in Hz;
two seeds do not establish reliable uncertainty bounds.

| Input | Output | Measured change | J–Q prediction |
| --- | --- | ---: | ---: |
| IT2 −0.03 nA | IT2 | −0.525 ± 0.018 | −0.610 |
| IT2 +0.03 nA | IT2 | +0.619 ± 0.214 | +0.610 |
| IT2 −0.03 nA | PV2 | −2.377 ± 0.037 | −4.156 |
| IT2 +0.03 nA | PV2 | +3.128 ± 2.514 | +4.156 |
| PV2 −0.03 nA | PV2 | −3.381 ± 0.256 | −5.521 |
| PV2 +0.03 nA | PV2 | +5.861 ± 0.384 | +5.521 |

The signs and direct IT2 response are encouraging. Negative IT2 input
suppresses PV2 less than predicted; negative PV2 input also gives weaker
suppression. Positive/negative asymmetry could reflect nonlinearity, slow
variability, operating-point differences, or measurement error. Positive-input
PV2 rates still change between the early and late response windows. Same-seed
controls do not reproduce identical pre-step activity, so subtraction does
not cancel stochastic noise. Keep both response definitions visible.

Across seed/condition vectors, mean five-population RMSE is 0.712 Hz for J–Q
versus 0.964 Hz for Q-only with before/after control subtraction. With direct
post-step control subtraction the values are 0.967 versus 1.135 Hz. These
are descriptive comparisons, not a validation claim.

Current signed-amplitude figures and tables are in
[`data/_old/l2_connected_steps_2seeds_30pa_100s/analysis/jq/amplitude_summary/`](../../data/_old/l2_connected_steps_2seeds_30pa_100s/analysis/jq/amplitude_summary):

- `drift_adjusted_hz.png`: individual-seed before/after changes minus the
  controls' changes, against the fixed predicted line.
- `matched_post_hz.png`: individual-seed post-step rates minus matched-label
  control rates, against the same predicted line.
- `response_summary.csv`: means, seed SD, counts, and predictions for every
  input/output pair under both response definitions.
- `signed_response_components.csv`: per-seed symmetric component
  `(response(+A) - response(-A))/2`, its slope divided by A, and sign asymmetry
  `(response(+A) + response(-A))/2`. A symmetric linear response has zero
  sign asymmetry; noise and control differences also affect this diagnostic.

Only ±0.03 nA has been sampled in this pilot. Measured points do not imply
that intermediate amplitudes or the zero-input response have been measured
on the same response curve. The dashed line is the J–Q prediction.

Regenerate from the repository root using the existing NetPyNE environment:

```bash
MPLCONFIGDIR=.mplcache OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  /home/nnovikov/conda_env/netpyne/bin/python \
  dev_scratch/step_resp/code/summarize_hstep_amplitudes.py
```

## Next experiment

Use the existing `net_hstep_newsec_var_seed_group_amp` experiment with a fresh
pilot-attempt label (proposed `pilot3`) and these full axes:

- Seeds: 1000–1004.
- Groups: IT2, PV2, and the ordinary empty `control` group.
- Signed amplitudes: −0.03, −0.015, +0.015, +0.03 nA.
- Timings: unchanged 100 s duration, 40 s onset, baseline 10–40 s, response
  60–100 s, early/late halves 60–80 and 80–100 s.
- All subset flags: `None`; preserve baseline inputs, surrogate inputs,
  corrections, connectivity, and the frozen J/Q predictor.

Run a complete fresh batch, including the old amplitudes for seeds 1000 and
1001. Do not substitute historical trials into the new grid: preserve a
self-contained run and compare the existing pilot separately. Control remains
an ordinary batch group, including its redundant amplitude-labelled trials.

| Count | Calculation | Jobs |
| --- | --- | ---: |
| Current-step simulations | 5 seeds × 2 stimulated groups × 4 amplitudes | 40 |
| Zero-input controls | 5 seeds × 1 empty group × 4 amplitude labels | 20 |
| Simulation children | 5 × 3 × 4 | **60** |
| Batch controller | One submission of the complete grid | **1** |
| Total Slurm jobs | 60 children + controller | **61** |

No extra fitting or remote analysis jobs are planned. Retain 30 MPI ranks and
128 GB per simulation, concurrency ten, and the 2-core/16-GB controller.
At full concurrency the requested resources total 302 cores and 1296 GB,
possibly spread across nodes. Existing wall-time ceilings are unchanged.

## Runtime estimate

The completed 12-child pilot took 17 min 10 s from controller submission to
the last trial finishing, with 16 min 36 s in the trial phase. Saved per-child
NetPyNE total times were 297.36–321.41 s (mean 309.25 s). Slurm scheduling,
launch, and controller polling add overhead beyond those application times.

For 60 children at concurrency ten there are approximately **6 waves**.
Application timing alone gives 29.7–32.1 minutes (30.9 minutes at the mean).
Scaling the observed trial phase from three to six waves gives 33.2
minutes; allow roughly **35–40 minutes once resources are available**, plus
queue delays and finalization. This is an estimate, not a wall-time limit;
queue delays can dominate and are not estimated here. Child application time
corresponds to about 155 core-hours at 30 ranks per child.

## Copy budget and processing

Copy the same compact artifacts as before: configuration JSON, result JSON,
population-rate NetCDF, and current NetCDF for each child, plus one child
index. That is **4 × 60 + 1 = 241 files**. The previous 49-file handoff
contained exactly 23,958,898 bytes for 12 trials.

| Artifact | Estimated size for 60 trials |
| --- | ---: |
| Rate NetCDFs | 57.64 MB |
| Current NetCDFs | 57.64 MB |
| Configuration JSONs | 4.12 MB |
| Result JSONs | 0.28 MB |
| Child index | About 0.11 MB |
| Total | **About 119.8 MB / 114.2 MiB** |

These estimates scale measured local sizes by five; slightly longer metadata
will change the exact total. Budget **130 MB for the copy**, plus local plots
and analysis outputs. Raw simulation PKLs, saved networks, and remote figures
remain on HPC. This estimates transferred compact data, not total HPC storage.
At effective 1–10 MB/s the payload alone would take roughly 12–120 s;
SSHFS/per-file overhead and bandwidth determine actual copy duration.

Copy once to a fresh local dataset, proposed `data/l2_connected_steps_5seeds_15_30pa_100s/`.
Use HPC paths in its manifest, verify source/local hashes, then run local
count/waveform checks, response extraction, the fixed J–Q/Q-only comparison,
signed-amplitude summary, and rate-dynamics figures. Compute new-amplitude
predictions with the same frozen matrices; do not refit them. Keep the two
response definitions and per-seed results, with raw-count window means for
numerical comparisons and smoothing only for display.

The central test is whether halving amplitude halves the measured change,
and whether positive/negative central slopes agree with `(I - J)^(-1) Q`.
Compare early and late windows as a settling diagnostic. Five seeds improve
replication but do not guarantee that these effects become precise. If the
halved-amplitude responses are lost in variability, record that limitation.

## Preparation required before submission

The installed monitoring/archive infrastructure supports 256 completion files,
1-MiB index/lifecycle records, 25-ID accounting chunks, and five-child log pages.
Its 100-ID observation cap accommodates this run's 61 scheduler IDs. The
separately promoted [60-child / concurrency-ten policy](../../../hpc/helper_src/INSTALL_BATCH_60_CONCURRENCY_10.md)
is installed and leaves per-job limits unchanged. Check the real request's count and
concurrency during protected preparation before submission. The broader
thousand-job refactor remains deferred.

Then update the experiment axes/attempt label, create the bounded 60-child
request and exact completion list, verify the resolved folder/grid, and use
the established commit/push/HPC-update and submit/monitor/finalize workflow.
Execution and processing were subsequently authorized by the user; retain
this protocol and record actual timing, copy sizes, and results in the run note.
