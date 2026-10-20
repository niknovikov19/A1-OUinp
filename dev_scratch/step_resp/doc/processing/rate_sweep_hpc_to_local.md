# Presynaptic-rate sweep: processing reference

**Description of completed processing, not a simulation/extraction/fitting request.**
The selected L2 inputs and outputs already exist locally.

The historical pipeline was: HPC simulation PKLs → sim_data_analyzer spike
cache → rate NetCDF → one verified local rate/configuration copy → local
curve fits and derivatives. Large PKLs and spike caches remained on HPC.

For the current predictor, the local input is
`data/l2_rate_sweep_j_5seeds/input/rates.nc`, with `input/cfg.json`.
[refit_rate_io.py](../../code/refit_rate_io.py) produced the selected L2 J;
[the short J record](../results/l2_rate_sweep_j.md) identifies its outputs and
the user decision to stop fitting.

The copied extract_rates_batch.py/analyze_rate_io.py files in code/ are
historical snapshots. The extractor still assumes its original analysis/batch/
file depth; these are not a ready-to-run alternative to the current local code.

[Source audit](../reference/rate_sweep_sources.md) and
[historical commands](../archive/rate_sweep_extraction_commands.md) are available
only for source/reproduction questions. The latter contains old launch/fitting
instructions and is not part of the current workload.
