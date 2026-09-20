import json
import re
import sys
import tempfile
from pathlib import Path


# Set import paths
DIR_REPO = Path(__file__).resolve().parents[2]
DIR_EXTERNAL = DIR_REPO / 'external'
for path in (DIR_REPO, DIR_EXTERNAL):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from sim_data_analyzer.batch_xr import (
    collect_batch_cell_stats_from_pkl,
    extract_batch_params_to_xr,
)
from sim_data_analyzer.xr_io import save_xr


# User parameters
DIRPATH_EXP = DIR_REPO / 'exp_results' / 'path_to_experiment'
DIRPATH_OUT = None
BATCH_PARAM_FIELDS = None
T_LIMITS = None
POP_NAMES = None
NSPIKES_MIN = 3
JOB_IDS = None
OVERWRITE = True


_CFG_RE = re.compile(r'^cfg_(\d+)(?:_|$)')
_INFERENCE_EXCLUDE = {
    'backupCfgFile',
    'filename',
    'saveFolder',
    'simLabel',
    'timestampFilename',
}


def _get_job_id(path, pattern):
    """Extract a numeric job ID from a result filename. """
    match = pattern.match(path.stem)
    if match is None:
        raise ValueError(f'Cannot extract job ID from {path.name}')
    return int(match.group(1))


def _load_cfgs(dirpath_exp, job_ids=None):
    """Load the small per-job configs before touching simulation pickles. """
    selected = None if job_ids is None else set(job_ids)
    cfgs = {}
    for path in sorted((Path(dirpath_exp) / 'cfg').glob('cfg_*.json')):
        job_id = _get_job_id(path, _CFG_RE)
        if selected is not None and job_id not in selected:
            continue
        if job_id in cfgs:
            raise ValueError(f'Multiple config files found for job {job_id}')
        with path.open('r') as file:
            cfgs[job_id] = json.load(file)['simConfig']
    if len(cfgs) == 0:
        raise FileNotFoundError(f'No selected cfg_*.json files in {dirpath_exp}')
    if selected is not None:
        missing = sorted(selected - set(cfgs))
        if missing:
            raise FileNotFoundError(f'Configs not found for jobs: {missing}')
    return cfgs


def _is_scalar(value):
    """Return whether a config value can be a batch coordinate. """
    return value is None or isinstance(value, (str, int, float, bool))


def _infer_batch_param_fields(cfgs, batch_param_fields=None):
    """Infer output batch dimensions and their config fields. """
    if batch_param_fields is not None:
        fields = dict(batch_param_fields)
    else:
        metadata = [cfg.get('batch_par_info', {}) for cfg in cfgs.values()]
        param_lists = [item.get('batch_params') for item in metadata]
        declared = [tuple(item) for item in param_lists if item is not None]
        if declared:
            if len(declared) != len(cfgs) or len(set(declared)) != 1:
                raise ValueError('Inconsistent batch_par_info.batch_params metadata')
            fields = {name: name for name in declared[0]}
        else:
            common = set.intersection(*(set(cfg) for cfg in cfgs.values()))
            fields = {}
            for name in sorted(common - _INFERENCE_EXCLUDE):
                if name.startswith('_'):
                    continue
                values = [cfg[name] for cfg in cfgs.values()]
                if all(_is_scalar(value) for value in values):
                    if len({repr(value) for value in values}) > 1:
                        fields[name] = name

    if len(fields) == 0:
        raise ValueError(
            'Could not infer batch parameters; set BATCH_PARAM_FIELDS explicitly'
        )

    return fields


def _get_job_grid(dirpath_exp, batch_param_fields, job_ids=None):
    """Build and optionally filter the batch grid with sim_data_analyzer. """
    job_idx = extract_batch_params_to_xr(
        Path(dirpath_exp) / 'cfg',
        cfg_param_fields=batch_param_fields,
        fname_cfg_templ='cfg_*.json',
        job_pos_in_fname=1,
    )
    if job_ids is not None:
        job_idx = job_idx.where(job_idx.isin(list(job_ids)), drop=True)
    return job_idx


def _resolve_t_limits(cfgs, t_limits=None):
    """Resolve and validate one common analysis interval in seconds. """
    if t_limits is not None:
        if len(t_limits) != 2:
            raise ValueError(f'Invalid time limits: {t_limits}')
        t0, t1 = t_limits
        if t1 is None:
            durations = {
                float(cfg.get(
                    'duration',
                    cfg.get('runtime_params', {}).get('time', {}).get('duration'),
                )) / 1000
                for cfg in cfgs.values()
            }
            if len(durations) != 1:
                raise ValueError(
                    'Inconsistent durations; provide a finite T_LIMITS end'
                )
            t1 = durations.pop()
        resolved = (float(t0), float(t1))
    else:
        job_limits = {}
        for job_id, cfg in cfgs.items():
            proc = cfg.get('runtime_params', {}).get('proc', {})
            limits = proc.get('rate_t_limits')
            duration = cfg.get(
                'duration',
                cfg.get('runtime_params', {}).get('time', {}).get('duration'),
            )
            t0_calc = cfg.get(
                't0_calc',
                cfg.get('runtime_params', {}).get('time', {}).get('t0_calc'),
            )
            if duration is None or t0_calc is None:
                raise KeyError(f'Cannot infer time limits for job {job_id}')
            if limits is None:
                limits = (float(t0_calc) / 1000, float(duration) / 1000)
            elif limits[1] is None:
                limits = (limits[0], float(duration) / 1000)
            job_limits[job_id] = tuple(float(value) for value in limits)

        unique = set(job_limits.values())
        if len(unique) != 1:
            raise ValueError(
                'Inconsistent inferred time limits; set T_LIMITS explicitly'
            )
        resolved = unique.pop()
    if len(resolved) != 2 or resolved[1] <= resolved[0]:
        raise ValueError(f'Invalid time limits: {resolved}')
    return resolved


