# Connected L2 current-step validation: draft specification

HISTORICAL — retained evidence/proposals, not a current contract or pending run.

Paths written as data/ or code/ are relative to dev_scratch/step_resp/, not this document.

## Purpose

Test whether the measured open-loop J and Q predict the steady population-rate
change produced by an added somatic current in a connected L2 circuit:

```text
delta_r_pred = solve(I - J, Q @ delta_h)
```

The input is a step held to simulation end. The measured response is the late
mean rate change; the transient is retained to check settling, but predicting
its time course is outside this experiment's scope. This document proposes
the first setup. The user has authorized first-test execution; its revised
parameters and completed local checks are recorded in
[`connected_hstep_testing.md`](connected_steps_2seeds_5pa_execution.md). Timings and grid
sizes below describe the initial broader proposal; the first test uses the
reviewed configuration in that status document.

## Identity and circuit

Proposed configuration location:

```text
exp_configs/batch_rxbkg_state1_mech1/net_hstep_newsec_var_seed_group_amp/
```

Use `EXP_LABEL = 'L2'` and population order:

```text
IT2, PV2, SOM2, VIP2, NGF2
```

Start from the calibrated h-sweep configuration and its bundled baseline
assets. Keep the same cell counts, membrane mechanisms, synaptic properties,
`wmult = 0.25`, `EEGain = 0.5`, and `newsec` connection targets. Background
`rx`, resting-current clamps, rate-control current corrections, and external
surrogate target rates retain their established values.

Change the subnet topology from fully frozen to connected within L2:

```python
cfg.subnet_build_flag = 1
cfg.subnet_params['pops_active'] = L2_POPS
cfg.subnet_params['conns_frozen'] = []
```

The subnet builder preserves active-to-active connections and uses frozen
surrogates for inputs from populations outside L2. Restore every existing
L2-to-L2 projection, including connections between cells of the same
population. Retain the model's existing autapse policy. L2-origin frozen
inputs must not duplicate the restored recurrent projections.

Use a connected network from time zero. The existing connected pulse example
also uses an EE surrogate/recurrent fader; this validation proposes no split
connections or fader, so the baseline and post-step measurements refer to the
same fixed circuit.

## Definition and delivery of h

`h_i` is an additional somatic IClamp amplitude in nA on every active cell of
population `i`, exactly as in Q identification. Each job has a complete
population-indexed vector `h_step`, including explicit zeros. It is derived
from a named spatial group and a separate signed current amplitude:

```text
h_step[i] = amp * group_multiplier[i]
h(t) = 0             for t < t_step
h(t) = h_step        for t_step <= t < simulation end
```

Declare one separate NetPyNE `stimSourceParams` IClamp and corresponding
`stimTargetParams` entry per population, targeting `soma`, `loc = 0.5`.
Use `delay = t_step`, `dur = simulation_duration - t_step`, and the job's
constant population-specific `amp`. NetPyNE already supports this rectangular
step directly; sparse `Vector.play` driving is unnecessary here.

The clamps are additive to all baseline-current components. Declare the same
sources and targets even in zero-step controls, and keep stimulus creation
order identical across jobs.

## Timing and rate measurements

Proposed first timing, to be checked in a pilot:

| Interval (s) | Purpose |
| --- | --- |
| 0–10 | Initial connected-circuit settling |
| 10–20 | Pre-step baseline measurement |
| 20 | Step onset |
| 20–40 | Allow the perturbed circuit to settle |
| 40–60 | Primary steady-response measurement |

Total duration is 60 s. Hold the step through simulation end, with no return
to zero. Independent jobs for different step vectors avoid carrying adaptation
from one probe into the next.

The timing constants are in milliseconds. Add only `H_STEP_TRESP = 40 * 1e3`
for the response-window start. Derive `RATE_WINDOWS` from those constants:
baseline `[T0_CALC, H_STEP_T0)`, response `[H_STEP_TRESP, SIM_DURATION)`,
and early/late response windows split at their midpoint. Convert to seconds
for the saved measurement windows; no separate window limits need editing.

Compare the 40–50 and 50–60 s means, and inspect the whole rate trace. A late
window is not evidence of a steady state by itself. If systematic drift or
adaptation remains, extend the common timing for controls and treatments
before the main batch; do not retune baseline inputs to obtain settling.

Obtain window means from population spike counts divided by cell count and
window duration. Use `sim_data_analyzer` for population selection, spike
processing, and compact rate traces. Keep counts or unsmoothed binned rates
for endpoint estimates; figure smoothing must not determine the static mean.

## Probe design and matched controls

Use seeds `1000`–`1004`. Preserve the h-sweep random-stream mapping, including
connection, background, and surrogate seeds. Neither the probe identifier nor
its amplitude enters random seeds. Within each seed, topology, cell placement,
and external random streams should match across controls and treatments;
confirm equal pre-step activity in a pilot.

