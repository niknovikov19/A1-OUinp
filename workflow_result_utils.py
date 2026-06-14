from pathlib import Path


def is_workflow_run(cfg):
    """Return whether the current job belongs to a workflow stage."""
    return hasattr(cfg, 'workflow_context')


def get_retention(cfg):
    """Return workflow retention flags or standalone keep-all defaults."""
    if not is_workflow_run(cfg):
        return {
            'keep_cfg': True,
            'keep_netparams': True,
            'keep_pkl': True,
        }
    return dict(cfg.workflow_retention)


def prepare_result_dirs(cfg, exp_name_sub, dirnames):
    """Create the result root and requested artifact directories."""
    dirpath_result = Path(cfg.saveFolder) / exp_name_sub
    for dirname in dirnames:
        (dirpath_result / dirname).mkdir(parents=True, exist_ok=True)
    return dirpath_result


def move_if_present(fpath_old, fpath_new, report_missing=True):
    """Move one output file when it exists."""
    fpath_old = Path(fpath_old)
    fpath_new = Path(fpath_new)
    if not fpath_old.exists():
        if report_missing:
            print('RESULT NOT FOUND: ', fpath_old)
        return None
    fpath_new.parent.mkdir(parents=True, exist_ok=True)
    if fpath_new.exists():
        fpath_new.unlink()
    fpath_old.rename(fpath_new)
    return fpath_new


def keep_or_remove(fpath_old, fpath_new, keep, report_missing=True):
    """Move a retained file or remove an unwanted one."""
    fpath_old = Path(fpath_old)
    if not fpath_old.exists():
        if report_missing and keep:
            print('RESULT NOT FOUND: ', fpath_old)
        return None
    if not keep:
        fpath_old.unlink()
        return None
    return move_if_present(fpath_old, fpath_new, report_missing=False)


def organize_standard_outputs(cfg, exp_name_sub, postfix):
    """Sort standard NetPyNE outputs according to retention flags."""
    exp_name = cfg.simLabel
    dirpath_stage = Path(cfg.saveFolder)
    retention = get_retention(cfg)
    dirnames = ['rasters', 'results', 'traces', 'rvec_figs', 'csd_figs']
    if retention['keep_cfg']:
        dirnames.append('cfg')
    if retention['keep_netparams']:
        dirnames.append('netpar')
    if retention['keep_pkl']:
        dirnames.append('pkl')
    if is_workflow_run(cfg):
        dirnames.append('results_last')
        if retention['keep_pkl']:
            dirnames.append('ctrl')
    dirpath_result = prepare_result_dirs(cfg, exp_name_sub, dirnames)

    # Move outputs that are always retained
    move_if_present(
        dirpath_stage / f'{exp_name}_raster.png',
        dirpath_result / 'rasters' / f'raster_{postfix}.png',
    )

    # Apply workflow retention to large and reconstructable outputs
    keep_or_remove(
        dirpath_stage / f'{exp_name}_data.pkl',
        dirpath_result / 'pkl' / f'data_{postfix}.pkl',
        retention['keep_pkl'],
        report_missing=not is_workflow_run(cfg) or retention['keep_pkl'],
    )
    keep_or_remove(
        dirpath_stage / f'{exp_name}_cfg.json',
        dirpath_result / 'cfg' / f'cfg_{postfix}.json',
        retention['keep_cfg'],
    )
    keep_or_remove(
        dirpath_stage / f'{exp_name}_netParams.json',
        dirpath_result / 'netpar' / f'netParams_{postfix}.json',
        retention['keep_netparams'],
    )

    if not is_workflow_run(cfg):
        return dirpath_result

    # Remove the duplicate parameters file even if an older run left one
    fpath_params = dirpath_stage / f'{exp_name}_params.json'
    if fpath_params.exists():
        fpath_params.unlink()

    # Sort compact last-second rates and optional controller data
    move_if_present(
        dirpath_stage / f'{exp_name}_result.json',
        dirpath_result / 'results_last' / f'result_last_{postfix}.json',
        report_missing=False,
    )
    keep_or_remove(
        dirpath_stage / f'{exp_name}_ctrl.pkl',
        dirpath_result / 'ctrl' / f'ctrl_{postfix}.pkl',
        retention['keep_pkl'],
        report_missing=False,
    )

    return dirpath_result


def relative_output(cfg, fpath):
    """Return an output path relative to the workflow stage root."""
    return Path(fpath).relative_to(Path(cfg.saveFolder)).as_posix()
