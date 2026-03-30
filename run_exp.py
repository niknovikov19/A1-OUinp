import argparse
import json
import os
from pathlib import Path
import pickle as pkl
from pprint import pprint

import matplotlib
import matplotlib.pyplot as plt
matplotlib.use('Agg')  # to avoid graphics error on servers
import numpy as np
import pandas as pd

from netpyne.batchtools import comm, specs
from netpyne import sim

import background_stim_new as bs
from create_base_cfg import create_base_cfg
from create_net_params import create_net_params
from load_module import load_module

from subnet_tuner import SubnetDesc, SubnetParamBuilder2

from collect_cell_gids import _collect_cell_gids

#import analysis.ou_tuning.data_proc_utils as proc_utils
#import analysis.ou_tuning.netpyne_res_parse_utils as parse_utils


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

def setCochCellLocationsX(cfg, netParams, pop, sz, scale):
    # Set the cell positions on a line
    if pop not in sim.net.pops:
        return
    offset = sim.simData['dminID'][pop]
    ncellinrange = 0  # number of cochlear cells with center frequency in frequency range represented by this model
    sidx = -1
    for idx, cf in enumerate(netParams.cf):
        if cf >= cfg.cochThalFreqRange[0] and cf <= cfg.cochThalFreqRange[1]:
            if sidx == -1:
                sidx = idx  # start index
            ncellinrange += 1
    if sidx > -1:
        offset += sidx
    for c in sim.net.cells:
        if c.gid in sim.net.pops[pop].cellGids:
            cf = netParams.cf[c.gid-sim.simData['dminID'][pop]]
            if cf >= cfg.cochThalFreqRange[0] and cf <= cfg.cochThalFreqRange[1]:
                c.tags['x'] = cellx = (
                    scale * (cf - cfg.cochThalFreqRange[0]) /
                    (cfg.cochThalFreqRange[1] - cfg.cochThalFreqRange[0])
                )
                # make sure these values consistent
                c.tags['xnorm'] = cellx / netParams.sizeX
            else:
                # put it outside range for core
                c.tags['x'] = cellx = 100000000
                # make sure these values consistent
                c.tags['xnorm'] = cellx / netParams.sizeX
            c.updateShape()


# Folder names for experiment configs and results (relative to this script)
DIRNAME_EXP_CONFIGS = 'exp_configs'
DIRNAME_EXP_RESULTS = 'exp_results'    # without batchtools

# Take batch flag from command line arguments, default to False
parser = argparse.ArgumentParser(description="Run experiment script.")
parser.add_argument('--batch', action='store_true',
                    help="Run in batch mode.")
parser.add_argument('--name', type=str,
                    help="Experiment name (required if not in batch mode).")
parser.add_argument('--subdir', type=str,
                    help="Subfolder where the exp is located")
parser.add_argument('--par', type=str,
                    help="Arbitrary param")
args, _ = parser.parse_known_args()
is_batch = args.batch

if not args.batch and args.name is None:
    raise ValueError("Either --name or --batch is requred")

# Experiment name (define the folder name in exp_configs and exp_results)
if not is_batch:
    exp_name = args.name

dirpath_self = Path(__file__).resolve().parent

if is_batch:
    # Get simLabel from batchtools to identify exp_name,
    # which is then used to generate the path to exp_cfg.py
    sim_label = comm.runner.mappings['simLabel']
    exp_name = sim_label[:-6]  # cut away job id
    print(f'>>>> EXP_NAME: {exp_name}', flush=True)

# Import experiment-specific config and batch py-files
dirpath_exp_cfg = dirpath_self / DIRNAME_EXP_CONFIGS
if args.subdir is not None:
    dirpath_exp_cfg /= args.subdir
dirpath_exp_cfg /= exp_name
fpath_exp_cfg = dirpath_exp_cfg / 'exp_cfg.py'
fpath_exp_batch = dirpath_exp_cfg / 'batch_params.py'
#print(f'Experiment config: {fpath_exp_cfg}')
cfg_mod = load_module(fpath_exp_cfg)
if is_batch:
    batch_mod = load_module(fpath_exp_batch)

# Initialize config object, common for every experiment of the model
cfg = create_base_cfg()

# Apply experiment-specific config modifications
if args.par is None:
    cfg_mod.apply_exp_cfg(cfg)
else:
    cfg_mod.apply_exp_cfg(cfg, args.par)

if not is_batch:
    # Automatically set the experiment name in config
    cfg.simLabel = exp_name.split('/')[-1]   # remove subfolders if any
    cfg.saveFolder = dirpath_self / DIRNAME_EXP_RESULTS / exp_name
    if hasattr(cfg, 'exp_name_sub'):
        cfg.saveFolder /= cfg.exp_name_sub
    cfg.saveFolder = str(cfg.saveFolder)

# Update config by batchtools (if applicable)
cfg.update()

comm.initialize()