For every seed and amplitude, the empty group produces a control with every
entry of `h_step` equal to zero, run with the same timing. Redundant controls
over amplitudes are accepted. For every treatment define the primary observed
response using the control with matching seed and amplitude:

```text
delta_r_obs(seed, step_group, amp) =
    mean_rate_treatment(40–60 s) - mean_rate_control(40–60 s)
```

Also save each job's pre/post change and its pre-step difference from the
matched control. The primary comparison removes drift in the unperturbed
connected circuit and compares two states at the same elapsed time.

Start with basis-vector probes, one input population per job:

```text
h_step = +0.005 nA * e_i
h_step = -0.005 nA * e_i
```

Here `e_i` selects one L2 population. Both signs test the local linear
approximation and expose directional differences. The same current magnitude
has different direct effects because Q differs between populations; save and
inspect the predicted rate changes before launch. The proposed magnitude is
small relative to the identification sweep and can be reduced if predicted
responses leave the measured operating range.

The first complete batch has 12 conditions per seed: five single-population
groups and one empty group, each at two amplitudes, giving 60 simulations.
After inspecting that batch, an optional second magnitude `+/-0.01 nA` adds
60 simulations, including the redundant empty-group controls at those
amplitudes. Choose optional multi-population vectors in advance
to test superposition after the individual input columns are validated.

A minimal pilot is seed 1000 with the zero-step control and positive IT2 and
NGF2 probes. It checks connectivity, step delivery, baseline matching, and
settling. Its outputs may be reused only if the finalized main protocol is
identical.

### Group definitions and batch coordinates

Define the spatial groups in the new experiment's `batch_params.py`:

```python
STEP_GROUPS = {
    'IT2': ['IT2'],
    'PV2': ['PV2'],
    'SOM2': ['SOM2'],
    'VIP2': ['VIP2'],
    'NGF2': ['NGF2'],
    # 'all_L2': L2_POPS.copy(),
    # 'IT2_PV2': {'IT2': 1, 'PV2': 0.5},
    'control': [],
}
GROUP_SET_LABEL = 'singlepop_v1'
AMP_VALUES = [-0.005, 0.005]
```

A list assigns multiplier 1 to each listed population. A dictionary specifies
population-specific dimensionless multipliers, including negative ones if
needed. Amplitude is never embedded in a group definition. The empty
`control` group is an ordinary empty group, which produces zero current for
any amplitude. Its name has no special meaning to the experiment code.
The five individual populations and this empty group are enabled initially;
the two multi-population examples are currently commented out.

The three batch coordinates are `seed_main` (integer), `step_group` (string),
and `amp` (signed numeric value in nA). `post_update(cfg)` resolves the group
and amplitude into the full `cfg.h_step` dictionary, derives `cfg.step_pops`
from nonzero currents, and sets all random streams from the seed alone.

The group axis is derived directly from `list(STEP_GROUPS)`. The ordinary
seed/group/amplitude Cartesian product produces all 60 jobs together, with
no separate control mode or name-specific validation. Zero is allowed as an
ordinary amplitude value as well.

Optional `SEEDS_SUBSET`, `GROUPS_SUBSET`, and `AMPS_SUBSET` select Cartesian
subsets for pilots and later HPC chunks without changing the full protocol
recorded in folder names. `None` selects the complete corresponding axis.
These settings treat all groups identically. The three-job minimal pilot is:

```python
SEEDS_SUBSET = [1000]
GROUPS_SUBSET = ['control', 'IT2', 'NGF2']
AMPS_SUBSET = [0.005]
```

`PILOT` and `PILOT_ATTEMPT` are in their own configuration block; they affect
folder naming only and do not select a smaller grid.

### Result folder and job names

The initial shared result subfolder is:

```text
exp_L2_pilot1_nseed_5_ngroup_6_namp_2_dur_60_step_t0_20_tresp_40_gset_singlepop_v1_amin_-0.005_amax_0.005_ictrl_wmult_0.25_ee_0.5
```

Times in the name are seconds, rounded to at most two decimal places with
trailing zeros removed; integer times have no decimal point. Group-set label,
group/amplitude counts, and amplitude bounds keep names compact even for many
amplitudes. The full
group table and exact grid, including irregular grids, live in each job's
configuration. Update the versioned group-set label if definitions or a grid
change while those counts/bounds remain identical; increment the pilot
attempt for a distinct rerun. Controls and execution subsets retain the full
protocol name rather than generating separate scientific datasets.

Individual files use all three coordinates, for example:

```text
rvec_00001_seed_1000_group_IT2_amp_0.005.nc
```

The result root follows the same experiment path under `exp_results/`.

## Prediction inputs and operating point

