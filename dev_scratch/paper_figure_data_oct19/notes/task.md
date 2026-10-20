# Task: trace Results figure data

Identify and document the simulation data underlying the figures in the Cortex, Thalamus, and Thalamocortical circuit subsections of `doc/paper/Bkg_paper_Oct19_v2.pdf`.

Primary candidate result folders:

- `exp_results/batch_rxbkg_state1_mech1/net_newsec_ee_fade_var_seed`
- `exp_results/batch_rxbkg_state1_mech1/net_newsec_var_seed`

Start from `exp_configs/batch_rxbkg_state1_mech1/net_newsec_ee_fade_var_seed/compare_rates.ipynb`, and inspect other relevant source/configuration files as needed.

Produce an organized mapping from paper figures/panels to analysis code, configuration parameters, source folders/files, and selection/aggregation rules. Distinguish verified links from hypotheses and record missing data or ambiguous provenance.

## Constraints

- Minimize load on the mounted HPC filesystem: use local paper/code first; list only relevant directories; prefer small metadata and cached summaries; avoid recursive scans and bulk loading/copying simulation data.
- Use `sim_data_analyzer` where useful for simulation analysis.
- Keep intermediate artifacts in this directory.
- Record important findings incrementally in `findings_log.md` so work survives an interrupted session.

## Intended artifacts

- `findings_log.md`: chronological evidence and decisions.
- Extracted paper text and a compact notebook/code inventory.
- Figure/panel inventory and source-data mapping, including confidence and outstanding gaps.
