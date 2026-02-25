import numpy as np


N_RXE = 20
N_RXI = 1

RXE_MAX = 10000
RXI_MAX = 2000

RXE_MIN = 5000
RXI_MIN = 2000

def get_batch_params():
    """Generate params for batchtools to probe. """
    params = {
        'rxe': np.linspace(RXE_MIN, RXE_MAX, N_RXE).tolist(),
        'rxi': np.linspace(RXI_MIN, RXI_MAX, N_RXI).tolist()
    }
    return params

def post_update(cfg):
    """Called after cfg.update() """

    for pop in cfg.bkg_spike_inputs:
        cfg.bkg_spike_inputs[pop]['exc']['r'] = cfg.rxe
        cfg.bkg_spike_inputs[pop]['inh']['r'] = cfg.rxi
