STIM_SEEDS = [1501, 1502]


def get_batch_params():
    """Return one successful and one intentionally failing coordinate. """
    return {'stim_seed': list(STIM_SEEDS)}


def post_update(cfg):
    """Propagate the selected batch seed into the simulation config. """
    cfg.seeds['stim'] = cfg.stim_seed
