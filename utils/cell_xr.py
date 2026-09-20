import numpy as np


POP_COORD_NAMES = ('pop', 'pop_post')


def _get_pop_coord(data):
    """Return the supported population coordinate name. """
    for coord_name in POP_COORD_NAMES:
        if coord_name in data.coords and data[coord_name].dims == ('gid',):
            return coord_name
    raise ValueError("Expected a 'pop(gid)' or 'pop_post(gid)' coordinate")


def get_pop_gids(data, pop_name):
    """Return GIDs belonging to one population. """
    coord_name = _get_pop_coord(data)
    pop_values = np.asarray(data[coord_name].values).astype(str)
    mask = pop_values == str(pop_name)
    if not np.any(mask):
        available = sorted(set(pop_values.tolist()))
        raise KeyError(f'Population {pop_name!r} not found; available: {available}')
    return np.asarray(data['gid'].values)[mask]


def select_pop(data, pop_name):
    """Select all cells belonging to one population. """
    return data.sel(gid=get_pop_gids(data, pop_name))


def get_batch_dims(data):
    """Return dimensions other than the per-cell GID dimension. """
    if 'job_id' in data.coords:
        dims = data['job_id'].dims
    elif hasattr(data, 'data_vars') and 'rate' in data:
        dims = data['rate'].dims
    else:
        dims = data.dims
    return tuple(dim for dim in dims if dim != 'gid')
