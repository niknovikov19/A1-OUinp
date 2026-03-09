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

from batch_params import N_DRXE, N_RXI


#EXP_LABEL = 'it2'
#POPS_USED = ['IT2']
#EXP_LABEL = 'pyr'
#POPS_USED = ['IT2', 'IT3', 'ITS4', 'ITP4', 'IT5A', 'CT5A',
#             'IT5B', 'CT5B', 'PT5B', 'IT6', 'CT6']
#EXP_LABEL = 'pv'
#POPS_USED = ['PV2', 'PV3', 'PV4', 'PV5A', 'PV5B', 'PV6']
#EXP_LABEL = 'it5a'
#POPS_USED = ['IT5A']
#EXP_LABEL = 'som'
#POPS_USED = ['SOM2', 'SOM3', 'SOM4', 'SOM5A', 'SOM5B', 'SOM6']
#EXP_LABEL = 'vip'
#POPS_USED = ['VIP2', 'VIP3', 'VIP4', 'VIP5A', 'VIP5B', 'VIP6']
#EXP_LABEL = 'tc'
#POPS_USED = ['TC']
EXP_LABEL = 'ngf'
POPS_USED = ['NGF1', 'NGF2', 'NGF3', 'NGF4', 'NGF5A', 'NGF5B', 'NGF6']
#EXP_LABEL = 'ct'
#POPS_USED = ['CT5A', 'CT5B', 'CT6']
#EXP_LABEL = 'it6'
#POPS_USED = ['IT6']
#EXP_LABEL = 'it4'
#POPS_USED = ['ITP4', 'ITS4']

# File with the info about (drxe, rxi) regions
RGN_JSON_NAME = f'regions_{EXP_LABEL}'

# Weights of background exc/inh inputs (from json file)
WX_JSON_LABEL = 'psp_0.5'
WX_JSON_NAME = 'wx_target_psp_0.5_soma_mech1_vrest_pyr_-70'

# Target sections of bkg inputs
XE_SEC = 'soma'
XI_SEC = 'soma'

# Constant input to set Vrest
USE_IBKG = 1
V_REST = -70

# Surrogate inputs
SURR_INP_ON = 1

REC_TRACES = 1
PLOT_TRACES = 0

# Length-weighted random selection from sec lists
SEC_DISTR_BY_LEN = 0

DIAG = 0

# Load mech multipliers from json
MECH_FROM_JSON = 1


def gen_exp_name_sub(cfg):
    t_limits = (cfg.t0_calc / 1000, cfg.duration / 1000)
    exp_name_sub = f'exp_{EXP_LABEL}'
    if not SURR_INP_ON:
        exp_name_sub += '_nosurr'
    exp_name_sub += f'_sz_{N_DRXE}_{N_RXI}'
    exp_name_sub += f'_t_{t_limits[0]}_{t_limits[1]}'
    exp_name_sub += f'_wx_{WX_JSON_LABEL}'
    exp_name_sub += f'_wmult_{cfg.wmult}_ee_{cfg.EEGain}'
    exp_name_sub += f'_lsec_{SEC_DISTR_BY_LEN}'
    exp_name_sub += f'_xsec_{XE_SEC}_{XI_SEC}'
    return exp_name_sub


def get_mech_changes():
    with open(dirpath_self / 'mech_changes_1.json', 'r') as fid:
        mech_changes = json.load(fid)
    return mech_changes    


