import json
import os
from pathlib import Path
import sys

dirpath_repo_root = Path(__file__).resolve().parents[3]
dirpath_self = Path(__file__).resolve().parent
sys.path.append(str(dirpath_repo_root))
sys.path.append(str(dirpath_self))

import matplotlib.pyplot as plt
import numpy as np

from analysis.ou_tuning import sim_res_proc_utils as proc
import diagnostics as diag
from analysis.model_utils.split_conn import split_conn_by_sections


EXP_LABEL = 'it2_som2'
POPS_USED = ['IT2', 'SOM2']

#RXE, RXI = 15000, 2000
RXE, RXI = 250, 1
WXE, WXI = 1.25, 5

USE_IBKG = 1
V_REST = -70

REC_TRACES = 0
PLOT_TRACES = 1

ADD_SUBCON = 0

# SUBCON_USED = None   # don't modify subConnParams
#SUBCON_USED = ['E->E2,3,4', 'E->I', 'SOM->E']
SUBCON_USED = ['E->E2,3,4']
SUBCON_NAME = 'ee'

# Split conns from sec-list 1-sec form (length-based)
SPLIT_CONNS = 1

# Choose a section from a list: 0=first, 1=random
RAND_SEC = 1

# Uniformly distribute locs within a section
UNI_LOCS = 1

# Number of different loc values (used when UNI_LOCS=0)
N_LOCS = 1

CONN_MOD = [
    {'name': 'EE_IT2_IT2_2', 'label': 'ee', 'sec': 'proximal'}
]


def apply_exp_cfg(cfg):

    # Duration
    cfg.duration = 3 * 1e3

    # Left point (ms) of the calculation time window (r, cv, ...)
    cfg.t0_calc = 2000

    # Populations to use
    cfg.pops_active = POPS_USED

    # Weight multipliers
    cfg.wmult = 0.25
    cfg.EEGain = 0.5

    # Turn connections on / off
    cfg.addConn = 1

    # Turn subConn on / off
    cfg.addSubConn = ADD_SUBCON

    # Choose a section from a list: 0=first, 1=random
    cfg.connRandomSecFromList = RAND_SEC

    cfg.createNEURONObj = True      # Create NEURON hoc objects
    cfg.createPyStruct = True       # Create Python structure
    cfg.saveCellSecs = True         # Save section data (includes hObj)
    cfg.saveCellConns = True        # Save connection data
    cfg.compactConnFormat = False   # Keep full dict format for conns
    cfg.includeParamsLabel=True

    # Background spiking input
    cfg.add_bkg_spike_input = 1
    cfg.bkg_spike_inputs = {}
    for n, pop in enumerate(POPS_USED):
        cfg.bkg_spike_inputs[pop] = {
            'exc': {'r': RXE, 'w': WXE, 'sec': 'apic', 'noise': 1,
                    'seed': cfg.seeds['stim'] + 10000 + n},
            'inh': {'r': RXI, 'w': WXI, 'sec': 'soma', 'noise': 1,
                    'seed': cfg.seeds['stim'] + 20000 + n},
        }
    
    # Static IClamp that sets the resting voltage
    if USE_IBKG:
        cfg.addIClamp = 1
        fname_ibkg = f'ibkg_mech1_vrest_{V_REST}.json'
        with open(dirpath_self / fname_ibkg, 'r') as fid:
            ibkg = json.load(fid)
        cfg.IClamp = {pop: {'amp': ibkg[pop]} for pop in POPS_USED
                      if pop in ibkg}

    # Cell mechanisms to modify
    with open(dirpath_self / 'mech_changes_1.json', 'r') as fid:
        cfg.mech_changes = json.load(fid)

    if 'plotRaster' in cfg.analysis:
        cfg.analysis['plotRaster']['include'] = POPS_USED
    if 'plotSpikeStats' in cfg.analysis:
        cfg.analysis['plotSpikeStats']['include'] = POPS_USED
    if 'plotTraces' in cfg.analysis:
        cfg.analysis['plotTraces']['include'] = POPS_USED
    
    cfg.analysis['plotRaster'] = False
    cfg.analysis['plotSpikeStats'] = False

    # Record voltage traces
    if REC_TRACES:
        ncells_rec = 5
        ncells_plot = 2
        cfg.recordCells = [(pop, list(range(ncells_rec))) for pop in POPS_USED]
        cfg.recordTraces = {'V_soma': {'sec': 'soma', 'loc': 0.5, 'var': 'v'}}
        cfg.recordStep =  0.1
        if PLOT_TRACES:
            cfg.analysis['plotTraces'] = {
                'include': [(pop, list(range(ncells_plot))) for pop in cfg.allpops],
                'timeRange': [1000, cfg.duration],
                'oneFigPer': 'cell', 'overlay': True,
                'saveFig': True, 'showFig': False, 'figSize': (18, 12)
            }


def modify_net_params(cfg, params):
    """Applied after netParams creation. """

    # Modify membrane mechanisms
    for v in cfg.mech_changes.values():
        secs_all = params.cellParams[v['pop']]['secs']
        if v['sec'] == 'all':
            secs = list(secs_all.values())
        else:
            secs = [secs_all[v['sec']]]
        for sec in secs:
            sec['mechs'][v['mech']][v['par']] *= v['mult']
            sec['mechs'][v['mech']][v['par']] += v['add']
    
    # Possible loc values
    if UNI_LOCS:
        locs = 'uniform(0, 1)'
    else:
        if N_LOCS == 1:
            locs = 0.5
        else:
            l = 1 / N_LOCS
            locs_ = np.round(np.arange(0, 1, l) + 0.5 * l, 3).tolist()
            locs = f'[{", ".join(locs_)}][int(rand.discunif(0, {N_LOCS - 1}))]'
    
    # Modify connections
    for c in CONN_MOD:
        params.connParams[c['name']]['sec'] = c['sec']
        params.connParams[c['name']]['loc'] = (
            'uniform(0, 1)' if UNI_LOCS else 0.5)
        if SPLIT_CONNS:
            split_conn_by_sections(params, c['name'])
    
    # Subconn
    if ADD_SUBCON and (SUBCON_USED is not None):
        params.subConnParams = {
            c: params.subConnParams[c] for c in SUBCON_USED
        }


