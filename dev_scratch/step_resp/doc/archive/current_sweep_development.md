# Static current-rate processing

HISTORICAL — retained evidence/proposals, not a current contract or pending run.

Paths written as data/ or code/ are relative to dev_scratch/step_resp/, not this document.

The h-r fitter is
[`code/analyze_h_io.py`](../../code/analyze_h_io.py). It is semantically parallel
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
The matching local dataset is `data/_old/l2_current_sweep_2seeds_pm100pa_t15s/`. The earlier one-seed
dataset remains in `data/_old/l2_current_sweep_1seed_pm100pa_t7p5s/`. The entire `data/` directory is
git-ignored because it contains copied and generated binary artifacts.

## Run

From the repository root, using the existing local NetPyNE environment:

```bash
MPLCONFIGDIR=.mplcache \
  /home/nnovikov/conda_env/netpyne/bin/python \
  dev_scratch/step_resp/code/analyze_h_io.py
```

The default dataset is `dev_scratch/step_resp/data/l2_current_sweep_5seeds_pm100pa_t40s`. Use
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

## Asymmetric five-seed pilot

The run `hsweep-l2-asym-pilot-001` completed as top-level Slurm job `117997`.
All five seeds ran concurrently with 30 cores and 128 GB per child. Protected
finalization verified the 21 declared outputs before the run was released.

The simulation output is under:

```text
/ddn/niknovikov19/repo/A1_OUinp/exp_results/
batch_rxbkg_unconn_state1_mech1/net_inpsur_hsweep_newsec_var_seed/
exp_L2_pilot4_nseed_5_t_5.0_45.0_tri_t0_5000_T_20000_h_-0.05_0.2_ictrl_wmult_0.25_ee_0.5/
```

Only its five `rvec_xr` and five `hvec_xr` files were copied to the ignored
local dataset `data/_old/l2_current_sweep_5seeds_m50_p200pa_t20s/`; every copy was checked byte-for-byte. The
probe covers `[-0.05, 0.2] nA` at a constant absolute slew rate. One cycle is
`0 -> 0.2 -> 0 -> -0.05 -> 0`; two cycles plus the 5-s baseline give a 45-s
simulation.

All populations fit successfully. The provisional pooled diagonal is stable
across the tested smoothing windows:

```text
smooth (s)   IT2     PV2     SOM2    VIP2    NGF2
0.1          17.11   179.60  115.39  135.42  43.68
0.2          17.14   179.47  115.30  135.50  43.59
0.4          17.20   178.96  114.87  135.71  43.32
```

At 0.2-s smoothing, the fit diagnostics are:

```text
pop    R²      rising Q   falling Q   branch relative difference
IT2    0.928      16.66       16.72       0.4%
PV2    0.892     168.67      189.03      11.4%
SOM2   0.934     106.78      125.55      16.2%
VIP2   0.962     126.94      145.55      13.7%
NGF2   0.725      79.77       16.40     131.8%
```

The added seeds and wider positive range give stable pooled estimates for the
first four populations, although PV2, SOM2, and VIP2 retain moderate branch
separation. NGF2 still has strong hysteresis and should not be represented by
its pooled static derivative without further treatment. The generated fit
figures have no axes grid.

## Symmetric slow five-seed retry

The run `hsweep-l2-sym-slow-pilot-001` completed as top-level Slurm job
`118003`. All five seeds ran concurrently with 30 cores and 128 GB per child.
Protected finalization verified the 21 declared outputs before the run was
released.

The simulation output is under:

```text
/ddn/niknovikov19/repo/A1_OUinp/exp_results/
batch_rxbkg_unconn_state1_mech1/net_inpsur_hsweep_newsec_var_seed/
exp_L2_pilot5_nseed_5_t_5.0_85.0_tri_t0_5000_T_40000_h_-0.1_0.1_ictrl_wmult_0.25_ee_0.5/
```

Only its five `rvec_xr` and five `hvec_xr` files were copied to the ignored
local dataset `data/l2_current_sweep_5seeds_pm100pa_t40s/`; every copy was checked byte-for-byte.
The probe covers `[-0.1, 0.1] nA` with a 40-s period: two symmetric cycles
after the 5-s baseline give an 85-s simulation. Each leg has a 10-s duration,
so the sweep speed is `0.01 nA/s`.

The provisional pooled diagonal is stable across the tested smoothing windows:

```text
smooth (s)   IT2     PV2     SOM2    VIP2    NGF2
0.1          20.76   187.92  122.83  151.80  54.70
0.2          20.77   188.13  122.93  151.78  54.77
0.4          20.79   188.48  123.37  151.76  54.88
```

At 0.4-s smoothing, NGF2 has pooled `R² = 0.865`; its rising and falling
branch fits have `R² = 0.951` and `0.931`, respectively. The negative-current
range constrains the rising curve's zero-rate left flank, resolving the prior
poorly constrained fit. Hysteresis remains substantial: the branch gains at
zero current are 83.82 and 31.46 Hz/nA, whereas the pooled derivative is 54.88
Hz/nA. Figures have no axes grid.
