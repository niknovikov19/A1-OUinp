# Selected L2 J: essential hand-off

**Completed analysis; further fitting was stopped by the user.** This page
identifies existing artifacts, not a fitting task.

J measures postsynaptic rate change per presynaptic rate change in fully
decoupled L2. The source sweep had five seeds and five presynaptic populations,
a 7.5-s triangle after a 5-s baseline, and 20 s total simulation time.

The selected fit pooled seeds and triangle branches over 5–20 s, with 0.2-s
additional smoothing and 64 weighted input bins. Derivatives were evaluated
at target rates [2, 12, 6, 7, 1] Hz in IT2/PV2/SOM2/VIP2/NGF2 order.

## Existing artifacts

Under [l2_rate_sweep_j_5seeds/](../../data/l2_rate_sweep_j_5seeds):

- Original measured fit: `processed/tau_0.2_bins_64/jmat_pooled.nc`, 23/25 finite.
- Prediction copy: `analysis/jmat_pooled_zero_filled.nc`; only SOM2→SOM2 and
  NGF2→NGF2 were set to zero by explicit user decision.
- Pairwise figures: `processed/tau_0.2_bins_64/fits/`.
- Verified source cache/configuration: `input/rates.nc` and `input/cfg.json`.

The two zeros are provisional assumptions, not measured absent projections.
The original fit is preserved. Several weak gains remain poorly identified;
the finite estimates are not all equally reliable. No connected step response
was used to tune this J.

[The prediction contract](../contracts/static_prediction.md) fixes the matrix
hash and orientation. [The registry](../../data/registry.md#j-l2-selected-presynaptic-rate-gain-analysis)
records source provenance. The
[historical refit log](../archive/l2_rate_sweep_j_refit_log.md) preserves the
missing-value diagnosis, fitting implementation, sensitivity results, and
optional reproduction code. That log is not a request to resume fitting.