""" if comm.is_host():
    fpath_cfg = "{}/{}_cfg.json".format(cfg.saveFolder, cfg.simLabel)
    fpath_cfg_2 = "{}/{}_cfg_2.json".format(cfg.saveFolder, cfg.simLabel)
    print(f'Saving to {fpath_cfg}', flush=True)
    cfg.save(fpath_cfg)
    #with open(fpath_cfg_2, 'w') as fid:
    #    json.dump(cfg.__dict__, fid, indent=4) """

# Apply experiment-specific post-update config modifications
# (derive other params from the ones set by batchtools in update_cfg)
if is_batch and hasattr(batch_mod, 'post_update'):
    batch_mod.post_update(cfg)

# Create netParams based on the config
netParams = create_net_params(cfg)

# Experiment-specific modification of netParams
if hasattr(cfg_mod, 'modify_net_params'):
    cfg_mod.modify_net_params(cfg, netParams) 

# Convert to a subnetwork with some pops. frozen, if needed
if hasattr(cfg, 'subnet_build_flag') and cfg.subnet_build_flag:
    desc = SubnetDesc()
    desc.pops_active = cfg.subnet_params['pops_active']
    desc.conns_frozen = cfg.subnet_params['conns_frozen']
    if 'conns_split' in cfg.subnet_params:
        desc.conns_split = cfg.subnet_params['conns_split']

    # Set firing rates of the frozen pops.
    if 'fpath_frozen_rates' in cfg.subnet_params:
        df = pd.read_csv(cfg.subnet_params['fpath_frozen_rates'])
    else:
        df = pd.read_csv(dirpath_exp_cfg / 'frozen_rates.csv')
    pop_names = df['pop_name'].tolist()
    frozen_rates = df.set_index('pop_name')['target_rate'].to_dict()
    if 'frozen_rates_custom' in cfg.subnet_params:
        for pop, r in cfg.subnet_params['frozen_rates_custom'].items():
            frozen_rates[pop] = r
    if 'target_cv' in df.columns:
        frozen_cvs = df.set_index('pop_name')['target_cv'].to_dict()
    else:
        frozen_cvs = {pop: 1.0 for pop in pop_names}
    
    # Get base seed for frozen populations
    base_seed = cfg.subnet_params.get('global_seed', cfg.seeds['stim'])

    for pop in pop_names:
        # Generate deterministic seed from base_seed and pop name
        pop_offset = sum([ord(c) for c in pop])  # hash from pop name
        seed = base_seed + pop_offset

        desc.inp_surrogates[pop] = {
            'type': 'irregular',
            'rate': frozen_rates[pop],
            'noise': frozen_cvs[pop],
            'seed': seed
        }
    
    # Build subnet
    spb = SubnetParamBuilder2()
    par_dict = netParams.__dict__
    par_sub = spb.build(par_dict, desc)
    netParams = specs.NetParams(par_sub)

# Experiment-specific modification of netParams (after subnet)
if hasattr(cfg_mod, 'modify_net_params_2'):
    cfg_mod.modify_net_params_2(cfg, netParams)

# Create a folder for the results
os.makedirs(cfg.saveFolder, exist_ok=True)

comm.initialize()

# Save cfg and netParams into the output folder
#print('SAVE CFG AND NETPARAMS', flush=True)
if comm.is_host():
    fpath_cfg = "{}/{}_cfg.json".format(cfg.saveFolder, cfg.simLabel)
    print(f'Saving to {fpath_cfg}', flush=True)
    cfg.save(fpath_cfg)
    netParams.save('{}/{}_netParams.json'.format(cfg.saveFolder, cfg.simLabel))
#print('SAVING DONE', flush=True)

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

    # Set cell locations for cochlear cells
    if cfg.cochlearThalInput:
        setCochCellLocationsX(
            cfg,
            netParams,
            'cochlea',
            netParams.popParams['cochlea']['numCells'],
            cfg.sizeX
        )

    # Create connections and external inputs
    sim.net.connectCells()      # create connections between cells based on params
    #print('Adding stims...', flush=True)
    sim.net.addStims() 			# add network stimulation

    import warnings
    warnings.simplefilter('once')

    # Extract min/max cell gid for every pop. across ranks into sim._pop_gid_range
    _collect_cell_gids()

    #from neuron import h
    #h.CVode().active(0)
    #h.dt = sim.cfg.dt

    # Setup variables to record for each cell (spikes, V traces, etc)
    sim.setupRecording()

    # Add OU current or conductance input to each cell
    ctrl_dict = None
    if sim.cfg.add_ou_current:
        if hasattr(sim.cfg, 'ou_ctrl_params'):
        #if False:
            sim, vecs_dict, ctrl_dict = bs.add_noise_iclamp_ctrl(sim)
        else:
            sim, vecs_dict = bs.add_noise_iclamp(sim)
    if sim.cfg.add_ou_conductance:
        sim, vecs_dict, OUFlags = bs.add_noise_gclamp(sim)
    
    """ # Print ik mechs
    if comm.is_host():
        hobj = sim.net.cells[0].secs['soma']['hObj']
        seg  = hobj(0.5)
        #print([name for name in dir(seg) if "ik" in name])
        print([name for name in dir(seg.kBK)])
        #print([name for name in seg.__dict__]) """
    
    print("Rank/nhosts:", sim.rank, sim.nhosts, flush=True)
    print("Local cells:", len(sim.net.cells), flush=True)

    # Experiment-specific modification of the network
    if hasattr(cfg_mod, 'modify_network'):
        cfg_mod.modify_network(sim) 

    # Run
    #if sim.rank == 0:
    print(f'Rank {sim.rank}: running...', flush=True)
    sim.runSim()               # run parallel Neuron simulation
    #if sim.rank == 0:
    #    print(f'Gathering the results...', flush=True)
    sim.gatherData()

    # Gather OUFlags
    """ if sim.cfg.add_ou_conductance:
        allOUFlags = sim.pc.py_allgather(OUFlags)
        combinedOUFlags = {}
        for flags in allOUFlags:
            combinedOUFlags.update(flags)
        sim.OUFlags = combinedOUFlags """

    # Gather controller traces
    if ctrl_dict is not None:
        print('>>> Gather controller data...', flush=True)
        ctrl_dict = bs.gather_ctrl_data(sim, ctrl_dict)
    
    # Save and plot the result
    sim.saveData()
    sim.analysis.plotData()    # plot spike raster etc

    #import time
    #time.sleep(10)

