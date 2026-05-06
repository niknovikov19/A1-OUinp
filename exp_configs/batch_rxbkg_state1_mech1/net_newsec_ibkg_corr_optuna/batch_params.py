
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
        'num_samples': 50,
        'max_concurrent': 4,
        'sample_interval': 1,
        'algorithm_config': {
            'seed': 1234,
        },
    }


def post_update(cfg):
    """Called after cfg.update() """
    for pop_name in IBKG_CORR_RANGES:
        par_name = get_ibkg_corr_param_name(pop_name)
        cfg.IClamp_corr[pop_name]['amp'] = getattr(cfg, par_name)
