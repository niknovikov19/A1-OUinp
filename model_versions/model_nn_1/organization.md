# model_nn_1 organization

## Purpose

`model_versions/model_nn_1` is an attempt to isolate a retained `net_newsec`-like workflow into an old-style NetPyNE layout. It is organized around the classic trio:

- `cfg.py`
- `netParams.py`
- `init.py`

The main goal is to keep the experiment understandable to users who are used to the older `cfg.py` / `netParams.py` / `init.py` pattern, while still preserving important experiment-specific behavior that previously lived in `exp_cfg.py`.

Important limitation:

- this folder is still not a validated faithful standalone reproduction
- but the active subnet path is no longer the local `subnet_builder.py` stand-in
- the active workflow now uses `subnet_tuner` from the NetPyNE conda environment

This folder is intentionally narrower in scope than the original repository workflow. It keeps:

- JSON-driven config loading
- user-editable post-load overrides
- base network construction
- post-build netParams modification
- subnet conversion
- recurrent/frozen split handling for the fader
- runtime fader hookup
- normal old-style NetPyNE run flow

This folder intentionally does not carry:

- OU-based inputs
- rate controller logic
- controller result gathering
- controller plotting
- cochlear / IC special branches
- repo-root path assumptions


## Top-level hierarchy

The practical hierarchy is:

1. `cfg_base.json`
2. `cfg.py`
3. `create_net_params_local.py`
4. `netParams.py`
5. `init.py`

The helper modules below support this main chain:

- `syn_mech_relabel.py`
- `conn_fader.py`

External active dependency:

- `subnet_tuner` from the NetPyNE conda environment

Local provisional file kept for reference/debugging:

- `subnet_builder.py`

The bundled assets below are data inputs to the chain:

- `cells/`
- `conn/`
- `target_sec_1.json`
- `target_state_1.csv`


## Main entrypoints

### `cfg.py`

Responsibility:

- Load the experiment definition from `cfg_base.json`
- Expose a single `cfg` object
- Provide a small override zone for interactive edits
- Provide small helpers for common edits after JSON load

Main objects and functions:

- `cfg = _load_cfg()`
- `_load_cfg()`
- `set_main_seed(cfg, seed_main)`
- `set_duration_bundle(cfg, duration, t0_calc=None, update_iclamp=True)`

Important idea:

`cfg_base.json` is the source of truth, while `cfg.py` is the thin shim that loads it and gives users a familiar place to make quick manual edits.


### `create_net_params_local.py`

Responsibility:

- Build the base full-network `NetParams`
- Use only bundled local assets inside `model_nn_1`
- Provide the old shared model definition without depending on repo-root files

Main entrypoint:

- `create_net_params(cfg)`

Important internal roles:

- `_asset_path(...)`
  Resolves bundled assets such as `cells/*.json`, `cells/cellDensity.pkl`, and `conn/conn.pkl`
- `_cfg_path(...)`
  Resolves an optional externally specified JSON file when `cfg.netpar_force_load` is used

Important behavior:

- Creates the baseline populations, cell rules, synaptic mechanisms, connectivity rules, background spike inputs, `IClamp`, and pulse sequence input
- Keeps the legacy model-building logic, but localizes the asset access
- Raises `NotImplementedError` when unsupported standalone branches are enabled

Unsupported branches rejected here:

- `addBkgConn`
- `cochlearThalInput`
- `ICThalInput`
- `add_ou_current`
- `add_ou_conductance`
- `replace_bkg_spikes_by_ou`


### `netParams.py`

Responsibility:

- Import local `cfg`
- Build the base network by calling `create_net_params(cfg)`
- Apply experiment-specific modifications that used to be layered from `exp_cfg.py`
- Export the final `netParams`

Current caution:

- this file currently depends on an external env-level `subnet_tuner` installation rather than a bundled local module
- the workflow now builds through the subnet stage and matches `netParams_example.json` for `popParams`, `connParams`, `synMechParams`, and `subConnParams`
- raw `IClamp` labels/order can still differ even though normalized source/target content matches

Main execution sequence:

1. Build base `netParams`
2. Apply mechanism changes
3. Retarget connection sections
4. Convert to subnet if enabled
5. Relabel split recurrent/frozen synaptic mechanisms for the fader

Main functions:

- `_apply_mech_changes(cfg, netParams)`
- `_apply_target_sections(netParams)`
- `_resolve_cfg_path(path_like)`
- `_build_subnet(cfg, netParams)`
- `_parse_split_pairs(cfg)`
- `_apply_split_synmech_labels(cfg, netParams)`

Important exported object:

- `netParams`


### `init.py`

Responsibility:

- Act as the old-style runtime entrypoint
- Import `cfg` and `netParams`
- Save the loaded config and transformed netParams
- Run the standard NetPyNE build sequence
- Attach the fader after instantiation
- Run / gather / save / plot in the classic order

Main runtime sequence:

