# Population-rate feedback controller

## Conceptual and mathematical description

The controller independently adjusts the tonic input to each neuronal population so
that its mean firing rate approaches a prescribed target. All cells in a population
receive the same control current, whereas different populations have independent
controllers. The population index is omitted below for clarity.

Let $N$ be the population size, $t_{ik}$ the time of spike $k$ from neuron
$i$, and $\Delta$ the spike-delivery delay. The normalized population spike
train is

$$
x(t)=\frac{1}{N}\sum_{i=1}^{N}\sum_k
\delta\!\left(t-t_{ik}-\Delta\right).
$$

The measured population rate $r(t)$ is an exponential estimate of this spike
train,

$$
\tau_r \dot r=-r+c_t x(t),
$$

where $c_t$ converts the simulation time unit to seconds. Equivalently, between
spikes $r$ decays with time constant $\tau_r$, and each delivered spike
increments it by $c_t/(N\tau_r)$. This normalization makes the long-time mean of
$r$ equal to the mean firing rate per neuron, in hertz.

For target rate $r^*$, the controller dynamics during adaptation are

$$
\begin{aligned}
e &= r^*-r, \\
\tau_m \dot m &= e-m, \\
q &= e-m, \\
\tau_u \dot u &= -u+k_u q, \\
\dot s &= k_s\,\phi_\epsilon(m), \\
z &= s+u,
\end{aligned}
$$

with the dead-zone function

$$
\phi_\epsilon(m)=
\begin{cases}
m-\epsilon, & m>\epsilon,\\
0, & |m|\leq\epsilon,\\
m+\epsilon, & m<-\epsilon.
\end{cases}
$$

Here $m$ is a slow estimate of the rate error. The residual $q=e-m$ isolates
faster deviations, and $u$ is a filtered transient correction. The state $s$
integrates persistent error but ignores fluctuations within the dead zone. Thus,
the slow branch learns the tonic correction while the fast branch improves the
transient response.

The complete controller is piecewise in time. Before adaptation starts, only the
rate estimator evolves and the controller output remains at its initial value.
During adaptation, the output is $s+u$. At the locking time, the controller states
are frozen and the fast branch is removed, leaving the learned tonic output:

$$
z(t)=
\begin{cases}
z_0, & t<t_0,\\
s(t)+u(t), & t_0\leq t\leq t_{\mathrm{lock}},\\
s(t_{\mathrm{lock}}), & t>t_{\mathrm{lock}}.
\end{cases}
$$

The initial conditions are $r=m=u=0$ and $s=z_0$. The rate estimator continues
to track spiking after locking, but it no longer changes the control output.

The controller output is converted directly into a somatic tonic current,

$$
I_{\mathrm{inj}}(t)=g_\mu z(t).
$$

With the sign convention used here, positive current is depolarizing.
Consequently, a population firing below target develops a positive correction,
whereas a population firing above target develops a negative correction.

## Conversion to static current corrections

The feedback controller was used as a calibration procedure rather than as a
permanent component of the model. For realization $j$, the final locked output
of population $p$ was converted to current as

$$
I_p^{(j)}=g_\mu z_p^{(j)}(t_{\mathrm{end}}).
$$

The static correction for subsequent simulations was the median across
realizations,

$$
\widetilde I_p=\operatorname{median}_j I_p^{(j)}.
$$

This correction is applied as an additional population-specific somatic current,
on top of the pre-existing constant current used to set the resting membrane
potential. Taking the median makes the calibration less sensitive to individual
network and input realizations.

## Implementation details

The dynamical controller is implemented by `RateController2` in
`mod/RateController2.mod`. For each population, every spike is connected to the
controller with weight $1/N$. In a distributed simulation, an equivalent
controller instance is created on every MPI rank that owns cells from that
population; all instances receive the global population spike stream and
therefore generate the same signal. The output is connected by a NEURON pointer
to a controlled current source at the midpoint of each cell's soma.

`rate_ctrl.py` creates the controllers, assigns population-specific targets, and
records $r$, $e$, $m$, $q$, $u$, $s$, and $z$. When control is enabled, the
experiment setup in
`exp_configs/batch_rxbkg_state1_mech1/net_newsec_ctrl_var_seed/exp_cfg.py` creates
the controlled current sources and loads the targets from `target_state_1.csv`.
The final outputs are processed in `compare_ctrl_res.ipynb`; the resulting
per-realization and median currents are stored in `ibkg_ctrl_1.json`.

The checked-in experiment configuration has since been repurposed: both
`CTRL_ON` and `USE_IBKG_CTRL` are currently disabled. Therefore, running the file
in its present state neither executes the feedback controller nor applies the
saved static corrections. The controller-calibration settings described here are
preserved by the result metadata, analysis notebook, and Git history; the
controller parameters themselves remain in `CTRL_PARAMS`.

## Numerical values

### Controller and calibration protocol

| Quantity | Symbol or setting | Value |
| --- | --- | ---: |
| Controller mechanism | -- | `RateController2` |
| Time-unit conversion | $c_t$ | $10^3\ \mathrm{ms\,s^{-1}}$ |
| Spike-delivery delay | $\Delta$ | $1\ \mathrm{ms}$ |
| Rate-estimator time constant | $\tau_r$ | $100\ \mathrm{ms}$ |
| Slow-error time constant | $\tau_m$ | $2500\ \mathrm{ms}$ |
| Fast-branch time constant | $\tau_u$ | $100\ \mathrm{ms}$ |
| Slow integrator gain | $k_s$ | $10^{-4}\ \mathrm{ms^{-1}}$ |
| Fast-branch gain | $k_u$ | $10^{-3}$ |
| Error dead-zone half-width | $\epsilon$ | $0.1\ \mathrm{Hz}$ |
| Initial output | $z_0$ | $0\ \mathrm{Hz}$ |
| Adaptation start | $t_0$ | $10\ \mathrm{s}$ |
| Locking time | $t_{\mathrm{lock}}$ | $160\ \mathrm{s}$ |
| Current gain | $g_\mu$ | $0.005\ \mathrm{nA\,Hz^{-1}}$ |
| Simulation duration | $t_{\mathrm{end}}$ | $220\ \mathrm{s}$ |
| Final rate-analysis window | -- | $200\text{--}220\ \mathrm{s}$ |
| Independent realizations | -- | $15$ |
| Main realization seeds | -- | $1000\text{--}1014$ |

### Population targets and derived static corrections

Only the thalamic populations below were active in the controller-calibration
run. The target file also contains cortical targets for other experiments.

| Population | Target rate $r_p^*$ (Hz) | Median static correction $\widetilde I_p$ (nA) |
| --- | ---: | ---: |
| TC | 8 | -0.235063 |
| HTC | 8 | -0.157992 |
| TI | 15 | -0.000466 |
| IRE | 15 | -0.019262 |
| TCM | 2 | -0.208839 |
| TIM | 10 | -0.000894 |
| IREM | 10 | -0.030767 |

The listed corrections are medians over the independent realizations and are
rounded to six decimal places; full-precision values and all realization-level
outputs are retained in `ibkg_ctrl_1.json`.
