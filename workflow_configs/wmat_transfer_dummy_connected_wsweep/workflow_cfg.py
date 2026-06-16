from copy import deepcopy


WORKFLOW_NAME = 'wmat_transfer_dummy_connected_wsweep'
MAX_ITERATIONS = 3
WEIGHT_UPDATE_FACTOR = 1.5
DW_T_LIMITS = [5, 15]
CONNECTED_T_LIMITS = [2, 3]

# These mounted batches are reused fixtures, not scientific sweep outputs
FIXTURE_NOTICE = (
    'Every iteration reuses unmatched mounted DW and connected-model data. '
    'Weight updates validate workflow plumbing and PSD metadata only.'
)
INITIAL_CONTEXT = {
    'wmat_multipliers': [
        {'pre': 'IT2', 'post': 'IT2', 'mult': 2},
    ],
}

# Local fixture publication should complete immediately
WAIT_REFRESH_SEC = 1
WAIT_TIMEOUT_SEC = 60

# Retention values remain part of the normal stage specification
RETENTION = {
    'keep_cfg': True,
    'keep_netparams': False,
    'keep_pkl': False,
}

# These defaults are unused by linked-result executor stages
RAY_CHECKPOINT_PATH = 'exp_logs/workflows/ray'
BATCH_RUN_DEFAULTS = {
    'partition': 'unused',
    'realtime': '0:01:00',
    'nodes': 1,
    'cores_per_node': 1,
    'mem_gb': 1,
    'max_concurrent': 1,
}

DW_SOURCE = (
    'exp_results/batch_rxbkg_unconn_state1_mech1/'
    'net_inpsur_dw_var_seed_ibkg/'
    'exp_dw_adj_L2_ee_2_nseed_1_ibkg_-0.1_0.1_10_'
    't_5.0_15.0_ictrl_wmult_0.25_ee_0.5'
)
CONNECTED_SOURCE = (
    'exp_results/batch_rxbkg_state1_mech1/'
    'net_newsec_ee_fade_var_seed/'
    'exp_L2_ee_fade_nseed_2_t_2.0_3.0_wmult_0.25_ee_0.5'
)

# Ordered fixture stages use workflow-local executors and processors
STAGES = [
    {
        'name': 'dw',
        'experiment': (
            'batch_rxbkg_unconn_state1_mech1/'
            'net_inpsur_dw_var_seed_ibkg'
        ),
        'executor': 'link_existing_results.py',
        'executor_params': {
            'source_dir': DW_SOURCE,
            'linked_dirs': {
                'cfg': 'cfg',
                'results': 'results',
            },
            'output_dir': 'results',
            'output_pattern': 'result_{job:05d}_*.json',
        },
        'processor': 'process_dw.py',
        'processor_params': {
            'target_rates_path': (
                'exp_configs/batch_rxbkg_unconn_state1_mech1/'
                'net_inpsur_dw_var_seed_ibkg/target_state_1.csv'
            ),
            'required_pops': ['IT2', 'PV2', 'SOM2', 'VIP2', 'NGF2'],
        },
        'batch_param_overrides': {
            'seed_main': [1000],
            'ibkg_dw_adj': [
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
            ],
        },
        'experiment_overrides': {},
        'batch_run': {},
    },
    {
        'name': 'connected',
        'experiment': (
            'batch_rxbkg_state1_mech1/'
            'net_newsec_ee_fade_var_seed'
        ),
        'executor': 'link_existing_results.py',
        'executor_params': {
            'source_dir': CONNECTED_SOURCE,
            'linked_dirs': {
                'cfg': 'cfg',
                'pkl': 'pkl',
            },
            'output_dir': 'pkl',
            'output_pattern': 'data_{job:05d}_*.pkl',
        },
        'processor': 'process_connected_psd.py',
        'processor_params': {
            'pop_names': ['IT2', 'PV2', 'SOM2', 'VIP2', 'NGF2'],
            't_limits': CONNECTED_T_LIMITS,
            'dt_bin': 0.005,
            'tau_smooth': 0.05,
            'psd_win_len': 1,
            'psd_win_overlap': 0.5,
            'psd_fmin': 0,
            'psd_fmax': 50,
            'psd_average': 'median',
            'plot_dpi': 200,
        },
        'batch_param_overrides': {
            'seed_main': [1000, 1001],
        },
        'experiment_overrides': {},
        'batch_run': {},
    },
]


