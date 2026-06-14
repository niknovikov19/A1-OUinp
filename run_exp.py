import argparse
import json
import numbers
import os
from pathlib import Path
import pickle as pkl
from pprint import pprint
from types import SimpleNamespace

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
import rate_ctrl as ctrl

from subnet_tuner import SubnetDesc, SubnetParamBuilder2

from collect_cell_gids import _collect_cell_gids
from workflow_utils import make_job_record

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


def _normalize_batch_metrics(metrics):
    if metrics is None:
        return {}
    if not isinstance(metrics, dict):
        raise TypeError(
            "get_batch_metrics(sim) must return a dict[str, float | int]"
        )

    metrics_norm = {}
    for key, value in metrics.items():
        if not isinstance(key, str):
            raise TypeError("Metric names returned by get_batch_metrics(sim) must be strings")
        if isinstance(value, np.generic):
            value = value.item()
        if isinstance(value, bool):
            value = int(value)

        if isinstance(value, numbers.Integral):
            metrics_norm[key] = int(value)
            continue
        if isinstance(value, numbers.Real):
            value = float(value)
            if not np.isfinite(value):
                raise ValueError(f"Metric {key!r} must be finite, got {value!r}")
            metrics_norm[key] = value
            continue

        raise TypeError(
            f"Metric {key!r} must be numeric, got value {value!r}"
        )

    return metrics_norm


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


def _collect_batch_metrics(cfg_mod, sim):
    if not hasattr(cfg_mod, 'get_batch_metrics'):
        return {}

    metrics = _normalize_batch_metrics(cfg_mod.get_batch_metrics(sim))
    expected_metric = getattr(sim.cfg, 'optuna_metric_name', None)
    if expected_metric is not None and expected_metric not in metrics:
        raise ValueError(
            f"Configured Optuna metric {expected_metric!r} was not returned by "
            "get_batch_metrics(sim)"
        )
    return metrics


def _read_runtime_overrides(fpath):
    """Load optional workflow runtime overrides."""
    if fpath is None:
        return None
    with open(fpath, 'r') as fid:
        runtime_overrides = json.load(fid)
    if 'batch_param_names' not in runtime_overrides:
        runtime_overrides['batch_param_names'] = list(
            runtime_overrides['batch_params']
        )
    return runtime_overrides


def _write_json_atomic(fpath, value):
    """Write JSON by atomically replacing the destination file."""
    fpath = Path(fpath)
    fpath.parent.mkdir(parents=True, exist_ok=True)
    fpath_tmp = fpath.with_suffix(f'{fpath.suffix}.tmp')
    with open(fpath_tmp, 'w') as fid:
        json.dump(value, fid, indent=2, sort_keys=True)
    os.replace(fpath_tmp, fpath)


def _get_workflow_job_id(sim_label):
    """Extract the BatchTools integer job ID from simLabel."""
    try:
        return int(sim_label.rsplit('_', 1)[1])
    except (IndexError, ValueError) as exc:
        raise ValueError(
            f'Workflow simLabel has no integer job ID: {sim_label!r}'
        ) from exc


def _write_workflow_job_meta(cfg, runtime_overrides, outputs):
    """Write the compact workflow completion record."""
    dirpath_stage = Path(cfg.saveFolder)
    output_paths = []
    for output in outputs:
        fpath_output = Path(output)
        if not fpath_output.is_absolute():
            fpath_output = dirpath_stage / fpath_output
        if not fpath_output.is_file():
            raise FileNotFoundError(
                f'Declared workflow output does not exist: {fpath_output}'
            )
        output_paths.append(fpath_output.relative_to(dirpath_stage).as_posix())

    # Store only batch coordinates and stage references per job
    batch_params = {
        name: getattr(cfg, name)
        for name in runtime_overrides['batch_param_names']
    }
    record = make_job_record(
        runtime_overrides,
        cfg.simLabel,
        _get_workflow_job_id(cfg.simLabel),
        batch_params,
        output_paths,
    )
    fpath_meta = dirpath_stage / 'job_meta' / f'{cfg.simLabel}.json'
    _write_json_atomic(fpath_meta, record)


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
parser.add_argument('--job_id_len', type=int, default=6,
                    help="Number of characters to strip from the end of simLabel to get exp_name")
