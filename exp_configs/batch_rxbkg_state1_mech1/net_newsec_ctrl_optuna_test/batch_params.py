N_SEEDS = 1
FIXED_SEED_MAIN = 1000


def get_optuna_config():
    return {
        'params': {
            'seed_main': FIXED_SEED_MAIN,
            'ctrl_mu_gain': (0.001, 0.02),
            'ctrl_ks_ctrl': (1e-5, 5e-4),
            'ctrl_ku_ctrl': (1e-4, 5e-3),
        },
        'metric': 'loss_rate_mae',
        'mode': 'min',
        'num_samples': 6,
        'max_concurrent': 2,
        'sample_interval': 1,
        'algorithm_config': {
            'seed': 1234,
        },
    }


def _sync_ctrl_params(cfg):
    if not hasattr(cfg, 'ou_ctrl_params'):
        return

    cfg.ou_ctrl_params['mu_gain'] = cfg.ctrl_mu_gain
    cfg.ou_ctrl_params['ks_ctrl'] = cfg.ctrl_ks_ctrl
    cfg.ou_ctrl_params['ku_ctrl'] = cfg.ctrl_ku_ctrl


def post_update(cfg):
    cfg.seed_main = int(cfg.seed_main)

    cfg.seeds['stim'] = cfg.seed_main
    cfg.seeds['conn'] = cfg.seed_main * 2
    cfg.subnet_params['global_seed'] = cfg.seed_main * 3

    _sync_ctrl_params(cfg)

    for n, pop in enumerate(cfg.bkg_spike_inputs):
        cfg.bkg_spike_inputs[pop]['exc']['seed'] = (
            cfg.seeds['stim'] + 10000 + n
        )
        cfg.bkg_spike_inputs[pop]['inh']['seed'] = (
            cfg.seeds['stim'] + 20000 + n
        )