def gen_exp_name_sub(sim):
    cfg = sim.cfg
    t_limits = (cfg.t0_calc / 1000, cfg.duration / 1000)
    exp_name_sub = f'exp_{EXP_LABEL}'
    exp_name_sub += f'_rx_{RXE}_{RXI}_wx_{WXE}_{WXI}'
    exp_name_sub += f'_conn_{cfg.addConn}'
    subcon_str = SUBCON_NAME if ADD_SUBCON else '0'
    exp_name_sub += f'_subcon_{subcon_str}'
    exp_name_sub += f'_t_{t_limits[0]}_{t_limits[1]}'
    if USE_IBKG:
        exp_name_sub += f'_vrest_{V_REST}'
    exp_name_sub += f'_wmult_{cfg.wmult}_ee_{cfg.EEGain}'
    exp_name_sub += f'_randsec_{RAND_SEC}'
    exp_name_sub += f'_splitcon_{SPLIT_CONNS}'
    if UNI_LOCS:
        exp_name_sub += '_loc_uni'
    else:
        exp_name_sub += f'_loc_{N_LOCS}'
        
    if len(CONN_MOD) > 0:
        mods = []
        for c in CONN_MOD:
            mods.append(f"{c['label']}_{c['sec']}")
        exp_name_sub += '_seclst_' + '_'.join(mods)

    return exp_name_sub


def post_run(sim):
    """Called in the end of a job (after runnig and saving). """

    cfg = sim.cfg
    exp_name = cfg.simLabel

    # Metric calculation time interval in seconds
    t_limits = (cfg.t0_calc / 1000, cfg.duration / 1000)

    exp_name_sub = gen_exp_name_sub(sim)

    # Create a subfolder to put the results
    dirpath_res = Path(cfg.saveFolder)
    dirpath_res_sub = dirpath_res / exp_name_sub
    os.makedirs(dirpath_res_sub, exist_ok=True)

    # Move results to the subfolder
    res_names = ['cfg.json', 'netParams.json', 'raster.png']
    for res_name in res_names:
        fname = f'{exp_name}_{res_name}'
        if (dirpath_res / fname).exists():
            (dirpath_res / fname).rename(dirpath_res_sub / fname)
        
    # Move traces to the subfodler
    os.makedirs(dirpath_res_sub / 'traces', exist_ok=True)
    for fpath in dirpath_res.glob(f'{exp_name}_*traces*.png'):
        fpath.rename(dirpath_res_sub / 'traces' / fpath.name)
    
    # Save rates, CVs, voltage stats, and timings to a json file
    res = proc.calc_rates_and_cvs(sim, t_limits, nspikes_min=3)
    res |= proc.calc_v_stats(sim, t_limits, med_win=0.05)
    res['timing'] = sim.timingData
    fpath_res = dirpath_res_sub / f'{exp_name}_result.json'
    with open(fpath_res, 'w') as fid:
        json.dump(res, fid, indent=4)
    

def final(sim):
    diag.count_conns(sim)
    diag.count_synmechs(sim)
    diag.count_netcons_neuron(sim)
    #diag.count_pointprocesses(sim)
    diag.report_min_delay(sim)
    #diag.conn_distance_percentiles(sim)

    # Count post-synaptic sections
    #pops_pre = ['IT2', 'SOM2']
    pops_pre = ['IT2']
    pops_post = ['IT2']
    sec_groups = {
        'soma': ['soma'],
        #'Adend': ['Adend1', 'Adend2', 'Adend3'],
        'Bdend': ['Bdend'],
        'Adend1': ['Adend1'],
        'Adend2': ['Adend2'],
        'Adend3': ['Adend3']
    }
    sec_counts = diag.count_conn_target_secs(
        sim, sec_groups, pops_pre, pops_post)

    # Output folder
    exp_name_sub = gen_exp_name_sub(sim)
    dirpath_res = Path(sim.cfg.saveFolder)
    dirpath_res_sub = dirpath_res / exp_name_sub

    # Timings
    timings = {'duration': sim.cfg.duration}
    t_keys_used = ['runTime', 'totalTime']
    timings |= {k: sim.timingData[k] for k in t_keys_used}

    if ADD_SUBCON: subcon = SUBCON_USED or 'ALL'
    else: subcon = 'NONE'

    if sim.rank == 0:
        # Save diagnostic info
        res = {
            'subConn': subcon,
            'connRandomSecFromList': RAND_SEC,
            'conn_targets': {
                'pops_pre': pops_pre,
                'pops_post': pops_post,
                'sec_groups': sec_groups,
                'sec_counts': sec_counts
            },
            'timings': timings
        }
        fpath_res = dirpath_res_sub / f'diag.json'
        with open(fpath_res, 'w') as fid:
            json.dump(res, fid, indent=4)
        
        # Print diagnostic info
        print('Conn targets by sec group:', sec_counts)

        diag.print_cell_nseg(sim, 'IT2')
    