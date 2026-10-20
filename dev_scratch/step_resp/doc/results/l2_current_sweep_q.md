# Selected L2 Q: essential hand-off

**Completed identification.** No simulation or refit is requested by this page.

Fully decoupled L2, seeds 1000–1004, all populations probed simultaneously with
separate added somatic currents. The triangle covered ±0.1 nA, T = 40 s,
two cycles after 5 s at zero: 85 s total. Q is the derivative at zero added
current, pooled over seeds and branches with 0.2-s smoothing.

| Population | Pooled Q (Hz/nA) |
| --- | ---: |
| IT2 | 20.77 |
| PV2 | 188.13 |
| SOM2 | 122.93 |
| VIP2 | 151.78 |
| NGF2 | 54.77 |

Dataset: [l2_current_sweep_5seeds_pm100pa_t40s/](../../data/l2_current_sweep_5seeds_pm100pa_t40s).
Selected file: `processed/tau_0.2/qmat.nc`; curves: `processed/tau_0.2/fits/`.

The diagonal is stable over tested 0.1/0.2/0.4-s smoothing. Branch dependence
remains: NGF2 rising/falling gains at 0.4 s are 83.82/31.46 Hz/nA versus pooled
54.88. A stable pooled number therefore does not establish a unique static gain.

[The prediction contract](../contracts/static_prediction.md) fixes the selected
hash/orientation. [The registry](../../data/registry.md#q-l2-selected-direct-current-gains)
records source provenance. [Code and optional reproduction](../processing/current_sweep_to_q.md)
are reference material; [earlier development](../archive/current_sweep_development.md)
is historical, not additional pending work.
