import numpy as np


N_SEEDS = 2
FADE_POSTS = ['TI', 'IRE']


def get_batch_params():
    """Generate params for batchtools to probe. """
    params = {
        'seed_main': (1000 + np.arange(N_SEEDS)).tolist(),
        'fade_post': list(FADE_POSTS),
    }
    return params


def post_update(cfg):
    """Called after cfg.update() """

    # Select the restored projection before building the subnet
    if cfg.fade_post not in FADE_POSTS:
        raise ValueError(f'Unknown fading target: {cfg.fade_post}')
    cfg.subnet_params['conns_split'] = {f'IREM, {cfg.fade_post}': 0.5}

    cfg.seeds['stim'] = cfg.seed_main
    cfg.seeds['conn'] = cfg.seed_main * 2
    cfg.subnet_params['global_seed'] = cfg.seed_main * 3

    for n, pop in enumerate(cfg.bkg_spike_inputs):
        cfg.bkg_spike_inputs[pop]['exc']['seed'] = (
            cfg.seeds['stim'] + 10000 + n
        )
        cfg.bkg_spike_inputs[pop]['inh']['seed'] = (
            cfg.seeds['stim'] + 20000 + n
        )

