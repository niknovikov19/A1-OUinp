import numpy as np


N_SEEDS = 5

#POPS_PRE = ['ITP4', 'IT2']
POPS_PRE = ['IT2', 'PV2', 'SOM2', 'VIP2', 'NGF2']


def get_batch_params():
    """Generate params for batchtools to probe. """
    params = {
        'seed_main': (1000 + np.arange(N_SEEDS)).tolist(),
        'pop_pre': POPS_PRE
    }
    return params


def post_update(cfg):
    """Called after cfg.update() """

    # Seeds
    cfg.seeds['stim'] = cfg.seed_main
    cfg.seeds['conn'] = cfg.seed_main * 2
    cfg.subnet_params['global_seed'] = cfg.seed_main * 3

    # Seeds for bkg netstims
    for n, pop in enumerate(cfg.bkg_spike_inputs):
        cfg.bkg_spike_inputs[pop]['exc']['seed'] = (
            cfg.seeds['stim'] + 10000 + n
        )
        cfg.bkg_spike_inputs[pop]['inh']['seed'] = (
            cfg.seeds['stim'] + 20000 + n
        )
    
    # Store batch params for reference
    cfg.batch_par_info = {
        'n_seeds': N_SEEDS,
        'pops_pre': POPS_PRE,
        'batch_params': ['seed_main', 'pop_pre']
    }
