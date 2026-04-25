N_SEEDS = 1
FIXED_SEED_MAIN = 1000
SIM_DURATION = 15 * 1e3

# Optuna-tuned IClamp correction ranges
IBKG_CORR_RANGES = {
    'HTC': (-0.5, 0.5),
    'TC': (-0.5, 0.5),
    'TCM': (-0.5, 0.5),
    'IRE': (-0.1, 0.1),
    'IREM': (-0.1, 0.1),
    'TI': (-0.01, 0.01),
    'TIM': (-0.01, 0.01),
}


def get_ibkg_corr_param_name(pop_name):
    return f'ibkg_corr_{pop_name}'


def _append_iclamp_entry(existing, entry):
    if isinstance(existing, dict):
        return [existing, entry]
    if isinstance(existing, list):
        return existing + [entry]
    raise TypeError(f'Unsupported IClamp entry type: {type(existing)!r}')


def get_optuna_config():
    """Generate params for Optuna to probe. """
    params = {
        get_ibkg_corr_param_name(pop_name): bounds
        for pop_name, bounds in IBKG_CORR_RANGES.items()
    }
    return {
        'params': params,
        'metric': 'loss_rate_mae',
        'mode': 'min',
        'num_samples': 12,
        'max_concurrent': 2,
        'sample_interval': 1,
        'algorithm_config': {
            'seed': 1234,
        },
    }


def post_update(cfg):
    """Called after cfg.update() """

    # Add Optuna-tuned DC offset IClamp
    if not hasattr(cfg, 'IClamp') or cfg.IClamp is None:
        cfg.IClamp = {}

    for pop_name in IBKG_CORR_RANGES:
        par_name = get_ibkg_corr_param_name(pop_name)
        corr_entry = {
            'amp': getattr(cfg, par_name),
            'dur': SIM_DURATION,
        }
        if pop_name in cfg.IClamp:
            cfg.IClamp[pop_name] = _append_iclamp_entry(cfg.IClamp[pop_name], corr_entry)
        else:
            cfg.IClamp[pop_name] = corr_entry
