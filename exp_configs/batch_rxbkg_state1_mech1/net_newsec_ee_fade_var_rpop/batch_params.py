from collections.abc import Mapping, Sequence

import numpy as np


N_RATE_PTS = 10

POP_FRZ_RATES = {
    #'IT2': (0.1, 6),
    #'PV2': (0.1, 40),
    'SOM2': (0.1, 10),
    'VIP2': (0.1, 25)
}


def get_batch_params():
    """Generate params for batchtools to probe. """
    params = {
        'pop_frz': list(POP_FRZ_RATES.keys()),
        'rate_pt': np.arange(N_RATE_PTS).tolist()
    }
    return params


def _is_lst(z):
    if isinstance(z, Mapping):
        return False
    if isinstance(z, (str, bytes)):
        return False
    if np.isscalar(z):
        return False
    return isinstance(z, (Sequence, np.ndarray))

def _lst_remove(lst, x):
    if _is_lst(lst):
        lst[:] = [y for y in lst if y != x]


def post_update(cfg):
    """Called after cfg.update() """
    pop_frz = cfg.pop_frz
    
    # Remove pop_frz from active
    _lst_remove(cfg.subnet_params['pops_active'], pop_frz)

    # Set custom rate for surrogate pop_frz
    r1, r2 = POP_FRZ_RATES[pop_frz]
    r = np.linspace(r1, r2, N_RATE_PTS)[cfg.rate_pt]
    r = np.round(r, 1)
    if 'frozen_rates_custom' not in cfg.subnet_params:
        cfg.subnet_params['frozen_rates_custom'] = {}
    cfg.subnet_params['frozen_rates_custom'][pop_frz] = r

    # Remove pop_frz from places where it is treated as active
    cfg.bkg_spike_inputs.pop(pop_frz, None)
    if cfg.analysis.get('plotRaster'):
        _lst_remove(cfg.analysis['plotRaster'].get('include'), pop_frz)
    if cfg.analysis.get('plotSpikeStats'):
        _lst_remove(cfg.analysis['plotSpikeStats'].get('include'), pop_frz)
    if cfg.analysis.get('plotTraces'):
        _lst_remove(cfg.analysis['plotTraces'].get('include'), pop_frz)
    if hasattr(cfg, 'IClamp'):
        cfg.IClamp.pop(pop_frz, None)

