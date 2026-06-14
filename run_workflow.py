import argparse
import hashlib
import os
from pathlib import Path
import shlex
import shutil

import pandas as pd
import xarray as xr

from load_module import load_module
from workflow_utils import (
    compare_resolved_params,
    expand_param_grid,
    hash_data,
    merge_batch_params,
    poll_job_records,
    read_json,
    sort_batchtools_files,
    validate_job_records,
    write_json_atomic,
)


DIR_REPO = Path(__file__).resolve().parent
DIR_EXP_CONFIGS = DIR_REPO / 'exp_configs'
DIR_WORKFLOW_CONFIGS = DIR_REPO / 'workflow_configs'
DIR_WORKFLOW_RESULTS = DIR_REPO / 'exp_results' / 'workflows'


def _load_batchtools():
    """Load BatchTools only when a stage is actually launched."""
    from batchtk.runtk import Template
    from batchtk.runtk.dispatchers import LocalDispatcher
    from netpyne.batchtools.search import search
    from netpyne.batchtools.submits import SlurmSubmit

    class LocalSlurmSubmit(SlurmSubmit):
        """Submit BatchTools payloads through local Slurm."""

        SUBMIT_TEMPLATE = Template(
            template='sbatch {output_dir}/{label}.sh',
            key_args={'output_dir', 'label'},
        )

        SCRIPT_TEMPLATE = Template(
            template="""\
#!/bin/bash
#SBATCH --job-name={label}
#SBATCH -t {realtime}
#SBATCH --nodes={nodes}
#SBATCH --ntasks-per-node={coresPerNode}
#SBATCH --cpus-per-task=1
#SBATCH --mem={mem}
#SBATCH --partition={partition}
#SBATCH -o {stdout}
#SBATCH -e {stderr}
#SBATCH --export=ALL
export JOBID=$SLURM_JOB_ID
{handles}
{env}
{custom}
cd {project_dir}
{command}
wait
""",
            key_args={
                'label', 'realtime', 'nodes', 'coresPerNode', 'mem',
                'partition', 'stdout', 'stderr', 'handles',
                'env', 'custom', 'project_dir', 'command',
            },
        )

    return search, LocalDispatcher, LocalSlurmSubmit


def _source_hash(fpath):
    """Hash a workflow configuration source file."""
    return hashlib.sha256(Path(fpath).read_bytes()).hexdigest()


def _prepare_run(cfg_mod, fpath_cfg, run_id):
    """Create or validate the immutable workflow run metadata."""
    params = cfg_mod.get_workflow_params()
    params['workflow_source_hash'] = _source_hash(fpath_cfg)
    workflow_name = params['workflow_name']
    dirpath_run = DIR_WORKFLOW_RESULTS / workflow_name / run_id
    dirpath_meta = dirpath_run / 'meta'
    fpath_resolved = dirpath_meta / 'resolved_params.json'

    # Load existing metadata
    if fpath_resolved.exists():
        saved = read_json(fpath_resolved)
        differences = compare_resolved_params(saved, params)
        # Prohibit changes in either parameters or workflow code
        if differences:
            details = '\n'.join(
                f"  {item['key']}: saved={item['saved']!r}, "
                f"current={item['current']!r}"
                for item in differences
            )
            raise ValueError(
                f'Run ID {run_id!r} has resolved parameter mismatches:\n'
                f'{details}'
            )
        return dirpath_run, params

    # Create metadata
    dirpath_meta.mkdir(parents=True, exist_ok=True)
    shutil.copy2(fpath_cfg, dirpath_meta / 'workflow_cfg.py')
    write_json_atomic(fpath_resolved, params)   # defined in workflow_cfg.py
    write_json_atomic(dirpath_meta / 'state.json', {
        'status': 'initialized',
        'completed_iterations': [],
    })
    return dirpath_run, params