def _resolve_pop_names(cfgs, pop_names=None):
    """Resolve analyzed populations from configs when available. """
    if pop_names is not None:
        return list(pop_names)
    values = []
    for cfg in cfgs.values():
        names = cfg.get('pops_used')
        if names is None:
            names = cfg.get('runtime_params', {}).get('pops_used')
        if names is not None:
            values.append(tuple(names))
    if len(values) == 0:
        return None
    if len(values) != len(cfgs) or len(set(values)) != 1:
        raise ValueError('Inconsistent pops_used metadata across jobs')
    return list(values[0])


def _prepare_output_path(dirpath_exp, dirpath_out, overwrite):
    """Create and validate the output location before reading pickles. """
    dirpath_out = (
        Path(dirpath_exp) / 'cell_rates'
        if dirpath_out is None else Path(dirpath_out)
    )
    try:
        dirpath_out.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise PermissionError(
            f'Cannot create {dirpath_out}; set DIRPATH_OUT to a writable path'
        ) from exc

    # Check the destination before opening any large source files
    try:
        with tempfile.TemporaryFile(dir=dirpath_out):
            pass
    except OSError as exc:
        raise PermissionError(
            f'Cannot write in {dirpath_out}; set DIRPATH_OUT to a writable path'
        ) from exc
    path = dirpath_out / 'cell_rates_xr_combined.nc'
    if path.exists() and not overwrite:
        raise FileExistsError(f'Output already exists: {path}')
    return path


def _save_dataset(dataset, path):
    """Write one combined per-cell dataset. """
    try:
        save_xr(dataset, path, engine='scipy')
    except OSError as exc:
        raise PermissionError(
            f'Cannot write {path}; set DIRPATH_OUT to a writable path'
        ) from exc


def collect_cell_rates_from_pkl(
        dirpath_exp, dirpath_out=None, batch_param_fields=None,
        t_limits=None, pop_names=None, nspikes_min=3, job_ids=None,
        overwrite=True):
    """Collect per-cell rates and CVs from one batch of simulation pickles. """
    dirpath_exp = Path(dirpath_exp)
    if nspikes_min < 2:
        raise ValueError('nspikes_min should be at least 2')
    output_path = _prepare_output_path(
        dirpath_exp,
        dirpath_out=dirpath_out,
        overwrite=overwrite,
    )
    cfgs = _load_cfgs(dirpath_exp, job_ids=job_ids)

    # Resolve all lightweight metadata before opening large pickle files
    fields = _infer_batch_param_fields(cfgs, batch_param_fields)
    job_idx = _get_job_grid(dirpath_exp, fields, job_ids=job_ids)
    t_limits = _resolve_t_limits(cfgs, t_limits=t_limits)
    pop_names = _resolve_pop_names(cfgs, pop_names=pop_names)
    print(f'Grid: {dict(job_idx.sizes)}, {int(job_idx.count())} jobs')
    print(f'Time: {t_limits}, populations: {"auto" if pop_names is None else len(pop_names)}')

    # Delegate pickle loading, cell statistics, and batch stacking
    dataset = collect_batch_cell_stats_from_pkl(
        job_idx_xr=job_idx,
        dirpath_data=dirpath_exp / 'pkl',
        fname_templ='data_{job:05d}_*.pkl',
        pop_names=pop_names,
        t_limits=t_limits,
        nspikes_min=nspikes_min,
        skip_missing=True,
    )
    dataset.attrs['batch_params_json'] = json.dumps(list(job_idx.dims))
    _save_dataset(dataset, output_path)
    print(f'Done: {output_path}')
    print(f'Shape: {dict(dataset.sizes)}')
    return dataset


def main():
    """Run collection using the editable parameter block. """
    collect_cell_rates_from_pkl(
        dirpath_exp=DIRPATH_EXP,
        dirpath_out=DIRPATH_OUT,
        batch_param_fields=BATCH_PARAM_FIELDS,
        t_limits=T_LIMITS,
        pop_names=POP_NAMES,
        nspikes_min=NSPIKES_MIN,
        job_ids=JOB_IDS,
        overwrite=OVERWRITE,
    )


if __name__ == '__main__':
    main()
