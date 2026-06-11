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


## Fix Applied

The one-time normalizer was run once:

- script: `_scripts/normalize_cfg_base_once.py`
- backup: `cfg_base.json.bak_20260611T050113Z`
- changed split-pair `wmat` entries: `163`
- skipped split pairs missing from `wmat`: `33`

Config changes made by the normalizer:

- removed active `wmult`
- set `add_pulses = 0`
- added guard metadata under `model_nn_1_cfg_base_normalization`
- pre-compensated existing fader split-pair `wmat` entries by `2.0`

Code changes:

- `create_net_params_local.py` now uses `cfg_base.wmat` directly
- `EEGain` and other downstream gain multipliers remain active
- `cfg.py` now provides `scale_wmat(cfg, factor)` for intentional manual global scaling
- `netParams.py` preserves an existing connection `sec` if no target-section rule matches


## Environment

Python used:

- `/home/nnovikov/conda_env/netpyne/bin/python`

Observed environment warnings:

- MPI library warning during import
- Matplotlib created a temporary cache directory because the default config path was not writable

Effect on this test:

- did not block config load
- did not block netParams build
- no simulation was attempted


## Executive Result

The active old-style workflow now reproduces the structural `netParams_example.json` reference for the core network.

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

### 1. Connection weights now match exactly

Severity:

- resolved

Observed:

- all 7580 common `connParams` match exactly
- previous 4x `wmult` mismatch is gone
- previous 2x fader split mismatch is gone

Representative spot checks:

- `CxTh_CT5A_HTC = 0.175`
- `frz_CxTh_CT5A_HTC = 0.175`
- `EE_IT2_IT2_2 = 0.045`
- `frz_EE_IT2_IT2_2 = 0.045`
- `EI_CT5A_NGF1_NGF_1 = 0.19`

Interpretation:

- `cfg_base.wmat` is now the source of truth
- split-pair `wmat` entries are pre-compensated for `subnet_tuner` static halving
- class/pop/layer gain multipliers such as `EEGain` remain active


### 2. Pulse mismatch is resolved

Severity:

- resolved

Observed:

- generated `popParams` count now matches reference
- generated `connParams` count now matches reference
- no generated-only `PulseSeq`
- no generated-only `PulseSeq->TCM`

Interpretation:

- `add_pulses = 0` now matches the provided reference netParams
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
python3 -m py_compile model_versions/model_nn_1/cfg.py model_versions/model_nn_1/create_net_params_local.py model_versions/model_nn_1/netParams.py model_versions/model_nn_1/init.py model_versions/model_nn_1/conn_fader.py model_versions/model_nn_1/syn_mech_relabel.py model_versions/model_nn_1/_scripts/normalize_cfg_base_once.py
```

Non-simulation netParams comparison:

```bash
/home/nnovikov/conda_env/netpyne/bin/python model_versions/model_nn_1/_test/_real_compare.py
```

Guard check:

- rerunning `_scripts/normalize_cfg_base_once.py` fails with the expected guard error


## Conclusion

The one-time JSON normalization and `wmult` removal fixed the active netParams parity bugs.

The remaining raw differences are limited to `IClamp` naming/order and are functionally equivalent under the current comparison.

No simulation was run in this pass.
