import re

import numpy as np


L2_POPS = ['IT2', 'PV2', 'SOM2', 'VIP2', 'NGF2']

# Define spatial groups independently of the signed amplitude in nA
STEP_GROUPS = {
    'IT2': ['IT2'],
    'PV2': ['PV2'],
    #'SOM2': ['SOM2'],
    #'VIP2': ['VIP2'],
    #'NGF2': ['NGF2'],
    #'all_L2': L2_POPS.copy(),
    #'IT2_PV2': {'IT2': 1, 'PV2': 0.5},
    'control': [],
}

# Define the complete seed and amplitude grid used in names and metadata
N_SEEDS = 5
GROUP_SET_LABEL = '1pop_v1'
AMP_VALUES = [-0.03, -0.015, 0.015, 0.03]

# Label pilot datasets and keep revised attempts in separate result folders
PILOT = 1
PILOT_ATTEMPT = 3

# Restrict batch axes to listed values; None uses the full corresponding axis
SEEDS_SUBSET = None
GROUPS_SUBSET = None
AMPS_SUBSET = None


def get_step_groups(pops_used):
    """Normalize group definitions to population multipliers. """
    groups = {}
    for name, definition in STEP_GROUPS.items():
        if re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*', name) is None:
            raise ValueError(f'Invalid step-group name: {name!r}')
        if isinstance(definition, list):
            if len(set(definition)) != len(definition):
                raise ValueError(f'Duplicate populations in step group {name}')
            multipliers = {pop: 1 for pop in definition}
        elif isinstance(definition, dict):
            multipliers = dict(definition)
        else:
            raise TypeError(f'Expected a list or dict for step group {name}')

        unknown = set(multipliers) - set(pops_used)
        if unknown:
            raise ValueError(f'Inactive step targets in {name}: {sorted(unknown)}')
        if not all(np.isfinite(value) for value in multipliers.values()):
            raise ValueError(f'Non-finite multipliers in step group {name}')
        groups[name] = multipliers
    return groups


def _select_subset(values, subset, name):
    """Select a nonempty subset of one protocol axis. """
    selected = list(values if subset is None else subset)
    if not selected or len(set(selected)) != len(selected):
        raise ValueError(f'{name} must be nonempty and have no duplicates')
    if any(value not in values for value in selected):
        raise ValueError(f'{name} contains values outside the protocol')
    return selected


def get_batch_params():
    """Generate seed, spatial-group, and signed-amplitude axes. """
    if not AMP_VALUES or not all(np.isfinite(amp) for amp in AMP_VALUES):
        raise ValueError('AMP_VALUES must contain finite currents')

    # Form the Cartesian grid from the group definitions and optional subsets
    seeds = _select_subset(range(1000, 1000 + N_SEEDS), SEEDS_SUBSET, 'seeds')
    groups = _select_subset(list(STEP_GROUPS), GROUPS_SUBSET, 'groups')
    amps = _select_subset(AMP_VALUES, AMPS_SUBSET, 'amplitudes')
    return {'seed_main': seeds, 'step_group': groups, 'amp': amps}


def post_update(cfg):
    """Resolve the step vector and seed streams after the batch update. """
    axes = get_batch_params()
    for name, values in axes.items():
        if getattr(cfg, name) not in values:
            raise ValueError(f'Unexpected batch value for {name}')

    # Derive the current vector from one group and one scalar amplitude
    multipliers = cfg.step_groups[cfg.step_group]
    cfg.h_step = {
        pop: cfg.amp * multipliers.get(pop, 0)
        for pop in cfg.pops_used
    }
    cfg.step_pops = [pop for pop, current in cfg.h_step.items() if current != 0]

    # Match all stochastic streams across groups and amplitudes for each seed
    cfg.seeds['stim'] = cfg.seed_main
    cfg.seeds['conn'] = cfg.seed_main * 2
    cfg.subnet_params['global_seed'] = cfg.seed_main * 3
    for n, pop in enumerate(cfg.bkg_spike_inputs):
        cfg.bkg_spike_inputs[pop]['exc']['seed'] = cfg.seeds['stim'] + 10000 + n
        cfg.bkg_spike_inputs[pop]['inh']['seed'] = cfg.seeds['stim'] + 20000 + n

    cfg.batch_par_info = {
        'pilot': PILOT,
        'pilot_attempt': PILOT_ATTEMPT,
        'n_seeds': N_SEEDS,
        'group_set_label': GROUP_SET_LABEL,
        'step_group_names': list(STEP_GROUPS),
        'amp_values_nA': AMP_VALUES.copy(),
        'step_groups': cfg.step_groups,
        'batch_params': list(axes),
        'batch_axes': axes,
    }
