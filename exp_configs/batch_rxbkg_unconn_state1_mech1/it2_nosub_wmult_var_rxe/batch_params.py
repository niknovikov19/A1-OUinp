import numpy as np


def get_batch_params():
    """Generate params for batchtools to probe. """
    params = {
        'rxe': np.arange(1e4, 4e4, 2000).tolist()
    }
    return params


def post_update(cfg):
    """Called after cfg.update() """

    for pop in cfg.bkg_spike_inputs:
        cfg.bkg_spike_inputs[pop]['exc']['r'] = cfg.rxe
