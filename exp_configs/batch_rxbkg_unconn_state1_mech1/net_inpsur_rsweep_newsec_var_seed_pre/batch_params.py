import numpy as np


PYR_POPS = ['IT2', 'IT3', 'ITP4', 'ITS4', 'IT5A', 'IT5B', 'IT6',
            'CT5A', 'CT5B', 'CT6', 'PT5B']
PV_POPS = ['PV2', 'PV3', 'PV4', 'PV5A', 'PV5B', 'PV6']
SOM_POPS = ['SOM2', 'SOM3', 'SOM4', 'SOM5A', 'SOM5B', 'SOM6']
VIP_POPS = ['VIP2', 'VIP3', 'VIP4', 'VIP5A', 'VIP5B', 'VIP6']
NGF_POPS = ['NGF1', 'NGF2', 'NGF3', 'NGF4', 'NGF5A', 'NGF5B', 'NGF6']

L2_POPS = ['IT2', 'PV2', 'SOM2', 'VIP2', 'NGF2']
L4_POPS = ['ITP4', 'ITS4', 'PV4', 'SOM4', 'VIP4', 'NGF4']
CTX_POPS = PYR_POPS + PV_POPS + SOM_POPS + VIP_POPS + NGF_POPS

THAL_E_POPS = ['TC', 'HTC', 'TCM']
THAL_I_POPS = ['TI', 'TIM', 'IRE', 'IREM']
CORE_POPS = ['TC', 'HTC', 'TI', 'IRE']
MATX_POPS = ['TCM', 'TIM', 'IREM']
THAL_POPS = CORE_POPS + MATX_POPS


N_SEEDS = 5

#POPS_PRE = ['ITP4', 'IT2']
POPS_PRE = CTX_POPS


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
