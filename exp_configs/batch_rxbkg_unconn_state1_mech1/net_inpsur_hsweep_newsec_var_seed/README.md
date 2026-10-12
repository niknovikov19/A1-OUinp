# L2 h-sweep experiment

This experiment measures the direct open-loop population-rate response to an
additional somatic current `h`. It uses the calibrated `newsec` baseline with
all active-to-active connections replaced by frozen surrogate inputs.

The five L2 populations (`IT2`, `PV2`, `SOM2`, `VIP2`, and `NGF2`) receive
simultaneous, population-specific triangular currents. NetPyNE creates and
targets a separate zero-amplitude IClamp for each population. After network
creation, `modify_network()` attaches the waveform to those declared clamps
with `Vector.play`; it does not construct clamps manually.

The initial configuration is an explicitly labelled one-seed pilot using a
uniform amplitude of 0.1 nA. Its purpose is to choose useful fixed amplitudes
for the later five-seed dataset. Background rates, surrogate target rates,
membrane changes, resting-current clamps, and rate-control current corrections
are copied unchanged from `net_inpsur_rsweep_newsec_var_seed_pre`.
`PILOT_ATTEMPT` gives reruns a new result directory while retaining failed-run
evidence; the current attempt is 2.

Each job saves population-rate dynamics in `rvec_xr/` and the exact applied
current waveforms in `hvec_xr/`. The only batch coordinate is `seed_main`.
