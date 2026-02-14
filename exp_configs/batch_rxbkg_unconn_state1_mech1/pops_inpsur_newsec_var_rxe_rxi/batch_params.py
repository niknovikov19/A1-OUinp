import numpy as np


N_RXE = 5
N_RXI = 5

RXE_MAX = 100000
RXI_MAX = 6000

RX_MIN = 0.1

def get_batch_params():
    """Generate params for batchtools to probe. """
    params = {
        'rxe': np.linspace(RX_MIN, RXE_MAX, N_RXE).tolist(),
        'rxi': np.linspace(RX_MIN, RXI_MAX, N_RXI).tolist()
    }
    return params

def post_update(cfg):
    """Called after cfg.update() """

    for pop in cfg.bkg_spike_inputs:
        cfg.bkg_spike_inputs[pop]['exc']['r'] = cfg.rxe
        cfg.bkg_spike_inputs[pop]['inh']['r'] = cfg.rxi