parser.add_argument(
    '--runtime-overrides',
    '--runtime_overrides',
    dest='runtime_overrides',
    help='Workflow runtime override JSON',
)
args, _ = parser.parse_known_args()
is_batch = args.batch
runtime_overrides = _read_runtime_overrides(args.runtime_overrides)

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
    exp_name = sim_label[:-args.job_id_len]  # cut away job id
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

# Apply compact workflow overrides before BatchTools updates the grid axes
if runtime_overrides is not None:
    cfg.workflow_context = {
        name: runtime_overrides[name]
        for name in (
            'workflow_name',
            'run_id',
            'iteration',
            'stage',
            'stage_spec_hash',
        )
    }
    cfg.workflow_result_subdir = runtime_overrides['result_subdir']
    cfg.workflow_retention = runtime_overrides['retention']
    cfg.savePickle = runtime_overrides['retention']['keep_pkl']
    exp_overrides = runtime_overrides.get('experiment_overrides', {})
    if exp_overrides and not hasattr(cfg_mod, 'apply_runtime_overrides'):
        raise AttributeError(
            f'{fpath_exp_cfg} does not implement apply_runtime_overrides()'
        )
    if exp_overrides:
        cfg_mod.apply_runtime_overrides(cfg, exp_overrides)

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
    keep_cfg = (
        runtime_overrides is None or
        runtime_overrides['retention']['keep_cfg']
    )
    keep_netparams = (
        runtime_overrides is None or
        runtime_overrides['retention']['keep_netparams']
    )
    if keep_cfg:
        fpath_cfg = "{}/{}_cfg.json".format(cfg.saveFolder, cfg.simLabel)
        print(f'Saving to {fpath_cfg}', flush=True)
        cfg.save(fpath_cfg)
    if keep_netparams:
        _save_netparams_stripped(
            netParams,
            '{}/{}_netParams.json'.format(cfg.saveFolder, cfg.simLabel),
        )
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
        ctrl_dict = ctrl.gather_ctrl_data(sim, ctrl_dict)
    
    # Save and plot the result
    sim.saveData()
    sim.analysis.plotData()    # plot spike raster etc

    #import time
    #time.sleep(10)

# Finalize
if comm.is_host():
    if runtime_overrides is None:
        _save_netparams_stripped(
            netParams,
            "{}/{}_params.json".format(cfg.saveFolder, cfg.simLabel),
        )
    print('transmitting data...')
    inputs = cfg.get_mappings()
    workflow_outputs = []
    
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
            need_plot = cfg.get('plot_ctrl_traces', False)
            if need_plot:
                ctrl.plot_save_ctrl_traces(sim, ctrl_dict)
        
        # Experiment-specific result processing
        if hasattr(cfg_mod, 'post_run'):
            post_outputs = cfg_mod.post_run(sim)
            if post_outputs is not None:
                workflow_outputs = post_outputs

        batch_metrics = _collect_batch_metrics(cfg_mod, sim)

    else:
        print(f'>>>>>>>>>>> {cfg.simLabel} SKIPPED', flush=True)
        avgRates = {}
        sim = SimpleNamespace(cfg=cfg)
        batch_metrics = _collect_batch_metrics(cfg_mod, sim)

    # Publish workflow completion only after post_run has sorted all outputs
    if runtime_overrides is not None:
        _write_workflow_job_meta(
            cfg,
            runtime_overrides,
            workflow_outputs,
        )

    # Finish and report to batchtools
    """ avgRates['loss'] = 700
    out_json = json.dumps({**inputs, **avgRates})
    try:
        comm.send(out_json)
    except:
        print('COMM SEND FAILED') """
    comm.send({'done': 1, **batch_metrics})
    comm.close()


# Experiment-specific final actions
#if hasattr(cfg_mod, 'final'):
#    cfg_mod.final(sim)
