import numpy as np


N_SEEDS = 5

# Population groups used to define frozen connection groups
PYR_POPS = ['IT2', 'IT3', 'ITP4', 'ITS4', 'IT5A', 'IT5B', 'IT6',
            'CT5A', 'CT5B', 'CT6', 'PT5B']
PV_POPS = ['PV2', 'PV3', 'PV4', 'PV5A', 'PV5B', 'PV6']
SOM_POPS = ['SOM2', 'SOM3', 'SOM4', 'SOM5A', 'SOM5B', 'SOM6']
VIP_POPS = ['VIP2', 'VIP3', 'VIP4', 'VIP5A', 'VIP5B', 'VIP6']
NGF_POPS = ['NGF1', 'NGF2', 'NGF3', 'NGF4', 'NGF5A', 'NGF5B', 'NGF6']
CTX_POPS = PYR_POPS + PV_POPS + SOM_POPS + VIP_POPS + NGF_POPS

THAL_E_POPS = ['TC', 'HTC', 'TCM']
THAL_I_POPS = ['TI', 'TIM', 'IRE', 'IREM']
THAL_POPS = THAL_E_POPS + THAL_I_POPS

CORE_E_POPS = ['TC', 'HTC']
CORE_I_POPS = ['TI', 'IRE']
CORE_POPS = CORE_E_POPS + CORE_I_POPS

MATX_E_POPS = ['TCM']
MATX_I_POPS = ['TIM', 'IREM']
MATX_POPS = MATX_E_POPS + MATX_I_POPS

L2_POPS = ['IT2', 'PV2', 'SOM2', 'VIP2', 'NGF2']
L4_POPS = ['ITP4', 'ITS4', 'PV4', 'SOM4', 'VIP4', 'NGF4']

# Reusable connection groups from the parent experiment
E_POPS = PYR_POPS + THAL_E_POPS
CONNS_EE = [(p1, p2) for p1 in E_POPS for p2 in E_POPS]
CONNS_IRE_TC = [
    (p1, p2) for p1 in ['IRE', 'IREM'] for p2 in THAL_E_POPS
]
CONNS_THAL = [(p1, p2) for p1 in THAL_POPS for p2 in THAL_POPS]
CONNS_THAL_ETHAL = [
    (p1, p2) for p1 in THAL_POPS for p2 in THAL_E_POPS
]
CONNS_TI_ETHAL = [
    (p1, p2) for p1 in ['TI', 'TIM'] for p2 in THAL_E_POPS
]
CONNS_ETHAL_TI = [
    (p1, p2) for p1 in THAL_E_POPS for p2 in ['TI', 'TIM']
]
CONNS_THAL_TI = [
    (p1, p2) for p1 in THAL_POPS for p2 in ['TI', 'TIM']
]
CONNS_IREM_IRE = [('IREM', 'IRE')]
CONNS_IREM_IRE_EE = CONNS_IREM_IRE + CONNS_EE
CONNS_IREM_CORE_EE = [
    ('IREM', p2) for p2 in CORE_POPS
] + CONNS_EE
CONNS_MATX_TI = [(p1, 'TI') for p1 in MATX_POPS]

# Top-10 connection-freezing conditions in priority order
FRZ_CONN_GROUPS = [
    {'none': []},
    {'thal_irem': [(p1, 'IREM') for p1 in THAL_POPS]},
    {'irem_ire_ti': [('IREM', p2) for p2 in ['IRE', 'TI']]},
    {'irem_tim': [('IREM', 'TIM')]},
    {'ti_tc': [('TI', p2) for p2 in CORE_E_POPS]},
    {'tim_tc': [('TIM', p2) for p2 in CORE_E_POPS]},
    {'irem_ire': CONNS_IREM_IRE},
    {'irem_ti': [('IREM', 'TI')]},
    {'irem_core': [('IREM', p2) for p2 in CORE_POPS]},
    {'ti_tim_tc': [(p1, p2) for p1 in ['TI', 'TIM'] for p2 in CORE_E_POPS]},
]


def get_frz_conns_by_name():
    """Return frozen connections keyed by unique group name. """
    groups = {}
    for group in FRZ_CONN_GROUPS:
        if len(group) != 1:
            raise ValueError('Each frozen connection group needs one name')
        name, conns = next(iter(group.items()))
        if name in groups:
            raise ValueError(f'Duplicate frozen connection group: {name}')
        groups[name] = conns
    return groups


def get_batch_params():
    """Generate params for batchtools to probe. """
    frz_conns_by_name = get_frz_conns_by_name()
    params = {
        'seed_main': (1000 + np.arange(N_SEEDS)).tolist(),
        'frz_conn_group': list(frz_conns_by_name),
    }
    return params


def post_update(cfg):
    """Derive seed and frozen-connection params after cfg.update(). """

    # Set stochastic seeds from the batch seed axis
    cfg.seeds['stim'] = cfg.seed_main
    cfg.seeds['conn'] = cfg.seed_main * 2
    cfg.subnet_params['global_seed'] = cfg.seed_main * 3

    # Select the connections frozen for this batch trial
    frz_conns_by_name = get_frz_conns_by_name()
    cfg.subnet_params['conns_frozen'] = list(
        frz_conns_by_name[cfg.frz_conn_group]
    )

    # Set background input seeds for every active population
    for n, pop in enumerate(cfg.bkg_spike_inputs):
        cfg.bkg_spike_inputs[pop]['exc']['seed'] = (
            cfg.seeds['stim'] + 10000 + n
        )
        cfg.bkg_spike_inputs[pop]['inh']['seed'] = (
            cfg.seeds['stim'] + 20000 + n
        )

    # Store batch metadata for downstream collectors
    cfg.batch_par_info = {
        'n_seeds': N_SEEDS,
        'frz_conn_groups': list(frz_conns_by_name),
        'batch_params': ['seed_main', 'frz_conn_group'],
    }
