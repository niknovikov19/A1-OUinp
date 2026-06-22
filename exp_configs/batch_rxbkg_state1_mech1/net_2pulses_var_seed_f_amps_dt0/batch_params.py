import numpy as np


N_SEEDS = 1
F_VALUES = [2, 5]
AMP1_VALUES = [0.01, 0.02, 0.03]
AMP2_VALUES = [0.01, 0.02, 0.03]
DT0_VALUES = [0, 25, 50]
PULSE_T0 = 5000
PULSE_ZERO_WEIGHT = 1e-6
PULSE_COUNT_EPS = 1e-9


def get_batch_params():
    """Generate params for batchtools to probe."""
    params = {
        'seed_main': (1000 + np.arange(N_SEEDS)).tolist(),
        'f': F_VALUES,
        'amp1': AMP1_VALUES,
        'amp2': AMP2_VALUES,
        'dt0': DT0_VALUES,
    }
    return params


def _as_pulse_list(pulse_seq_params):
    """Return pulse params as a list."""
    if isinstance(pulse_seq_params, dict):
        return [pulse_seq_params]
    return list(pulse_seq_params)


def _expand_pulse_rates(rates, n_pulses):
    """Expand scalar or cyclic pulse-rate settings to all pulses."""
    if np.isscalar(rates):
        return [rates] * n_pulses

    rates = list(rates)
    if len(rates) == 0:
        raise ValueError('PULSE_PARAMS["rates"] cannot be empty')
    return [rates[n % len(rates)] for n in range(n_pulses)]


def _get_pulse_weight(amp):
    """Return the actual pulse weight for one public amp value."""
    if amp == 0:
        return PULSE_ZERO_WEIGHT
    return amp


def _get_t_last(cfg, pulse_params):
    """Resolve the inclusive last pulse-start time in ms."""
    t_last_vals = [
        pulse_par.get('t_last', None)
        for pulse_par in pulse_params
    ]
    t_last_vals = [
        cfg.duration if value is None else value
        for value in t_last_vals
    ]
    return min(t_last_vals)


def _get_n_pulses(t0, t_last, period):
    """Return the number of pulse starts from t0 through t_last."""
    return int(np.floor((t_last - t0) / period + PULSE_COUNT_EPS)) + 1


def _get_jitter_offsets(cfg, n_pulses, jitter, rand_type):
    """Return shared paired-pulse jitter offsets."""
    offsets = np.zeros(n_pulses)
    if jitter == 0:
        return offsets

    rng = np.random.default_rng(cfg.seeds['stim'] + 30000)
    if rand_type == 'uni':
        offsets[1:] = rng.uniform(-jitter, jitter, n_pulses - 1)
    elif rand_type == 'norm':
        offsets[1:] = rng.normal(0, jitter, n_pulses - 1)
    else:
        raise ValueError(f'Unknown pulse rand_type: {rand_type}')
    return offsets


def _validate_shared_jitter_params(pulse_params):
    """Require identical jitter controls for all paired streams."""
    ref_par = pulse_params[0]
    ref_key = (ref_par['jitter'], ref_par['rand_type'])
    for pulse_par in pulse_params[1:]:
        key = (pulse_par['jitter'], pulse_par['rand_type'])
        if key != ref_key:
            raise ValueError('Paired pulse streams need matching jitter params')


def _validate_pulse_windows(cfg, pulse_params):
    """Reject jittered pulse windows outside the simulation interval."""
    for pulse_par in pulse_params:
        starts = np.asarray(pulse_par['tpulse'], dtype=float)
        ends = starts + pulse_par['width']
        if np.any(starts < 0) or np.any(ends > cfg.duration):
            raise ValueError(
                f"Jittered pulse windows leave cfg.duration for "
                f"{pulse_par['name']}"
            )


def _set_pulse_timing(cfg, pulse_params):
    """Derive common pulse period, count, rates, and paired starts."""
    if cfg.f <= 0:
        raise ValueError('Batch pulse frequency f must be positive')

    # Use the later stream start to keep both streams at the same pulse count
    period = 1000 / cfg.f
    starts = [pulse_par['t0'] for pulse_par in pulse_params]
    t0_late = max(starts)
    t_last = _get_t_last(cfg, pulse_params)
    if t0_late >= cfg.duration:
        raise ValueError('Pulse t0 should be before cfg.duration')
    if t_last < t0_late:
        raise ValueError('Pulse t_last should be at or after the later t0')
    if t_last > cfg.duration:
        raise ValueError('Pulse t_last should be at or before cfg.duration')

    n_pulses = _get_n_pulses(t0_late, t_last, period)
    ref_par = pulse_params[0]
    _validate_shared_jitter_params(pulse_params)
    offsets = _get_jitter_offsets(
        cfg,
        n_pulses,
        ref_par['jitter'],
        ref_par['rand_type'],
    )

    # Apply the same offsets to both streams so paired dt0 stays constant
    for pulse_par in pulse_params:
        base_starts = pulse_par['t0'] + np.arange(n_pulses) * period
        pulse_par['period'] = period
        pulse_par['n_pulses'] = n_pulses
        pulse_par['tpulse'] = (base_starts + offsets).tolist()
        pulse_par['rates'] = _expand_pulse_rates(
            pulse_par['rates'],
            n_pulses,
        )

    if ref_par['jitter'] != 0:
        _validate_pulse_windows(cfg, pulse_params)


def post_update(cfg):
    """Derive seed and pulse params after cfg.update()."""

    # Set stochastic seeds from the batch seed axis
    cfg.seeds['stim'] = cfg.seed_main
    cfg.seeds['conn'] = cfg.seed_main * 2
    cfg.subnet_params['global_seed'] = cfg.seed_main * 3

    # Set background input seeds for every active population
    for n, pop in enumerate(cfg.bkg_spike_inputs):
        cfg.bkg_spike_inputs[pop]['exc']['seed'] = (
            cfg.seeds['stim'] + 10000 + n
        )
        cfg.bkg_spike_inputs[pop]['inh']['seed'] = (
            cfg.seeds['stim'] + 20000 + n
        )

    if not getattr(cfg, 'add_pulses', 0):
        return

    # Convert batch coordinates into two pulse-generator parameter dicts
    pulse_params = _as_pulse_list(cfg.pulse_seq_params)
    if len(pulse_params) != 2:
        raise ValueError('Two pulse sequence params are required')
    pulse_params[0]['t0'] = PULSE_T0
    pulse_params[1]['t0'] = PULSE_T0 + cfg.dt0
    pulse_params[0]['weight'] = _get_pulse_weight(cfg.amp1)
    pulse_params[1]['weight'] = _get_pulse_weight(cfg.amp2)
    _set_pulse_timing(cfg, pulse_params)
    cfg.pulse_seq_params = pulse_params

    # Store compact batch metadata for downstream scripts
    cfg.batch_par_info = {
        'n_seeds': N_SEEDS,
        'f_values': F_VALUES,
        'amp1_values': AMP1_VALUES,
        'amp2_values': AMP2_VALUES,
        'dt0_values': DT0_VALUES,
        'batch_params': ['seed_main', 'f', 'amp1', 'amp2', 'dt0'],
    }
