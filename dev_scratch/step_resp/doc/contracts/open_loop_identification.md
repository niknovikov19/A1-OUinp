# Open-loop identification contract

CURRENT CONTRACT — definitions and invariants, not a new experiment plan.

For `r = F(r, h)`, linearize as `dr = J dr + Q dh`, giving the static connected
prediction `dr_pred = solve(I - J, Q @ dh)`.

- h_i is extra somatic current in nA on every active cell of population i,
  separate from all calibrated baseline currents.
- J[post, pre] is the output-rate derivative with respect to presynaptic
  population rate, in Hz/Hz, at frozen target rates. It is not anatomical weight.
- Q[post, h_pop] is the derivative with respect to added current, in Hz/nA,
  evaluated at h = 0.
- L2 order: IT2, PV2, SOM2, VIP2, NGF2; targets `[2, 12, 6, 7, 1]` Hz.

Saved arrays are input-first: J_saved[pop_pre, pop_post] and
Q_saved[pop_h, pop_post]. Align labels and transpose before solving.
Keep rx, frozen-surrogate target rates, ibkg/rate-control corrections, membrane
calibration, and baseline assets unchanged. Operating-point differences are
limitations to report, not permission to retune. No oscillatory identification
or transient-response prediction is currently planned.

## Presynaptic-rate sweep for J

Family: `exp_configs/batch_rxbkg_unconn_state1_mech1/net_inpsur_rsweep_newsec_var_seed_pre/`.
Replace active recurrent inputs with frozen surrogates, including within-population
inputs. Sweep one presynaptic surrogate rate with a slow triangle, measure all
postsynaptic rates, fit static curves, and differentiate at the target rate.
Seed and presynaptic population are batch coordinates.

## Added-current sweep for Q

Family: `exp_configs/batch_rxbkg_unconn_state1_mech1/net_inpsur_hsweep_newsec_var_seed/`.
Use the same fully decoupled topology; frozen rates stay fixed. Declare separate
NetPyNE soma(0.5) IClamps, then attach sparse triangular corners to amplitudes
using Vector.play and keep play vectors alive. Drive all active populations
simultaneously; active recurrent connections, including within-population ones,
are frozen, so Q's off-diagonals are structural zeros in this setup.

Seed is the only batch coordinate. Population current ranges may differ; read
actual hvec values rather than assuming equal amplitudes. Fit r_i(h_i) locally,
pool seeds/branches for the declared estimate, differentiate at zero, and retain
rising/falling diagnostics. [The registry](../../data/registry.md) identifies
selected runs; NGF2 branch dependence and J's provisional zeros remain limitations.