def _get_experiment_paths(experiment):
    """Resolve experiment config paths and BatchTools label fields."""
    dirpath_exp = DIR_EXP_CONFIGS / experiment
    if '/' in experiment:
        exp_subdir, exp_name = experiment.rsplit('/', 1)
    else:
        exp_subdir, exp_name = None, experiment
    return {
        'dirpath': dirpath_exp,
        'batch_params': dirpath_exp / 'batch_params.py',
        'exp_cfg': dirpath_exp / 'exp_cfg.py',
        'subdir': exp_subdir,
        'name': exp_name,
    }


def _resolve_stage_spec(workflow_params, stage_name, iteration,
                        run_id, wmat_multipliers, ibkg_corrections=None):
    """Resolve one subordinate stage into a compact immutable specification."""
    # workflow_params come from workflow_cfg.py
    stage_cfg = workflow_params[f'{stage_name}_stage']
    exp_paths = _get_experiment_paths(stage_cfg['experiment'])
    batch_mod = load_module(exp_paths['batch_params'])
    default_params = batch_mod.get_batch_params()   # from batch.py
    params = merge_batch_params(
        default_params,
        stage_cfg.get('batch_param_overrides', {}),
    )

    # Merge workflow values with optional experiment-specific additions
    # Overrides are defined by workflow_cfg.py -> get_workflow_params()
    # Overrides are applied by exp_cfg.py -> apply_runtime_overrides()
    exp_overrides = dict(stage_cfg.get('experiment_overrides', {}))
    exp_overrides['wmat_multipliers'] = wmat_multipliers
    if ibkg_corrections is not None:
        exp_overrides['ibkg_corrections'] = ibkg_corrections

    batch_run = dict(workflow_params['batch_run_defaults'])
    batch_run.update(stage_cfg.get('batch_run', {}))
    spec = {
        'workflow_name': workflow_params['workflow_name'],
        'run_id': run_id,
        'iteration': iteration,
        'stage': stage_name,
        'experiment': stage_cfg['experiment'],
        'batch_params': params,   # from batch.py + stage overrides (workflow_cfg.py)
        'batch_param_overrides': stage_cfg.get(
            'batch_param_overrides',
            {},
        ),
        'experiment_overrides': exp_overrides,   # from workflow_cfg.py, used in exp_cfg.py
        'retention': workflow_params['retention'],
        'batch_run': batch_run,
        'result_subdir': 'sim_results',
    }
    spec['stage_spec_hash'] = hash_data(spec)
    return spec, exp_paths


def _prepare_stage_dirs(dirpath_stage):
    """Create the stable directories owned by one workflow stage."""
    for relpath in (
        'meta',
        'batchtools/scripts',
        'batchtools/logs',
        'batchtools/comm',
        'job_meta',
        'sim_results',
        'processed',
    ):
        (dirpath_stage / relpath).mkdir(parents=True, exist_ok=True)


def _build_slurm_config(stage_spec, exp_paths, fpath_runtime):
    """Build the BatchTools Slurm payload for one stage."""
    batch_run = stage_spec['batch_run']
    n_cores = batch_run['cores_per_node']
    n_tasks = batch_run['nodes'] * n_cores
    subdir_arg = ''
    if exp_paths['subdir'] is not None:
        subdir_arg = f' --subdir {shlex.quote(exp_paths["subdir"])}'
    runtime_arg = shlex.quote(fpath_runtime.as_posix())
    command = (
        f'srun --mpi=pmi2 -n {n_tasks} nrniv -python -mpi '
        f'run_exp.py --batch{subdir_arg} '
        f'--runtime_overrides {runtime_arg}'
    )
    return {
        'partition': batch_run['partition'],
        'realtime': batch_run['realtime'],
        'nodes': batch_run['nodes'],
        'coresPerNode': n_cores,
        'mem': f'{batch_run["mem_gb"]}G',
        'custom': '\n'.join([
            'source ~/.bashrc',
            'conda activate netpyne_batch_slurm',
            'export LD_LIBRARY_PATH=$CONDA_PREFIX/lib:$LD_LIBRARY_PATH',
            'export MKL_THREADING_LAYER=GNU',
        ]),
        'command': command,
    }


