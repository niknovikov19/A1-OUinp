# Proposed uncorrected thalamus table — 2026-10-20

The user confirmed that the two improving single-projection interventions are
**IREM → TI** and **IREM → IRE**. The initially written IRE → TI / IRE → IREM
directions were corrected before defining the proposed comparison.

The proposed table has seven population rows, a target-rate column, and seven
condition columns. Suggested column groups: surrogate/frozen starting conditions
(all-surrogate, IREM→TI frozen, IREM→IRE frozen); naive full recurrence; and full
recurrence reached by fading (from all-surrogate, from the IREM→TI surrogate
condition, from the IREM→IRE surrogate condition). Show rate in Hz as mean ± SD
over seeds, with an optional final row of mean absolute population bias. Preserve
the population-specific pattern, since an aggregate error alone cannot establish
similar outcomes. Follow-up: the [numerical CSV](../data/tables/population_rate_table_thalamus_fading.csv)
is now prepared, with the two missing condition columns left blank. See the
[caption and reproduction notes](thalamus_fading_table_caption.md).

## Availability

All existing conditions below use all seven thalamic populations, seeds 1000–1014,
10 s duration and 7–10 s rate summaries, before second-stage current corrections.
Local per-seed caches and representative cfgs already exist under
`dev_scratch/thal_frz/{analysis/collected,cfg}/`. Their metadata and mean-rate
summaries were previously inventoried through `sim_data_analyzer` in
`data/inventories/supplementary_data_readiness.json`.

| Proposed condition | Existing experiment label | Status |
|---|---|---|
| All-surrogate | `thal_unconn` (15 seeds) | Available |
| IREM→TI remains surrogate | `irem_ti_0` | Available |
| IREM→IRE remains surrogate | `irem_ire_0` | Available |
| Naive full recurrence | `thal_ee_1` | Available |
| Full recurrence reached by fading all-surrogate inputs | `thal_all_fade` | Available |
| Full recurrence reached by fading IREM→TI | No matching experiment found | Missing in inspected mounts |
| Full recurrence reached by fading IREM→IRE | No matching experiment found | Missing in inspected mounts |

Existing labels use the suffix
`_nseed_15_t_7.0_10.0_wmult_0.25_ee_0.5` and prefix `exp_`, under the mounted
`net_newsec_ee_fade_var_seed` batch. The five cohorts thus supply five of seven
condition columns, plus the targets. The saved cfgs explicitly verify frozen
pairs `[IREM, TI]` and `[IREM, IRE]` for the respective interventions.

A fresh nonrecursive name listing of all three mounted batches found no additional
single-projection thalamic fades. See
`data/inventories/thalamus_branch_fading_name_check.json`. No remote file contents
were read in this follow-up check. Generic/misnamed experiments outside these
inventories or unmounted batches have not been ruled out.

The existing `thal_ti_tc_fade` and `thal_tc_ti_fade` restore different connection
sets and cannot fill the missing columns. Likewise, `a1_ee_fade_irem_ire_0` is a
full-A1 E–E-fading experiment retaining an IREM→IRE freeze; its name does not
identify a thalamus-only IREM→IRE restoration experiment.

## Interpretation and missing runs

The table is a useful endpoint test of dependence on the route into the same
fully recurrent circuit. Existing population-bias MAE is 0.545 Hz for all-surrogate,
2.382 Hz for IREM→TI frozen, 1.717 Hz for IREM→IRE frozen, 5.443 Hz for naive
recurrence, and 5.316 Hz for all-surrogate-to-recurrence fading. Here MAE is the
mean over populations of `abs(mean rate over seeds − target)`, not mean trial-level
absolute error. The closeness of the last two aggregate values does not by itself
establish equivalent population patterns or statistical equivalence.

To fill the two missing columns, use the existing connection-fader code with all
seven thalamic populations, `CONNS_FROZEN=[]`, `EE_FADER_ON=1`, and
`CONNS_SPLIT=[('IREM', 'TI')]` or `[('IREM', 'IRE')]`. All other connections remain
recurrent throughout. Start the selected pair entirely surrogate and end entirely
recurrent. Preserve baseline inputs, target rates, gains, and absence of second-stage
corrections; retain all 15 seeds and a common explicit fade/measurement schedule.
This is two parameter-only conditions (30 realizations), not a new model feature.
Do not use the current module defaults unchanged: they select full A1 and a
permanent IREM→IRE freeze.

The all-thalamus saved conductance example visually supports a 3–5 s transition;
the historical cfg does not serialize the fade points. Verify the intended schedule
before calling new conditions exact protocol matches. The existing 10 s duration
and 7–10 s endpoint window provide a sensible initial design. Retain compact
population rate time courses across the whole run so the initial improved phase
and post-restoration convergence can be checked, rather than only endpoint averages.

If all three fade conditions approach the same off-target population-rate pattern,
the supported statement is that the tested restorations fail to sustain the improved
state and approach a similar recurrent outcome. It is evidence consistent with
monostability over the tested conditions, not proof of a unique attractor for every
initial state or an “always” claim. Do not label outcomes equivalent merely because
a difference test is nonsignificant. Same numeric seeds also do not guarantee
identical realized connectivity/noise across static and fading construction paths.
