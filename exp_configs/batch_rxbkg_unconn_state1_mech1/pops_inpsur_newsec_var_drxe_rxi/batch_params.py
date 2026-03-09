import numpy as np


N_DRXE = 20
N_RXI = 20


def get_batch_params():
    """Generate params for batchtools to probe. """
    params = {
        'drxe_num': np.arange(N_DRXE).tolist(),
        'rxi_num': np.arange(N_RXI).tolist()
    }
    return params


def post_update(cfg):
    """Called after cfg.update() """

    pops_used = []

    cfg.need_run = True
    for pop in cfg.bkg_spike_inputs:

        rgn = cfg.drxe_rxi_regions['regions'][pop]
        rxe0, rxi0 = rgn['rxe0'], rgn['rxi0']
        drxe, drxi = rgn['drxe'], rgn['drxi']
        k = rgn['rxi_rxe_slope']

        rxi_vals = np.linspace(rxi0, rxi0 + drxi, N_RXI)
        rxi = rxi_vals[cfg.rxi_num]

        rxe1 = rxe0 + (rxi - rxi0) / k
        rxe_vals = np.linspace(rxe1 - drxe, rxe1, N_DRXE)
        rxe = rxe_vals[cfg.drxe_num]

        if rxe == 0: rxe = 1e-3
        if rxi == 0: rxi = 1e-3

        if (rxe > 0) and (rxi > 0):
            pops_used.append(pop)

        cfg.bkg_spike_inputs[pop]['exc']['r'] = rxe
        cfg.bkg_spike_inputs[pop]['inh']['r'] = rxi
    
    if len(pops_used) == 0:
        cfg.need_run = 0
    
    if cfg.subnet_build_flag:
        cfg.subnet_params['pops_active'] = pops_used
    else:
        cfg.pops_active = pops_used
    
    cfg.bkg_spike_inputs = {
        pop: inp
        for pop, inp in cfg.bkg_spike_inputs.items()
        if pop in pops_used
    }
