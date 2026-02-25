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
from analysis.model_utils.split_conn import split_conn_by_sections
import diagnostics as diag


EXP_LABEL = 'it2'
POPS_USED = ['IT2']

# Background spiking input
RXE, RXI = 15000, 1500
WXE, WXI = 0.05, 0.25

# Target sections of bkg inputs
XE_SEC = 'Adend1'
#XE_SEC = 'soma'
XI_SEC = 'soma'
#XI_SEC = 'Adend1'

# Constant input to set Vrest
USE_IBKG = 1
V_REST = -70

# Surrogate inputs
SURR_INP_ON = 0

REC_TRACES = 1
PLOT_TRACES = 1

# Length-weighted random selection from sec lists
SEC_DISTR_BY_LEN = 1

DIAG = 0

# Load mech multipliers from json
MECH_FROM_JSON = 0

# Mechanism changes (for MECH_FROM_JSON=0)
GKDR_MULT = 1.5
GKAP_MULT = 1
GLEAK_MULT = 1
GCAT_MULT = 1
GCAL_MULT = 1
GCAN_MULT = 1
GKBK_MULT = 1
GIH_MULT = 1
GNAX_MULT = 1

# Use one cell per population
ONE_CELL = 1


def gen_exp_name_sub(cfg):
    t_limits = (cfg.t0_calc / 1000, cfg.duration / 1000)
    exp_name_sub = f'exp_{EXP_LABEL}'
    exp_name_sub += f'_rx_{RXE}_{RXI}_wx_{WXE}_{WXI}'
    exp_name_sub += f'_t_{t_limits[0]}_{t_limits[1]}'
    exp_name_sub += f'_xsec_{XE_SEC}_{XI_SEC}'
    if not MECH_FROM_JSON:
        mechs = {'gkdr': GKDR_MULT, 'gkap': GKAP_MULT, 'gl': GLEAK_MULT, 
                 'gih': GIH_MULT, 'gnax': GNAX_MULT, 'gkbk': GKBK_MULT}
        if (GCAT_MULT == 0) and (GCAL_MULT == 0) and (GCAN_MULT == 0):
            mechs |= {'gca': 0}
        else:
            mechs |= {'gcat': GCAT_MULT, 'gcal': GCAL_MULT,
                      'gcan': GCAN_MULT}                 
        for name, mult in mechs.items():
            if mult != 1:
                exp_name_sub += f'_{name}_{mult}'
    if ONE_CELL:
        exp_name_sub += '_1cell'
    return exp_name_sub


def get_mech_changes():
    if MECH_FROM_JSON:
        with open(dirpath_self / 'mech_changes_1.json', 'r') as fid:
            mech_changes = json.load(fid)
    else:
        mech_change_info = {
            'gkdr': ('kdr', 'gbar', GKDR_MULT),
            'gkap': ('kap', 'gbar', GKAP_MULT),
            'gleak': ('pas', 'g', GLEAK_MULT),
            'gcat': ('cat', 'gcatbar', GCAT_MULT),
            'gcal': ('cal', 'gcalbar', GCAL_MULT),
            'gcan': ('can', 'gcanbar', GCAN_MULT),
            'gkbk': ('kBK', 'gpeak', GKBK_MULT),
            'gih': ('ih', 'gbar', GIH_MULT),
            'gnax': ('nax', 'gbar', GNAX_MULT)
        }
        mech_changes = {}
        for pop in POPS_USED:
            for name, ch in mech_change_info.items():
                mech_changes[f'{name}_{pop}'] = {
                    'pop': f'{pop}_reduced', 'sec': 'all',
                    'mech': ch[0], 'par': ch[1], 'mult': ch[2]
                }
    return mech_changes


