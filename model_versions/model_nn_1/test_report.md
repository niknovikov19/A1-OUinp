# model_nn_1 test report

## Scope

Goal:

- test the current active `model_nn_1` workflow against `netParams_example.json`
- use the real `subnet_tuner` dependency available in the NetPyNE conda env
- report parity without running a simulation

Reference pair:

- `cfg_base.json`
- `netParams_example.json`

Active workflow path tested:

- `cfg.py`
- `netParams.py`


## Current Weight Pipeline

The workflow now follows the original-style weight flow:

- raw `wmat` is loaded from bundled `conn/conn.pkl`
- `cfg.wmult = 0.25` is applied inside `create_net_params_local.py`
- `EEGain` and other class/pop/layer gain multipliers remain active
- the active/reference `subnet_tuner` duplicates fader-managed split rules without static weight halving
- runtime `ConnFader` handles the recurrent/frozen fade after network instantiation

Config state:

- `cfg_base.json` no longer stores `wmat`
- `cfg_base.json` no longer carries the one-time normalization metadata
- `add_pulses = 0` still matches the provided reference netParams


## Environment

Python used:

- `/home/nnovikov/conda_env/netpyne/bin/python`

Observed environment warning:

- MPI library warning during import

Effect on this test:

- did not block config load
- did not block netParams build
- no simulation was attempted


## Executive Result

The active old-style workflow reproduces the structural `netParams_example.json` reference for the core network.

Exact parity:

- `popParams`
- `connParams`
- `synMechParams`
- `subConnParams`

Functional parity:

- `IClamp` source and target content matches as a multiset
- raw `IClamp` labels/order still differ for some entries

Remaining known non-exact raw comparison:

- `stimSourceParams`: 22 raw diffs caused by `IClamp` numbering/order
- `stimTargetParams`: 23 generated-only and 23 reference-only `IClamp` labels, with matching normalized target content


## Section-by-section Comparison

### Counts

| Section | Generated | Reference |
| --- | ---: | ---: |
| `popParams` | 57 | 57 |
| `connParams` | 7580 | 7580 |
| `stimSourceParams` | 111 | 111 |
| `stimTargetParams` | 111 | 111 |
| `synMechParams` | 12 | 12 |
| `subConnParams` | 0 | 0 |

### Raw key-level parity

| Section | Common keys | Exact matches | Raw diffs | Notes |
| --- | ---: | ---: | ---: | --- |
| `popParams` | 57 | 57 | 0 | exact |
| `connParams` | 7580 | 7580 | 0 | exact |
| `stimSourceParams` | 111 | 89 | 22 | `IClamp` numbering/order only |
| `stimTargetParams` | 88 | 88 | 0 | 23 generated-only and 23 reference-only `IClamp` names |
| `synMechParams` | 12 | 12 | 0 | exact |
| `subConnParams` | 0 | 0 | 0 | exact |


## Findings

### 1. Connection weights match exactly

Severity:

- resolved

Observed:

- all 7580 common `connParams` match exactly
- global `wmult` is now applied once from the pipeline
- fader split weights are no longer compensated in `netParams.py`
- `conns_split = 0.5` is structural fader metadata for the active subnet builder

Representative spot checks:

- `CxTh_CT5A_HTC = 0.175`
- `frz_CxTh_CT5A_HTC = 0.175`
- `EE_IT2_IT2_2 = 0.045`
- `frz_EE_IT2_IT2_2 = 0.045`
- `EI_CT5A_NGF1_NGF_1 = 0.19`

Interpretation:

- `conn.pkl` is again the source of raw weight matrices
- `cfg_base.json` holds editable scalar weight controls, not matrix payloads
- class/pop/layer gain multipliers such as `EEGain` remain active
- the external subnet builder must preserve split rule weights to reproduce this reference


### 2. Pulse mismatch remains resolved

Severity:

- resolved

Observed:

- generated `popParams` count matches reference
- generated `connParams` count matches reference
- no generated-only `PulseSeq`
- no generated-only `PulseSeq->TCM`

Interpretation:

- `add_pulses = 0` matches the provided reference netParams
- `pulse_seq_params` can remain in cfg as inactive/editable experiment metadata


### 3. `IClamp` content still matches functionally

Severity:

- low

Observed:

- `IClamp` source multiset matches exactly
- `IClamp` target multiset matches exactly
- raw labels differ because sources are numbered by `cfg.IClamp` insertion order

Interpretation:

- this is not a difference in amplitudes, durations, delays, sections, locations, or target populations
- only the generated label names differ for some `IClamp` entries


## Verification Commands

Compile/static check:

```bash
python3 -m py_compile model_versions/model_nn_1/cfg.py model_versions/model_nn_1/create_net_params_local.py model_versions/model_nn_1/netParams.py model_versions/model_nn_1/init.py model_versions/model_nn_1/conn_fader.py model_versions/model_nn_1/syn_mech_relabel.py
```

Non-simulation subnet semantic check:

```bash
MPLCONFIGDIR=/home/nnovikov/repo/A1-OUinp/model_versions/model_nn_1/.mplcache /home/nnovikov/conda_env/netpyne/bin/python - <<'PY'
from subnet_tuner import SubnetDesc, SubnetParamBuilder2
params = {
    'popParams': {
        'A': {'cellType': 'A', 'numCells': 1},
        'B': {'cellType': 'B', 'numCells': 1},
    },
    'connParams': {
        'A_B': {
            'preConds': {'pop': ['A']},
            'postConds': {'pop': ['B']},
            'weight': 1,
            'synMech': 'AMPA',
        },
    },
    'stimSourceParams': {},
    'stimTargetParams': {},
    'cellParams': {},
    'synMechParams': {},
    'subConnParams': {},
}
desc = SubnetDesc()
desc.pops_active = ['A', 'B']
desc.conns_frozen = {'A': ['B']}
desc.conns_split = {'A, B': 0.5}
desc.inp_surrogates = {'A': {'type': 'irregular', 'rate': 1, 'noise': 1, 'seed': 1}}
out = SubnetParamBuilder2().build(params, desc)
print(out['connParams']['A_B']['weight'], out['connParams']['frz_A_B']['weight'])
PY
```

Non-simulation netParams comparison:

```bash
MPLCONFIGDIR=/home/nnovikov/repo/A1-OUinp/model_versions/model_nn_1/.mplcache /home/nnovikov/conda_env/netpyne/bin/python model_versions/model_nn_1/_test/_real_compare.py
```


## Conclusion

Removing `wmat` from `cfg_base.json` and restoring weight transforms to the build pipeline preserved netParams parity.

The active subnet builder now preserves fader split weights, so the old local pre-compensation step was removed.

The remaining raw differences are limited to `IClamp` naming/order and are functionally equivalent under the current comparison.

No simulation was run in this pass.
