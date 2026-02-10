from pathlib import Path

import numpy as np
import pandas as pd

from cfg_base import cfg


# Duration
cfg.duration = 7 * 1e3

# Turn off the connections
cfg.addConn = 0

# Populations to use
POP_ACTIVE = 'IT5A'
cfg.pops_active = [POP_ACTIVE]
cfg.allpops = cfg.pops_active
if 'plotRaster' in cfg.analysis:
    cfg.analysis['plotRaster']['include'] = cfg.pops_active
if 'plotSpikeStats' in cfg.analysis:
    cfg.analysis['plotSpikeStats']['include'] = cfg.pops_active
if 'plotTraces' in cfg.analysis:
    cfg.analysis['plotTraces']['include'] = cfg.pops_active

cfg.analysis['plotSpikeStats'] = False

# Constant input increasing across the cells
# ("I" of the f-I curve)
cfg.add_ou_current = 1
cfg.ou_common = 1    # all pops receive the same OU input
cfg.ou_noise_duration = cfg.duration
cfg.ou_tau = 10
cfg.OUamp = [-0.02, 0.1]   # interpolate between 2 values from 1st to last cell
cfg.OUstd = 0   # zero std. -> constant input

# Mechanisms to modify
cfg.mech_changes = {
    'sec': 'all',
    'mech': 'kdr',
    'par': 'gbar',
    'mult': 1
}

# Strong ramp-up pulse for switching between the steady-states
cfg.ou_ramp_dur = 1000   # duration
cfg.ou_ramp_t0 = 3500    # start time
cfg.ou_ramp_offset = 1.75   # amplitude (current to soma)
cfg.ou_ramp_mult = 0
cfg.ou_ramp_type = 'up'

# NetStim inputs (weak, just to randomly jitter the cells between steady-states)
cfg.bkg_r = 150    # firing rate
cfg.bkg_w = 0.5   # weight
cfg.bkg_spike_inputs = {
    pop: {'r': cfg.bkg_r, 'w': cfg.bkg_w}
    for pop in cfg.pops_active
}

# Experiment folder and name
cfg.saveFolder = 'sim_output/' + (
    f'sim_{POP_ACTIVE}_{cfg.mech_changes["mech"]}'
    f'_mult_{cfg.mech_changes["mult"]}'
    f'_ouamp_{cfg.OUamp[0]}_{cfg.OUamp[1]}'
)
cfg.simLabel = '00005'

# Load a table of pop sizes
dirpath_self = Path(__file__).resolve().parent
fpath_csv = dirpath_self / 'pops_sz.csv'
pops_sz_df = pd.read_csv(fpath_csv)
pops_sz = pops_sz_df.set_index('pop')['ncells'].to_dict()

# Choose the cells to record voltages for each active pop.
ncells_rec = 500
cfg.pop_cells_rec = {}
for pop in cfg.allpops:
    N = np.minimum(pops_sz[pop], ncells_rec)
    cfg.pop_cells_rec[pop] = np.linspace(0, pops_sz[pop] - 1, N, dtype=int)

# Record voltage traces
cfg.recordCells = [(pop, list(cfg.pop_cells_rec[pop]))
                    for pop in cfg.allpops]
cfg.recordTraces = {
    'V_soma': {'sec': 'soma', 'loc': 0.5, 'var': 'v'}
}
cfg.recordStep =  0.1
""" cfg.analysis['plotTraces'] = {
    'include': [(pop, cells_rec) for pop in cfg.allpops],
    'timeRange': [0, cfg.duration],
    'oneFigPer': 'cell', 'overlay': False,
    'saveFig': True, 'showFig': False, 'figSize': (18, 12)
} """

# Update via batchtools
cfg.update_cfg()
