# Experiment candidates — no next protocol selected

These are distinct options, not an agreed sequence or permission to launch.
Each entry records where the idea came from, whether new features are needed,
and what decision is missing. Any chosen protocol would get its own amplitudes,
seeds, windows, job count, runtime/copy estimate, and new dataset identity.

## E2 — targeted follow-up of the negative IT2→PV2 discrepancy

Origin/status: an assistant proposal made explicit in this planning review,
motivated by the latest results; not a previously agreed experiment.
Proposed priority: P2, ahead of broadening the probe set if explaining the
current mismatch is the scientific objective.

The five-seed result has a negative IT2→PV2 response weaker than predicted at
−0.03 nA, but close at −0.015 nA. The response is not proportional between
those points. This is evidence to explain, not proof of a particular mechanism.
[Measured values and limitations](../results/connected_steps_5seeds_15_30pa.md).

Possible questions are narrower-amplitude behavior versus dependence on the
settling/averaging interval. These are different tests: the design should not
change several factors and then attribute the result to one. No amplitudes,
durations, number of seeds, or preferred explanation have been selected.

Implementation: existing step groups, amplitude axis, timing parameters, raw
rates, and analysis cover either kind of follow-up. Configuration/request
changes would be needed, not a new stimulus feature or fitter. There is no
blanket need to rerun J/Q or change the baseline. Core reproducibility remains
a disclosed limitation unless K1/E1 is separately resumed.

## E3 — probe the remaining individual L2 input populations

Origin/status: the earlier connected-experiment proposal included all five
single-population inputs; execution subsequently focused on IT2/PV2. The
SOM2/VIP2/NGF2 directions remain an unselected extension, not an overdue run.
Proposed priority: P3, after deciding that broader column coverage is useful.
[Original scope](../archive/connected_step_initial_proposal.md#probe-design-and-matched-controls).

Question: does the fixed predictor work for input directions not tested by
the completed connected batches? This adds input groups, not more active
populations: all five L2 populations are already present in the circuit.

Implementation: enable the existing group definitions in
[batch_params.py](../../../../exp_configs/batch_rxbkg_state1_mech1/net_hstep_newsec_var_seed_group_amp/batch_params.py),
choose amplitudes/seeds, and version the group/grid/attempt metadata. The
experiment/analysis already represent arbitrary input groups. No new network
or current-delivery feature is required. Different Q scales and provisional
SOM2/NGF2 self-gains matter when choosing/interpreting probes.

Dependency: a reviewed protocol and a measurement-quality decision; K1/E1 is
needed for a claim of exact matched-noise comparisons, not for merely running
descriptive comparisons. A grid over 60 jobs would require reviewed chunks
or new authority; very-large-batch support is not assumed.

## E4 — simultaneous inputs: test response addition

Origin/status: optional weighted/named groups and a later superposition test
were discussed in the original design; no combined-input batch was selected.
Proposed priority: P3, after choosing sufficiently interpretable component probes.
[Original proposal](../archive/connected_step_initial_proposal.md#probe-design-and-matched-controls)
and [implemented group interface](../contracts/connected_current_steps.md#groups-and-batch-axes).

Question: does the connected response to a combined current vector agree with
the fixed J–Q prediction and with the sum of the individual responses? The
prediction adds linearly by construction; the simulation need not.

Implementation: existing list/dict group definitions support this without new
stimulus code. Config/request changes are sufficient for simulation; a direct
measured-sum comparison table/figure may need a small local analysis addition,
since that comparison is not an existing dedicated output. It does not require
a new fitter.

Dependency: comparable individual and combined protocols. An IT2/PV2 combination
can use already tested directions; it does not require E3 first. Which old
trials are compatible, whether new component trials are needed, and the actual
weights/amplitudes remain decisions rather than assumptions.

## Not additional open experiments

The longer 100-s two-seed test and the five-seed/two-magnitude amplitude test
already happened. They are not repeated here as future work. The small
[same-seed repeat test E1](simulation_reproducibility.md#e1--small-identical-input-repeat-test)
belongs to bug verification, not this scientific extension queue. Further
J fitting is stopped; dynamic/oscillatory response prediction is outside the
current project scope. Neither is silently reintroduced by these candidates.
