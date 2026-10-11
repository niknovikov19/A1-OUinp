STIM_SEEDS = [1301, 1302]


def get_batch_params():
    """Return the two B2 simulation coordinates. """
    return {'stim_seed': list(STIM_SEEDS)}


def post_update(cfg):
    """Propagate the selected batch seed into the simulation config. """
    cfg.seeds['stim'] = cfg.stim_seed
