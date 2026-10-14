# Plan for estimating the static current-response matrix Q

## Objective

Measure the direct, open-loop effect of an added current on each population's
steady firing rate. Define `h_i` as the amplitude of a new somatic IClamp on
every active cell in population `i`, in nA. At the unperturbed operating point
`h = 0`, estimate

```text
Q[post, pre] = d r_post / d h_pre
```

This experiment keeps the calibrated baseline untouched: background `rx`,
frozen surrogate inputs and their target rates, membrane mechanisms, and both
existing `ibkg` and rate-control current corrections. The new clamp adds only
`h`; it does not replace or modify a baseline clamp.

## Experiment identity and initial scope

The experiment configuration will be located at:

```text
exp_configs/batch_rxbkg_unconn_state1_mech1/
net_inpsur_hsweep_newsec_var_seed/
```

Its results will use the matching path below `exp_results/`. The directory name
uses `hsweep` rather than naming a triangular waveform so that another sweep
waveform can be adopted later without renaming the experiment family. The
generated run label and saved configuration must identify the actual waveform
and current ranges used by each run.

The first meaningful experiment is restricted to the five L2 populations:

```python
EXP_LABEL = 'L2'
POPS_USED = L2_POPS
```

Here `L2_POPS` is `IT2`, `PV2`, `SOM2`, `VIP2`, and `NGF2`. A separate
pre/post label is unnecessary because the direct current response is
one-to-one. Intermediate pilot and diagnostic runs are allowed before the
canonical L2 dataset and should be clearly marked as such.

## Experiment design

1. Use the five active L2 populations and the fully frozen recurrent-input
   setup from the [presynaptic triangular sweep](../../exp_configs/batch_rxbkg_unconn_state1_mech1/net_inpsur_rsweep_newsec_var_seed_pre/exp_cfg.py),
   including its `newsec` connection targeting. Leave every frozen
   presynaptic population at its constant target rate.
2. Declare a separate, zero-amplitude somatic IClamp for each population
   through NetPyNE's `stimSourceParams` and `stimTargetParams`. This leaves
   clamp creation, population targeting, section selection, and storage in
   NetPyNE's normal stimulus machinery.
3. After NetPyNE creates the network, use the experiment's `modify_network()`
   hook only to find these declared clamps and attach a triangular waveform to
   each clamp's `_ref_amp` with `Vector.play`. Follow the waveform-driving part
   of the [existing time-varying current implementation](../../exp_configs/batch_rxbkg_unconn_state1_mech1/net_inpsur_hr_osc_var_seed_f_amp/exp_cfg.py),
   without manually constructing new IClamp objects. Store the play vectors so
   they remain alive for the whole simulation. Use a few linearly interpolated
   triangle corners rather than a timestep-sized vector per cell.
4. Hold `h_i = 0` for the first 5 s. Then run a continuous, zero-centered
   triangle: `0 -> +A_i -> 0 -> -A_i -> 0`, repeating with period 7.5 s.
   Start with a 20 s simulation, matching the presynaptic sweep. The waveform
   is deterministic and its actual current values are known exactly.
5. Drive all active populations simultaneously. With active-to-active
   connections frozen and each clamp local to its own population, each output
   rate depends on its own `h_i`; the resulting Q is diagonal. Verify the
   decoupled topology in a pilot run rather than relying on that assumption.
6. Make `seed_main` the only batch coordinate, provisionally using seeds
   `1000`–`1004` to match the existing J sweep. Current amplitudes `A_i` are
   fixed configuration values, not a batch coordinate.

## Pilot and next run

The completed one-seed pilot used a common `0.1 nA` amplitude, a `7.5 s`
triangle period, and a `20 s` simulation with the first `5 s` unperturbed.
It established measurable pooled slopes, but the rising and falling branches
differ substantially for several populations.

For the next diagnostic run, keep the common amplitude at `0.1 nA`, double the
period to `15 s`, and extend the simulation to `35 s` so that two complete
post-baseline cycles remain available. This isolates the effect of sweep
speed. A simultaneous increase to `0.25 nA` is deferred: with `T = 15 s`, the
triangle would move 25% faster in current space rather than slower. If the
wider range is later needed, use `T = 18.75 s` to preserve the present speed,
or `T = 37.5 s` to halve it. Population-specific amplitudes remain compatible
with the seed-only batch design and the fitter.

## Processing and checks

1. Run simulations and extract compact population-rate traces on HPC. Keep
   detailed simulation artifacts there; copy rate traces and representative
   configuration metadata locally for fitting.
2. Fit each population's rate-versus-`h_i` curve locally and evaluate its
   derivative at `h_i = 0` to obtain `Q[i, i]` in Hz/nA. Save fitted curves,
   diagnostic figures, and a population-labelled Q matrix.
3. Inspect rising and falling branches separately for lag or hysteresis;
   exclude turning points if smoothing or delayed responses bias the fit.
   Assess consistency across cycles and seeds, and flag failed or unstable
   fits rather than silently filling matrix entries.
4. Compare the unperturbed open-loop rates and baseline configuration with
   those used to estimate J. A mismatch is a diagnostic, not permission to
   retune the baseline. Confirm population ordering before combining J and Q.

The downstream recurrent-response prediction, `(I - J)^-1 Q delta_h`, and
closed-loop validation are separate work after Q has been checked. The L2
pilot and local fitter are now implemented; see
[`h_r_processing.md`](h_r_processing.md) for the processing command, outputs,
and current pilot diagnostics.
