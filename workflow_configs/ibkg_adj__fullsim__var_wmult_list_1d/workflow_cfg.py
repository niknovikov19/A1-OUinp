from copy import deepcopy

import numpy as np


WORKFLOW_NAME = 'ibkg_adj__fullsim__var_wmult_list_1d'

POPS_USED = ['IT2', 'PV2', 'SOM2', 'VIP2', 'NGF2']

conns_ee = [('IT2', 'IT2')]
conns_ep = [('IT2', p) for p in POPS_USED if p != 'IT2'] 
conns_pe = [(p, 'IT2') for p in POPS_USED if p != 'IT2']
conn_groups = {'ee': conns_ee, 'ep': conns_ep, 'pe': conns_pe}

#wmult_vals = [1, 2]
wmult = 2

# Weight variants define explicit pre, post, multiplier triplets
WMULT_VARIANTS = {
    'base': [],
    f'ee{wmult}': [(c[0], c[1], wmult) for c in conns_ee],
    f'efb{wmult}': [(c[0], c[1], wmult) for c in (conns_ep + conns_pe)],
    f'ee{wmult}_efb{wmult}': [(c[0], c[1], wmult) for c in (conns_ee + conns_ep + conns_pe)]
}

#for gr_name, conns in conn_groups.items():
#    for wmult in wmult_vals:
#        v = [(conn[0], conn[1], wmult) for conn in conns]
""" WMULT_VARIANTS = {
    'w2': [('IT2', p, 2) for p in POPS_USED],
    'w5': [('IT2', p, 5) for p in POPS_USED],
    'w10': [('IT2', p, 10) for p in POPS_USED],
    'w20': [('IT2', p, 20) for p in POPS_USED],
} """

WMULT_VARIANT_KEYS = list(WMULT_VARIANTS)

EXP_LABEL = 'L2_wmult_list_ee_efb_2'

MAX_ITERATIONS = len(WMULT_VARIANT_KEYS)

# Stage 1 duration
DW_DURATION = 15000
DW_T0_CALC = 5000

# Stage 2 duration
FULLSIM_DURATION = 15000
FULLSIM_T0_CALC = 5000

DW_T_LIMITS = [DW_T0_CALC / 1000, DW_DURATION / 1000]
FULLSIM_T_LIMITS = [DW_T0_CALC / 1000, FULLSIM_DURATION / 1000]

N_SEEDS = 1

# Batch params shared by both subordinate stages
SEED_VALUES = (1000 + np.arange(N_SEEDS)).tolist()
IBKG_DW_ADJ_VALUES = np.linspace(-0.5, 0.1, 10).tolist()

# Surr-to-real conn fader for fullsim stage
FADER_PTS = [
    (0, 0),
    (3000, 0),
    (5000, 1),
    (FULLSIM_DURATION, 1)
]

FULLSIM_RUNTIME_PARAMS = {
    'time': {
        'duration': FULLSIM_DURATION,
        't0_calc': FULLSIM_T0_CALC
    },
    'pops_used': POPS_USED,
    'conn': {
        'fader_pts': FADER_PTS
    },
    'inp': {
        'add_pulses': False
    },
    'rec': {
        'traces': False,
        'lfp': False
    },
    'proc': {
        'rate_t_limits': FULLSIM_T_LIMITS,
        'rate_dt_bin': 0.005,
        'rate_tau_smooth': 0.01
    },
    'out': {
        'plot_traces': False,
        'plot_csd': False,
        'plot_rate_dynamics': 1,
        'save_rate_xr': 1
    },
}

# The context identifies one explicit point on the variant sweep
INITIAL_CONTEXT = {
    'wmult_id': 0,
    'wmult_variant': WMULT_VARIANT_KEYS[0],
    'wmat_multipliers': [
        {'pre': pre, 'post': post, 'mult': mult}
        for pre, post, mult in WMULT_VARIANTS[WMULT_VARIANT_KEYS[0]]
    ]
}

# Poll compact job records after BatchTools returns
WAIT_REFRESH_SEC = 10
WAIT_TIMEOUT_SEC = None

# Which results to store
RETENTION = {
    'keep_cfg': 1,
    'keep_netparams': 1,
    'keep_pkl': 0
}

# Shared Ray folder
RAY_CHECKPOINT_PATH = 'exp_logs/workflows/ray'

# BatchTools runtime shared by subordinate stages
BATCH_RUN_DEFAULTS = {
    'partition': 'cpu.q',
    'realtime': '7:00:00',
    'nodes': 1,
    'cores_per_node': 60,
    'mem_gb': 256,
    'max_concurrent': 6
}

