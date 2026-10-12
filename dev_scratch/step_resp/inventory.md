# Existing rate-sweep inventory

## Scope

This inventory covers the existing open-loop rate-sweep experiment and its
post-processing, with emphasis on `results/` and `combined/`.

The experiment configuration is documented in
[`net_inpsur_rsweep_newsec_var_seed_pre`](../../exp_configs/batch_rxbkg_unconn_state1_mech1/net_inpsur_rsweep_newsec_var_seed_pre/README.md).

The original read-only HPC result root is:

```text
/ddn/niknovikov19/repo/A1_OUinp/exp_results/
└── batch_rxbkg_unconn_state1_mech1/
    └── net_inpsur_rsweep_newsec_var_seed_pre/
```

The corresponding selected local artifacts are under:

```text
exp_results/batch_rxbkg_unconn_state1_mech1/
└── net_inpsur_rsweep_newsec_var_seed_pre/
```

## What the experiment measures

The current full experiment uses five seeds and varies each of 36 cortical
presynaptic populations. All connections are frozen, so active recurrent
feedback is absent. One selected `pop_prefrz` population is driven with
independent inhomogeneous-Poisson spike trains whose rate follows a slow
triangle after a five-second baseline.

The historical analysis fits each static input-output relation and stores:

```text
W[pre, post] = d r_post / d r_pre at r_pre = target_rate[pre]
```

`W` is a local rate gain in Hz/Hz, not an anatomical weight. It combines the
realized surrogate input, projection convergence and synaptic properties,
postsynaptic response, and operating state.

## Dataset inventory

| HPC experiment directory | Per-job results | Important `combined/` artifacts | Assessment |
| --- | ---: | --- | --- |
| `exp_pre_it24_post_L2_nseed_1_npre_2_t_3.0_5.0_ictrl_wmult_0.25_ee_0.5` | 2 | None | Early IT2/ITP4 probe |
| `exp_pre_it24_post_L2_nseed_1_npre_2_t_5.0_20.0_ictrl_wmult_0.25_ee_0.5` | 2 | None | Longer one-seed probe |
| `exp_pre_it24_post_L2_nseed_5_npre_2_t_5.0_20.0_ictrl_wmult_0.25_ee_0.5` | 10 | 10 spike caches and one rate NetCDF | Preprocessed, no fitted matrix |
| `exp_pre_L2_post_L2_nseed_5_npre_5_t_5.0_20.0_ictrl_wmult_0.25_ee_0.5` | 42 files for 25 job IDs | None | Legacy folder with duplicate artifacts for 17 job IDs; not canonical |
| `exp_pre_L2_post_L2_nseed_5_npre_5_t_5.0_20.0_tri_t0_5000_T_7500_rmax_10xbkg_500_ictrl_wmult_0.25_ee_0.5` | 25 | 25 spike caches, one rate NetCDF, coefficients, and a 5×5 matrix at 0.4-second smoothing | Clean L2 sweep; 24 fits and two `NaN` matrix entries |
| `exp_pre_L4_post_L4_nseed_5_npre_6_t_5.0_20.0_tri_t0_5000_T_7500_rmax_10xbkg_500_ictrl_wmult_0.25_ee_0.5` | 30 | Two rate NetCDF variants; spike caches for 30 jobs over 1-20 seconds and 25 jobs over 2-20 seconds | Preprocessed, no fitted matrix |
| `exp_pre_ctx_post_ctx_nseed_5_npre_36_t_5.0_20.0_tri_t0_5000_T_7500_rmax_10xbkg_500_ictrl_wmult_0.25_ee_0.5` | 180 | 180 spike caches, one rate NetCDF, coefficients, and a 36×36 matrix at 0.2-second smoothing | Canonical full-cortex sweep; matrix has 107 `NaN` entries |

For every clean run, `cfg/`, `pkl/`, and `results/` counts match the batch
size. The legacy L2 folder without a stimulus tag contains multiple files for
some job IDs and should not be used without de-duplication.

## Processing

See [`processing.md`](processing.md) for the short, reusable HPC-to-local
workflow. It describes the required scripts and outputs without relying on
the history of the individual experiment folders above.

## Canonical combined layout

The full cortical HPC run has:

```text
combined/
├── data_proc/
│   ├── rates_dt_0.002_tau_0.01_t_1_20.0.nc
│   └── spikes_1_20.0/
│       └── spikes_00000.npz ... spikes_00179.npz
└── results/
    ├── richards_coeffs_tau_0.2.json
    ├── wmat_tau_0.2.json
    ├── wmat_tau_0.2.nc
    └── fit_pngs_tau_0.2/          # Empty on HPC
```

## Code snapshot and provenance

Relevant historical files were copied unchanged into [`code/`](code):

| Copy | Original | Historical role |
| --- | --- | --- |
| [`code/extract_rates_batch.py`](code/extract_rates_batch.py) | [`analysis/batch/extract_rates_batch.py`](../../analysis/batch/extract_rates_batch.py) | Pickle-to-spike extraction and spike-to-rate NetCDF construction |
| [`code/analyze_rate_io.py`](code/analyze_rate_io.py) | [`analysis/batch/analyze_rate_io.py`](../../analysis/batch/analyze_rate_io.py) | Richards fitting and static gain matrix generation |
| [`code/tau_calculation.py`](code/tau_calculation.py) | [`analysis/batch/tau_calculation.py`](../../analysis/batch/tau_calculation.py) | Experimental L2 synaptic-time-constant matrix; not used in the historical rate-sweep pipeline |

The copied files have the same SHA-256 hashes as their originals. They retain
hard-coded experiment paths and execution assumptions. In particular, the
copied `extract_rates_batch.py` resolves the repository from its original
file depth and must be refactored before execution from `code/`.

## Provenance confidence

Confirmed directly:

- File counts, names, timestamps, JSON structure, matrix shape, missing-value
  counts, and HPC/local content hashes.
- The transformations implemented by the current scripts.
- The experiment configuration and `post_run()` output contract.

Inferred from matching artifact schemas and timestamps:

- Which exact script or notebook invocation produced each historical
  `combined/` artifact.
- That the September HPC coefficient file is the result of an interrupted
  rerun.
- The tool used to copy selected HPC artifacts locally.

Future processing should write a manifest containing script hash, parameters,
input hashes, output paths, completion status, and execution location.