# Finalize
if comm.is_host():
    netParams.save("{}/{}_params.json".format(cfg.saveFolder, cfg.simLabel))
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
        
        # Save controller data
        if ctrl_dict is not None:
            fpath_res = '{}/{}_ctrl.pkl'.format(cfg.saveFolder, cfg.simLabel)
            with open(fpath_res, 'wb') as fid:
                pkl.dump(ctrl_dict, fid)

        # Plot controller signals and save the figures
        if ctrl_dict is not None:
            bs.plot_save_ctrl_traces(sim, ctrl_dict)
        
        # Experiment-specific result processing
        if hasattr(cfg_mod, 'post_run'):
            cfg_mod.post_run(sim)
        
        """ # Gather controller data
        if ctrl_dict is not None:
            #pprint(rank_ctrl_dicts)
            ctrl_dict_all = {}
            for rank_ctrl_dict in rank_ctrl_dicts:
                for pop, ctrl_data in rank_ctrl_dict.items():
                    #print('Gather ctrl data: ', pop, flush=True)
                    if ((pop not in ctrl_dict_all) or 
                            (ctrl_dict_all[pop]['tvec'] is None)):
                        ctrl_dict_all[pop] = ctrl_data
                #print('----------', flush=True)
            ctrl_dict = ctrl_dict_all """
        
        """ # Plot and save controller signals
        for pop_vis in ctrl_dict.keys():
            #cells = bs._get_local_cells(sim, pop_vis)
            #if len(cells) == 0:
            #    continue
            #print('CELL TYPE: ', type(cells[0]))
            #print('SECS TYPE: ', type(cells[0].secs))
            #print('SECS: ', cells[0].secs.keys())
            #pprint(cells[0].__dict__)
            #print(f'CTRL KEYS ({pop_vis}): ', ctrl_dict[pop_vis].keys())            

            tvec_ctrl = ctrl_dict[pop_vis]['tvec']
            rvec_ctrl = ctrl_dict[pop_vis]['rvec']
            zvec_ctrl = ctrl_dict[pop_vis]['zvec']
            r0 = ctrl_dict[pop_vis]['r0']

            print(f'Plot {pop_vis}, t: ', np.array(tvec_ctrl))
            print(f'Plot {pop_vis}, r: ', np.array(rvec_ctrl))
            print(f'Plot {pop_vis}, z: ', np.array(zvec_ctrl))
            
            #stim = cells[0].secs['soma']['stims'][0]
            #tvec_stim = stim['tvec']
            #zvec_stim = stim['zvec']

            plt.figure()
            plt.subplot(3, 1, 1)
            plt.plot(np.array(tvec_ctrl), np.array(rvec_ctrl))
            plt.plot([0, cfg.duration], [r0, r0], '--')
            plt.title(f'Controller rate, {pop_vis}')
            plt.subplot(3, 1, 2)
            plt.plot(np.array(tvec_ctrl), np.array(zvec_ctrl))
            plt.title(f'Controller z, {pop_vis}')
            #plt.subplot(3, 1, 3)
            #plt.plot(np.array(tvec_stim), np.array(zvec_stim))
            #plt.title(f'IClamp i, {pop_vis}')
            #plt.title(f'Voltage, {pop_vis}')
            plt.xlabel('Time')
            plt.savefig(f'{cfg.saveFolder}/{cfg.simLabel}_ctrl_traces_{pop_vis}.png') """

        
    else:
        print(f'>>>>>>>>>>> {cfg.simLabel} SKIPPED', flush=True)
        avgRates = {}

    # Finish and report to batchtools
    """ avgRates['loss'] = 700
    out_json = json.dumps({**inputs, **avgRates})
    try:
        comm.send(out_json)
    except:
        print('COMM SEND FAILED') """
    comm.send({'done': 1})
    comm.close()


# Experiment-specific final actions
#if hasattr(cfg_mod, 'final'):
#    cfg_mod.final(sim)
