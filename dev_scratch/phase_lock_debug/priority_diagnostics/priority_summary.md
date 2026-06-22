# Priority Diagnostic Summary

## Setup
- Amp-zero job seed: `1000`
- Synthetic controls: `white`, `constant`, `slow_0p8`
- Method: `fit`, target frequency from batch coord

## Geometry
- Pulse period: `0.2 s`
- Pulse width: `0.05 s`
- Pulse pad: `0.02 s`
- Clean interval: `0.11 s`
- Fit half-width: `0.382 s`
- Median fit valid mass: `0.52`

## Immediate Read
- White noise passed through the same periodic mask produces a clean `5.1 Hz` power peak for every tested trace.
- Actual amp-zero ITCs are often comparable to the white-noise ITCs and to the finite-sample floor.
- The priority diagnostics therefore support the mask/estimator-artifact explanation, not a stimulus-driven effect.
- The current raw power and phase plots should be treated as contaminated until amp-zero or synthetic-mask null correction is added.

## ITC Check
| signal | trace | actual ITC | white ITC | floor | actual peak Hz | white peak Hz |
|---|---:|---:|---:|---:|---:|---:|
| rates | pop=IT2 | 0.0495 | 0.115 | 0.0711 | 5.1 | 5.1 |
| rates | pop=PV2 | 0.0144 | 0.0151 | 0.0711 | 4.9 | 5.1 |
| rates | pop=SOM2 | 0.105 | 0.116 | 0.0711 | 5.1 | 5.1 |
| rates | pop=VIP2 | 0.151 | 0.122 | 0.0711 | 4.9 | 5.1 |
| rates | pop=NGF2 | 0.0526 | 0.0601 | 0.0711 | 5.1 | 5.1 |
| lfp | y=100 | 0.0485 | 0.0421 | 0.0711 | 5.1 | 5.1 |
| csd | y=100 | 0.112 | 0.0837 | 0.0711 | 5.1 | 5.1 |
