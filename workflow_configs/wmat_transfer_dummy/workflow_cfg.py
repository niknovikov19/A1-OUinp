from copy import deepcopy


WORKFLOW_NAME = 'wmat_transfer_dummy'
MAX_ITERATIONS = 1
DW_T_LIMITS = [5, 15]
RR_T_LIMITS = [5, 7]

# These mounted batches are compatible fixtures, not one scientific iteration
FIXTURE_NOTICE = (
    'The mounted DW and RR batches use unmatched weight and current settings. '
    'This workflow validates plumbing and processing only.'
)
INITIAL_CONTEXT = {
    'scientific_use': False,
    'fixture_notice': FIXTURE_NOTICE,
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
RR_SOURCE = (
    'exp_results/batch_rxbkg_unconn_state1_mech1/'
    'net_inpsur_rr_osc_var_seed_pre_f_amp/'
    'exp_rr_osc_pre_post_L2_nseed_1_npre_5_nf_1_namp_1_'
    't_5.0_7.0_osc_t0_5000_ictrl_wmult_0.25_ee_0.5'
)

# Ordered fixture stages reuse the production workflow processors
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
        'name': 'rr',
        'experiment': (
            'batch_rxbkg_unconn_state1_mech1/'
            'net_inpsur_rr_osc_var_seed_pre_f_amp'
        ),
        'executor': 'link_existing_results.py',
        'executor_params': {
            'source_dir': RR_SOURCE,
            'linked_dirs': {
                'cfg': 'cfg',
                'rvec_xr': 'rvec_xr',
            },
            'output_dir': 'rvec_xr',
            'output_pattern': 'rvec_{job:05d}_*.nc',
        },
        'processor': 'process_rr.py',
        'processor_params': {
            'harmonics': [1, 2],
        },
        'batch_param_overrides': {
            'seed_main': [1000],
            'pop_pre': ['IT2', 'PV2', 'SOM2', 'VIP2', 'NGF2'],
            'osc_f': [5],
            'osc_amp': [15],
        },
        'experiment_overrides': {},
        'batch_run': {},
    },
]


def get_workflow_params():
    """Return all serializable dummy workflow parameters."""
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
    """Generate the default dummy workflow result directory name."""
    stages = {
        stage['name']: stage
        for stage in workflow_params['stages']
    }
    dw_params = stages['dw']['batch_param_overrides']
    rr_params = stages['rr']['batch_param_overrides']
    return (
        f'exp_wmat_transfer_dummy'
        f'_dw_nseed_{len(dw_params["seed_main"])}'
        f'_nibkg_{len(dw_params["ibkg_dw_adj"])}'
        f'_t_{DW_T_LIMITS[0]}_{DW_T_LIMITS[1]}'
        f'_rr_nseed_{len(rr_params["seed_main"])}'
        f'_npre_{len(rr_params["pop_pre"])}'
        f'_nf_{len(rr_params["osc_f"])}'
        f'_namp_{len(rr_params["osc_amp"])}'
        f'_t_{RR_T_LIMITS[0]}_{RR_T_LIMITS[1]}'
    )


def get_stage_overrides(stage_name, iteration, iteration_context,
                        stage_results, history):
    """Check fixture stage dependencies without altering source settings."""
    if stage_name == 'dw':
        return {}
    if stage_name == 'rr':
        if 'dw' not in stage_results:
            raise ValueError('Dummy RR stage requires the DW stage result')
        return {}
    raise KeyError(f'Unknown dummy workflow stage: {stage_name}')


def finish_iteration(iteration, iteration_context, stage_results, history):
    """Record smoke-test outputs and stop after one fixture iteration."""
    corrections = stage_results['dw']
    transfer_ds = stage_results['rr']
    transfer_sizes = {
        name: int(size)
        for name, size in transfer_ds.sizes.items()
    }
    return {
        'result': {
            'scientific_use': False,
            'fixture_notice': FIXTURE_NOTICE,
            'ibkg_corrections': corrections,
            'transfer_sizes': transfer_sizes,
        },
        'next_context': None,
        'stop_reason': 'Dummy linked-results smoke test completed',
    }
