# Connected L2 current-step experiment

The implemented interface is documented in the
[current contract](../../../dev_scratch/step_resp/doc/contracts/connected_current_steps.md).
The [experiment registry](../../../dev_scratch/step_resp/data/registry.md) records
actual completed protocols, local datasets, HPC source paths, and limitations.

The current batch defaults describe the completed five-seed amplitude test:
IT2/PV2/ordinary empty control × −0.03/−0.015/+0.015/+0.03 nA, 60 trials,
100 s duration, onset 40 s, response 60–100 s.
[Results and provenance](../../../dev_scratch/step_resp/doc/results/connected_steps_5seeds_15_30pa.md).

- [batch_params.py](batch_params.py): groups, amplitude/seed axes, execution
  subsets, protocol timings, and attempt labels.
- [exp_cfg.py](exp_cfg.py): connected network, additive NetPyNE IClamps,
  derived windows, and compact output contract.

All L2 recurrent projections remain active, including within-population ones;
outside-L2 inputs remain frozen surrogates. Baseline calibration is unchanged.
Empty groups have no special handling: they generate zero added current for
every amplitude. h_step[pop] = amp × group multiplier.

No new run is authorized by these defaults. Choose an explicit protocol and
new attempt before another launch. Historical pilot settings and old helper
limits are not the current experiment contract.
