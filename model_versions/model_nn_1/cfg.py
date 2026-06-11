import json
from pathlib import Path

from netpyne.batchtools import specs


DIRPATH_SELF = Path(__file__).resolve().parent


def _load_cfg():
    """Load the experiment config from the local JSON bundle."""
    with open(DIRPATH_SELF / 'cfg_base.json', 'r') as fid:
        data = json.load(fid)
    return specs.SimConfig(data['simConfig'])


def _iter_iclamp_entries(iclamp):
    for entry in iclamp.values():
        if isinstance(entry, list):
            for item in entry:
                yield item
        else:
            yield entry


def set_main_seed(cfg, seed_main):
    """Update the seed bundle used by background inputs and subnet build."""
    cfg.seed_main = int(seed_main)
    cfg.seeds['stim'] = int(seed_main)
    cfg.seeds['conn'] = int(seed_main) * 2

    subnet_params = getattr(cfg, 'subnet_params', None)
    if subnet_params is not None:
        subnet_params['global_seed'] = int(seed_main) * 3

    bkg_inputs = getattr(cfg, 'bkg_spike_inputs', None)
    if bkg_inputs:
        for n, pop in enumerate(bkg_inputs):
            bkg_inputs[pop]['exc']['seed'] = cfg.seeds['stim'] + 10000 + n
            bkg_inputs[pop]['inh']['seed'] = cfg.seeds['stim'] + 20000 + n


def set_duration_bundle(cfg, duration, t0_calc=None, update_iclamp=True):
    """Convenience helper for common timing edits after loading JSON config."""
    cfg.duration = float(duration)
    if t0_calc is not None:
        cfg.t0_calc = float(t0_calc)

    if hasattr(cfg, 'printPopAvgRates') and len(cfg.printPopAvgRates) >= 2:
        cfg.printPopAvgRates[1] = cfg.duration

    if update_iclamp and getattr(cfg, 'IClamp', None):
        for entry in _iter_iclamp_entries(cfg.IClamp):
            if isinstance(entry, dict) and 'dur' in entry:
                entry['dur'] = cfg.duration


def scale_wmat(cfg, factor):
    """Apply an intentional manual global weight scale after loading cfg_base."""
    factor = float(factor)
    for post_weights in cfg.wmat.values():
        for post in post_weights:
            post_weights[post] *= factor


cfg = _load_cfg()


# User overrides
# Edit loaded values here when exploring a variant of the experiment.
# Examples:
# cfg.EEGain = 0.5
# scale_wmat(cfg, 1.1)
# set_main_seed(cfg, 1111)
# set_duration_bundle(cfg, 5000.0, t0_calc=3000.0)
# cfg.recordCells = [('IT2', [0, 1])]
# cfg.recordTraces = {'V_soma': {'sec': 'soma', 'loc': 0.5, 'var': 'v'}}
# cfg.recordLFP = False
# cfg.analysis['plotRaster']['saveFig'] = False
# cfg.fader_pts = [(0, 0), (3000, 0), (5000, 1), (cfg.duration, 1)]
# cfg.pulse_seq_params['weight'] = 0.1
