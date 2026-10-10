import argparse
import json
from pathlib import Path

from hpc_job import (
    HpcJobValidationError,
    calculate_parameter_grid_size,
    validate_repo_path,
    validate_request,
    validate_result_destination,
)


class HpcPreflightError(HpcJobValidationError):
    """Represent an incompatible repository target or result plan."""


def read_tracked_request(repo_root, request_path):
    """Read one request confined beneath hpc_jobs/requests."""
    repo_root = Path(repo_root).resolve()
    request_path = validate_repo_path(request_path, 'request path')
    parts = Path(request_path).parts
    if parts[:2] != ('hpc_jobs', 'requests') or len(parts) != 3:
        raise HpcPreflightError('Request must be directly below hpc_jobs/requests')
    if Path(request_path).suffix != '.json':
        raise HpcPreflightError('Request file must use the .json suffix')
    fpath = repo_root / request_path
    if fpath.is_symlink() or not fpath.is_file():
        raise HpcPreflightError(f'Request file does not exist: {request_path}')
    with open(fpath, 'r') as fid:
        request = validate_request(json.load(fid))
    if Path(request_path).stem != request['request_id']:
        raise HpcPreflightError('Request filename must equal request_id')
    return request


def _load_dependencies(cfg_factory, module_loader):
    """Load simulation dependencies only for a real ordinary preflight."""
    if cfg_factory is None:
        from create_base_cfg import create_base_cfg
        cfg_factory = create_base_cfg
    if module_loader is None:
        from load_module import load_module
        module_loader = load_module
    return cfg_factory, module_loader


def _validate_result_subdir(value):
    """Validate one experiment-defined result-directory name."""
    value = validate_repo_path(value, 'experiment result subdirectory')
    if len(Path(value).parts) != 1:
        raise HpcPreflightError('Experiment result subdirectory must be one name')
    return value


def resolve_result_subdir(exp_mod, cfg):
    """Resolve one established experiment result-directory name."""
    if hasattr(exp_mod, 'get_result_subdir'):
        value = exp_mod.get_result_subdir(cfg)
    elif hasattr(exp_mod, 'gen_exp_name_sub'):
        value = exp_mod.gen_exp_name_sub(cfg)
    elif hasattr(cfg, 'exp_name_sub'):
        value = cfg.exp_name_sub
    else:
        raise HpcPreflightError(
            'Experiment must expose get_result_subdir(cfg), '
            'gen_exp_name_sub(cfg), or cfg.exp_name_sub'
        )
    if not isinstance(value, str):
        raise HpcPreflightError('Experiment result subdirectory must be text')
    return _validate_result_subdir(value)


def _resolve_experiment_files(repo_root, target, require_batch):
    """Resolve the required tracked files for one ordinary experiment."""
    dirpath = repo_root / 'exp_configs' / target
    fpath_cfg = dirpath / 'exp_cfg.py'
    fpath_batch = dirpath / 'batch_params.py'
    if not fpath_cfg.is_file() or fpath_cfg.is_symlink():
        raise HpcPreflightError(f'Missing experiment config: {fpath_cfg}')
    if require_batch and (not fpath_batch.is_file() or fpath_batch.is_symlink()):
        raise HpcPreflightError(f'Missing batch parameters: {fpath_batch}')
    return fpath_cfg, fpath_batch


def resolve_ordinary_plan(repo_root, request, cfg_factory=None,
                          module_loader=None):
    """Resolve a single or batch request from its scientific config files."""
    repo_root = Path(repo_root).resolve()
    request = validate_request(request)
    if request['job_kind'] not in {'single', 'batch'}:
        raise HpcPreflightError('Ordinary preflight requires single or batch')
    cfg_factory, module_loader = _load_dependencies(
        cfg_factory,
        module_loader,
    )
    fpath_cfg, fpath_batch = _resolve_experiment_files(
        repo_root,
        request['target'],
        request['job_kind'] == 'batch',
    )

    # Apply the same config mutation used before network construction
    cfg = cfg_factory()
    exp_mod = module_loader(fpath_cfg)
    exp_mod.apply_exp_cfg(cfg)
    result_subdir = resolve_result_subdir(exp_mod, cfg)
    result_path = (
        Path('exp_results') /
        request['target'] /
        result_subdir
    ).as_posix()

    if request['job_kind'] == 'single':
        planned_jobs = 1
        parameter_axis_sizes = {}
    else:
        batch_mod = module_loader(fpath_batch)
        parameter_axes = batch_mod.get_batch_params()
        planned_jobs = calculate_parameter_grid_size(
            parameter_axes,
            request['max_simulation_jobs'],
        )
        if request['max_concurrent_simulation_jobs'] > planned_jobs:
            raise HpcPreflightError(
                'Batch concurrency exceeds planned simulation jobs'
            )
        parameter_axis_sizes = {
            name: len(values)
            for name, values in parameter_axes.items()
        }
    return {
        'resolved_result_path': result_path,
        'planned_jobs': planned_jobs,
        'parameter_axis_sizes': parameter_axis_sizes,
    }


