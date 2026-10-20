# Rate-model prototype: background for static J–Q prediction

REFERENCE — background/source audit; experiment selection is in data/registry.md.

Paths written as data/ or code/ are relative to dev_scratch/step_resp/, not this document.

## Project idea

Treat the recurrent simulation as a black-box steady-state map. Around an
operating point `(r0, h0)`, write:

```text
r = F(r, h)
```

and linearize it:

```text
delta_r = J delta_r + Q delta_h
delta_r_hat = (I - J)^-1 Q delta_h
```

`J[post, pre]` is the open-loop effect of changing presynaptic population
rate `pre` on the output rate of population `post`. `Q delta_h` is the direct
response to the external perturbation before recurrent feedback. More
generally, this direct forcing can be called `b`, giving
`delta_r_hat = (I - J)^-1 b`.

The project is to estimate these quantities with the real spiking simulation,
close the loop mathematically, and compare the predicted steady-state rate
change with a fully recurrent simulation under the same perturbation.

## Connection to the triangular-wave experiment

The existing experiment freezes recurrent connections, varies one surrogate
presynaptic rate with a slow triangle, and measures all postsynaptic rates.
Its fitted matrix is stored as:

```text
W[pre, post] = d r_post / d r_pre
```

It therefore provides the required Jacobian after an orientation change:

```text
J[post, pre] = W[pre, post]
```

No separate dynamic step-response identification is needed to estimate J.
The spiking-model J/Q sweeps and connected rectangular-step validation have
since been implemented. Use the [registry](../../data/registry.md) for their
current status; the toy implementation below is background, not a pending plan.

## Relevant reference implementation

The useful files in the read-only `external/resp_predictor` repository are:

- [`description.ipynb`](../../../../external/resp_predictor/description.ipynb):
  clearest derivation and toy numerical demonstration of the first-order
  prediction.
- [`description.md`](../../../../external/resp_predictor/description.md): an earlier
  written derivation; it stops at the empty `Idea` section and is less complete
  than the notebook.
- [`resp_predictor.py`](../../../../external/resp_predictor/resp_predictor.py): main
  first-order prototype. It estimates `J` and `Q` from open-loop
  one-population probes, forms `(I - J)^-1`, and predicts responses to
  simultaneous perturbations. It also experiments with fitting at several
  perturbation magnitudes and interpolating between them.
- [`resp_pred.py`](../../../../external/resp_predictor/resp_pred.py): older
  procedural version of the same first-order idea.
- [`rate_model/`](../../../../external/resp_predictor/rate_model): a lightweight
  simulation substitute exposing full recurrent `run()` and
  one-population/open-loop `run_1pop()` operations. Its scientific details are
  not part of the planned spiking-simulation implementation.

Snapshots of the two descriptions are kept in
[`resp_predictor_reference/`](resp_predictor).

## Simulation-level calculation underlying the implemented workflow

1. Determine a common operating-point rate vector `r0`.
2. Fit the triangular-sweep curves locally and evaluate their derivatives at
   `r0` to construct `J` with dimensions `pop_post x pop_pre`.
3. Specify an external perturbation and obtain its direct open-loop response
   `b`. If the perturbation is parameterized as `delta_h`, this is
   `b = Q delta_h`.
4. Predict the recurrent response with
   `delta_r_hat = solve(I - J, b)`.
5. Run the corresponding fully recurrent simulation and compare its
   steady-state `delta_r` with the prediction.
6. Repeat over perturbation magnitudes and multi-population directions to map
   the useful linear range.

The existing triangular sweep supplies step 2. It does not, by itself,
identify `Q` for an arbitrary external-input mechanism.

## Checks that matter

- Matrix orientation and identical population ordering across `r0`, `J`, and
  the perturbation vector.
- Failed curve fits and `NaN` entries before matrix inversion.
- Conditioning of `I - J`; near-singularity predicts large amplification and
  makes errors in `J` consequential.
- Consistency between the open-loop and recurrent operating points.
- Prediction error as a function of perturbation size, direction, population,
  and seed.

## Out-of-scope or secondary branches

- `resp_predictor_2.py`, `resp_pred_test_1.ipynb`, and `rank1_hess.py` explore
  second-order derivatives and Hessian corrections. They are experimental and
  not needed for the first simulation implementation.
- `wc.py` is an early standalone Wilson-Cowan demonstration superseded by the
  `rate_model/` package.
- Controller files and controller notebooks are unrelated to the current
  goal.
- Oscillatory, spectral, eigenmode, and transfer-function work is excluded.
- Dynamic step-response kernels are not planned at this stage.
