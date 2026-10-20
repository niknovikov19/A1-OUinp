# Connected current-step contract

CURRENT CONTRACT — implemented behavior; run-specific grids are in the registry.

Configuration: `exp_configs/batch_rxbkg_state1_mech1/net_hstep_newsec_var_seed_group_amp/`.
All five L2 populations are active with original active-to-active projections,
including within-population recurrence. Do not duplicate them with L2-origin
surrogates; outside-L2 inputs remain frozen surrogates. No fader or baseline
retuning. The construction check preserved 25 L2 projection pairs/175 rules,
not a measurement of realized synapse counts.

## Groups and batch axes

STEP_GROUPS contains dimensionless spatial multipliers: lists imply one;
dictionaries permit weighted groups. Amp is a separate signed nA coordinate:

```text
h_step[pop] = amp * group_multiplier.get(pop, 0)
batch axes = seed_main × step_group × amp
```

Any empty group yields zero current for all amps. `control` has no special code
path or separate batch mode. Redundant amplitude-labelled controls are intentional.
Streams depend on seed_main only, but [exact stochastic matching is not established](../issues/same_seed_reproducibility.md).

SEEDS_SUBSET/GROUPS_SUBSET/AMPS_SUBSET select Cartesian execution subsets; None
selects the full axis. PILOT/PILOT_ATTEMPT only affect naming, not grid/timings.

## Delivery, timing, naming

NetPyNE creates separate soma(0.5) IClamps: delay = onset, duration = simulation
end minus onset. No Vector.play is needed. Declare one clamp per active cell
even at zero current; baseline clamps remain separate.

Config timings are milliseconds. Derive half-open windows from T0_CALC,
H_STEP_T0, H_STEP_TRESP, and SIM_DURATION: baseline to onset, response from
H_STEP_TRESP to end, early/late equal halves of response. Latest completed
timings: 100 s total, onset 40 s, baseline 10–40 s, response 60–100 s,
early 60–80 s, late 80–100 s. Future protocols need not reuse these values.

EXP_LABEL names the circuit; GROUP_SET_LABEL versions group definitions.
Protocol folder names include seed/group/amp counts, duration/onset/response-start,
group-set label, amplitude bounds, and calibration labels. Path timings are
seconds, at most two decimals, no unnecessary trailing zeros. Subsets retain
the full protocol name. Save exact grids/groups in configs; counts/bounds
cannot encode irregular grids. Increment attempt for a distinct rerun.

## Saved interface

Each postfix includes seed/group/amp. Required per trial:

- cfg/cfg_<postfix>.json: full configuration and batch metadata.
- results/result_<postfix>.json: raw window counts/means, h vector, topology
  rules, and instantiated clamp counts.
- rvec_xr/rvec_<postfix>.nc: raw 5-ms sim_data_analyzer population-rate bins.
- hvec_xr/hvec_<postfix>.nc: current vector on the same time grid.

Leave raw PKLs/network files on HPC. Resource policy is operational, not part
of this scientific contract: latest run used 30 ranks/128 GB per child,
60-child ceiling and concurrency ten. Check installed helpers before launch.
