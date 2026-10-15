# Connected L2 current-step experiment

All twelve first-pilot simulations completed and 49 required outputs passed
protected finalization. Local descriptive analysis is in
[`connected_hstep_analysis.md`](../../../dev_scratch/step_resp/connected_hstep_analysis.md).
The same-seed reproducibility issue is documented there and its fix is deferred.
Test settings and launch status are recorded in
[`connected_hstep_testing.md`](../../../dev_scratch/step_resp/connected_hstep_testing.md).
The specification is
[`connected_hstep_spec.md`](../../../dev_scratch/step_resp/connected_hstep_spec.md).

The current configuration is the second pilot: ±0.03 nA, 100 s duration,
step onset 40 s, response 60–100 s, and the same two seeds and three groups.
See [the second-pilot run note](../../../dev_scratch/step_resp/connected_hstep_pilot2.md).

## Configuration to review

[`batch_params.py`](batch_params.py) defines the spatial groups and batch axes.
[`exp_cfg.py`](exp_cfg.py) defines the connected network, step timing, additive
NetPyNE IClamps, measurement windows, and outputs.

The first test enables `IT2`, `PV2`, and the empty `control` group. The other
individual L2 groups and the `all_L2`/`IT2_PV2` examples are currently commented
out. A list implies multiplier 1 for each listed population; a dictionary
assigns explicit multipliers. `IT2_PV2` uses multipliers 1 and 0.5. Group
definitions contain no current amplitudes. Any empty group produces zero
current for every amplitude, without name-specific handling.

The batch grid has three coordinates:

```text
seed_main:   1000–1001
step_group:  IT2, PV2, control
amp:         -0.03, +0.03 nA
```

In `post_update(cfg)`, the selected group is expanded into the full current
dictionary `cfg.h_step[pop] = cfg.amp * multiplier`. Unlisted populations have
zero current. `cfg.step_pops` is derived from the nonzero entries. All random
streams depend only on `seed_main`.

The group axis comes directly from `list(STEP_GROUPS)`; there is no separate
group-name configuration or batch mode. The first test grid produces 12 jobs:
eight treatment jobs and four zero-current jobs from the empty group, repeated
over the two amplitudes. This redundancy is intentional. Its `amp` coordinate
is still recorded even though the applied current is zero. An amplitude of
zero is also allowed for any group.

`PILOT` and `PILOT_ATTEMPT` only label the result folder; they do not change
the grid or simulation duration.

`SEEDS_SUBSET`, `GROUPS_SUBSET`, and `AMPS_SUBSET` optionally select smaller
Cartesian batches from the full grid. `None` selects the full axis. The same
selectors apply to every group, including `control`. For the three-job pilot,
select seed `[1000]`, groups `['control', 'IT2', 'PV2']`, and amplitude
`[0.03]`. These selectors are for future pilot/chunk preparation. The current
grid has twelve children, within the already promoted twelve-child ceiling.

## Connected circuit and input

All existing L2-to-L2 projections remain recurrent, including projections
within each population. Inputs from outside L2 remain frozen surrogates. There
is no connection fader. The seven calibration assets in this folder are copies
of those used in `net_inpsur_hsweep_newsec_var_seed`.

Each population receives one separately named NetPyNE IClamp at `soma(0.5)`.
Its amplitude is constant, with a 40-s delay and 60-s duration. The baseline
current clamps are separate. No `Vector.play` waveform is needed.

`RATE_WINDOWS` is derived from `T0_CALC`, `H_STEP_T0`, `H_STEP_TRESP`, and
`SIM_DURATION`. These timing parameters are in milliseconds;
`H_STEP_TRESP = 60 * 1e3` sets the current response start to 60 s.
The baseline runs from `T0_CALC` to step onset; the response runs from
`H_STEP_TRESP` to simulation end. Early/late windows split the response
interval equally, so they follow any timing change automatically.

The current simulation lasts 100 s. Window statistics use raw spike counts over
half-open intervals: baseline 10–40 s, response 60–100 s, and settling checks
60–80 s and 80–100 s. Saved rate traces have 5-ms bins with no smoothing;
figures use a 0.2-s rolling average and have no axes grid.

## Result naming and outputs

The default protocol folder is:

```text
exp_L2_pilot2_nseed_2_ngroup_3_namp_2_dur_100_step_t0_40_tresp_60_gset_1pop_v1_amin_-0.03_amax_0.03_ictrl_wmult_0.25_ee_0.5
```

Path timings use seconds, rounded to at most two decimal places with trailing
zeros removed: `20`, `20.5`, or `20.12`. Configuration timings remain in
milliseconds.

This name describes the complete grid, including the empty group; execution
subsets do not change it. Store the full normalized group table, amplitude
grid, and actual batch axes in each configuration. Change `GROUP_SET_LABEL` when
changing group definitions or selecting a different grid with the same
counts and amplitude bounds; use `PILOT_ATTEMPT` for a distinct rerun.

Each job's postfix includes all batch coordinates, for example:

```text
00001_seed_1000_group_IT2_amp_0.03
```

Required outputs are `cfg/cfg_<postfix>.json`,
`results/result_<postfix>.json`, `rvec_xr/rvec_<postfix>.nc`, and
`hvec_xr/hvec_<postfix>.nc`. The result JSON includes window spike counts and
rates, the resolved current vector, connection-rule topology metadata, and
instantiated clamp counts. Topology metadata counts rules rather than realized
synapses. Existing per-job completion files are not overwritten.

Raw PKLs, saved network parameters, rasters, and rate/current figures are
organized in separate typed subfolders. Prediction fitting and J/Q comparison
remain local analysis work, separate from simulation execution.
