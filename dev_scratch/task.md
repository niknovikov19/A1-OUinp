
## Task 1 - new experiment with batch-selection of frozen connections

Create a new experiment `exp_configs/batch_rxbkg_state1_mech1/net_newsec_var_seed_frzconns`, based on `exp_configs/batch_rxbkg_state1_mech1/net_newsec_ee_fade_var_seed`.

In addition to `seed_main`, add a second batch parameter: `frz_conn_group`, which give the name of a group of connections that should be frozen in this trial.

Define connection groups as `{name: [(pop_pre, pop_post)]}`, e.g.:

```
FRZ_CONN_GROUPS = [
    {'irem_ire': [(p1, p2) for p1 in ['IREM'] for p2 in ['IRE']]},
    {'matx_ti': [(p1, p2) for p1 in MATX_POPS for p2 in ['TI']]}
```

There are many examples of pops, conns, and conn groups in the beginning of `exp_configs/batch_rxbkg_state1_mech1/net_newsec_ee_fade_var_seed/exp_cfg.py` (mostly commented). Move them to the new  `batch_params.py`, with some cleanup.

Active populations and fader settings remain in `exp_cfg.py`.

Check what happens in `apply_exp_cfg()`, and if needed - add the required code to `post_update()`.

Make sure that the new `exp_cfg.py` accounts for the new batch param everywhere it's needed (paths, etc..) E.g. check `exp_configs/batch_rxbkg_state1_mech1/net_2pulses_var_seed_f_amps_dt0/exp_cfg.py` to see how it deals with several batch params (but don't drag unnecessary stuff from there).

You cannot run simulations in this environment, so limit your testing with smoke-runs. Use `netpyne` conda env.


## Task 2 - Multi-experiment batch cell rates collection

Create a wrapper around `utils/batch/collect_cell_rates_from_pkl.py` that runs it for several experiments.
New script: `utils/batch/collect_cell_rates_from_pkl_multiexp.py`.

It should read a list of experiments from a json file, and feed them to `collect_cell_rates_from_pkl.py` as if they were given by `DIRPATH_EXP`.
The json file should contain a path to the common root folder, and a list of subfolder names corresponding to the experiments.

Other `collect_cell_rates_from_pkl.py` params remain the same, you can duplicate them in the new script and feed dows as they are.

If `DIRPATH_OUT` is None, then `collect_cell_rates_from_pkl.py` keeps the old behavior (writes into the experiment folders). 
If `DIRPATH_OUT` is not None, create a separate subfodler for each experiment (same names as given in json file) and write there.

Keep in mind that `sim_results/` is read-only in your env. Don't try to write there and minimize reading of large files. 