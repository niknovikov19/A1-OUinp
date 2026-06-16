from copy import deepcopy


WORKFLOW_NAME = 'ibkg_adj__fullsim__var_wmult_1d'
POPS_USED = ['IT2', 'PV2', 'SOM2', 'VIP2', 'NGF2']
WMULT_CONNS = [('IT2', 'IT2')]
WMULT_SWEEP_VALS = [1, 1.5, 2, 3]
MAX_ITERATIONS = len(WMULT_SWEEP_VALS)
DW_T_LIMITS = [5, 15]
FULLSIM_T_LIMITS = [5, 10]
SEED_VALUES = [1000, 1001, 1002]
IBKG_DW_ADJ_VALUES = [
    -0.1,
    -0.0778,
    -0.0556,
    -0.0333,
    -0.0111,
    0.0111,
    0.0333,
    0.0556,
    0.0778,
    0.1,
]
FADER_PTS = [
    (0, 0),
    (3000, 0),
    (5000, 1),
    (10000, 1),
]
FULLSIM_RUNTIME_PARAMS = {
    'time': {
        'duration': 10000,
        't0_calc': 5000,
    },
    'pops_used': POPS_USED,
    'conn': {
        'fader_pts': FADER_PTS,
    },
    'inp': {
        'add_pulses': False,
    },
    'rec': {
        'traces': False,
        'lfp': False,
    },
    'proc': {
        'rate_t_limits': FULLSIM_T_LIMITS,
        'rate_dt_bin': 0.005,
        'rate_tau_smooth': 0.02,
    },
    'out': {
        'plot_traces': False,
        'plot_csd': False,
        'plot_rate_dynamics': False,
        'save_rate_xr': True,
    },
}

# The context identifies one point on the one-dimensional weight sweep
INITIAL_CONTEXT = {
    'wmult_idx': 0,
    'wmult_val': WMULT_SWEEP_VALS[0],
    'wmat_multipliers': [
        {'pre': pre, 'post': post, 'mult': WMULT_SWEEP_VALS[0]}
        for pre, post in WMULT_CONNS
    ],
}

# Poll compact job records after BatchTools returns
WAIT_REFRESH_SEC = 30
WAIT_TIMEOUT_SEC = None

# Keep compact simulation inputs and diagnostics only
RETENTION = {
    'keep_cfg': True,
    'keep_netparams': False,
    'keep_pkl': False,
}

# Shared Ray state stays outside workflow result directories
RAY_CHECKPOINT_PATH = 'exp_logs/workflows/ray'

# BatchTools runtime shared by subordinate stages
BATCH_RUN_DEFAULTS = {
    'partition': 'cpu.q',
    'realtime': '7:00:00',
    'nodes': 1,
    'cores_per_node': 60,
    'mem_gb': 256,
    'max_concurrent': 6,
}

# Ordered subordinate batches use workflow-local processors
STAGES = [
    {
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
            'required_pops': POPS_USED,
        },
        'batch_param_overrides': {
            'seed_main': SEED_VALUES,
            'ibkg_dw_adj': IBKG_DW_ADJ_VALUES,
        },
        'experiment_overrides': {
            'duration': 15000,
            't0_calc': 5000,
        },
        'batch_run': {},
    },
    {
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
            'plot_dpi': 200,
        },
        'batch_param_overrides': {
            'seed_main': SEED_VALUES,
        },
        'experiment_overrides': {},
        'batch_run': {},
    },
]


def _make_wmat_multipliers(wmult_val):
    """Apply one scalar multiplier to all configured connections."""
    return [
        {'pre': pre, 'post': post, 'mult': wmult_val}
        for pre, post in WMULT_CONNS
    ]


def _make_context(wmult_idx):
    """Build the workflow context for one sweep position."""
    wmult_val = WMULT_SWEEP_VALS[wmult_idx]
    return {
        'wmult_idx': wmult_idx,
        'wmult_val': wmult_val,
        'wmat_multipliers': _make_wmat_multipliers(wmult_val),
    }


