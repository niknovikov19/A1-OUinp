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

The completed two-seed slow pilot came from this HPC result directory:

```text
/ddn/niknovikov19/repo/A1_OUinp/exp_results/
batch_rxbkg_unconn_state1_mech1/net_inpsur_hsweep_newsec_var_seed/
exp_L2_pilot3_nseed_2_t_5.0_35.0_tri_t0_5000_T_15000_amp_0.1_ictrl_wmult_0.25_ee_0.5/
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
The matching local dataset is `data/l2_slow_pilot/`. The earlier one-seed
dataset remains in `data/l2_pilot2/`. The entire `data/` directory is
git-ignored because it contains copied and generated binary artifacts.

## Run

From the repository root, using the existing local NetPyNE environment:

```bash
MPLCONFIGDIR=.mplcache \
  /home/nnovikov/conda_env/netpyne/bin/python \
  dev_scratch/step_resp/code/analyze_h_io.py
```

The default dataset is `dev_scratch/step_resp/data/l2_slow_pilot`. Use
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

## Slow two-seed pilot

The run `hsweep-l2-slow-pilot-001` completed as top-level Slurm job `117990`.
Seed 1000 ran as child `117991`; seed 1001 ran as the next sequential child.
Both children used 30 MPI ranks and 128 GB. Protected finalization verified
all nine declared outputs before the checkout was released.

At a 0.2-s additional smoothing window, the provisional pooled diagonal is:

```text
IT2    20.20 Hz/nA
PV2   193.85 Hz/nA
SOM2  116.92 Hz/nA
VIP2  122.99 Hz/nA
NGF2   63.97 Hz/nA
```

The rising/falling relative differences are about 5.8%, 1.4%, 8.9%, 0.8%, and
179%, respectively. The slower probe therefore largely removes the branch
split for the first four populations. NGF2 remains unsuitable for a pooled
static derivative: its branch estimates are about 172 and 9.67 Hz/nA, and its
pooled `R²` is about 0.62. PV2 also has substantial seed-to-seed baseline
variation and a pooled `R²` of about 0.78.

The pooled estimates are stable across the tested fitting windows:

```text
smooth (s)   IT2     PV2     SOM2    VIP2    NGF2
0.1          20.20   193.83  116.21  123.04  64.59
0.2          20.20   193.85  116.92  122.99  63.97
0.4          20.23   194.01  118.04  122.78  63.00
```

These remain pilot diagnostics rather than a final Q. The period change and
addition of a second seed happened together, so differences from the first
pilot cannot be attributed exclusively to slower probing.

## Next dataset

The next five-seed run probes the asymmetric interval `[-0.05, 0.2] nA` with a
`20 s` period. One cycle is `0 -> 0.2 -> 0 -> -0.05 -> 0`; two cycles plus the
5-s baseline give a `45 s` simulation. Its planned local dataset name is
`data/l2_asym_pilot/`. Fit figures no longer draw axes grids.