1. `comm.initialize()`
2. Create `saveFolder`
3. Save `cfg` and stripped `netParams`
4. `sim.initialize(simConfig=cfg, netParams=netParams)`
5. `sim.net.createPops()`
6. `sim.net.createCells()`
7. cache `allCells` and `allPops`
8. `setdminID(...)`
9. `sim.net.connectCells()`
10. `sim.net.addStims()`
11. `sim.setupRecording()`
12. `_setup_fader(sim)`
13. `sim.runSim()`
14. `sim.gatherData()`
15. `sim.saveData()`
16. `sim.analysis.plotData()`

Main functions:

- `setdminID(sim, lpop)`
- `setCochCellLocationsX(cfg, netParams, pop, scale)`
- `_save_netparams_stripped(netParams, fpath)`
- `_get_cond_pops(conds)`
- `_get_2pop_conns(pops_pre, pops_post)`
- `_parse_split_pairs(cfg)`
- `_setup_fader(sim)`

Important note:

`setCochCellLocationsX(...)` is still present as leftover compatibility code, but the standalone workflow is not intended to carry cochlear branches.


## Helper modules

### `subnet_builder.py`

Responsibility:

- Historical/provisional local stand-in for a missing subnet module during earlier isolation work
- Not part of the active tested workflow path anymore

Main public classes:

- `SubnetDesc`
- `SubnetParamBuilder2`

`SubnetDesc` is a container for:

- `pops_active`
- `conns_frozen`
- `conns_split`
- `inp_surrogates`

`SubnetParamBuilder2.build(params_in, desc)` does the actual transformation.

Its main jobs are:

- keep only active real populations
- keep auxiliary stimulus populations such as `VecStim` / `NetStim` inputs
- duplicate selected connection rules into frozen `frz_...` copies
- create `popfrz` surrogate populations
- preserve targeted `stimTargetParams`
- preserve compatible `subConnParams`

Important warning:

- this file is kept only as a local artifact from the earlier isolation attempt
- the active workflow now imports `SubnetDesc` and `SubnetParamBuilder2` from `subnet_tuner`, not from this file


### `syn_mech_relabel.py`

Responsibility:

- Distinguish recurrent and frozen copies of the same logical connection rule by synaptic mechanism label

Main functions:

- `_dup_synmech_label(params, old_label, suffix)`
- `_relabel_conn_synmech(params, conn, suffix)`
- `_rule_kind_and_base_pops(conn, verbose=False)`

Main idea:

If a rule is split into recurrent and frozen forms, the fader needs them to be independently modulatable. This helper duplicates synaptic mechanism definitions so one rule can use labels like:

- `AMPA_rec`
- `NMDA_rec`
- `AMPA_frz`
- `NMDA_frz`


### `conn_fader.py`

Responsibility:

- Build and attach runtime modulators that cross-fade recurrent and frozen connection groups

Main class:

- `ConnFader`

Main methods:

- `add_conn_group(group_name, conns_pos, conns_neg, pts)`
- `create_modulators()`
- `connect_modulators()`
- `setup_recording(rec_dt=None)`
- `gather_recs()`
- `plot_recs(gathered=None)`

Main idea:

The fader is a runtime object, not a pure `netParams` object. It must be created after cells and connections exist, because it wires NEURON shared variables into instantiated synapses.


## Bundled assets and what they mean

### `cfg_base.json`

Primary experiment definition.

Contains:

- baseline NetPyNE config
- retained experiment parameters
- globally scaled `wmat` values used directly by the local builder
- split-pair `wmat` values pre-compensated for `subnet_tuner` static halving
- subnet settings
- bkg spike input settings
- `IClamp` settings
- inactive pulse settings
- fader settings
- recording / plotting settings

Important notes:

- `wmult` is intentionally not active in this standalone workflow because the global scale is baked into `wmat`
- `EEGain` and other class/pop/layer gain multipliers remain active during netParams construction
- `_scripts/normalize_cfg_base_once.py` records the one-time normalization metadata and refuses to run twice


### `cells/`

Bundled cell-rule JSON files and density data used by `create_net_params_local.py`.

Purpose:

- make the base network builder local and movable


### `conn/conn.pkl`

Bundled connectivity matrices used by `create_net_params_local.py`.

Purpose:

- provide local connectivity probabilities, distances, and weights


### `target_sec_1.json`

Used by `netParams.py`.

Purpose:

- override the default postsynaptic target section for connection rules


### `target_state_1.csv`

Used by `netParams.py` during subnet construction.

Purpose:

- define target firing rates and optional CV values for surrogate frozen populations


## Dependency graph

The direct dependency graph is:

- `cfg.py` depends on `cfg_base.json`
- `create_net_params_local.py` depends on `cells/` and `conn/`
- `netParams.py` depends on:
  - `cfg.py`
  - `create_net_params_local.py`
  - external `subnet_tuner`
  - `syn_mech_relabel.py`
  - `target_sec_1.json`
  - `target_state_1.csv`
- `init.py` depends on:
  - `cfg.py`
  - `netParams.py`
  - `conn_fader.py`

In runtime order:

- `cfg.py` must be loadable first
- `netParams.py` can then construct the final model specification
- `init.py` can then instantiate and run that specification

