# model_nn_1 implementation log

## 2026-06-10 step 1
- Created the implementation log.
- Confirmed the current folder only had `cfg_base.json` and the sketch `run_exp_simple.py`.
- Compared the reference `net_newsec` experiment assets against `cfg_base.json`.
- Found that the main missing retained config items were pulse settings and fader timecourse settings.

## 2026-06-10 step 2
- Updated `cfg_base.json` so the retained experiment config now includes:
  - `add_pulses`,
  - `pulse_seq_params`,
  - `fader_on`,
  - `fader_pts`,
  - `fader_group_name`,
  - `fader_rec_dt`.
- Added `cfg.py` as a thin JSON loader around `specs.SimConfig(...)`.
- Added a small post-load override section plus helper functions for common seed and duration edits.

## 2026-06-10 step 3
- Added `netParams.py` with the retained post-build experiment logic:
  - mech changes,
  - target-section reassignment,
  - subnet build,
  - post-subnet recurrent/frozen synMech relabeling for the fader.
- Added a local fallback for frozen-rate loading so subnet assembly can use `target_state_1.csv` when the configured external path is unavailable.
- Added `init.py` with the old-style entrypoint flow and runtime fader hookup.
- Added local helper files `conn_fader.py`, `syn_mech_relabel.py`, and `target_sec_1.json`.
- Added a local `target_state_1.csv` fallback asset.

## 2026-06-10 step 4
- Ran static verification only.
- `py_compile` passed for the new Python files.
- Confirmed subnet, split-connection, pulse, mech-change, and fader wiring are present in the new workflow.
- Confirmed the new Python workflow does not include OU setup or ratecontroller logic.
- Noted that inactive OU-related keys still remain in `cfg_base.json`, but they are not used by the new Python workflow.

## 2026-06-10 step 5
- Vendorized the retained base-model assets into `model_nn_1/cells/` and `model_nn_1/conn/`.
- Added `create_net_params_local.py` as a local base builder wired to bundled assets instead of repo-root paths.
- Removed carried-over OU/cochlear/IC background branches from the standalone builder and left explicit `NotImplementedError` guards for those unsupported features.
- Added a local `subnet_builder.py` to replace the missing repo-level subnet builder for active-pop filtering, frozen surrogate populations, and split recurrent/frozen connection duplication.
- Rewired `netParams.py` and `init.py` so the old-style workflow now depends on local helper modules instead of repo-root imports and `chdir(...)`.
- Updated `cfg_base.json` so the frozen-rate file points to the bundled `target_state_1.csv` by default.

## 2026-06-10 step 6
- Re-ran static verification without simulation.
- `py_compile` passed for `cfg.py`, `create_net_params_local.py`, `subnet_builder.py`, `netParams.py`, `init.py`, `conn_fader.py`, and `syn_mech_relabel.py`.
- Confirmed the old-style entrypoint files no longer reference `subnet_tuner`, repo-root `create_net_params`, repo-root `chdir(...)`, or external helper imports like `from input ...`.
- Confirmed the bundled standalone assets now include 19 cell-rule JSON files plus `cellDensity.pkl` and `conn.pkl`.

## 2026-06-10 step 7
- Added `organization.md` with a detailed description of the standalone setup.
- Documented the hierarchy from `cfg_base.json` to `cfg.py`, `netParams.py`, and `init.py`.
- Documented helper-module responsibilities, dependency graph, subnet/fader interaction, and the most important function call relations.

## 2026-06-10 step 8
- Tested the current workflow against `netParams_example.json` without running simulations.
- Confirmed that the real `netParams.py` path currently fails during subnet build.
- Used a harness-only workaround to continue parity measurement without editing the workflow.
- Added `test_report.md` with the failure trace, section-by-section comparison, and the main remaining mismatches against the reference netParams.

## 2026-06-10 step 9
- Moved the temporary comparison harness files into `model_nn_1/_test/` instead of deleting them.

## 2026-06-10 step 10
- Rewrote `test_report.md` to remove overconfident parity claims derived from the improvised local subnet replacement.
- Reframed the reliable result as: the real current workflow fails during subnet build, so faithfulness against `netParams_example.json` is not yet established.
- Updated `organization.md` to mark `subnet_builder.py` as a provisional stand-in for a missing original dependency.

## 2026-06-10 step 11
- Rewired `netParams.py` to use the real `subnet_tuner` dependency from the NetPyNE conda environment.
- Re-ran the non-simulation netParams comparison against `netParams_example.json` through the real active workflow path.
- Rewrote `test_report.md` with the real comparison results.
- Updated `organization.md` so it reflects the active external subnet dependency and the remaining verified parity mismatches.

## 2026-06-11 step 12
- Traced the connection weight mismatches to two mechanisms:
  - `cfg_base.json` stores `wmat` after `wmult = 0.25` has already been applied, but the builder applies `cfg.wmult` again.
  - real `subnet_tuner` halves split recurrent/frozen rule weights for `conns_split = 0.5`, while `netParams_example.json` keeps full weights for both copies.
- Traced the `IClamp` mismatch to insertion-order-based numbering rather than different amplitudes or targets.
- Updated `test_report.md` with the root-cause evidence and did not modify workflow code.

## 2026-06-11 step 13
- Added `_scripts/normalize_cfg_base_once.py` and ran it once.
- The script backed up `cfg_base.json`, removed active `wmult`, disabled pulses by default, and pre-compensated 163 existing split-pair `wmat` entries.
- Removed the active `cfg.wmult` multiplication from `create_net_params_local.py` while keeping `EEGain` and other gain multipliers active.
- Added `scale_wmat(cfg, factor)` for intentional manual global weight scaling in `cfg.py`.
- Re-ran non-simulation verification against `netParams_example.json`; `popParams`, `connParams`, `synMechParams`, and `subConnParams` now match exactly.
