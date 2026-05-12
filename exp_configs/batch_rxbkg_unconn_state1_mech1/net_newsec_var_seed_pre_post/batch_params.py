import numpy as np


N_SEEDS = 1


def get_batch_params():
    """Generate params for batchtools to probe. """
    params = {
        'seed_main': (1000 + np.arange(N_SEEDS)).tolist(),
    }
    return params


def post_update(cfg):
    """Called after cfg.update() """

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
