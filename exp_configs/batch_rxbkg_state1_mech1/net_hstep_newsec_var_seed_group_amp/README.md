# Connected L2 current-step experiment

Local configuration tests and real network-parameter construction have passed.
The twelve-child policy promotion passed; the first controller exposed an
HPC companion-repository import path, now corrected. Test status is recorded in
[`connected_hstep_testing.md`](../../../dev_scratch/step_resp/connected_hstep_testing.md).
The specification is
[`connected_hstep_spec.md`](../../../dev_scratch/step_resp/connected_hstep_spec.md).

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
amp:         -0.005, +0.005 nA
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
`[0.005]`. These selectors are for future pilot/chunk preparation; the current
first test needs twelve children, so a Gate-B promotion raises the protected
ten-child ceiling to twelve before its ordinary HPC request is prepared.

## Connected circuit and input

All existing L2-to-L2 projections remain recurrent, including projections
within each population. Inputs from outside L2 remain frozen surrogates. There
is no connection fader. The seven calibration assets in this folder are copies
of those used in `net_inpsur_hsweep_newsec_var_seed`.

Each population receives one separately named NetPyNE IClamp at `soma(0.5)`.
Its amplitude is constant, with a 20-s delay and 20-s duration. The baseline
current clamps are separate. No `Vector.play` waveform is needed.

`RATE_WINDOWS` is derived from `T0_CALC`, `H_STEP_T0`, `H_STEP_TRESP`, and
`SIM_DURATION`. These timing parameters are in milliseconds;
`H_STEP_TRESP = 30 * 1e3` sets the first test's response start to 30 s.
The baseline runs from `T0_CALC` to step onset; the response runs from
`H_STEP_TRESP` to simulation end. Early/late windows split the response
interval equally, so they follow any timing change automatically.

The first simulation lasts 40 s. Window statistics use raw spike counts over
half-open intervals: baseline 10–20 s, response 30–40 s, and settling checks
30–35 s and 35–40 s. Saved rate traces have 5-ms bins with no smoothing;
figures use a 0.2-s rolling average and have no axes grid.

## Result naming and outputs

The default protocol folder is:

```text
exp_L2_pilot1_nseed_2_ngroup_3_namp_2_dur_40_step_t0_20_tresp_30_gset_1pop_v1_amin_-0.005_amax_0.005_ictrl_wmult_0.25_ee_0.5
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
00001_seed_1000_group_IT2_amp_0.005
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
