# L2 h-sweep experiment

This experiment measures the direct open-loop population-rate response to an
additional somatic current `h`. It uses the calibrated `newsec` baseline with
all active-to-active connections replaced by frozen surrogate inputs.

The five L2 populations (`IT2`, `PV2`, `SOM2`, `VIP2`, and `NGF2`) receive
simultaneous, population-specific triangular currents. NetPyNE creates and
targets a separate zero-amplitude IClamp for each population. After network
creation, `modify_network()` attaches the waveform to those declared clamps
with `Vector.play`; it does not construct clamps manually.

`H_SWEEP_MIN` and `H_SWEEP_MAX` set the common current limits.
`H_SWEEP_LIMITS` repeats them for each active population because downstream
waveform and metadata handling remain population-indexed. One period follows
`0 -> max -> 0 -> min -> 0` at constant absolute sweep speed.

The current five-seed pilot sweeps from `-0.1` to `0.1 nA` with a `40 s`
period. Background rates, surrogate target rates, membrane changes,
resting-current clamps, and rate-control current corrections are copied
unchanged from `net_inpsur_rsweep_newsec_var_seed_pre`. `PILOT_ATTEMPT` gives
reruns a new result directory while retaining earlier evidence; the current
attempt is 5.

Each 85-second L2 simulation child uses 30 tasks/ranks and 128 GB RAM. The
five seeds may run concurrently; the BatchTools controller uses a separate
lightweight allocation.

Each job saves population-rate dynamics in `rvec_xr/` and the exact applied
current waveforms in `hvec_xr/`. The only batch coordinate is `seed_main`.
