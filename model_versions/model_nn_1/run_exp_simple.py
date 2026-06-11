import json
import os
from types import SimpleNamespace

import matplotlib
matplotlib.use('Agg')  # to avoid graphics error on servers
import numpy as np

from netpyne.batchtools import comm, specs
from netpyne import sim
from neuron import h

from collect_cell_gids import _collect_cell_gids


def setdminID(sim, lpop):
    # Setup min, max ID and dnumc for each population in lpop
    # Gather cell tags; see https://github.com/Neurosim-lab/netpyne/blob/development/netpyne/sim/gather.py
    alltags = sim._gatherAllCellTags()
    dGIDs = {pop: [] for pop in lpop}
    for tinds in range(len(alltags)):
        if alltags[tinds]['pop'] in lpop:
            dGIDs[alltags[tinds]['pop']].append(tinds)
    sim.simData['dminID'] = {pop: np.amin(
        dGIDs[pop]) for pop in lpop if len(dGIDs[pop]) > 0}
    sim.simData['dmaxID'] = {pop: np.amax(
        dGIDs[pop]) for pop in lpop if len(dGIDs[pop]) > 0}
    sim.simData['dnumc'] = {pop: np.amax(
        dGIDs[pop]) - np.amin(dGIDs[pop]) for pop in lpop if len(dGIDs[pop]) > 0}


def _save_netparams_stripped(netParams, fpath):
    """Save netParams JSON with spkTimes stripped from VecStim pops.

    The in-memory netParams object is not modified; spkTimes are only omitted
    from the written file to keep file sizes manageable.
    """
    d = netParams.todict()
    for pop in d.get('popParams', {}).values():
        if isinstance(pop, dict) and pop.get('cellModel') == 'VecStim':
            pop.pop('spkTimes', None)
    sim.saveJSON(fpath, {'net': {'params': d}})


# Initialize config object, common for every experiment of the model
cfg = None

# Create netParams based on the config
netParams = None


# Needed for fader
cfg.includeParamsLabel = True
cfg.cache_efficient = 0

# Fader params
FADER_PTS = []
CONNS_SPLIT = []
cfg.subnet_params['conns_split'] = {
    f'{c[0]}, {c[1]}': 0.5 for c in CONNS_SPLIT
}

# TODO
def _rule_kind_and_base_pops(conn): pass
def _relabel_conn_synmech(netParams, conn, kind): pass

# Set distinct synMech labels for surrogate and recurrent inputs
split_pairs = set(CONNS_SPLIT)
rank = int(h.ParallelContext().id())
for cname, conn in netParams.connParams.items():
    kind, pops_pre_base, pops_post = _rule_kind_and_base_pops(
        conn  #, verbose=(rank == 0)
    )
    if kind is None:
        continue
    needs_split = any(
        (p_pre, p_post) in split_pairs
        for p_pre in pops_pre_base
        for p_post in pops_post
    )
    if needs_split:
        _relabel_conn_synmech(netParams, conn, kind)

# Create a folder for the results
os.makedirs(cfg.saveFolder, exist_ok=True)

comm.initialize()

# Save cfg and netParams into the output folder
if comm.is_host():
    fpath_cfg = "{}/{}_cfg.json".format(cfg.saveFolder, cfg.simLabel)
    print(f'Saving to {fpath_cfg}', flush=True)
    cfg.save(fpath_cfg)
    _save_netparams_stripped(netParams, '{}/{}_netParams.json'.format(cfg.saveFolder, cfg.simLabel))

# Run or skip
if hasattr(cfg, 'need_run'):
    need_run = cfg.need_run
else:
    need_run = True

if need_run:
    # Initialize
    sim.initialize(simConfig=cfg, netParams=netParams)

    # Create populations
    sim.net.createPops()

    # Create cells
    sim.net.createCells()

    # Collect cells and pops
    sim.net.allCells = [cell.__getstate__() for cell in sim.net.cells]
    sim.net.allPops = {label: pop.__getstate__()
                       for label, pop in sim.net.pops.items()}

    # Set min/max cell gid for each population
    setdminID(sim, cfg.allpops)

    # Create connections and external inputs
    sim.net.connectCells()      # create connections between cells based on params
    #print('Adding stims...', flush=True)
    sim.net.addStims() 			# add network stimulation

    import warnings
    warnings.simplefilter('once')

    # Extract min/max cell gid for every pop. across ranks into sim._pop_gid_range
    _collect_cell_gids()

    # Setup variables to record for each cell (spikes, V traces, etc)
    sim.setupRecording()
    
    print("Rank/nhosts:", sim.rank, sim.nhosts, flush=True)
    print("Local cells:", len(sim.net.cells), flush=True)

    from analysis.model_utils.net_utils import get_2pop_conns
    from conn_fader import ConnFader

    # Find recurrent/surrogate conns for positive/inverse modulation
    conns_pos, conns_neg = [], []
    for pop_pre, pop_post in CONNS_SPLIT:
        conns_pos_ = get_2pop_conns(sim, pop_pre, pop_post)   # recurrent conns
        conns_neg_ = get_2pop_conns(sim, pop_pre + 'frz', pop_post)   # surrogate inputs
        conns_pos += conns_pos_
        conns_neg += conns_neg_
    
    # Setup the fader
    fader = ConnFader(
        sim, T=sim.cfg.duration, dt=sim.cfg.dt    
    )
    fader.add_conn_group(
        group_name='ee',
        conns_pos=conns_pos,
        conns_neg=conns_neg,
        pts=FADER_PTS
    )
    fader.create_modulators()
    fader.connect_modulators()
    fader.setup_recording(rec_dt=1)
    sim.ee_fader = fader

    # Run
    #if sim.rank == 0:
    print(f'Rank {sim.rank}: running...', flush=True)
    sim.runSim()               # run parallel Neuron simulation
    #if sim.rank == 0:
    #    print(f'Gathering the results...', flush=True)
    sim.gatherData()
    
    # Save and plot the result
    sim.saveData()
    sim.analysis.plotData()    # plot spike raster etc

# Finalize
if comm.is_host():
    _save_netparams_stripped(netParams, "{}/{}_params.json".format(cfg.saveFolder, cfg.simLabel))
    print('transmitting data...')
    inputs = cfg.get_mappings()
    
    if need_run:    
        # Save average firing rates to a separate json file
        avgRates = sim.analysis.popAvgRates(
            tranges=[cfg.duration - 1000, cfg.duration],
            show=False
        )
        fpath_res = '{}/{}_result.json'.format(cfg.saveFolder, cfg.simLabel)
        with open(fpath_res, 'w') as fid:
            json.dump({'rates': avgRates}, fid, indent=4)

    else:
        print(f'>>>>>>>>>>> {cfg.simLabel} SKIPPED', flush=True)
        avgRates = {}
        sim = SimpleNamespace(cfg=cfg)

    # Finish and report to batchtools
    batch_metrics = {}
    comm.send({'done': 1, **batch_metrics})
    comm.close()
