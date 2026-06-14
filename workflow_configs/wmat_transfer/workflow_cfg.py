from copy import deepcopy


WORKFLOW_NAME = 'wmat_transfer'
MAX_ITERATIONS = 1

# Initial recurrent connection-weight adjustments
INITIAL_WMAT_MULTIPLIERS = [
    {'pre': 'IT2', 'post': 'IT2', 'mult': 2},
]

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

# BatchTools runtime shared by both subordinate stages
BATCH_RUN_DEFAULTS = {
    'partition': 'cpu.q',
    'realtime': '7:00:00',
    'nodes': 1,
    'cores_per_node': 60,
    'mem_gb': 256,
    'max_concurrent': 6,
}

# Background-current compensation batch
DW_STAGE = {
    'experiment': (
        'batch_rxbkg_unconn_state1_mech1/'
        'net_inpsur_dw_var_seed_ibkg'
    ),
    # Replace only named grid axes; omitted axes keep experiment defaults
    'batch_param_overrides': {},
    # Override existing single-job cfg fields after apply_exp_cfg()
    'experiment_overrides': {},
    'batch_run': {},
}

# Oscillatory transfer batch
RR_STAGE = {
    'experiment': (
        'batch_rxbkg_unconn_state1_mech1/'
        'net_inpsur_rr_osc_var_seed_pre_f_amp'
    ),
    # Replace only named grid axes; omitted axes keep experiment defaults
    'batch_param_overrides': {},
    # Override existing single-job cfg fields after apply_exp_cfg()
    'experiment_overrides': {},
    'batch_run': {},
}

TRANSFER_HARMONICS = [1, 2]


def get_workflow_params():
    """Return all serializable workflow parameters."""
    return {
        'workflow_name': WORKFLOW_NAME,
        'max_iterations': MAX_ITERATIONS,
        'initial_wmat_multipliers': deepcopy(INITIAL_WMAT_MULTIPLIERS),
        'wait_refresh_sec': WAIT_REFRESH_SEC,
        'wait_timeout_sec': WAIT_TIMEOUT_SEC,
        'retention': deepcopy(RETENTION),
        'ray_checkpoint_path': RAY_CHECKPOINT_PATH,
        'batch_run_defaults': deepcopy(BATCH_RUN_DEFAULTS),
        'dw_stage': deepcopy(DW_STAGE),
        'rr_stage': deepcopy(RR_STAGE),
        'transfer_harmonics': list(TRANSFER_HARMONICS),
    }


def get_next_wmat(iteration, transfer_ds, history):
    """Choose the next weights and optionally stop the outer loop."""
    # Replace this default with the scientific update rule
    return {
        'wmat_multipliers': history[-1]['wmat_multipliers'],
        'stop_reason': 'Default workflow configuration runs one iteration',
    }
