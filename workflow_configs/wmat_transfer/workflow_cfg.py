from copy import deepcopy


WORKFLOW_NAME = 'wmat_transfer'
MAX_ITERATIONS = 1

# Initial recurrent connection-weight adjustments
INITIAL_CONTEXT = {
    'wmat_multipliers': [
        {'pre': 'IT2', 'post': 'IT2', 'mult': 2},
    ],
}

# Result polling after BatchTools returns
WAIT_REFRESH_SEC = 30
WAIT_TIMEOUT_SEC = None

# Workflow-only simulation output retention
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

# Ordered subordinate batches and workflow-local processors
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
            'required_pops': ['IT2', 'PV2', 'SOM2', 'VIP2', 'NGF2'],
        },
        'batch_param_overrides': {},
        'experiment_overrides': {},
        'batch_run': {},
    },
    {
        'name': 'rr',
        'experiment': (
            'batch_rxbkg_unconn_state1_mech1/'
            'net_inpsur_rr_osc_var_seed_pre_f_amp'
        ),
        'processor': 'process_rr.py',
        'processor_params': {
            'harmonics': [1, 2],
        },
        'batch_param_overrides': {},
        'experiment_overrides': {},
        'batch_run': {},
    },
]


def get_workflow_params():
    """Return all serializable workflow parameters."""
    return {
        'workflow_name': WORKFLOW_NAME,
        'max_iterations': MAX_ITERATIONS,
        'initial_context': deepcopy(INITIAL_CONTEXT),
        'wait_refresh_sec': WAIT_REFRESH_SEC,
        'wait_timeout_sec': WAIT_TIMEOUT_SEC,
        'retention': deepcopy(RETENTION),
        'ray_checkpoint_path': RAY_CHECKPOINT_PATH,
        'batch_run_defaults': deepcopy(BATCH_RUN_DEFAULTS),
        'stages': deepcopy(STAGES),
    }


def get_run_id(workflow_params):
    """Generate the default workflow result directory name."""
    run_id = (
        f'exp_wmat_transfer_niter_'
        f'{workflow_params["max_iterations"]}'
    )

    # Append every initial weight adjustment in stable list order
    weights = workflow_params['initial_context']['wmat_multipliers']
    for item in weights:
        run_id += (
            f'_w_{item["pre"]}_{item["post"]}_{item["mult"]}'
        )
    return run_id


def get_stage_overrides(stage_name, iteration, iteration_context,
                        stage_results, history):
    """Resolve dynamic overrides from prior stages and iterations."""
    wmat_multipliers = iteration_context['wmat_multipliers']
    if stage_name == 'dw':
        return {
            'experiment_overrides': {
                'wmat_multipliers': wmat_multipliers,
            },
        }
    if stage_name == 'rr':
        if 'dw' not in stage_results:
            raise ValueError('RR stage requires the DW stage result')
        return {
            'experiment_overrides': {
                'wmat_multipliers': wmat_multipliers,
                'ibkg_corrections': stage_results['dw'],
            },
        }
    raise KeyError(f'Unknown workflow stage: {stage_name}')


def get_next_wmat(iteration, transfer_ds, history):
    """Choose the next weights and optionally stop the outer loop."""
    # Replace this default with the scientific update rule
    return {
        'wmat_multipliers': history[-1]['context']['wmat_multipliers'],
        'stop_reason': 'Default workflow configuration runs one iteration',
    }


def finish_iteration(iteration, iteration_context, stage_results, history):
    """Finish one iteration and choose its continuation context."""
    if 'dw' not in stage_results or 'rr' not in stage_results:
        raise ValueError('Iteration requires both DW and RR stage results')

    # Include current context in the scientific update history
    update_history = history + [{
        'iteration': iteration,
        'context': iteration_context,
        'result': {
            'ibkg_corrections': stage_results['dw'],
        },
    }]
    update = get_next_wmat(
        iteration,
        stage_results['rr'],
        update_history,
    )
    next_wmat = update.get('wmat_multipliers')
    stop_reason = update.get('stop_reason')
    if next_wmat is None and stop_reason is None:
        raise ValueError('get_next_wmat() returned no weights or stop reason')

    next_context = None
    if stop_reason is None:
        next_context = {
            'wmat_multipliers': next_wmat,
        }
    return {
        'result': {
            'ibkg_corrections': stage_results['dw'],
            'next_wmat_multipliers': next_wmat,
        },
        'next_context': next_context,
        'stop_reason': stop_reason,
    }
