import numpy as np


# Population groups
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

IBKG_MIN = -0.1
IBKG_MAX = 0.1
IBKG_NUM = 10

IBKG_DW_ADJ_VALUES = np.linspace(
    IBKG_MIN, IBKG_MAX, IBKG_NUM
).round(4).tolist()


def get_batch_params():
    """Generate params for batchtools to probe."""
    # Batch grid
    params = {
        'seed_main': (1000 + np.arange(N_SEEDS)).tolist(),
        'ibkg_dw_adj': IBKG_DW_ADJ_VALUES,
    }
    return params


def post_update(cfg):
    """Called after cfg.update()."""
    # Main seed bundle
    cfg.seeds['stim'] = cfg.seed_main
    cfg.seeds['conn'] = cfg.seed_main * 2
    cfg.subnet_params['global_seed'] = cfg.seed_main * 3

    # Adjustable current
    for entry in cfg.IClamp_ibkg_dw_adj.values():
        entry['amp'] = cfg.ibkg_dw_adj

    # Background input seeds
    for n, pop in enumerate(cfg.bkg_spike_inputs):
        cfg.bkg_spike_inputs[pop]['exc']['seed'] = (
            cfg.seeds['stim'] + 10000 + n
        )
        cfg.bkg_spike_inputs[pop]['inh']['seed'] = (
            cfg.seeds['stim'] + 20000 + n
        )

    # Batch metadata
    cfg.batch_par_info = {
        'n_seeds': N_SEEDS,
        'ibkg_dw_adj_values': IBKG_DW_ADJ_VALUES,
        'batch_params': ['seed_main', 'ibkg_dw_adj'],
    }