def apply_exp_cfg(cfg):

    # Duration
    cfg.duration = 12 * 1e3
    #cfg.duration = 5 * 1e3

    # Left point (ms) of the calculation time window (r, cv, ...)
    cfg.t0_calc = 7000
    #cfg.t0_calc = 3000

    # Populations to use
    pops_active = POPS_USED

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

    # Load bkg weights from json
    fname_ibkg = dirpath_self / f'{WX_JSON_NAME}.json'
    with open(fname_ibkg, 'r') as fid:
        wx_json = json.load(fid)
    
    # Load info about (drxe, rxi) regions
    fname_rgn = dirpath_self / f'{RGN_JSON_NAME}.json'
    with open(fname_rgn, 'r') as fid:
        cfg.drxe_rxi_regions = json.load(fid)
    
    # Background spiking input
    cfg.add_bkg_spike_input = 1
    cfg.replace_bkg_spikes_by_ou = 0   # 1 = use NetStim's
    cfg.bkg_spike_inputs = {}
    for n, pop in enumerate(POPS_USED):
        wxe = wx_json['wx_target'][pop]['xe']
        wxi = wx_json['wx_target'][pop]['xi']
        # Values of r will be set in batch
        cfg.bkg_spike_inputs[pop] = {
            'exc': {'r': 0, 'w': wxe, 'sec': XE_SEC, 'noise': 1,
                    'seed': cfg.seeds['stim'] + 10000 + n},
            'inh': {'r': 0, 'w': wxi, 'sec': XI_SEC, 'noise': 1,
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
    
    cfg.analysis['plotRaster'] = False
    cfg.analysis['plotSpikeStats'] = False

    # Record voltage traces
    if REC_TRACES:
        ncells_rec = 5
        ncells_plot = 1
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
    
    # Create experiment subfolder
    exp_name_sub = gen_exp_name_sub(cfg)
    dirpath_res_sub = Path(cfg.saveFolder) / exp_name_sub
    os.makedirs(dirpath_res_sub, exist_ok=True)


def post_run(sim):
    """Called in the end of a job (after runnig and saving). """

    cfg = sim.cfg
    exp_name = cfg.simLabel

    # Metric calculation time interval in seconds
    t_limits = (cfg.t0_calc / 1000, cfg.duration / 1000)

    # Experiment sub-name
    exp_name_sub = gen_exp_name_sub(cfg)

    # Generate filename postfix with batch param values
    drxe_num, rxi_num = cfg.drxe_num, cfg.rxi_num
    exp_id = exp_name.split('_')[-1]
    postfix = (f'{exp_id}_drxe_{drxe_num}_rxi_{rxi_num}')

    # Create subfolders to put the results
    dirpath_res = Path(cfg.saveFolder)
    dirpath_res_sub = dirpath_res / exp_name_sub
    os.makedirs(dirpath_res_sub, exist_ok=True)
    dirnames_sub = ['rasters', 'results', 'cfg', 'pkl', 'netpar', 'traces']
    for dirname in dirnames_sub:
        os.makedirs(dirpath_res_sub / dirname, exist_ok=True)

    # Move results to a subfolder
    data_info = [
        ('raster', 'png', 'rasters'),
        ('data', 'pkl', 'pkl'),
        ('cfg', 'json', 'cfg'),
        ('netParams', 'json', 'netpar')
    ]
    for di in data_info:
        data_name, ext, dirname_sub = di
        fpath_old = dirpath_res / f'{exp_name}_{data_name}.{ext}'
        fpath_new = dirpath_res_sub / dirname_sub / f'{data_name}_{postfix}.{ext}'
        if fpath_old.exists():
            fpath_old.rename(fpath_new)
        else:
            print('RESULT NOT FOUND: ', fpath_old)
    
    # Move traces to a subfolder
    trace_files = list(dirpath_res.glob(f'{exp_name}*_traces*.png'))
    for n, fpath_old in enumerate(trace_files):
        fpath_new = dirpath_res_sub / 'traces' / f'trace_{postfix}_{n}.png'
        fpath_old.rename(fpath_new)
    
    # Save rates, CVs, and voltage stats to a json file
    if cfg.need_run:
        res = {}
        res['timing'] = sim.timingData
        res |= proc.calc_rates_and_cvs(sim, t_limits, nspikes_min=3)
        res |= proc.calc_v_stats(sim, t_limits, med_win=0.05)
        fpath_res = dirpath_res_sub / 'results' / f'result_{postfix}.json'
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
    pops_pre = ['IT2frz']
    pops_post = ['IT2']
    sec_groups = {
        'soma': ['soma'],
        #'dend': ['dend'],
        #'ori1': ['ori1'],
        #'ori2': ['ori2'],
        #'rad1': ['rad1'],
        #'rad2': ['rad2']
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