def get_workflow_params():
    """Return all serializable connected sweep parameters."""
    return {
        'workflow_name': WORKFLOW_NAME,
        'max_iterations': MAX_ITERATIONS,
        'initial_context': deepcopy(INITIAL_CONTEXT),
        'weight_update_factor': WEIGHT_UPDATE_FACTOR,
        'wait_refresh_sec': WAIT_REFRESH_SEC,
        'wait_timeout_sec': WAIT_TIMEOUT_SEC,
        'retention': deepcopy(RETENTION),
        'ray_checkpoint_path': RAY_CHECKPOINT_PATH,
        'batch_run_defaults': deepcopy(BATCH_RUN_DEFAULTS),
        'stages': deepcopy(STAGES),
    }


def get_run_id(workflow_params):
    """Generate the default connected sweep result directory name."""
    stages = {
        stage['name']: stage
        for stage in workflow_params['stages']
    }
    dw_params = stages['dw']['batch_param_overrides']
    connected_params = stages['connected']['batch_param_overrides']
    return (
        f'exp_wmat_transfer_dummy_connected_wsweep'
        f'_niter_{workflow_params["max_iterations"]}'
        f'_dw_nseed_{len(dw_params["seed_main"])}'
        f'_nibkg_{len(dw_params["ibkg_dw_adj"])}'
        f'_t_{DW_T_LIMITS[0]}_{DW_T_LIMITS[1]}'
        f'_L2_ee_fade_nseed_{len(connected_params["seed_main"])}'
        f'_t_{CONNECTED_T_LIMITS[0]}_{CONNECTED_T_LIMITS[1]}'
    )


def get_stage_overrides(stage_name, iteration, iteration_context,
                        stage_results, history):
    """Attach current dummy weights while preserving fixture settings."""
    wmat_multipliers = iteration_context['wmat_multipliers']
    if stage_name == 'dw':
        return {
            'experiment_overrides': {
                'wmat_multipliers': wmat_multipliers,
            },
        }
    if stage_name == 'connected':
        if 'dw' not in stage_results:
            raise ValueError('Connected stage requires the DW stage result')
        return {
            'experiment_overrides': {
                'wmat_multipliers': wmat_multipliers,
            },
        }
    raise KeyError(f'Unknown connected sweep stage: {stage_name}')


def _scale_wmat_multipliers(wmat_multipliers, factor):
    """Scale every configured dummy weight multiplier."""
    scaled = deepcopy(wmat_multipliers)
    for item in scaled:
        item['mult'] *= factor
    return scaled


def finish_iteration(iteration, iteration_context, stage_results, history):
    """Record one connected sweep step and return the next context."""
    current_wmat = iteration_context['wmat_multipliers']
    next_wmat = _scale_wmat_multipliers(
        current_wmat,
        WEIGHT_UPDATE_FACTOR,
    )
    psd_xr = stage_results['connected']
    psd_sizes = {
        name: int(size)
        for name, size in psd_xr.sizes.items()
    }
    return {
        'result': {
            'scientific_use': False,
            'fixture_notice': FIXTURE_NOTICE,
            'current_wmat_multipliers': current_wmat,
            'next_wmat_multipliers': next_wmat,
            'ibkg_corrections': stage_results['dw'],
            'psd_sizes': psd_sizes,
        },
        'next_context': {
            'wmat_multipliers': next_wmat,
        },
        'stop_reason': None,
    }