def _write_stage_metadata(dirpath_stage, stage_spec):
    """Write the compact stage specification before launching jobs."""
    fpath_spec = dirpath_stage / 'meta' / 'stage_spec.json'
    write_json_atomic(fpath_spec, stage_spec)
    return fpath_spec


def _stage_is_complete(dirpath_stage, stage_spec):
    """Check the completion manifest and all compact job records."""
    fpath_complete = dirpath_stage / 'meta' / 'stage_complete.json'
    if not fpath_complete.exists():
        return False
    complete_info = read_json(fpath_complete)
    if complete_info.get('stage_spec_hash') != stage_spec['stage_spec_hash']:
        return False

    expected = expand_param_grid(stage_spec['batch_params'])
    _, missing = validate_job_records(
        dirpath_stage,
        expected,
        list(stage_spec['batch_params']),
        stage_spec['stage_spec_hash'],
    )
    return not missing


def _run_stage(dirpath_stage, stage_spec, exp_paths, workflow_params):
    """Run, wait for, and organize one subordinate BatchTools batch."""
    _prepare_stage_dirs(dirpath_stage)
    fpath_runtime = _write_stage_metadata(dirpath_stage, stage_spec)
    if _stage_is_complete(dirpath_stage, stage_spec):
        print(f'Skipping complete stage: {dirpath_stage}', flush=True)
        return

    expected = expand_param_grid(stage_spec['batch_params'])
    slurm_config = _build_slurm_config(
        stage_spec,
        exp_paths,
        fpath_runtime,
    )
    ray_config = {
        'runtime_env': {
            'working_dir': '.',
            'excludes': [
                '**/*.pkl',
                '**/*.out',
                '/.git/',
                '**/__pycache__/',
                '/exp_results/',
                '/exp_logs_old/',
                '/OLD/',
            ],
        },
    }
    checkpoint_path = (
        DIR_REPO / workflow_params['ray_checkpoint_path']
    ).resolve()
    checkpoint_path.mkdir(parents=True, exist_ok=True)

    # Let output markers win over BatchTools communication failures
    search, dispatcher, submitter = _load_batchtools()
    search_error = None
    try:
        # Run the batch
        search(
            dispatcher_constructor=dispatcher,
            submit_constructor=submitter,
            label=exp_paths['name'],
            params=stage_spec['batch_params'],
            output_path=dirpath_stage.as_posix(),
            checkpoint_path=checkpoint_path.as_posix(),
            run_config=slurm_config,
            metric='done',
            mode='max',
            sample_interval=1,
            num_samples=1,
            max_concurrent=stage_spec['batch_run']['max_concurrent'],
            batch=True,
            ray_config=ray_config,
            algorithm='variant_generator',
            remote_dir=DIR_REPO.as_posix(),
            advanced_logging=False,
            attempt_restore=False
        )
    except Exception as exc:
        search_error = exc
        print(f'BatchTools returned an error: {exc!r}', flush=True)

    # Wait for results
    records = poll_job_records(
        dirpath_stage,
        expected,
        list(stage_spec['batch_params']),
        stage_spec['stage_spec_hash'],
        workflow_params['wait_refresh_sec'],
        workflow_params['wait_timeout_sec']
    )
    summary_file = DIR_REPO / f'{exp_paths["name"]}.csv'
    sort_batchtools_files(dirpath_stage, summary_file)
    write_json_atomic(dirpath_stage / 'meta' / 'stage_complete.json', {
        'status': 'complete',
        'stage_spec_hash': stage_spec['stage_spec_hash'],
        'job_count': len(records),
        'batchtools_error': repr(search_error) if search_error else None
    })


def _load_ibkg_corrections(fpath_csv):
    """Load required median background-current corrections."""
    table = pd.read_csv(fpath_csv).set_index('pop')
    if table['median_ibkg'].isna().any():
        missing = table.index[table['median_ibkg'].isna()].tolist()
        raise ValueError(f'Missing ibkg corrections for populations: {missing}')
    return table['median_ibkg'].astype(float).to_dict()