def _merge_batch_params(default_params, overrides):
    """Apply workflow axis overrides without accepting unknown names."""
    unknown = sorted(set(overrides) - set(default_params))
    if unknown:
        raise HpcPreflightError(f'Unknown batch parameter overrides: {unknown}')
    params = {
        name: list(values)
        for name, values in default_params.items()
    }
    for name, values in overrides.items():
        values = list(values)
        if not values:
            raise HpcPreflightError(f'Batch parameter {name!r} cannot be empty')
        params[name] = values
    return params


def resolve_workflow_plan(repo_root, request, module_loader=None):
    """Resolve one workflow request from workflow and batch config files."""
    repo_root = Path(repo_root).resolve()
    request = validate_request(request)
    if request['job_kind'] != 'workflow':
        raise HpcPreflightError('Workflow preflight requires a workflow request')
    if module_loader is None:
        from load_module import load_module
        module_loader = load_module
    dirpath = repo_root / 'workflow_configs' / request['target']
    fpath_cfg = dirpath / 'workflow_cfg.py'
    if not fpath_cfg.is_file() or fpath_cfg.is_symlink():
        raise HpcPreflightError(f'Missing workflow config: {fpath_cfg}')
    cfg_mod = module_loader(fpath_cfg)
    workflow = cfg_mod.get_workflow_params()
    if workflow.get('workflow_name') != request['target']:
        raise HpcPreflightError('Workflow name differs from request target')
    result_id = cfg_mod.get_run_id(workflow)
    result_id = _validate_result_subdir(result_id)
    result_path = (
        Path('exp_results') /
        'workflows' /
        request['target'] /
        result_id
    ).as_posix()

    # Count the static grids of stages that actually submit simulations
    simulation_stages = {
        stage['name']: stage
        for stage in workflow['stages']
        if stage.get('executor') is None
    }
    if set(simulation_stages) != set(request['stage_jobs']):
        raise HpcPreflightError(
            'Workflow simulation stages differ from request stage_jobs'
        )
    max_iterations = workflow['max_iterations']
    if isinstance(max_iterations, bool) or not isinstance(max_iterations, int):
        raise HpcPreflightError('Workflow max_iterations must be an integer')
    if max_iterations < 1:
        raise HpcPreflightError('Workflow max_iterations must be positive')

    planned_jobs = {}
    parameter_axis_sizes = {}
    for stage_name, stage in simulation_stages.items():
        dirpath_exp = repo_root / 'exp_configs' / stage['experiment']
        fpath_batch = dirpath_exp / 'batch_params.py'
        if not fpath_batch.is_file() or fpath_batch.is_symlink():
            raise HpcPreflightError(f'Missing batch parameters: {fpath_batch}')
        batch_mod = module_loader(fpath_batch)
        params = _merge_batch_params(
            batch_mod.get_batch_params(),
            stage.get('batch_param_overrides', {}),
        )
        per_iteration = calculate_parameter_grid_size(params)
        concurrency = request['stage_jobs'][stage_name][
            'max_concurrent_simulation_jobs'
        ]
        if concurrency > per_iteration:
            raise HpcPreflightError(
                f'{stage_name} concurrency exceeds its per-iteration jobs'
            )
        planned_jobs[stage_name] = per_iteration * max_iterations
        parameter_axis_sizes[stage_name] = {
            name: len(values)
            for name, values in params.items()
        }
    if sum(planned_jobs.values()) > request['max_simulation_jobs']:
        raise HpcPreflightError('Workflow static job plan exceeds request limit')
    return {
        'resolved_result_path': result_path,
        'planned_jobs': planned_jobs,
        'parameter_axis_sizes': parameter_axis_sizes,
    }


def preflight_request(repo_root, request, check_collision=True,
                      cfg_factory=None, module_loader=None):
    """Resolve and validate one tracked request without running a simulation."""
    request = validate_request(request)
    if request['job_kind'] == 'workflow':
        plan = resolve_workflow_plan(repo_root, request, module_loader)
    else:
        plan = resolve_ordinary_plan(
            repo_root,
            request,
            cfg_factory,
            module_loader,
        )
    if plan['resolved_result_path'] != request['expected_result_path']:
        raise HpcPreflightError('Resolved result path differs from request')
    if check_collision:
        try:
            validate_result_destination(repo_root, plan['resolved_result_path'])
        except HpcJobValidationError as exc:
            raise HpcPreflightError(str(exc)) from exc
    return {
        'schema_version': 1,
        'request_id': request['request_id'],
        'job_kind': request['job_kind'],
        'target': request['target'],
        **plan,
        'status': 'ok',
    }


def main_cli():
    """Run a read-only repository preflight for one tracked request."""
    parser = argparse.ArgumentParser(description='Preflight one HPC job request.')
    parser.add_argument('request_path')
    parser.add_argument('--repo-root', default=Path(__file__).resolve().parent)
    parser.add_argument('--skip-collision-check', action='store_true')
    args = parser.parse_args()
    repo_root = Path(args.repo_root).resolve()
    request = read_tracked_request(repo_root, args.request_path)
    result = preflight_request(
        repo_root,
        request,
        check_collision=not args.skip_collision_check,
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == '__main__':
    main_cli()
