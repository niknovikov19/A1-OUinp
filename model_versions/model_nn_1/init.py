"""
init.py

Old-style entrypoint for the model_nn_1 non-batch workflow.
"""

import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import numpy as np

from netpyne.batchtools import comm
from netpyne import sim

from cfg import cfg
from conn_fader import ConnFader
from netParams import netParams


def setdminID(sim, lpop):
    """Cache gid ranges used by downstream helpers and saved sim data."""
    alltags = sim._gatherAllCellTags()
    dGIDs = {pop: [] for pop in lpop}
    for tinds in range(len(alltags)):
        if alltags[tinds]['pop'] in lpop:
            dGIDs[alltags[tinds]['pop']].append(tinds)
    sim.simData['dminID'] = {
        pop: np.amin(dGIDs[pop]) for pop in lpop if len(dGIDs[pop]) > 0
    }
    sim.simData['dmaxID'] = {
        pop: np.amax(dGIDs[pop]) for pop in lpop if len(dGIDs[pop]) > 0
    }
    sim.simData['dnumc'] = {
        pop: np.amax(dGIDs[pop]) - np.amin(dGIDs[pop])
        for pop in lpop if len(dGIDs[pop]) > 0
    }


def setCochCellLocationsX(cfg, netParams, pop, scale):
    """Reconstruct cochlear x positions when cochlear input is enabled."""
    if pop not in sim.net.pops:
        return
    for cell in sim.net.cells:
        if cell.gid not in sim.net.pops[pop].cellGids:
            continue
        cf = netParams.cf[cell.gid - sim.simData['dminID'][pop]]
        if cfg.cochThalFreqRange[0] <= cf <= cfg.cochThalFreqRange[1]:
            cellx = scale * (
                (cf - cfg.cochThalFreqRange[0]) /
                (cfg.cochThalFreqRange[1] - cfg.cochThalFreqRange[0])
            )
        else:
            cellx = 100000000
        cell.tags['x'] = cellx
        cell.tags['xnorm'] = cellx / netParams.sizeX
        cell.updateShape()


def _save_netparams_stripped(netParams, fpath):
    """Avoid saving large VecStim spike-time arrays in the exported netParams JSON."""
    data = netParams.todict()
    for pop in data.get('popParams', {}).values():
        if isinstance(pop, dict) and pop.get('cellModel') == 'VecStim':
            pop.pop('spkTimes', None)
    sim.saveJSON(fpath, {'net': {'params': data}})


def _as_list(value):
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _lists_intersect(list1, list2):
    return bool(set(list1) & set(list2))


def _get_cond_pops(conds):
    if 'pop' in conds:
        return _as_list(conds['pop'])
    if 'cellType' in conds:
        pops = []
        cell_types = _as_list(conds['cellType'])
        for pop, par in sim.net.params.popParams.items():
            if par.get('cellType') in cell_types:
                pops.append(pop)
        return pops
    return []


def _get_2pop_conns(pops_pre, pops_post):
    pops_pre = _as_list(pops_pre)
    pops_post = _as_list(pops_post)
    conns = []
    for conn_name, conn in sim.net.params.connParams.items():
        conn_pops_pre = _get_cond_pops(conn['preConds'])
        conn_pops_post = _get_cond_pops(conn['postConds'])
        if (_lists_intersect(pops_pre, conn_pops_pre) and
                _lists_intersect(pops_post, conn_pops_post)):
            conns.append(conn_name)
    return conns


def _parse_split_pairs(cfg):
    split_cfg = getattr(cfg, 'subnet_params', {}).get('conns_split', {})
    if isinstance(split_cfg, dict):
        raw_pairs = split_cfg.keys()
    else:
        raw_pairs = split_cfg

    split_pairs = []
    for pair in raw_pairs:
        if isinstance(pair, str):
            pop_pre, pop_post = [part.strip() for part in pair.split(',', 1)]
        else:
            pop_pre, pop_post = pair
        split_pairs.append((pop_pre, pop_post))
    return split_pairs


def _setup_fader(sim):
    """Attach runtime modulators that cross-fade recurrent and frozen inputs."""
    if not getattr(sim.cfg, 'fader_on', 0):
        return

    split_pairs = _parse_split_pairs(sim.cfg)
    fader_pts = getattr(sim.cfg, 'fader_pts', [])
    if not split_pairs or not fader_pts:
        return

    conns_pos, conns_neg = [], []
    for pop_pre, pop_post in split_pairs:
        conns_pos.extend(_get_2pop_conns(pop_pre, pop_post))
        conns_neg.extend(_get_2pop_conns(pop_pre + 'frz', pop_post))

    fader = ConnFader(sim, T=sim.cfg.duration, dt=sim.cfg.dt)
    fader.add_conn_group(
        group_name=getattr(sim.cfg, 'fader_group_name', 'ee'),
        conns_pos=conns_pos,
        conns_neg=conns_neg,
        pts=fader_pts,
    )
    fader.create_modulators()
    fader.connect_modulators()
    fader.setup_recording(rec_dt=getattr(sim.cfg, 'fader_rec_dt', 1.0))
    sim.ee_fader = fader


# Save the loaded config and transformed netParams before any run starts
comm.initialize()

Path(cfg.saveFolder).mkdir(parents=True, exist_ok=True)
if comm.is_host():
    cfg.save(f'{cfg.saveFolder}/{cfg.simLabel}_cfg.json')
    _save_netparams_stripped(netParams, f'{cfg.saveFolder}/{cfg.simLabel}_netParams.json')

need_run = getattr(cfg, 'need_run', True)
if need_run:
    # Follow the classic NetPyNE initialization and build sequence
    sim.initialize(simConfig=cfg, netParams=netParams)
    sim.net.createPops()
    sim.net.createCells()

    # Cache instantiated cells and pops on the simulation object
    sim.net.allCells = [cell.__getstate__() for cell in sim.net.cells]
    sim.net.allPops = {
        label: pop.__getstate__() for label, pop in sim.net.pops.items()
    }

    setdminID(sim, cfg.allpops)

    if cfg.cochlearThalInput:
        setCochCellLocationsX(cfg, netParams, 'cochlea', cfg.sizeX)

    sim.net.connectCells()
    sim.net.addStims()
    sim.setupRecording()
    _setup_fader(sim)

    print('Rank/nhosts:', sim.rank, sim.nhosts, flush=True)
    print('Local cells:', len(sim.net.cells), flush=True)

    # Run the simulation and emit the standard NetPyNE outputs
    sim.runSim()
    sim.gatherData()
    sim.saveData()
    sim.analysis.plotData()

    if comm.is_host():
        # Save a small summary JSON alongside the standard outputs
        avgRates = sim.analysis.popAvgRates(
            tranges=[cfg.duration - 1000, cfg.duration],
            show=False,
        )
        with open(f'{cfg.saveFolder}/{cfg.simLabel}_result.json', 'w') as fid:
            json.dump({'rates': avgRates}, fid, indent=4)
else:
    print(f'>>>>>>>>>>> {cfg.simLabel} SKIPPED', flush=True)