Both saved matrices use input-first orientation. Align by population labels
before transposing:

```text
J[post, pre] = W_saved[pre, post]
Q[post, h_pop] = Q_saved[h_pop, post]
```

The Q source is the completed symmetric slow five-seed identification:

```text
dev_scratch/step_resp/data/l2_current_sweep_5seeds_pm100pa_t40s/processed/
    tau_0.2/qmat.nc
    tau_0.2/richards_coeffs.json
```

Propose the pooled 0.2-s Q as the primary estimate. Retain 0.1-s and 0.4-s
versions and separate rising/falling derivatives as declared sensitivity
analyses. NGF2 branch gains differ strongly, so its prediction uncertainty
must remain visible. Do not select a Q variant retrospectively to improve
agreement with connected results.

J was evaluated at the frozen presynaptic target-rate vector:

```text
r_target = [2, 12, 6, 7, 1] Hz
```

Q was evaluated at zero added current with those frozen inputs. Measure the
connected zero-step baseline and compare it with `r_target` and with the
open-loop unperturbed output rates. Connecting the circuit can shift both
rates and input statistics; subtracting the measured connected baseline does
not relocate the existing derivatives to that new operating point. Report
any mismatch as a limitation of this J/Q test. If it is large, discuss the
identification strategy before treating the test as a local validation;
baseline correction is not an automatic processing step.

Before computing numerical predictions, choose and validate a finite J.
The local candidates inspected on 2026-10-14 are:

| Local J candidate, relative to the r-sweep result root | Missing entries (`pre -> post`) |
| --- | --- |
| `exp_pre_L2_post_L2/combined/results/wmat_tau_0.3.nc` | PV2 -> NGF2; VIP2 -> SOM2; VIP2 -> NGF2 |
| `ctx/wmat_tau_0.2.nc`, restricted to L2 | PV2 -> NGF2; SOM2 -> IT2; NGF2 -> VIP2 |

The common local result root is:

```text
exp_results/batch_rxbkg_unconn_state1_mech1/
net_inpsur_rsweep_newsec_var_seed_pre/
```

These missing values are failed or unavailable estimates, not established
structural zeros. Resolve their fitting/provenance and freeze one consistent
J source before the main prediction comparison. Do not combine entries from
different matrices without an explicit scientific decision and provenance.
Baseline/topology pilots can proceed independently of this fitting issue.

Save matrix labels, input hashes, fitting settings, evaluation point, and
predicted responses in a local prediction manifest before examining treatment
outcomes. Compute with `solve(I - J, Q @ h_step)` and record the condition
number of `I - J`. This static calculation alone does not establish dynamical
stability; use the connected baseline and step traces to assess settling.

## Comparison and outputs

For each probe, compare the five-component predicted and observed rate-change
vectors, first per seed and then across seeds. Report absolute errors in Hz,
mean error and variation across seeds, and overall vector error. Relative
errors are useful only where the response is appreciably different from zero.
Seeds are independent replicates; smoothed time samples are not.

Include the direct prediction `Q @ h_step` alongside the feedback prediction
to test whether J improves the result. Inspect positive/negative symmetry,
the response divided by step amplitude, and the central difference across
the two signs. Keep predictions below zero visible as evidence that the
linear approximation left its useful range, rather than clipping them.

HPC jobs should save ordinary configurations and raw simulation artifacts,
compact population rate traces and applied-current metadata, and window
counts/means with seed and probe identifiers. Retain a topology summary that
verifies recurrent L2 projections, absence of duplicated L2 surrogates, and
the external surrogate rates. Save grid-free rate/current figures for pilots.

Copy compact traces, window summaries, and representative metadata once to:

```text
dev_scratch/step_resp/data/l2_hstep_validation/
    input/
    predictions/
    processed/
    figures/
```

Keep comparison code in `dev_scratch/step_resp/code/` and process locally in
the existing NetPyNE environment. Document remote provenance using HPC paths,
not read-only mount paths.

Proposed HPC allocation remains 30 ranks and 128 GB per child, with concurrency
5 and a lightweight BatchTools controller. The current protected ceiling is
ten children per submitted batch, so execute this probe set in explicit
chunks of at most ten jobs; retain all selected empty-group/amplitude
combinations and pair results through seed/group/amplitude metadata. Every
chunk uses the same reviewed protocol.

## Items to settle before implementation

1. Review the implemented configuration, group selection, and 60-s timing.
2. Primary J source and resolution of its missing entries.
3. Whether to start with `+/-0.005 nA` in every population or choose
   population-specific amplitudes from the predicted responses.
4. Primary pooled Q convention and presentation of NGF2 branch sensitivity.

After settling these choices: implement the connected configuration and
compact outputs, verify topology and additive clamps, run the minimal pilot,
check the connected operating point, then launch the complete probe set and
compare static predictions locally.
