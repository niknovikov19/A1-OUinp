# Periodic Mask Fit Demo

## Parameters
- Event frequency: `5 Hz`
- Event period: `0.2 s`
- Pulse width: `0.05 s`
- Pulse pad: `0.02 s`
- Clean interval: `0.11 s`
- Fit target frequency: `5 Hz`
- Fit half-width: `0.382 s`

## Results
| signal | ITC | random floor | median valid mass | peak freq | peak/median power |
|---|---:|---:|---:|---:|---:|
| white | 0.0722 | 0.0707 | 0.545 | 5.1 | 1.52 |
| slow | 0.0112 | 0.0707 | 0.545 | 3.5 | 3.47 |
| white_plus_slow | 0.00663 | 0.0707 | 0.545 | 5.1 | 1.45 |