Current caveat:

- the dependency graph is structurally correct for the active path
- but one key dependency currently lives outside the folder, in the NetPyNE conda environment


## Functional layering

This setup is intentionally layered in three levels.

### Level 1: config layer

Files:

- `cfg_base.json`
- `cfg.py`

Role:

- define what experiment should be built


### Level 2: specification layer

Files:

- `create_net_params_local.py`
- `netParams.py`
- `subnet_builder.py`
- `syn_mech_relabel.py`

Role:

- define what network should exist before NEURON objects are instantiated


### Level 3: runtime layer

Files:

- `init.py`
- `conn_fader.py`

Role:

- instantiate the network
- attach runtime-only modulation objects
- run, record, gather, and save


## Most important call relations

The most important call relations are:

- `cfg.py`:
  - `_load_cfg()` -> `cfg`

- `netParams.py`:
  - `create_net_params(cfg)` -> base `netParams`
  - `_apply_mech_changes(...)`
  - `_apply_target_sections(...)`
  - `_build_subnet(...)`
    - build `SubnetDesc`
    - read `target_state_1.csv`
    - `SubnetParamBuilder2.build(...)`
  - `_apply_split_synmech_labels(...)`
    - `_rule_kind_and_base_pops(...)`
    - `_relabel_conn_synmech(...)`

- `init.py`:
  - `_save_netparams_stripped(...)`
  - `sim.initialize(...)`
  - `sim.net.createPops()`
  - `sim.net.createCells()`
  - `sim.net.connectCells()`
  - `sim.net.addStims()`
  - `_setup_fader(sim)`
    - `_parse_split_pairs(...)`
    - `_get_2pop_conns(...)`
    - `ConnFader.add_conn_group(...)`
    - `ConnFader.create_modulators()`
    - `ConnFader.connect_modulators()`
    - `ConnFader.setup_recording(...)`


## How the subnet and fader pieces fit together

This is the most experiment-specific part of the organization. It now runs through the external `subnet_tuner` dependency, but the overall result still has verified mismatches against the reference netParams.

Step 1:

- `create_net_params_local.py` builds the full recurrent network spec

Step 2:

- `netParams.py` reads `cfg.subnet_params`
- `_build_subnet(...)` converts selected presynaptic populations into frozen surrogate populations like `IT2frz`
- the local builder duplicates selected rules into `frz_...` connection rules

Step 3:

- `_apply_split_synmech_labels(...)` relabels synaptic mechanisms so recurrent and frozen copies are distinguishable

Step 4:

- `init.py` instantiates the network
- `_setup_fader(sim)` locates:
  - recurrent rules from `pop_pre -> pop_post`
  - frozen rules from `pop_prefrz -> pop_post`

Step 5:

- `ConnFader` attaches runtime modulators that fade one group in while fading the other out

This division is intentional in structure:

- subnet conversion is a specification-time transformation
- fader wiring is a runtime transformation

The subnet side is no longer using the local provisional stand-in. The generated connection rules now match the provided reference exactly after the one-time `cfg_base.json` normalization.


## What is saved before and after a run

Before simulation:

- `cfg.save(...)` writes the loaded config
- `_save_netparams_stripped(...)` writes the transformed network specification without large `VecStim` spike-time arrays

After simulation:

- standard NetPyNE outputs are saved through `sim.saveData()`
- a small result JSON is written with population average rates


## Design rules for future edits

If you extend this setup, the intended rules are:

- put persistent experiment values into `cfg_base.json`
- keep `cfg.py` thin and user-editable
- keep base model construction in `create_net_params_local.py`
- keep experiment-specific netParams transforms in `netParams.py`
- keep subnet logic in `subnet_builder.py`
- keep recurrent/frozen synMech label logic in `syn_mech_relabel.py`
- keep instantiated-network modulation logic in `conn_fader.py`
- keep runtime orchestration in `init.py`

Good signs:

- a new feature belongs clearly to config, netParams transform, or runtime transform

Bad signs:

- `cfg.py` starts rebuilding experiment logic that already exists in JSON
- `init.py` starts modifying static network specification details that should have been handled in `netParams.py`
- helper modules begin depending on repo-root paths or external repo utilities again


## Current limits

The current standalone setup is designed for the retained `net_newsec` / `net_newsec_var_seed` experiment shape.

Known limits:

- no OU or rate-control branches
- no full support for repo-level special inputs
- no attempt to preserve batch/reporting extras
- active subnet dependency is external to this folder
- raw `IClamp` names/order can differ from the reference even though normalized source/target content matches


## Minimal mental model

If someone wants the shortest useful mental model, it is:

- `cfg_base.json` says what experiment to build
- `cfg.py` loads that config and lets the user tweak it
- `create_net_params_local.py` builds the generic full network
- `netParams.py` converts that generic network into the exact experiment network
- `init.py` instantiates the network and attaches runtime fader modulation

That is the current organization of this setup; the non-simulation netParams comparison now verifies core structural parity with the provided reference.
