import numpy as np


N_RXE = 5
N_RXI = 5

pop_regions = {
    'SOM2': {'dmax': 12680, 'q': 0.175, 'rxe0': -2340, 'rxi0': 250, 'rxi_max': 8000},
    'SOM3': {'dmax': 12600, 'q': 0.175, 'rxe0': -2360, 'rxi0': 250, 'rxi_max': 8000},
    'SOM4': {'dmax': 13140, 'q': 0.165, 'rxe0': -2060, 'rxi0': 250, 'rxi_max': 8000},
    'SOM5A': {'dmax': 14170, 'q': 0.16, 'rxe0': -460, 'rxi0': 250, 'rxi_max': 8000},
    'SOM5B': {'dmax': 14190, 'q': 0.16, 'rxe0': -570, 'rxi0': 250, 'rxi_max': 8000},
    'SOM6': {'dmax': 13990, 'q': 0.175, 'rxe0': 3570, 'rxi0': 250, 'rxi_max': 8000},

    'PV2': {'dmax': 10270, 'q': 0.1675, 'rxe0': -11070, 'rxi0': 250.0, 'rxi_max': 7500},
    'PV3': {'dmax': 10140, 'q': 0.168, 'rxe0': -11070, 'rxi0': 250.0, 'rxi_max': 7500},
    'PV4': {'dmax': 12000, 'q': 0.1495, 'rxe0': -3690, 'rxi0': 250.0, 'rxi_max': 7500},
    'PV5A': {'dmax': 10820, 'q': 0.174, 'rxe0': 2960, 'rxi0': 250.0, 'rxi_max': 7500},
    'PV5B': {'dmax': 10840, 'q': 0.174, 'rxe0': 2970, 'rxi0': 250.0, 'rxi_max': 7500},
    'PV6': {'dmax': 10280, 'q': 0.167, 'rxe0': -3600, 'rxi0': 250.0, 'rxi_max': 7500},

    'NGF1': {'dmax': 28190, 'q': 0.115, 'rxe0': 24410, 'rxi0': 500, 'rxi_max': 7500},
    'NGF2': {'dmax': 27750, 'q': 0.115, 'rxe0': 24720, 'rxi0': 500, 'rxi_max': 7500},
    'NGF3': {'dmax': 27800, 'q': 0.115, 'rxe0': 25000, 'rxi0': 500, 'rxi_max': 7500},
    'NGF4': {'dmax': 28840, 'q': 0.112, 'rxe0': 23130, 'rxi0': 500, 'rxi_max': 7500},
    'NGF5A': {'dmax': 29020, 'q': 0.114, 'rxe0': 25040, 'rxi0': 500, 'rxi_max': 7500},
    'NGF5B': {'dmax': 29460, 'q': 0.113, 'rxe0': 25130, 'rxi0': 500, 'rxi_max': 7500},
    'NGF6': {'dmax': 32300, 'q': 0.114, 'rxe0': 23270, 'rxi0': 500, 'rxi_max': 7500}
}

def get_batch_params():
    """Generate params for batchtools to probe. """
    params = {
        'drxe_pos': np.linspace(0, 1, N_RXE).tolist(),
        'rxi_pos': np.linspace(0, 1, N_RXI).tolist()
    }
    return params

def post_update(cfg):
    """Called after cfg.update() """
    for pop in cfg.bkg_spike_inputs:
        rgn = pop_regions[pop]
        drxe = rgn['dmax'] * (cfg.drxe_pos - 1)
        rxi = rgn['rxi0'] + (rgn['rxi_max'] - rgn['rxi0']) * cfg.rxi_pos
        rxe = rgn['rxe0'] + (rxi - rgn['rxi0']) / rgn['q'] + drxe
        cfg.need_run = (rxe > 0)
        cfg.bkg_spike_inputs[pop]['exc']['r'] = rxe
        cfg.bkg_spike_inputs[pop]['inh']['r'] = rxi
    
    cfg.pop_regions = pop_regions