def apply_exp_cfg(cfg):

    # Duration
    cfg.duration = 5 * 1e3

    # Left point (ms) of the calculation time window (r, cv, ...)
    cfg.t0_calc = 1000

    # Populations to use
    pops_active = POPS_USED

    # Use one cell per population
    if ONE_CELL:
        cfg.singleCellPops = 1

    # Subnet parameters
    cfg.subnet_build_flag = SURR_INP_ON
    cfg.subnet_params = {
        'pops_active': pops_active,   
        'conns_frozen': 'all',   # all inputs are surrogate, no recurrent connections
        'fpath_frozen_rates': str(dirpath_self / 'target_state_1.csv'),   # surrogate input
    }

    if not SURR_INP_ON:
        cfg.pops_active = POPS_USED
        cfg.addConn = 0

    cfg.need_run = 1

    # Weight multipliers
    cfg.wmult = 0.25
    cfg.EEGain = 0.5

    # Connectivity params
    cfg.addSubConn = 0
    cfg.connRandomSecFromList = 1
    cfg.connWeightSecByLength = SEC_DISTR_BY_LEN

    if DIAG:
        cfg.createNEURONObj = True      # Create NEURON hoc objects
        cfg.createPyStruct = True       # Create Python structure
        cfg.saveCellSecs = True         # Save section data (includes hObj)
        cfg.saveCellConns = True        # Save connection data
        cfg.compactConnFormat = False   # Keep full dict format for conns
        cfg.includeParamsLabel=True

    # Background spiking input
    cfg.add_bkg_spike_input = 1
    cfg.replace_bkg_spikes_by_ou = 0   # use NetStim's
    cfg.bkg_spike_inputs = {}
    for n, pop in enumerate(POPS_USED):
        cfg.bkg_spike_inputs[pop] = {
            'exc': {'r': RXE, 'w': WXE, 'sec': XE_SEC, 'noise': 1,
                    'seed': cfg.seeds['stim'] + 10000 + n},
            'inh': {'r': RXI, 'w': WXI, 'sec': XI_SEC, 'noise': 1,
                    'seed': cfg.seeds['stim'] + 20000 + n},
        }
    
    # Static IClamp that sets the resting voltage
    if USE_IBKG:
        cfg.addIClamp = 1
        fname_ibkg = f'ibkg_mech1_vrest_{V_REST}.json'
        with open(dirpath_self / fname_ibkg, 'r') as fid:
            ibkg = json.load(fid)
        cfg.IClamp = {pop: {'amp': ibkg[pop]}
                      for pop in POPS_USED if pop in ibkg}

    # Determine cell mechs to modify
    cfg.mech_changes = get_mech_changes()

    if 'plotRaster' in cfg.analysis:
        cfg.analysis['plotRaster']['include'] = POPS_USED
    if 'plotSpikeStats' in cfg.analysis:
        cfg.analysis['plotSpikeStats']['include'] = POPS_USED
    if 'plotTraces' in cfg.analysis:
        cfg.analysis['plotTraces']['include'] = POPS_USED
    
    #cfg.analysis['plotRaster'] = False
    cfg.analysis['plotSpikeStats'] = False

    # Record voltage traces
    if REC_TRACES:
        if ONE_CELL:
            ncells_rec = 1
            ncells_plot = 1
        else:
            ncells_rec = 5
            ncells_plot = 3
        cfg.recordCells = [(pop, list(range(ncells_rec))) for pop in POPS_USED]
        cfg.recordTraces = {
            'V_soma': {'sec': 'soma', 'loc': 0.5, 'var': 'v'},
            'V_Adend1': {'sec': 'Adend1', 'loc': 0.5, 'var': 'v'},
            'ik_soma': {'sec': 'soma', 'loc': 0.5, 'var': 'ik'},
            'ik_Adend1': {'sec': 'Adend1', 'loc': 0.5, 'var': 'ik'},
        }
        cfg.recordStep =  0.1
        if PLOT_TRACES:
            cfg.analysis['plotTraces'] = {
                'include': [(pop, list(range(ncells_plot))) for pop in cfg.allpops],
                'timeRange': [1500, cfg.duration],
                'oneFigPer': 'cell', 'overlay': False,
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
            if v['mech'] in sec['mechs']:
                sec['mechs'][v['mech']][v['par']] *= v['mult']
                #sec['mechs'][v['mech']][v['par']] += v['add']
    
    # Set target sections from json file
    with open(dirpath_self / 'target_sec_1.json', 'r') as fid:
        target_sec = json.load(fid)
    for cname, conn in params.connParams.items():
        pop_pre = conn['preConds'].get('pop', None)
        pop_post = conn['postConds'].get('pop', None)
        if (pop_pre is None) or (pop_post is None):
            raise ValueError(f'Pre or post pop is not specified for conn {cname}')
        conn['sec'] = None
        for _, ts in target_sec.items():
            if (pop_pre in ts['pops_pre']) and (pop_post in ts['pops_post']):
                #print(f'Sec info: {cname} {ts_name}')
                conn['sec'] = ts['sec']
                break
        if conn['sec'] is None:
            raise ValueError(f'No target sec info found for conn {cname}')
    

def post_run(sim):
    """Called in the end of a job (after runnig and saving). """

    cfg = sim.cfg
    exp_name = cfg.simLabel

    # Metric calculation time interval in seconds
    t_limits = (cfg.t0_calc / 1000, cfg.duration / 1000)

    # Experiment sub-name
    exp_name_sub = gen_exp_name_sub(cfg)

    # Create a subfolder to put the results
    dirpath_res = Path(cfg.saveFolder)
    dirpath_res_sub = dirpath_res / exp_name_sub
    os.makedirs(dirpath_res_sub, exist_ok=True)

    # Move results to the subfolder
    res_names = ['cfg.json', 'netParams.json', 'raster.png', 'data.pkl']
    for res_name in res_names:
        fname = f'{exp_name}_{res_name}'
        if (dirpath_res / fname).exists():
            (dirpath_res / fname).rename(dirpath_res_sub / fname)
        
    # Move traces to the subfodler
    #os.makedirs(dirpath_res_sub / 'traces', exist_ok=True)
    for fpath in dirpath_res.glob(f'{exp_name}_*traces*.png'):
        #fpath.rename(dirpath_res_sub / 'traces' / fpath.name)
        fpath.rename(dirpath_res_sub / fpath.name)
    
    # Save rates, CVs, voltage stats, and timings to a json file
    res = {}
    res['timing'] = sim.timingData
    res |= proc.calc_rates_and_cvs(sim, t_limits, nspikes_min=3)
    if REC_TRACES:
        res |= proc.calc_v_stats(sim, t_limits, med_win=0.05)
    fpath_res = dirpath_res_sub / f'{exp_name}_result.json'
    with open(fpath_res, 'w') as fid:
        json.dump(res, fid, indent=4)


def final(sim):
    if not DIAG:
        return

    diag.count_conns(sim)
    diag.count_synmechs(sim)
    diag.count_netcons_neuron(sim)
    #diag.count_pointprocesses(sim)
    diag.report_min_delay(sim)
    #diag.conn_distance_percentiles(sim)

    # Count post-synaptic sections
    pops_pre = ['ITP4frz']
    pops_post = ['ITP4']
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
    if sim.rank == 0:
        print('Conn targets by sec group:', sec_counts)
        #diag.print_cell_nseg(sim, 'IT2')