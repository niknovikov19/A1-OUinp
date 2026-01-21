import numpy as np


N_RXE = 25
N_RXI = 25

def get_batch_params():
    """Generate params for batchtools to probe. """
    params = {
        'rxe': np.linspace(4e3, 40e3, N_RXE).tolist(),
        'rxi': np.linspace(3e3, 15e3, N_RXI).tolist()
    }
    return params

def post_update(cfg):
    """Called after cfg.update() """

    for pop in cfg.bkg_spike_inputs:
        cfg.bkg_spike_inputs[pop]['exc']['r'] = cfg.rxe
        cfg.bkg_spike_inputs[pop]['inh']['r'] = cfg.rxi
