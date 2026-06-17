from copy import deepcopy

import numpy as np


WORKFLOW_NAME = 'ibkg_adj__fullsim__var_wmult_1d'

POPS_USED = ['IT2', 'PV2', 'SOM2', 'VIP2', 'NGF2']

#WMULT_CONNS = [('IT2', 'IT2')]
WMULT_CONNS = [('IT2', 'IT2'), ('IT2', 'NGF2')]
#WMULT_SWEEP_VALS = [1, 1.5, 2, 3]
WMULT_SWEEP_VALS = [5, 10, 15, 30]

EXP_LABEL = 'L2_wmult_ee_engf'

MAX_ITERATIONS = len(WMULT_SWEEP_VALS)

# Stage 1 duration
DW_DURATION = 15000
DW_T0_CALC = 5000

# Stage 2 duration
FULLSIM_DURATION = 15000
FULLSIM_T0_CALC = 5000

DW_T_LIMITS = [DW_T0_CALC / 1000, DW_DURATION / 1000]
FULLSIM_T_LIMITS = [DW_T0_CALC / 1000, FULLSIM_DURATION / 1000]

# Batch params
#SEED_VALUES = [1000]
SEED_VALUES = (1000 + np.arange(3)).tolist()
IBKG_DW_ADJ_VALUES = np.linspace(-0.25, 0.1, 10).tolist()

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

# The context identifies one point on the one-dimensional weight sweep
INITIAL_CONTEXT = {
    'wmult_id': 0,
    'wmult_val': WMULT_SWEEP_VALS[0],
    'wmat_multipliers': [
        {'pre': pre, 'post': post, 'mult': WMULT_SWEEP_VALS[0]}
        for pre, post in WMULT_CONNS
    ]
}

# Poll compact job records after BatchTools returns
WAIT_REFRESH_SEC = 10
WAIT_TIMEOUT_SEC = None

# Whih results to store
RETENTION = {
    'keep_cfg': 1,
    'keep_netparams': 1,
    'keep_pkl': 0
}

# Shared ray fodler
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
        # Sweep over ibkg range to achieve target r0 for given wmult
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
        # Connected model run with given wmult and ibkg from dw stage
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


def _make_wmat_multipliers(wmult_val):
    """Apply one scalar multiplier to all configured connections."""
    return [
        {'pre': pre, 'post': post, 'mult': wmult_val}
        for pre, post in WMULT_CONNS
    ]


def _make_context(wmult_id):
    """Build the workflow context for one sweep position."""
    wmult_val = WMULT_SWEEP_VALS[wmult_id]
    return {
        'wmult_id': wmult_id,
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
    #conn_text = '_'.join(
    #    f'{pre}_{post}'
    #    for pre, post in workflow_params['wmult_conns']
    #)

    wvals = workflow_params['wmult_sweep_vals']
    wvals_text = f'{np.min(wvals):g}_{np.max(wvals):g}_{len(wvals):g}'

    ibkg_text = (f'{np.min(IBKG_DW_ADJ_VALUES):g}'
                 f'_{np.max(IBKG_DW_ADJ_VALUES):g}'
                 f'_{len(IBKG_DW_ADJ_VALUES):g}')
    #'_'.join([
    #    np.min(IBKG_DW_ADJ_VALUES), np.max(IBKG_DW_ADJ_VALUES),
    #    len(IBKG_DW_ADJ_VALUES)
    #])

    return (
        #f'{WORKFLOW_NAME}'
        f'{EXP_LABEL}'
        #f'_L2_wconn_{conn_text}'
        f'_wvals_{wvals_text}'
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
    """Record one sweep point and advance to the next multiplier."""
    if 'dw' not in stage_results or 'fullsim' not in stage_results:
        raise ValueError('Iteration requires DW and fullsim stage results')

    # Build the next context while allowing the final iteration to complete
    next_id = iteration_context['wmult_id'] + 1
    next_context = {'wmult_id': next_id}
    next_wmult_val = None
    if next_id < len(WMULT_SWEEP_VALS):
        next_context = _make_context(next_id)
        next_wmult_val = next_context['wmult_val']

    psd_sizes = {
        name: int(size)
        for name, size in stage_results['fullsim'].sizes.items()
    }
    return {
        'result': {
            'wmult_id': iteration_context['wmult_id'],
            'wmult_val': iteration_context['wmult_val'],
            'wmat_multipliers': iteration_context['wmat_multipliers'],
            'ibkg_corrections': stage_results['dw'],
            'psd_sizes': psd_sizes,
            'next_wmult_val': next_wmult_val
        },
        'next_context': next_context,
        'stop_reason': None
    }