def _processing_is_complete(dirpath_stage, stage_hash):
    """Validate a processor manifest and all declared output files."""
    fpath_complete = dirpath_stage / 'meta' / 'processing_complete.json'
    if not fpath_complete.exists():
        return False
    info = read_json(fpath_complete)
    if info.get('stage_spec_hash') != stage_hash:
        return False
    outputs = info.get('outputs', [])
    return bool(outputs) and all(
        (dirpath_stage / relpath).is_file()
        for relpath in outputs
    )


def _process_dw(dirpath_stage, exp_paths):
    """Run or resume the DW result processor."""
    stage_spec = read_json(dirpath_stage / 'meta' / 'stage_spec.json')
    fpath_complete = dirpath_stage / 'meta' / 'processing_complete.json'
    fpath_csv = dirpath_stage / 'processed' / 'ibkg_intersections.csv'
    processing_complete = _processing_is_complete(
        dirpath_stage,
        stage_spec['stage_spec_hash'],
    )
    if processing_complete:
        return _load_ibkg_corrections(fpath_csv)

    processor = load_module(exp_paths['dirpath'] / 'explore_results.py')
    outputs = processor.process_stage(dirpath_stage)
    write_json_atomic(fpath_complete, {
        'status': 'complete',
        'stage_spec_hash': stage_spec['stage_spec_hash'],
        'outputs': outputs,
    })
    return _load_ibkg_corrections(fpath_csv)


def _process_rr(dirpath_stage, exp_paths, harmonics):
    """Run or resume the RR transfer processor."""
    stage_spec = read_json(dirpath_stage / 'meta' / 'stage_spec.json')
    fpath_complete = dirpath_stage / 'meta' / 'processing_complete.json'
    fpath_transfer = dirpath_stage / 'processed' / 'transfer_matrix.nc'
    processing_complete = _processing_is_complete(
        dirpath_stage,
        stage_spec['stage_spec_hash'],
    )
    if processing_complete:
        return xr.open_dataset(fpath_transfer).load()

    processor = load_module(exp_paths['dirpath'] / 'process_results.py')
    transfer_ds, outputs = processor.process_stage(
        dirpath_stage,
        harmonics=harmonics,
    )
    write_json_atomic(fpath_complete, {
        'status': 'complete',
        'stage_spec_hash': stage_spec['stage_spec_hash'],
        'outputs': outputs,
    })
    return transfer_ds


def _load_history(dirpath_run):
    """Load completed iteration summaries in numerical order."""
    history = []
    dirpath_iterations = dirpath_run / 'iterations'
    for fpath in sorted(dirpath_iterations.glob('iter_*/meta/iteration.json')):
        item = read_json(fpath)
        if item.get('status') != 'complete':
            break

        # Completed iterations remain resumable only while both stages validate
        dirpath_iter = fpath.parents[1]
        stages_valid = True
        for stage_name in ('dw', 'rr'):
            dirpath_stage = dirpath_iter / stage_name
            fpath_spec = dirpath_stage / 'meta' / 'stage_spec.json'
            if not fpath_spec.exists():
                stages_valid = False
                break
            stage_spec = read_json(fpath_spec)
            stages_valid = (
                _stage_is_complete(dirpath_stage, stage_spec) and
                _processing_is_complete(
                    dirpath_stage,
                    stage_spec['stage_spec_hash'],
                )
            )
            if not stages_valid:
                break
        if not stages_valid:
            break
        history.append(item)
    return history


