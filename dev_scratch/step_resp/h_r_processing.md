# Static current-rate processing

The h-r fitter is
[`code/analyze_h_io.py`](code/analyze_h_io.py). It is semantically parallel
to the r-r fitter:

```text
r-r: frozen presynaptic rate -> postsynaptic rate -> derivative at r_pre = r0
h-r: added population current -> same-population rate -> derivative at h = 0
```

Both pool time samples and seeds, fit a Richards curve, evaluate its local
derivative, and save a labelled input-population by output-population matrix.
The h-r matrix has structural-zero off-diagonal entries because all active
recurrent connections are frozen in this experiment.

## HPC source and local workspace

The current pilot came from this HPC result directory:

```text
/ddn/niknovikov19/repo/A1_OUinp/exp_results/
batch_rxbkg_unconn_state1_mech1/net_inpsur_hsweep_newsec_var_seed/
exp_L2_pilot2_nseed_1_t_5.0_20.0_tri_t0_5000_T_7500_amp_0.1_ictrl_wmult_0.25_ee_0.5/
```

Keep the simulation output on HPC. For fitting, copy each compact `rvec` and
`hvec` pair once into a short, ignored local dataset directory:

```text
dev_scratch/step_resp/data/<dataset>/
├── input/
│   ├── rvec_xr/rvec_<job>_seed_<seed>.nc
│   └── hvec_xr/hvec_<job>_seed_<seed>.nc
└── processed/
```

The fitter discovers all pairs and derives the actual current independently
for each seed and population from `hvec`; it does not assume equal IClamp
amplitudes. It requires one job per seed because seed is the only batch
coordinate. Raw PKLs, configurations, and network parameters are not needed.
The current local dataset is `data/l2_pilot2/`. The entire `data/` directory
is git-ignored because it contains copied and generated binary artifacts.

## Run

From the repository root, using the existing local NetPyNE environment:

```bash
MPLCONFIGDIR=.mplcache \
  /home/nnovikov/conda_env/netpyne/bin/python \
  dev_scratch/step_resp/code/analyze_h_io.py
```

The default dataset is `dev_scratch/step_resp/data/l2_pilot2`. Use
`--data-dir dev_scratch/step_resp/data/<dataset>` for another run.
`--smooth-win`, `--fit-start`, `--fit-stop`, and `--turn-margin` control the
fit. `--no-plot` disables figures. Do not install another scientific Python
stack; use the existing NetPyNE environment shown above.

The fitter:

1. validates every h/r pair and combines it as `seed x pop x time`;
2. adds the configurable rolling average to the saved rate traces;
3. selects the triangular-sweep interval and excludes turning-point margins;
4. pools seeds and fits `r_i(h_i)` for each population;
5. evaluates `dr_i/dh_i` at `h_i = 0`;
6. repeats the fit separately on rising and falling branches;
7. saves the combined data, coefficients, diagonal Q matrix, and one figure
   per population.

Outputs are grouped by fitting configuration rather than mixed in one folder:

```text
data/<dataset>/processed/
├── h_rate.nc
└── tau_<window>/
    ├── richards_coeffs.json
    ├── qmat.json
    ├── qmat.nc
    └── fits/<population>.png
```

The Q files follow the existing r-r orientation: input population is the first
dimension and output population is the second.

## Current pilot

The single-seed, common-amplitude pilot completed five pooled fits at a 0.2-s
additional smoothing window. Its provisional diagonal values are:

```text
IT2    26.42 Hz/nA
PV2   207.50 Hz/nA
SOM2   92.17 Hz/nA
VIP2  149.96 Hz/nA
NGF2   97.60 Hz/nA
```

These are diagnostics, not the final Q. Rising/falling derivatives differ by
about 44%, 39%, 20%, 12%, and 195%, respectively. NGF2 in particular has a
poor pooled fit (`R²` about 0.51) and a branch split of about 132 versus
1.7 Hz/nA. Inspect branch and seed consistency before accepting a population's
pooled derivative; the final estimate requires the planned multi-seed run.
Repeating the fits with 0.1-, 0.2-, and 0.4-s rolling windows leaves the pooled
values broadly similar and does not remove the NGF2 branch split.

## Next waveform

The clean next diagnostic is to keep the common amplitude at `0.1 nA`, double
the triangle period from `7.5` to `15 s`, and run `35 s`: the unchanged `5 s`
baseline plus two complete triangles. This halves the sweep speed and tests
whether the branch split is caused by insufficient settling.

Increasing the amplitude to `0.25 nA` while only doubling the period would not
slow the probe in current space. Triangle speed is `4 A / T`: it would change
from about `0.0533` to `0.0667 nA/s`, 25% faster, and would spend less time
near `h = 0`. At `0.25 nA`, preserving the old speed requires `T = 18.75 s`;
halving it requires `T = 37.5 s` and an `80 s` run for two post-baseline
cycles. The timing-only pilot should come first because the present range
already approaches silence or saturation in several populations.
