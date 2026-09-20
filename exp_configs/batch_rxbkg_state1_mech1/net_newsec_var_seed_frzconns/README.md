# Top-10 thalamic connection-freezing batch

Implements the final mixed run list in [the experiment report](../../../dev_scratch/thal_frz/analysis/exp_frz_key_experiments_and_next.md). The batch axes are `seed_main` and `frz_conn_group` (the ordered list below). Group order expresses priority; actual execution order depends on the batch runner.

| Order | `frz_conn_group` | Frozen projections | Reference |
|---:|---|---|---|
| 1 | `none` | none | Old `thal_ee_1` |
| 2 | `thal_irem` | all seven thalamic populations → IREM | New N1 |
| 3 | `irem_ire_ti` | IREM → [IRE, TI] | New N2 |
| 4 | `irem_tim` | IREM → TIM | New N3 |
| 5 | `ti_tc` | TI → [TC, HTC] | New N4 |
| 6 | `tim_tc` | TIM → [TC, HTC] | Old-equivalent `tim_core_0` |
| 7 | `irem_ire` | IREM → IRE | Old `irem_ire_0` |
| 8 | `irem_ti` | IREM → TI | Old `irem_ti_0` |
| 9 | `irem_core` | IREM → [TC, HTC, TI, IRE] | Old `irem_core_0` |
| 10 | `ti_tim_tc` | [TI, TIM] → [TC, HTC] | New N5 |

All conditions use `THAL_POPS = [TC, HTC, TCM, TI, TIM, IRE, IREM]`, surrogate inputs, `wmult=0.25`, `EEGain=0.5`, and no fading. Simulation duration is 15 s; rates, CVs, and cell-input statistics use 10-15 s. `thal_irem` includes IREM → IREM. Nonexistent requested projections have no effect; `tim_tc` omits the nonexistent TIM → TI/IRE pairs from the older `tim_core_0` list.

Seeds follow the existing mapping: stimulus = seed, connectivity = 2 × seed, surrogate = 3 × seed. Background seeds use a common population order across all ten conditions. Some archived core/matrix experiments used a different population order, so their background seed assignments differ; these reruns reproduce the interventions with the common ordering used in this batch.

Cell-input statistics remain enabled (`CELL_INP_STATS_ON=1`) with the existing live-source setting (`CELL_INP_STATS_USE_FRZ=0`). For each active postsynaptic cell, the current recorder saves `n_pre`, `r_pre_mean`, `w_sum`, `wr_sum`, `r_pre_wmean`, `rate`, and `cv`. These are connection/rate summaries for live thalamic sources; they exclude surrogate and external-background inputs and are not conductance/current traces. The existing collector stacks them over seed and frozen-group axes.
