# Full-thalamus freezing experiments and next runs

## Scope and notation

Sources: [mean rates](exp_frz_info_r_mean.csv), [target rates](target_state_1.csv), and the per-seed NetCDF datasets in `collected/`.

- Old experiments: all 15 with `pops_active == A`, excluding `fade` and `unconn`; sorted by increasing MAE (lowest error first).
- New experiments and the final mixed run list: sorted by scientific priority, highest first.
- `C = [TC, HTC, TI, IRE]`, `M = [TCM, TIM, IREM]`, `A = C + M`.
- `E = [TC, HTC, TCM]`, `I = [TI, TIM]`, `RE = [IRE, IREM]`. Here `I` excludes reticular populations.
- `CE = [IT2, IT3, ITP4, ITS4, IT5A, IT5B, IT6, CT5A, CT5B, CT6, PT5B]`.
- `X → Y` expands to all requested pre/post pairs; only existing projections are affected. `+` between connection sets means their union.
- Rate groups are `TC/HTC/TCM`, `TI/TIM`, `IRE/IREM`; their targets are `8/8/2`, `15/10`, `15/10` Hz.
- MAE = mean across seven populations of `abs(mean rate over seeds − target)`. MAE is calculated from unrounded collected means, then displayed to two decimals; it is not the average of per-seed MAEs.

## All eligible old experiments, ordered by MAE

| Rank | Experiment | Frozen connections | E rates (Hz) | I rates (Hz) | RE rates (Hz) | MAE (Hz) | Main observation |
|---:|---|---|---|---|---|---:|---|
| 1 | `irem_core_0` | `IREM → C` | `10.30/8.09/4.73` | `15.12/9.44` | `16.31/10.76` | 1.12 | Largest overall improvement in this set; core improves, TCM rises. |
| 2 | `matx_core_0` | `M → C` | `10.81/8.23/4.83` | `14.70/9.27` | `15.61/11.15` | 1.24 | Similar to freezing only IREM output into the core. |
| 3 | `irem_ire_0` | `IREM → IRE` | `12.14/8.95/4.92` | `13.75/9.37` | `16.19/10.94` | 1.72 | Strong improvement from one projection; IRE approaches target. |
| 4 | `thal_pe_0` | `A → E` | `9.40/8.35/1.79` | `11.41/8.22` | `13.11/12.90` | 1.73 | Relay rates approach target; TI/TIM remain below target. |
| 5 | `thal_pti_0` | `A → I` | `12.51/12.13/2.21` | `15.31/10.68` | `13.45/12.84` | 2.03 | Restoring interneuron input conditions also improves relay rates. |
| 6 | `matx_ti_0` | `M → TI` | `14.15/11.04/4.94` | `15.07/8.77` | `15.70/11.66` | 2.26 | TI approaches target; residual core and matrix relay errors remain. |
| 7 | `tim_core_0` | `TIM → [TC, HTC]`* | `13.65/9.74/5.46` | `12.84/8.73` | `15.49/11.81` | 2.37 | Strong core improvement, but TCM rises from the baseline's 3.67 Hz. |
| 8 | `irem_ti_0` | `IREM → TI` | `14.38/11.79/4.74` | `15.13/8.72` | `15.62/11.73` | 2.38 | TI approaches target; a second candidate disinhibitory branch. |
| 9 | `thal_ti_tc_0` | `[TI, TIM] → E` | `12.80/12.60/2.19` | `11.52/8.25` | `13.59/12.76` | 2.71 | Interneuron output matters; TCM is much closer to target than in `tim_core_0`. |
| 10 | `thal_tc_ti_0` | `E → [TI, TIM]` | `21.85/18.17/3.79` | `10.82/7.77` | `13.66/13.31` | 5.27 | Little change from the fully coupled reference. |
| 11 | `thal_ee_0` | `(CE + E) → (CE + E)` | `21.88/18.15/3.74` | `10.75/7.76` | `13.50/13.45` | 5.32 | Little change; interpret in light of which requested projections actually exist. |
| 12 | `thal_ee_1` | none | `22.29/18.51/3.67` | `10.66/7.75` | `13.46/13.49` | 5.44 | Fully coupled reference: high relay rates, low TI/TIM, high IREM. |
| 13 | `irem_tc_0` | `IREM → [TC, HTC]` | `31.20/24.37/4.85` | `11.90/8.07` | `15.67/12.64` | 7.25 | Freezing direct IREM output to core relay cells worsens their rates. |
| 14 | `thal_ire_tc_0` | `[IRE, IREM] → E` | `48.71/37.37/54.34` | `4.64/3.97` | `10.82/22.09` | 22.16 | Large deterioration when live reticular-to-relay output is replaced. |
| 15 | `thal_ee_0_ire_tc_0` | `(CE + E) → (CE + E)` + `RE → E` | `49.14/38.64/57.40` | `4.07/3.62` | `10.16/22.90` | 23.18 | Adding the E-to-E freeze does not rescue the reticular-output intervention. |

