# Thalamic fading table

**Table Sx. Thalamic population firing rates before current correction, with
surrogate inputs, frozen projections, and restoration of recurrence by fading.**
Rows show the seven modeled thalamic populations. The target-rate column gives
the prescribed firing rate in Hz. Each available condition reports the mean
population firing rate ± sample standard deviation across 15 realizations (seeds
1000–1014), averaged over 7–10 s of a 10 s simulation. Rates and standard
deviations are in Hz and are displayed to two decimal places.

In the all-surrogate condition, recurrent inputs within the thalamic subcircuit
are replaced by fixed-rate Poisson surrogate inputs. In the IREM→TI and IREM→IRE
frozen conditions, only the named projection is replaced by surrogate input;
the remaining thalamic connections remain recurrent. The fully recurrent column
shows the naive recurrent reference. The three fading columns refer to restoration
of full thalamic recurrence from the corresponding surrogate/frozen starting
condition: all-surrogate, IREM→TI frozen, and IREM→IRE frozen, respectively.
Inputs from the excluded cortical subcircuit remain surrogate inputs. All
conditions precede second-stage thalamic current corrections; baseline currents
are retained.

**Blank cells indicate unavailable experiments:** the IREM→TI and IREM→IRE
single-projection fading cohorts have not been located in the inspected mounted
results. They are placeholders, not zero rates or evidence about their outcomes.
The existing all-surrogate-to-recurrence fading cohort supplies the fifth
condition column. The table reports firing rates, rather than the signed errors
reported in the separate cortex/thalamus error tables.

## Files and reproduction

- [Paper table CSV](../data/tables/population_rate_table_thalamus_fading.csv): seven population rows, target rate, and seven condition columns; the last two columns have 14 empty cells in total.
- [Unrounded per-seed rates](../data/tables/thalamus_fading_rates_per_seed.csv): 525 records = five available conditions × seven populations × 15 seeds.
- [Source inventory and numerical summaries](../data/inventories/thalamus_fading_table_sources.json): original experiment paths, local cache/cfg paths, SHA-256 hashes, unrounded means and sample SDs, seeds, targets, window, and missing-condition status.
- [Initial assessment and missing-run parameters](thalamus_branch_fading_table_assessment.md).

Run from the repository root:

```bash
/home/nnovikov/conda_env/netpyne/bin/python dev_scratch/paper_figure_data_oct19/code/build_thalamus_fading_table.py
```

The generator uses `sim_data_analyzer.xr_io.load_xr` to read the five existing
local NetCDF caches under `dev_scratch/thal_frz/analysis/collected/`. It selects
the modeled population names explicitly, excluding surrogate-source coordinates
ending in `frz`. It checks the seed sets, active populations, targets, duration,
summary window, frozen/split projections, finite rates, and agreement with the
previously inventoried unrounded means. It reads no mounted result files and
does not run simulations. Its missing columns are explicit placeholders and
remain empty until verified sources are added deliberately.

## Sources and interpretation

| CSV condition | Existing experiment label |
|---|---|
| All-surrogate | `thal_unconn` |
| IREM→TI frozen | `irem_ti_0` |
| IREM→IRE frozen | `irem_ire_0` |
| Fully recurrent | `thal_ee_1` |
| Faded from all-surrogate | `thal_all_fade` |
| Faded IREM→TI | Missing |
| Faded IREM→IRE | Missing |

The existing experiment folders share the prefix `exp_` and suffix
`_nseed_15_t_7.0_10.0_wmult_0.25_ee_0.5`, under
`exp_results/batch_rxbkg_state1_mech1/net_newsec_ee_fade_var_seed/`. This table
uses the short uncorrected `thal_ee_1` reference, rather than the 220 s
`thal_orig` cohort used in the main error table. It retains the original E–E gain;
the excluded “without 50% E–E decrease” proposal is not part of this comparison.

The current table supports comparison of the available endpoint rate patterns.
It cannot yet establish convergence for the two missing restorations. Similar
endpoint population rates would be evidence consistent with convergence under
the tested protocols, rather than a general proof of monostability. Time courses
are needed to demonstrate the initial improved phase and its subsequent loss.
Historical saved cfgs do not serialize the precise fade points; the all-thalamus
conductance image visually supports a 3–5 s transition for the inspected example.
Same numeric seeds do not guarantee identical realized connectivity/noise across
static and fading construction paths.