def get_workflow_params():
    """Return all serializable workflow parameters."""
    return {
        'workflow_name': WORKFLOW_NAME,
        'max_iterations': MAX_ITERATIONS,
        'initial_context': deepcopy(INITIAL_CONTEXT),
        'wmult_conns': deepcopy(WMULT_CONNS),
        'wmult_sweep_vals': deepcopy(WMULT_SWEEP_VALS),
        'wait_refresh_sec': WAIT_REFRESH_SEC,
        'wait_timeout_sec': WAIT_TIMEOUT_SEC,
        'retention': deepcopy(RETENTION),
        'ray_checkpoint_path': RAY_CHECKPOINT_PATH,
        'batch_run_defaults': deepcopy(BATCH_RUN_DEFAULTS),
        'stages': deepcopy(STAGES),
    }


def get_run_id(workflow_params):
    """Generate the default workflow result directory name."""
    conn_text = '_'.join(
        f'{pre}_{post}'
        for pre, post in workflow_params['wmult_conns']
    )
    vals_text = '_'.join(
        f'{value:g}'
        for value in workflow_params['wmult_sweep_vals']
    )
    return (
        f'exp_{WORKFLOW_NAME}'
        f'_L2_wconn_{conn_text}'
        f'_wvals_{vals_text}'
        f'_dw_nseed_{len(SEED_VALUES)}'
        f'_nibkg_{len(IBKG_DW_ADJ_VALUES)}'
        f'_t_{DW_T_LIMITS[0]}_{DW_T_LIMITS[1]}'
        f'_fullsim_nseed_{len(SEED_VALUES)}'
        f'_t_{FULLSIM_T_LIMITS[0]}_{FULLSIM_T_LIMITS[1]}'
    )


def get_stage_overrides(stage_name, iteration, iteration_context,
                        stage_results, history):
    """Resolve dynamic weights and compensation currents."""
    wmat_multipliers = iteration_context['wmat_multipliers']
    if stage_name == 'dw':
        return {
            'experiment_overrides': {
                'wmat_multipliers': wmat_multipliers,
            },
        }
    if stage_name == 'fullsim':
        if 'dw' not in stage_results:
            raise ValueError('Fullsim stage requires the DW stage result')
        runtime_params = deepcopy(FULLSIM_RUNTIME_PARAMS)
        runtime_params['conn']['wmat_multipliers'] = wmat_multipliers
        runtime_params['inp']['ibkg_corrections'] = stage_results['dw']
        return {
            'experiment_overrides': {
                'runtime_params': runtime_params,
            },
        }
    raise KeyError(f'Unknown workflow stage: {stage_name}')


def finish_iteration(iteration, iteration_context, stage_results, history):
    """Record one sweep point and advance to the next multiplier."""
    if 'dw' not in stage_results or 'fullsim' not in stage_results:
        raise ValueError('Iteration requires DW and fullsim stage results')

    # Build the next context while allowing the final iteration to complete
    next_idx = iteration_context['wmult_idx'] + 1
    next_context = {'wmult_idx': next_idx}
    next_wmult_val = None
    if next_idx < len(WMULT_SWEEP_VALS):
        next_context = _make_context(next_idx)
        next_wmult_val = next_context['wmult_val']

    psd_sizes = {
        name: int(size)
        for name, size in stage_results['fullsim'].sizes.items()
    }
    return {
        'result': {
            'wmult_idx': iteration_context['wmult_idx'],
            'wmult_val': iteration_context['wmult_val'],
            'wmat_multipliers': iteration_context['wmat_multipliers'],
            'ibkg_corrections': stage_results['dw'],
            'psd_sizes': psd_sizes,
            'next_wmult_val': next_wmult_val,
        },
        'next_context': next_context,
        'stop_reason': None,
    }