*The saved `tim_core_0` cfg requests `TIM → C`. The current `conn/conn.pkl` and saved weights have no `TIM → TI` or `TIM → IRE` projections, so its effective freeze is `TIM → [TC, HTC]`. Use that explicit pair list for the rerun, retaining the old experiment name as provenance. Requested pair counts in earlier tables include nonexistent projections.

## What the next runs should resolve

The leading hypothesis is that network recruitment of IREM suppresses IRE, TI, and possibly TIM, reducing their inhibition of relay cells. IREM also inhibits relay cells directly, so these routes compete. The proposed `IREM → TIM` test adds the candidate path `relay → IREM ┤ TIM ┤ relay` to the core inhibitory routes already implicated by the data.

Freezing replaces a projection's live presynaptic source with target-rate surrogate activity. The postsynaptic neurons remain simulated. In particular, freezing `A → IREM` restores surrogate network input to IREM, including its recurrent input where present, while keeping its outputs to other populations live. Calibration predicts a rate near 10 Hz; this is not a hard output clamp. Both mean rate and timing can change, so rescue alone does not separate their contributions or prove one closed loop.

## Ten new experiments, ordered by importance

Every condition retains all seven active thalamic populations and the existing surrogate/background settings. N1–N10 are proposal IDs, not existing result labels. Their effective projection sets were checked against the current connectivity and are distinct from the 15 old conditions and from one another.

| Priority / ID | Freeze | Main comparison and question |
|---|---|---|
| 1 / N1 | `A → IREM` | First upstream test: does restoring IREM's calibrated input condition improve the network while preserving its live outputs to other populations? Compare with `thal_ee_1`, including whether IREM approaches 10 Hz. |
| 2 / N2 | `IREM → [IRE, TI]` | Test the combined core disinhibitory route. Existing `irem_ire_0`, `irem_ti_0`, and baseline complete a 2×2 branch comparison; `irem_core_0` adds the direct relay-output freeze. |
| 3 / N3 | `IREM → TIM` | Test whether IREM suppresses TIM and thereby disinhibits relay cells. Does TIM approach 10 Hz, and does its restored live output help both core relays and TCM? |
| 4 / N4 | `TI → [TC, HTC]` | Isolate core-interneuron output to core relays. Compare with the equivalent existing `TIM → [TC, HTC]` condition, `tim_core_0`. |
| 5 / N5 | `[TI, TIM] → [TC, HTC]` | Complete the TI-versus-TIM output factorial using N4, `tim_core_0`, and baseline. Compare with `thal_ti_tc_0` to isolate the additional effect of freezing their outputs to TCM. |
| 6 / N6 | `IREM → [IRE, TI, TIM]` | Combine N2 and N3. Does adding the TIM branch correct residual matrix/core error while keeping direct IREM-to-relay output live? |
| 7 / N7 | `C → IREM` | If N1 helps, isolate the core inputs recruiting IREM. The existing projections are from TC, HTC, and IRE. |
| 8 / N8 | `M → IREM` | Complement N7: isolate matrix input, including IREM recurrence. Existing projections are from TCM and IREM. N7/N8/N1/baseline form an input-source factorial. |
| 9 / N9 | `(A → IREM) + (IREM → [IRE, TI])` | Combine N1 and N2: does replacing the output branch still help after IREM receives surrogate inputs? A small extra effect is consistent with a shared route, but also with saturation or compensation. |
| 10 / N10 | `[TI, TIM] → TCM` | Isolate matrix-relay inhibition. Together with N5, baseline, and old `thal_ti_tc_0`, separate core-target and matrix-target contributions to the TCM trade-off. |

