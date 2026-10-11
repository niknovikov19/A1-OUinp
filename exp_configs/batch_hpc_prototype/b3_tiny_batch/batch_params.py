STIM_SEEDS = [1401, 1402, 1403, 1404]


def get_batch_params():
    """Return the four B3 simulation coordinates. """
    return {'stim_seed': list(STIM_SEEDS)}


def post_update(cfg):
    """Propagate the selected batch seed into the simulation config. """
    cfg.seeds['stim'] = cfg.stim_seed
