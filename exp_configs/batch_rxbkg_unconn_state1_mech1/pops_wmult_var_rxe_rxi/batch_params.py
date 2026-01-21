import numpy as np


N_RXE = 15
N_RXI = 15

def get_batch_params():
    """Generate params for batchtools to probe. """
    params = {
        'rxe': np.linspace(1, 20000, N_RXE).tolist(),
        'rxi': np.linspace(1, 2000, N_RXI).tolist()
    }
    return params

def post_update(cfg):
    """Called after cfg.update() """

    for pop in cfg.bkg_spike_inputs:
        cfg.bkg_spike_inputs[pop]['exc']['r'] = cfg.rxe
        cfg.bkg_spike_inputs[pop]['inh']['r'] = cfg.rxi
