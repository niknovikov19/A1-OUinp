import numpy as np


N_SEEDS = 1
F_VALUES = [2, 5]
AMP_VALUES = [0.01, 0.02, 0.03]
PULSE_ZERO_WEIGHT = 1e-6
PULSE_COUNT_EPS = 1e-9


def get_batch_params():
    """Generate params for batchtools to probe."""
    params = {
        'seed_main': (1000 + np.arange(N_SEEDS)).tolist(),
        'f': F_VALUES,
        'amp': AMP_VALUES,
    }
    return params


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


def _get_t_last(cfg):
    """Resolve the inclusive last pulse-start time in ms."""
    t_last = cfg.pulse_seq_params.get('t_last', None)
    if t_last is None:
        return cfg.duration
    return t_last


def _get_n_pulses(t0, t_last, period):
    """Return the number of pulse starts from t0 through t_last."""
    return int(np.floor((t_last - t0) / period + PULSE_COUNT_EPS)) + 1


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

    # Convert batch frequency and amplitude into pulse-generator params
    if cfg.f <= 0:
        raise ValueError('Batch pulse frequency f must be positive')
    period = 1000 / cfg.f
    t0 = cfg.pulse_seq_params['t0']
    if t0 >= cfg.duration:
        raise ValueError('Pulse t0 should be before cfg.duration')
    t_last = _get_t_last(cfg)
    if t_last < t0:
        raise ValueError('Pulse t_last should be at or after t0')
    if t_last > cfg.duration:
        raise ValueError('Pulse t_last should be at or before cfg.duration')
    n_pulses = _get_n_pulses(t0, t_last, period)

    # Update only fields controlled by the f/amp batch axes
    rates = cfg.pulse_seq_params['rates']
    cfg.pulse_seq_params['period'] = period
    cfg.pulse_seq_params['weight'] = _get_pulse_weight(cfg.amp)
    cfg.pulse_seq_params['n_pulses'] = n_pulses
    cfg.pulse_seq_params['rates'] = _expand_pulse_rates(rates, n_pulses)

    # Store compact batch metadata for downstream scripts
    cfg.batch_par_info = {
        'n_seeds': N_SEEDS,
        'f_values': F_VALUES,
        'amp_values': AMP_VALUES,
        'batch_params': ['seed_main', 'f', 'amp'],
    }
