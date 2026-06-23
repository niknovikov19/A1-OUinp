import argparse
import hashlib
import os
from pathlib import Path
import shlex
import shutil

from load_module import load_module
from workflow_utils import (
    collect_batchtools_artifacts,
    compare_resolved_params,
    expand_param_grid,
    file_fingerprint,
    hash_data,
    merge_batch_params,
    normalize_json,
    poll_job_records,
    read_json,
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


def _shutdown_ray_if_initialized():
    """Shutdown an existing Ray session when Ray is available."""
    try:
        import ray
    except ImportError:
        return
    if getattr(ray, 'is_initialized', lambda: False)():
        ray.shutdown()


def _is_ray_reinit_error(exc):
    """Detect the prelaunch Ray double-init error from BatchTools."""
    message = str(exc)
    return (
        'ray.init twice' in message or
        'ignore_reinit_error=True' in message
    )


def _get_workflow_source_hashes(dirpath_workflow):
    """Hash all workflow Python sources in the configuration folder."""
    return {
        fpath.name: hashlib.sha256(fpath.read_bytes()).hexdigest()
        for fpath in sorted(Path(dirpath_workflow).glob('*.py'))
    }


def _validate_run_id(run_id):
    """Validate one workflow result-directory name."""
    if not isinstance(run_id, str) or not run_id.strip():
        raise ValueError('Workflow run ID should be a non-empty string')
    if run_id in {'.', '..'} or '/' in run_id or '\\' in run_id:
        raise ValueError(
            f'Workflow run ID should be one directory name: {run_id!r}'
        )
    return run_id


def _resolve_run_id(cfg_mod, workflow_params, run_id=None):
    """Resolve CLI, environment, or workflow-configured run ID."""
    resolved = run_id
    if resolved is None:
        resolved = os.environ.get('A1_WORKFLOW_RUN_ID')
    if resolved is None:
        resolved = cfg_mod.get_run_id(workflow_params)
    return _validate_run_id(resolved)


def _prepare_run(cfg_mod, dirpath_workflow, run_id,
                 workflow_params=None):
    """Create or validate immutable workflow run metadata."""
    params = workflow_params
    if params is None:
        params = cfg_mod.get_workflow_params()
    params['workflow_source_hashes'] = _get_workflow_source_hashes(
        dirpath_workflow
    )
    params = normalize_json(params)
    workflow_name = params['workflow_name']
    dirpath_run = DIR_WORKFLOW_RESULTS / workflow_name / run_id
    dirpath_meta = dirpath_run / 'meta'
    fpath_resolved = dirpath_meta / 'resolved_params.json'

    # Prohibit changes in parameters or any workflow-local Python source
    if fpath_resolved.exists():
        saved = read_json(fpath_resolved)
        differences = compare_resolved_params(saved, params)
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

    # Snapshot the exact workflow implementation used by the run
    dirpath_source = dirpath_meta / 'workflow_source'
    dirpath_source.mkdir(parents=True, exist_ok=True)
    for fpath in sorted(Path(dirpath_workflow).glob('*.py')):
        shutil.copy2(fpath, dirpath_source / fpath.name)
    write_json_atomic(fpath_resolved, params)
    write_json_atomic(dirpath_meta / 'state.json', {
        'status': 'initialized',
        'completed_iterations': [],
    })
    return dirpath_run, params


def _resolve_experiment_cfg_paths(experiment):
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


def _get_stage_configs(workflow_params):
    """Validate and return ordered workflow stage configurations."""
    stages = workflow_params['stages']
    names = [stage['name'] for stage in stages]
    if len(names) != len(set(names)):
        raise ValueError(f'Workflow stage names should be unique: {names}')
    return stages


def _resolve_stage_spec(workflow_params, stage_cfg, iteration, run_id,
                        dynamic_overrides):
    """Resolve one stage into a compact immutable specification."""
    exp_paths = _resolve_experiment_cfg_paths(stage_cfg['experiment'])
    batch_mod = load_module(exp_paths['batch_params'])
    default_params = batch_mod.get_batch_params()

    # Apply static workflow settings followed by dynamic stage dependencies
    batch_overrides = dict(stage_cfg.get('batch_param_overrides', {}))
    batch_overrides.update(
        dynamic_overrides.get('batch_param_overrides', {})
    )
    params = merge_batch_params(default_params, batch_overrides)
    exp_overrides = dict(stage_cfg.get('experiment_overrides', {}))
    exp_overrides.update(
        dynamic_overrides.get('experiment_overrides', {})
    )
    batch_run = dict(workflow_params['batch_run_defaults'])
    batch_run.update(stage_cfg.get('batch_run', {}))

    spec = {
        'workflow_name': workflow_params['workflow_name'],
        'run_id': run_id,
        'iteration': iteration,
        'stage': stage_cfg['name'],
        'experiment': stage_cfg['experiment'],
        'executor': stage_cfg.get('executor'),
        'executor_params': stage_cfg.get('executor_params', {}),
        'processor': stage_cfg['processor'],
        'processor_params': stage_cfg.get('processor_params', {}),
        'batch_params': params,
        'batch_param_overrides': batch_overrides,
        'experiment_overrides': exp_overrides,
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
        'batchtools/summaries',
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


def _load_stage_executor(stage_spec, dirpath_workflow):
    """Load an optional workflow-local stage executor."""
    executor_name = stage_spec.get('executor')
    if executor_name is None:
        return None
    return load_module(Path(dirpath_workflow) / executor_name)


def _stage_is_complete(dirpath_stage, stage_spec,
                       dirpath_workflow=None):
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
    if missing:
        return False

    # Let workflow-local executors validate their external inputs
    if stage_spec.get('executor') is not None:
        if dirpath_workflow is None:
            return False
        executor = _load_stage_executor(
            stage_spec,
            dirpath_workflow,
        )
        return bool(executor.validate_stage(
            dirpath_stage,
            stage_spec,
            **stage_spec.get('executor_params', {}),
        ))
    return True


def _run_batchtools_stage(dirpath_stage, stage_spec, exp_paths,
                          workflow_params, fpath_runtime):
    """Launch and complete one subordinate BatchTools batch."""
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
    fpath_root_summary = DIR_REPO / f'{exp_paths["name"]}.csv'
    summary_before = file_fingerprint(fpath_root_summary)

    # Let output markers win over BatchTools communication failures
    search, dispatcher, submitter = _load_batchtools()
    search_error = None
    _shutdown_ray_if_initialized()
    try:
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
            attempt_restore=False,
        )
    except Exception as exc:
        search_error = exc
        print(f'BatchTools returned an error: {exc!r}', flush=True)
    finally:
        _shutdown_ray_if_initialized()

    # Wait for durable job outputs before touching BatchTools artifacts
    poll_timeout = workflow_params['wait_timeout_sec']
    if search_error and poll_timeout is None and _is_ray_reinit_error(search_error):
        poll_timeout = 0
    records = poll_job_records(
        dirpath_stage,
        expected,
        list(stage_spec['batch_params']),
        stage_spec['stage_spec_hash'],
        workflow_params['wait_refresh_sec'],
        poll_timeout,
    )
    artifacts = collect_batchtools_artifacts(
        dirpath_stage,
        root_summary=fpath_root_summary,
        root_summary_before=summary_before,
    )
    write_json_atomic(dirpath_stage / 'meta' / 'stage_complete.json', {
        'status': 'complete',
        'stage_spec_hash': stage_spec['stage_spec_hash'],
        'job_count': len(records),
        'batchtools_error': repr(search_error) if search_error else None,
        'batchtools_attempt': artifacts['attempt'],
        'batchtools_summaries': artifacts['summaries'],
    })


def _run_executor_stage(dirpath_stage, stage_spec, dirpath_workflow,
                        workflow_params):
    """Run and validate one workflow-local stage executor."""
    executor = _load_stage_executor(stage_spec, dirpath_workflow)
    executor_params = stage_spec.get('executor_params', {})
    executor.run_stage(
        dirpath_stage,
        stage_spec,
        **executor_params,
    )

    # Wait through the same durable job-record path as real batches
    expected = expand_param_grid(stage_spec['batch_params'])
    records = poll_job_records(
        dirpath_stage,
        expected,
        list(stage_spec['batch_params']),
        stage_spec['stage_spec_hash'],
        workflow_params['wait_refresh_sec'],
        workflow_params['wait_timeout_sec'],
    )
    if not executor.validate_stage(
        dirpath_stage,
        stage_spec,
        **executor_params,
    ):
        raise RuntimeError(
            f'Executor validation failed for stage {stage_spec["stage"]!r}'
        )
    write_json_atomic(dirpath_stage / 'meta' / 'stage_complete.json', {
        'status': 'complete',
        'stage_spec_hash': stage_spec['stage_spec_hash'],
        'job_count': len(records),
        'executor': stage_spec['executor'],
    })


def _run_stage(dirpath_stage, stage_spec, exp_paths, workflow_params,
               dirpath_workflow):
    """Run or resume one subordinate workflow stage."""
    _prepare_stage_dirs(dirpath_stage)
    fpath_runtime = _write_stage_metadata(dirpath_stage, stage_spec)
    if _stage_is_complete(
        dirpath_stage,
        stage_spec,
        dirpath_workflow,
    ):
        print(f'Skipping complete stage: {dirpath_stage}', flush=True)
        return

    # Dispatch local fixture executors without loading BatchTools
    if stage_spec.get('executor') is not None:
        _run_executor_stage(
            dirpath_stage,
            stage_spec,
            dirpath_workflow,
            workflow_params,
        )
        return
    _run_batchtools_stage(
        dirpath_stage,
        stage_spec,
        exp_paths,
        workflow_params,
        fpath_runtime,
    )


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


def _process_stage(dirpath_stage, stage_spec, dirpath_workflow):
    """Run or resume one workflow-local stage processor."""
    fpath_processor = dirpath_workflow / stage_spec['processor']
    processor = load_module(fpath_processor)
    processor_params = stage_spec.get('processor_params', {})
    processing_complete = _processing_is_complete(
        dirpath_stage,
        stage_spec['stage_spec_hash'],
    )
    if processing_complete:
        return processor.load_stage_result(
            dirpath_stage,
            stage_spec,
            **processor_params,
        )

    result, outputs = processor.process_stage(
        dirpath_stage,
        stage_spec,
        **processor_params,
    )
    missing = [
        relpath
        for relpath in outputs
        if not (dirpath_stage / relpath).is_file()
    ]
    if missing:
        raise FileNotFoundError(
            f'Processor declared missing outputs: {missing}'
        )
    write_json_atomic(
        dirpath_stage / 'meta' / 'processing_complete.json',
        {
            'status': 'complete',
            'stage_spec_hash': stage_spec['stage_spec_hash'],
            'outputs': outputs,
        },
    )
    return result


def _load_history(dirpath_run, stage_configs,
                  dirpath_workflow=None):
    """Load consecutive completed iterations with valid stage outputs."""
    history = []
    dirpath_iterations = dirpath_run / 'iterations'
    for fpath in sorted(dirpath_iterations.glob('iter_*/meta/iteration.json')):
        item = read_json(fpath)
        if item.get('status') != 'complete':
            break

        # Validate stages in the workflow-declared order
        dirpath_iter = fpath.parents[1]
        stages_valid = True
        for stage_cfg in stage_configs:
            stage_name = stage_cfg['name']
            dirpath_stage = dirpath_iter / stage_name
            fpath_spec = dirpath_stage / 'meta' / 'stage_spec.json'
            if not fpath_spec.exists():
                stages_valid = False
                break
            stage_spec = read_json(fpath_spec)
            expected_hash = item['stage_spec_hashes'].get(stage_name)
            stages_valid = (
                stage_spec['stage_spec_hash'] == expected_hash and
                _stage_is_complete(
                    dirpath_stage,
                    stage_spec,
                    dirpath_workflow,
                ) and
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


def run_workflow(workflow_name, run_id=None):
    """Run or resume one configured iterative workflow."""
    dirpath_workflow = DIR_WORKFLOW_CONFIGS / workflow_name
    cfg_mod = load_module(dirpath_workflow / 'workflow_cfg.py')
    workflow_params = cfg_mod.get_workflow_params()
    run_id = _resolve_run_id(
        cfg_mod,
        workflow_params,
        run_id=run_id,
    )
    dirpath_run = (
        DIR_WORKFLOW_RESULTS /
        workflow_params['workflow_name'] /
        run_id
    )
    print(f'Workflow run ID: {run_id}', flush=True)
    print(f'Workflow result path: {dirpath_run}', flush=True)

    # Prepare immutable metadata after resolving the result directory
    dirpath_run, params = _prepare_run(
        cfg_mod,
        dirpath_workflow,
        run_id,
        workflow_params=workflow_params,
    )
    stage_configs = _get_stage_configs(params)
    history = _load_history(
        dirpath_run,
        stage_configs,
        dirpath_workflow,
    )
    if history and history[-1].get('stop_reason'):
        print(
            f"Workflow already stopped: {history[-1]['stop_reason']}",
            flush=True,
        )
        return

    iteration_context = params['initial_context']
    if history:
        iteration_context = history[-1]['next_context']

    # Continue at the first iteration without a completed summary
    for iteration in range(len(history), params['max_iterations']):
        dirpath_iter = (
            dirpath_run / 'iterations' / f'iter_{iteration:03d}'
        )
        (dirpath_iter / 'meta').mkdir(parents=True, exist_ok=True)
        print(
            f'Iteration {iteration}: context={iteration_context}',
            flush=True,
        )
        stage_results = {}
        stage_spec_hashes = {}

        # Resolve each stage after all prior stage results are available
        for stage_cfg in stage_configs:
            stage_name = stage_cfg['name']
            dynamic_overrides = cfg_mod.get_stage_overrides(
                stage_name,
                iteration,
                iteration_context,
                stage_results,
                history,
            )
            stage_spec, exp_paths = _resolve_stage_spec(
                params,
                stage_cfg,
                iteration,
                run_id,
                dynamic_overrides,
            )
            dirpath_stage = dirpath_iter / stage_name
            # Run the stage
            _run_stage(
                dirpath_stage,
                stage_spec,
                exp_paths,
                params,
                dirpath_workflow,
            )
            # Process stage results
            stage_results[stage_name] = _process_stage(
                dirpath_stage,
                stage_spec,
                dirpath_workflow,
            )
            stage_spec_hashes[stage_name] = stage_spec['stage_spec_hash']

        # Delegate iteration science and continuation to the workflow config
        outcome = cfg_mod.finish_iteration(
            iteration,
            iteration_context,
            stage_results,
            history,
        )
        next_context = outcome.get('next_context')
        stop_reason = outcome.get('stop_reason')
        iteration_info = {
            'status': 'complete',
            'iteration': iteration,
            'context': iteration_context,
            'stage_spec_hashes': stage_spec_hashes,
            'result': outcome.get('result', {}),
            'next_context': next_context,
            'stop_reason': stop_reason,
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
        if next_context is None:
            raise ValueError(
                'finish_iteration() returned no next context or stop reason'
            )
        iteration_context = next_context

    write_json_atomic(dirpath_run / 'meta' / 'state.json', {
        'status': 'complete',
        'completed_iterations': [
            item['iteration']
            for item in history
        ],
        'stop_reason': 'Maximum iteration count reached',
    })


def main_cli():
    """Parse arguments and run a workflow."""
    parser = argparse.ArgumentParser(description='Run iterative workflow.')
    parser.add_argument(
        '--workflow',
        default=os.environ.get('A1_WORKFLOW_NAME', 'wmat_transfer'),
    )
    parser.add_argument(
        '--run-id',
        default=None,
    )
    args = parser.parse_args()
    run_workflow(args.workflow, args.run_id)


def main():
    WORKFLOW_NAME = 'ibkg_adj__fullsim__var_wmult_list_1d'
    run_workflow(WORKFLOW_NAME)


if __name__ == '__main__':
    main()