`TIM → [TC, HTC]` is an old-equivalent rerun, not an eleventh new experiment. Additional direct reticular-to-relay freezes are lower priority because the existing experiments already show strong deterioration. The proposals remain within the connection-freezing workflow.

## Cell-input statistics and comparison rules

Record input statistics in the new runs and selected old reruns using the same settings. Preserve seeds 1000–1014, simulation duration 10 s, and the 7–10 s measurement window used by the archived experiments.

- Separate contributions by presynaptic population and synaptic mechanism, identifying live, surrogate, and external-background sources separately. Total excitation/inhibition alone would hide the competing pathways.
- Record per-cell mean and variability of synaptic input, preferably both conductance and current where supported. Current also depends on postsynaptic voltage, so a current change alone need not imply changed presynaptic drive.
- Prioritize input onto IREM, IRE, TI, TIM, and the three relay populations; retain firing rates for all seven. For N1 inspect input to IREM; for N2/N3 inspect reticular input onto inhibitory cells; for N4/N5 and the TIM rerun inspect interneuron input onto TC/HTC and changes at TCM.
- Compare signed rate and input changes within matched seeds before averaging. Keep core and matrix readouts visible alongside MAE; a lower overall MAE can conceal a TCM increase.

Use identical recording definitions for the baseline and perturbations. Check effective frozen projections when simplifying an old condition, and compare rerun rates with the archived rates before attributing input-statistic differences to a circuit mechanism.

## Top 10 experiments to run next, old and new combined

This is the priority order for collecting cell-input statistics, not an MAE ranking. It contains five old reruns and five new conditions; the additional new proposals above are follow-ups.

| Run order | Origin | Frozen connections to run | Purpose of the recorded comparison |
|---:|---|---|---|
| 1 | Old: `thal_ee_1` | none | Common reference for rates and every input component. |
| 2 | New: N1 | `A → IREM` | Test upstream recruitment of IREM; measure changes in its inputs and its downstream effects. |
| 3 | New: N2 | `IREM → [IRE, TI]` | Test the combined core inhibitory route while keeping direct IREM-to-relay output live. |
| 4 | New: N3 | `IREM → TIM` | Test the matrix-interneuron route and whether it avoids the TCM worsening. |
| 5 | New: N4 | `TI → [TC, HTC]` | Measure the core-interneuron contribution to relay input and firing. |
| 6 | Old-equivalent: `tim_core_0` | `TIM → [TC, HTC]` | Use the clearer effective pair list; compare with N4 and examine why TCM increases. |
| 7 | Old: `irem_ire_0` | `IREM → IRE` | Record the strongest isolated IREM branch; quantify how IRE input/output changes. |
| 8 | Old: `irem_ti_0` | `IREM → TI` | Separate the TI branch from the IRE branch; together with N2 and baseline, measure their interaction. |
| 9 | Old: `irem_core_0` | `IREM → [TC, HTC, TI, IRE]` | Reproduce the lowest-MAE old condition; compare with N2 to measure the additional effect of freezing direct core-relay output. |
| 10 | New: N5 | `[TI, TIM] → [TC, HTC]` | Complete the TI/TIM output factorial with baseline, N4, and the TIM rerun. The archived `thal_ti_tc_0` supplies the broader all-relay rate comparison. |
