import numpy as np


# Target sec of the main tonic input (I)
#I_SEC = 'Adend1'
I_SEC = 'soma'

# Target sec of the weak spiking input
BKG_SEC = 'soma'

#AMP_VALS = [0.5, 0.75, 1, 1.25, 1.5, 1.75, 2]
#AMP_VALS = [0.75, 1.5]
#AMP_VALS = [0.25, 1, 2]
AMP_VALS = [-4, -2, 2, 4]
#RX_VALS = [50, 75, 100, 125, 150]
#RX_VALS = [1, 50, 100, 150]
RX_VALS = [1, 250, 500]
WX_VALS = [1]
#RX_VALS = [5000, 10000, 15000]
#WX_VALS = [0.01]


def get_batch_params():
    """Generate params for batchtools to probe. """
    params = {
        'ou_ramp_offset': AMP_VALS,
        'bkg_r': RX_VALS,
        'bkg_w': WX_VALS
    }
    return params


def post_update(cfg):
    """Called after cfg.update() """
    
    cfg.bkg_spike_inputs = {
        pop: {'exc': {
            'r': cfg.bkg_r, 'w': cfg.bkg_w, 'sec': BKG_SEC
        }}
        for pop in cfg.pops_active
    }
