NEURON {
  POINT_PROCESS RateController2
  RANGE tau, taum, tauu, r0, ks, ku, epsm
  RANGE rate, m, u, s, e, q, z, z0, t0, tlock
}

PARAMETER {
  tau   = 50   (ms)    : EMA time constant for measured rate
  taum  = 500  (ms)    : time constant of slow mean-error estimate m
  tauu  = 50   (ms)    : time constant of fast helper u

  r0    = 5.0  (Hz)    : target rate
  ks    = 0.0002 (/ms) : slow integrator gain for s
  ku    = 1.0          : gain of fast helper branch
  epsm  = 0.0  (Hz)    : dead zone on m; 0 -> linear controller

  z0    = 0.0  (Hz)    : initial control
  t0    = 0    (ms)    : controller start time
  tlock = 1000 (ms)    : controller lock time
}

STATE {
  rate  (Hz)           : measured rate (EMA of spikes)
  m     (Hz)           : slow estimate of mean error
  u     (Hz)           : fast dynamic helper
  s     (Hz)           : slow tonic correction
}

ASSIGNED {
  e     (Hz)           : instantaneous error = r0 - rate
  q     (Hz)           : fast residual = e - m
  z     (Hz)           : controller output
}

INITIAL {
  rate = 0.0
  m    = 0.0
  u    = 0.0
  s    = z0

  e = 0.0
  q = 0.0
  z = z0
}

BREAKPOINT {
  SOLVE states METHOD cnexp

  e = r0 - rate
  q = e - m

  if (t < t0) {
    z = z0
  } else if (t <= tlock) {
    z = s + u
  } else {
    z = s
  }
}

DERIVATIVE states {
  LOCAL ee, qq

  : rate estimator always runs
  rate' = -rate / tau

  if (t < t0) {
    m' = 0
    u' = 0
    s' = 0

  } else if (t <= tlock) {
    ee = r0 - rate
    m' = (ee - m) / taum

    qq = ee - m
    u' = (-u + ku * qq) / tauu

    s' = ks * phi(m)

  } else {
    : hard lock: freeze controller states
    m' = 0
    u' = 0
    s' = 0
  }
}

FUNCTION phi(x (Hz)) (Hz) {
  if (x > epsm) {
    phi = x - epsm
  } else if (x < -epsm) {
    phi = x + epsm
  } else {
    phi = 0.0
  }
}

NET_RECEIVE (w) {
  : each spike bumps the EMA so that steady state equals spike rate in Hz
  rate = rate + w * (1000.0 / tau)
}