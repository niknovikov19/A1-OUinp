import numpy as np


N_SEEDS = 1

POPS_PRE = ['TC']

POP_GROUPS_POST = {
    'E4': {'pops': ['ITP4', 'ITS4'], 'conns': []},
    'E4_PV4': {'pops': ['ITP4', 'ITS4', 'PV4'],
               'conns': [('PV4', ('ITP4', 'ITS4'))]},
    #'L4': {'pops': ['ITP4', 'ITS4', 'PV4', 'SOM4', 'VIP4', 'NGF4'], 'conns': []},
    'E2': {'pops': ['IT2'], 'conns': []},
    'E4_E2': {'pops': ['ITP4', 'ITS4', 'IT2'], 'conns': []},
    'E4_E2_ff': {'pops': ['ITP4', 'ITS4', 'IT2'],
                 'conns': [(('ITP4', 'ITS4'), 'IT2')]},
    'E4_E23_ff': {'pops': ['ITP4', 'ITS4', 'IT2', 'IT3'],
                  'conns': [(('ITP4', 'ITS4'), ('IT2', 'IT3')), ('IT2', 'IT3')]},
}

def _expand_conn_pairs(pre_spec, post_spec):
    """Expand a conn spec where each side is a pop name str or list of names."""
    pres = [pre_spec] if isinstance(pre_spec, str) else list(pre_spec)
    posts = [post_spec] if isinstance(post_spec, str) else list(post_spec)
    return [(p1, p2) for p1 in pres for p2 in posts]


def get_batch_params():
    """Generate params for batchtools to probe. """
    params = {
        'seed_main': (1000 + np.arange(N_SEEDS)).tolist(),
        'pop_pre': POPS_PRE,
        'pop_group_post': list(POP_GROUPS_POST.keys()),
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
    
    # Target of pulses
    if (hasattr(cfg, 'pulse_seq_params') and 
            isinstance(cfg.pulse_seq_params, dict)):
        cfg.pulse_seq_params['pop'] = cfg.pop_pre

    # Set active pops and connections from POP_GROUPS_POST spec
    pops_pre = [cfg.pop_pre]
    group = POP_GROUPS_POST[cfg.pop_group_post]
    pops_post = group['pops']

    # Collect any extra pops referenced in 'conns' that aren't in pops_pre/pops_post
    extra_pops = []
    for pre_spec, post_spec in group['conns']:
        pres = [pre_spec] if isinstance(pre_spec, str) else list(pre_spec)
        posts = [post_spec] if isinstance(post_spec, str) else list(post_spec)
        for p in pres + posts:
            if p not in pops_pre and p not in pops_post and p not in extra_pops:
                extra_pops.append(p)
    all_active = pops_pre + pops_post + extra_pops

    # Base active connections: pop_pre -> every pop in pops_post
    active_conns = set()
    for p1 in pops_pre:
        for p2 in pops_post:
            active_conns.add((p1, p2))

    # Additional connections defined in 'conns'
    for pre_spec, post_spec in group['conns']:
        active_conns.update(_expand_conn_pairs(pre_spec, post_spec))

    cfg.subnet_params['pops_active'] = all_active
    cfg.subnet_params['conns_frozen'] = [
        (p1, p2)
        for p1 in all_active
        for p2 in all_active
        if (p1, p2) not in active_conns
    ]
