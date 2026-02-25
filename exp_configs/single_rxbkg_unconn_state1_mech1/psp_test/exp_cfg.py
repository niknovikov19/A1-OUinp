import json
import os
from pathlib import Path
import sys

dirpath_repo_root = Path(__file__).resolve().parents[3]
dirpath_self = Path(__file__).resolve().parent
sys.path.append(str(dirpath_repo_root))
#sys.path.append(str(dirpath_self))

import matplotlib.pyplot as plt
import numpy as np

from analysis.ou_tuning import netpyne_res_parse_utils as parse_utils
from analysis.ou_tuning import sim_res_proc_utils as proc


EXP_NAME = 'tc'
POPS_USED = ['TC', 'TCM', 'HTC']

RXE, RXI = 1, 1
#WXE, WXI = 0.65, 2.5
#WXE, WXI = 0.1, 0.55   # PSP=0.2 mV in PV
#WXE, WXI = 0.25, 2   # PSP=0.5 mV in PV
#WXE, WXI = 0.25, 0.55   # PSP=0.5 mV in SOM
WXE, WXI = 0, 0

SEC_XE = 'soma'
SEC_XI = 'soma'

NOISE = 0
T0_XE = 0
T0_XI = 500

USE_IBKG = 1
IBKG_LABEL = '-70_pyr_tc'

ONE_CELL = 1


def apply_exp_cfg(cfg):

    # Duration
    cfg.duration = 3 * 1e3

    # Left point (ms) of the calculation time window (r, cv, ...)
    #cfg.t0_calc = cfg.duration - 1000
    cfg.t0_calc = 1000

    # Populations to use
    cfg.pops_active = POPS_USED

    # One cell per population
    if ONE_CELL:
        cfg.singleCellPops = 1

    # Unconnected
    cfg.addConn = 0

    # Background spiking input
    cfg.add_bkg_spike_input = 0
    cfg.bkg_spike_inputs = {}
    for n, pop in enumerate(POPS_USED):
        cfg.bkg_spike_inputs[pop] = {
            'exc': {'r': RXE, 'w': WXE, 'sec': SEC_XE,
                    'noise': NOISE, 'start': T0_XE,
                    'seed': cfg.seeds['stim'] + 10000 + n},
            'inh': {'r': RXI, 'w': WXI, 'sec': SEC_XI,
                    'noise': NOISE, 'start': T0_XI,
                    'seed': cfg.seeds['stim'] + 20000 + n},
        }
    
    # Static IClamp that sets the resting voltage
    if USE_IBKG:
        cfg.addIClamp = 1
        fname_ibkg = f'ibkg_mech1_vrest_{IBKG_LABEL}.json'
        with open(dirpath_self / fname_ibkg, 'r') as fid:
            ibkg = json.load(fid)
        cfg.IClamp = {pop: {'amp': ibkg[pop]}
                      for pop in cfg.pops_active if pop in ibkg}

    # Cell mechanisms to modify
    with open(dirpath_self / 'mech_changes_1.json', 'r') as fid:
        cfg.mech_changes = json.load(fid)
    
    if 'plotRaster' in cfg.analysis:
        cfg.analysis['plotRaster']['include'] = POPS_USED
    if 'plotSpikeStats' in cfg.analysis:
        cfg.analysis['plotSpikeStats']['include'] = POPS_USED
    if 'plotTraces' in cfg.analysis:
        cfg.analysis['plotTraces']['include'] = POPS_USED
    
    cfg.analysis['plotRaster'] = True
    cfg.analysis['plotSpikeStats'] = False

    # Record voltage traces
    ncells_rec = 300
    ncells_plot = 5
    if ONE_CELL:
        ncells_rec = 1
        ncells_plot = 1
    cfg.recordCells = [(pop, list(range(ncells_rec))) for pop in POPS_USED]
    cfg.recordTraces = {'V_soma': {'sec': 'soma', 'loc': 0.5, 'var': 'v'}}
    cfg.recordStep = 1
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


def post_run(sim):
    """Called in the end of a job (after runnig and saving). """

    cfg = sim.cfg
    exp_name = cfg.simLabel

    # Metric calculation time interval in seconds
    t_limits = (cfg.t0_calc / 1000, cfg.duration / 1000)

    exp_name_sub = f'exp_{EXP_NAME}'
    exp_name_sub += f'_rx_{RXE}_{RXI}_wx_{WXE}_{WXI}'
    exp_name_sub += f'_noise_{NOISE}_tx0_{T0_XE}_{T0_XI}'
    exp_name_sub += f'_t_{t_limits[0]}_{t_limits[1]}'
    exp_name_sub += f'_esec_{SEC_XE}_isec_{SEC_XI}'
    if USE_IBKG:
        exp_name_sub += f'_ibkg_{IBKG_LABEL}'
    if ONE_CELL:
        exp_name_sub += f'_1cell'
    exp_name_sub += f'_trec_{cfg.recordStep}'

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
    
    # Save rates, CVs, and voltage stats to a json file
    res = proc.calc_rates_and_cvs(sim, t_limits, nspikes_min=3)
    res |= proc.calc_v_stats(sim, t_limits, med_win=0.05)
    res['timing'] = sim.timingData
    fpath_res = dirpath_res_sub / f'{exp_name}_result.json'
    with open(fpath_res, 'w') as fid:
        json.dump(res, fid, indent=4)
    
    # Extract and save voltages xarray
    dirpath_v = dirpath_res_sub / 'voltages'
    os.makedirs(dirpath_v, exist_ok=True)
    sim_res = parse_utils.prepare_sim_result(sim)
    V_data = parse_utils.get_voltages_xr(sim_res)
    for pop, V_xr in V_data.items():
        if V_xr is None:
            continue
        V_xr.to_netcdf(dirpath_v / f'{pop}.nc')

    
    """ # Plot and save rate dynamics
    os.makedirs(dirpath_res_sub / 'rvec_figs', exist_ok=True)
    r_data = proc.calc_rate_dynamics(
        sim, t_limits=(3, None), tau_smooth=0.5, pops_used=POPS_ACTIVE)
    colors = plt.rcParams['axes.prop_cycle'].by_key()['color']
    for group_name, pops in POP_GROUPS.items():
        plt.figure(111); plt.clf()
        r0_lst = []
        for n, pop in enumerate(pops):
            tt, rr = r_data[pop]
            r0 = cfg.target_rates[pop]
            r0_lst.append(r0)
            plt.plot(tt, rr, label=pop, color=colors[n])
            plt.plot([tt[0], tt[-1]], [r0, r0], '--', color=colors[n])
        plt.xlabel('Time, s')
        plt.ylabel('Firing rate, Hz')
        plt.legend(bbox_to_anchor=(1, 1))
        plt.yscale('log')
        rmin = np.maximum(0.05, 0.5 * np.min(r0_lst))
        plt.ylim(rmin, None)
        plt.title(group_name)
        plt.savefig(
            dirpath_res_sub / 'rvec_figs' / f'rvec_{group_name}.png',
            dpi=300, bbox_inches='tight'
        ) """
