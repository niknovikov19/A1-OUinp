import numpy as np


N_RXE = 15
N_RXI = 15

# Coeffs. for expressing rxe via (rxi, drxe)
# rxe = rxe0 + drxe
# rxe0 = k0 + k1 * rxi
RXE0_COEFS = {
    'IT2': (6812.5, 2.0625)   # (k0, k1)
}

def get_batch_params():
    """Generate params for batchtools to probe. """
    params = {
        'drxe': np.linspace(-8e3, 0, N_RXE).tolist(),
        'rxi': np.linspace(2e3, 18e3, N_RXI).tolist()
    }
    return params

def post_update(cfg):
    """Called after cfg.update() """

    for pop in cfg.bkg_spike_inputs:
        k0, k1 = RXE0_COEFS[pop]
        cfg.rxe = k0 + k1 * cfg.rxi + cfg.drxe
        cfg.bkg_spike_inputs[pop]['exc']['r'] = cfg.rxe
        cfg.bkg_spike_inputs[pop]['inh']['r'] = cfg.rxi
    
    cfg.rxe0_coefs = RXE0_COEFS
