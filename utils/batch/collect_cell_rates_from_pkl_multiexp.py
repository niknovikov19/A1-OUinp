import json
from pathlib import Path
import sys

# Set import path
DIR_REPO = Path(__file__).resolve().parents[2]
if str(DIR_REPO) not in sys.path:
    sys.path.insert(0, str(DIR_REPO))

from utils.batch.collect_cell_rates_from_pkl import collect_cell_rates_from_pkl


# User parameters
# JSON keys: dirpath_root, experiments
FPATH_EXPERIMENTS_JSON = (
    DIR_REPO / 'exp_results' / 'path_to_experiments.json'
)
DIRPATH_OUT = None
BATCH_PARAM_FIELDS = None
T_LIMITS = None
POP_NAMES = None
NSPIKES_MIN = 3
JOB_IDS = None
OVERWRITE = True


def _load_experiments(fpath_experiments_json):
    """Load the common root and relative experiment folder names. """
    fpath = Path(fpath_experiments_json)
    with fpath.open('r') as file:
        config = json.load(file)

    # Resolve a relative common root from the JSON file location
    dirpath_root = Path(config['dirpath_root']).expanduser()
    if not dirpath_root.is_absolute():
        dirpath_root = fpath.parent / dirpath_root

    # Validate names before any output folders or large files are touched
    exp_names = config['experiments']
    if not isinstance(exp_names, list) or len(exp_names) == 0:
        raise ValueError('experiments should be a non-empty list')
    for exp_name in exp_names:
        if not isinstance(exp_name, str) or not exp_name:
            raise ValueError(
                'experiment folder names should be non-empty strings'
            )
        exp_path = Path(exp_name)
        invalid = (
            exp_path == Path('.')
            or exp_path.is_absolute()
            or '..' in exp_path.parts
        )
        if invalid:
            raise ValueError(f'Experiment should be a subfolder: {exp_name}')
    if len(exp_names) != len(set(exp_names)):
        raise ValueError('experiment folder names should be unique')

    return dirpath_root, exp_names


def collect_cell_rates_from_pkl_multiexp(
        fpath_experiments_json, dirpath_out=None, batch_param_fields=None,
        t_limits=None, pop_names=None, nspikes_min=3, job_ids=None,
        overwrite=True):
    """Collect per-cell statistics independently for several experiments. """
    dirpath_root, exp_names = _load_experiments(fpath_experiments_json)
    output_paths = {}

    # Run the single-experiment collector with unchanged analysis parameters
    for exp_name in exp_names:
        dirpath_exp = dirpath_root / exp_name
        exp_dirpath_out = None
        if dirpath_out is not None:
            exp_dirpath_out = Path(dirpath_out) / exp_name
            exp_dirpath_out.mkdir(parents=True, exist_ok=True)
        print(f'Collecting experiment: {exp_name}')
        collect_cell_rates_from_pkl(
            dirpath_exp=dirpath_exp,
            dirpath_out=exp_dirpath_out,
            batch_param_fields=batch_param_fields,
            t_limits=t_limits,
            pop_names=pop_names,
            nspikes_min=nspikes_min,
            job_ids=job_ids,
            overwrite=overwrite,
        )
        output_dir = (
            dirpath_exp / 'cell_rates'
            if exp_dirpath_out is None else exp_dirpath_out
        )
        output_paths[exp_name] = output_dir / 'cell_rates_xr_combined.nc'

    return output_paths


def main():
    """Run multi-experiment collection using the editable parameter block. """
    collect_cell_rates_from_pkl_multiexp(
        fpath_experiments_json=FPATH_EXPERIMENTS_JSON,
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