# Subordinate batch experiments and workflow-local processors
STAGES = [
    {
        # Sweep over ibkg range to achieve target r0 for given variant
        'name': 'dw',
        'experiment': (
            'batch_rxbkg_unconn_state1_mech1/'
            'net_inpsur_dw_var_seed_ibkg'
        ),
        'processor': 'process_dw.py',
        'processor_params': {
            'target_rates_path': (
                'exp_configs/batch_rxbkg_unconn_state1_mech1/'
                'net_inpsur_dw_var_seed_ibkg/target_state_1.csv'
            ),
            'required_pops': POPS_USED
        },
        'batch_param_overrides': {
            'seed_main': SEED_VALUES,
            'ibkg_dw_adj': IBKG_DW_ADJ_VALUES
        },
        'experiment_overrides': {
            'duration': DW_DURATION,
            't0_calc': DW_T0_CALC
        },
        'batch_run': {}
    },
    {
        # Connected model run with given variant and ibkg from dw stage
        'name': 'fullsim',
        'experiment': (
            'batch_rxbkg_state1_mech1/'
            'net_newsec_var_seed'
        ),
        'processor': 'process_fullsim_psd.py',
        'processor_params': {
            'pop_names': POPS_USED,
            'psd_win_len': 1,
            'psd_win_overlap': 0.5,
            'psd_fmin': 0,
            'psd_fmax': 50,
            'psd_average': 'median',
            'plot_dpi': 300
        },
        'batch_param_overrides': {
            'seed_main': SEED_VALUES
        },
        'experiment_overrides': {},
        'batch_run': {}
    }
]


def _make_wmat_multipliers(wmult_variant):
    """Expand one named weight variant into NetPyNE multiplier records."""
    return [
        {'pre': pre, 'post': post, 'mult': mult}
        for pre, post, mult in WMULT_VARIANTS[wmult_variant]
    ]


def _make_context(wmult_id):
    """Build the workflow context for one variant position."""
    wmult_variant = WMULT_VARIANT_KEYS[wmult_id]
    return {
        'wmult_id': wmult_id,
        'wmult_variant': wmult_variant,
        'wmat_multipliers': _make_wmat_multipliers(wmult_variant),
    }


def get_workflow_params():
    """Return all serializable workflow parameters."""
    return {
        'workflow_name': WORKFLOW_NAME,
        'max_iterations': MAX_ITERATIONS,
        'initial_context': deepcopy(INITIAL_CONTEXT),
        'wmult_variants': deepcopy(WMULT_VARIANTS),
        'wait_refresh_sec': WAIT_REFRESH_SEC,
        'wait_timeout_sec': WAIT_TIMEOUT_SEC,
        'retention': deepcopy(RETENTION),
        'ray_checkpoint_path': RAY_CHECKPOINT_PATH,
        'batch_run_defaults': deepcopy(BATCH_RUN_DEFAULTS),
        'stages': deepcopy(STAGES),
    }


def get_run_id(workflow_params):
    """Generate the default workflow result directory name."""
    wvars_text = '_'.join(workflow_params['wmult_variants'])

    ibkg_text = (f'{np.min(IBKG_DW_ADJ_VALUES):g}'
                 f'_{np.max(IBKG_DW_ADJ_VALUES):g}'
                 f'_{len(IBKG_DW_ADJ_VALUES):g}')

    return (
        f'{WORKFLOW_NAME}_{EXP_LABEL}'
        f'_wvars_{wvars_text}'
        f'_nseeds_{len(SEED_VALUES)}'
        f'_ibkg_{ibkg_text}'
        f'_tdw_{DW_T_LIMITS[0]}_{DW_T_LIMITS[1]}'
        f'_tfull_{FULLSIM_T_LIMITS[0]}_{FULLSIM_T_LIMITS[1]}'
    )


def get_stage_overrides(stage_name, iteration, iteration_context,
                        stage_results, history):
    """Resolve dynamic weights and compensation currents."""
    wmat_multipliers = iteration_context['wmat_multipliers']
    if stage_name == 'dw':
        return {
            'experiment_overrides': {
                'wmat_multipliers': wmat_multipliers
            }
        }
    if stage_name == 'fullsim':
        if 'dw' not in stage_results:
            raise ValueError('Fullsim stage requires the DW stage result')
        runtime_params = deepcopy(FULLSIM_RUNTIME_PARAMS)
        runtime_params['conn']['wmat_multipliers'] = wmat_multipliers
        runtime_params['inp']['ibkg_corrections'] = stage_results['dw']
        return {
            'experiment_overrides': {
                'runtime_params': runtime_params
            }
        }
    raise KeyError(f'Unknown workflow stage: {stage_name}')


def finish_iteration(iteration, iteration_context, stage_results, history):
    """Record one variant point and advance to the next variant."""
    if 'dw' not in stage_results or 'fullsim' not in stage_results:
        raise ValueError('Iteration requires DW and fullsim stage results')

    # Build the next context while allowing the final iteration to complete
    next_id = iteration_context['wmult_id'] + 1
    next_context = {'wmult_id': next_id}
    next_wmult_variant = None
    if next_id < len(WMULT_VARIANT_KEYS):
        next_context = _make_context(next_id)
        next_wmult_variant = next_context['wmult_variant']

    # Store compact PSD dimensions in the iteration summary
    psd_sizes = {
        name: int(size)
        for name, size in stage_results['fullsim'].sizes.items()
    }
    return {
        'result': {
            'wmult_id': iteration_context['wmult_id'],
            'wmult_variant': iteration_context['wmult_variant'],
            'wmat_multipliers': iteration_context['wmat_multipliers'],
            'ibkg_corrections': stage_results['dw'],
            'psd_sizes': psd_sizes,
            'next_wmult_variant': next_wmult_variant
        },
        'next_context': next_context,
        'stop_reason': None
    }
