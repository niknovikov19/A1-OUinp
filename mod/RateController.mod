NEURON {
  POINT_PROCESS RateController
  RANGE tau, taus, r0, k, kp, rate, u, z, s, z0, t0, tlock
}

PARAMETER {
  tau = 50 (ms)         : EMA time constant for rate
  taus = 500 (ms)       : slow time constant for s
  r0  = 5.0             : target rate (Hz)
  k   = 0.02            : adaptation gain (integral)
  kp  = 0.02            : adaptation gain (proportional)
  z0 = 0.0              : initial value of z
  t0  = 0 (ms)          : controller start time
  tlock = 1000 (ms)     : controller lock time
}

STATE {
  rate                  : (Hz)
  u                     : control variable (internal)
  s                     : slow-filtered control
}

ASSIGNED {
  z (Hz)          : control output
}

INITIAL {
  rate = 0.0
  u = z0
  z = z0
  s = z0
}

BREAKPOINT {
  SOLVE states METHOD cnexp
  
  if (t < t0) {
    z = u                       : controller inactive
  } else if (t <= tlock) {
    z = kp * (r0 - rate) + u    : normal PI control phase
  } else {
    z = s                       : locked phase - follow slow integrator
  }
}

DERIVATIVE states {
  rate' = -rate/tau
  if (t < t0) {
    :rate' = 0
    u'    = 0
    s'    = 0
  } else {
    :rate' = -rate/tau
    u'    = k * (r0 - rate)
    s'    = (z - s) / taus
  }
}

NET_RECEIVE (w) {
  rate = rate + w * (1000.0/tau)
  if (t >= t0) {
    : Each spike bumps the EMA by 1000/tau (so steady-state == spike freq in Hz)
    :rate = rate + w * (1000.0/tau)
  }
}