def run_workflow(workflow_name, run_id):
    """Run or resume one configured iterative workflow."""
    # Prepare
    fpath_cfg = DIR_WORKFLOW_CONFIGS / workflow_name / 'workflow_cfg.py'
    cfg_mod = load_module(fpath_cfg)
    dirpath_run, params = _prepare_run(cfg_mod, fpath_cfg, run_id)
    history = _load_history(dirpath_run)
    if history and history[-1].get('stop_reason'):
        print(
            f"Workflow already stopped: {history[-1]['stop_reason']}",
            flush=True,
        )
        return

    wmat_multipliers = params['initial_wmat_multipliers']
    if history:
        wmat_multipliers = history[-1].get(
            'next_wmat_multipliers',
            history[-1]['wmat_multipliers'],
        )

    # Continue at the first iteration without a completed summary
    for iteration in range(len(history), params['max_iterations']):
        dirpath_iter = (
            dirpath_run / 'iterations' / f'iter_{iteration:03d}'
        )
        (dirpath_iter / 'meta').mkdir(parents=True, exist_ok=True)
        print(
            f'Iteration {iteration}: weights={wmat_multipliers}',
            flush=True,
        )

        dw_spec, dw_paths = _resolve_stage_spec(
            params,
            'dw',
            iteration,
            run_id,
            wmat_multipliers,
        )
        dirpath_dw = dirpath_iter / 'dw'
        _run_stage(dirpath_dw, dw_spec, dw_paths, params)
        ibkg_corrections = _process_dw(dirpath_dw, dw_paths)

        rr_spec, rr_paths = _resolve_stage_spec(
            params,
            'rr',
            iteration,
            run_id,
            wmat_multipliers,
            ibkg_corrections=ibkg_corrections,
        )
        dirpath_rr = dirpath_iter / 'rr'
        _run_stage(dirpath_rr, rr_spec, rr_paths, params)
        transfer_ds = _process_rr(
            dirpath_rr,
            rr_paths,
            params['transfer_harmonics'],
        )

        # Delegate scientific weight selection to the workflow config
        callback_history = history + [{
            'iteration': iteration,
            'wmat_multipliers': wmat_multipliers,
            'ibkg_corrections': ibkg_corrections,
        }]
        update = cfg_mod.get_next_wmat(
            iteration,
            transfer_ds,
            callback_history,
        )
        next_wmat = update.get('wmat_multipliers')
        stop_reason = update.get('stop_reason')
        iteration_info = {
            'status': 'complete',
            'iteration': iteration,
            'wmat_multipliers': wmat_multipliers,
            'ibkg_corrections': ibkg_corrections,
            'next_wmat_multipliers': next_wmat,
            'stop_reason': stop_reason,
            'dw_stage_spec_hash': dw_spec['stage_spec_hash'],
            'rr_stage_spec_hash': rr_spec['stage_spec_hash'],
        }
        write_json_atomic(
            dirpath_iter / 'meta' / 'iteration.json',
            iteration_info,
        )
        history.append(iteration_info)
        write_json_atomic(dirpath_run / 'meta' / 'state.json', {
            'status': 'stopped' if stop_reason else 'running',
            'completed_iterations': [
                item['iteration']
                for item in history
            ],
            'stop_reason': stop_reason,
        })
        if stop_reason:
            print(f'Workflow stopped: {stop_reason}', flush=True)
            return
        if next_wmat is None:
            raise ValueError('get_next_wmat() returned no next weights')
        wmat_multipliers = next_wmat

    write_json_atomic(dirpath_run / 'meta' / 'state.json', {
        'status': 'complete',
        'completed_iterations': [
            item['iteration']
            for item in history
        ],
        'stop_reason': 'Maximum iteration count reached',
    })


def main():
    """Parse arguments and run a workflow."""
    parser = argparse.ArgumentParser(description='Run iterative workflow.')
    parser.add_argument(
        '--workflow',
        default=os.environ.get('A1_WORKFLOW_NAME', 'wmat_transfer'),
    )
    parser.add_argument(
        '--run-id',
        default=os.environ.get('A1_WORKFLOW_RUN_ID'),
        required=os.environ.get('A1_WORKFLOW_RUN_ID') is None,
    )
    args = parser.parse_args()
    run_workflow(args.workflow, args.run_id)


if __name__ == '__main__':
    main()
