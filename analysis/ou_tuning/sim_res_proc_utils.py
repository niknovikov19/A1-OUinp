from pathlib import Path
import sys

dirpath_repo_root = Path(__file__).resolve().parents[3]
dirpath_self = Path(__file__).resolve().parent
sys.path.append(str(dirpath_repo_root))
#sys.path.append(str(dirpath_self))

import numpy as np
from scipy.ndimage import median_filter

from analysis.ou_tuning import netpyne_res_parse_utils as utils
from analysis.ou_tuning import data_proc_utils as proc


def calc_rates_and_cvs(
        sim,   # NetPyNE sim object obtained after a simulation / loaded dict
        t_limits: tuple[float, float] | None = None,   # time window used for calculation
        nspikes_min: int = 3,   # min. number of spikes to use a cell in CV calculation
        per_cell_rates=False
        ) -> dict:
    
    if isinstance(sim, dict):
        sim_result = sim
    else:
        # Convert NetPyNE object to a dict (same as stored in pkl files)
        sim_result = utils.prepare_sim_result(sim)
    # Time limits
    if t_limits is None:
        t_limits = (0, utils.get_sim_duration(sim_result))
    # Extract spikes
    all_spikes = utils.get_net_spikes(sim_result)   # cells combined
    cell_spikes = utils.get_net_spikes(sim_result,
                                       combine_cells=False)   # per cell
    # Get the size of each pop.
    ncells = utils.get_net_size(sim_result)   # {pop: ncells}
    # Calculate rates and CVs
    if per_cell_rates:
        rates = proc.calc_net_rates(cell_spikes, time_limits=t_limits)
    else:
        rates = proc.calc_net_rates(all_spikes, time_limits=t_limits, ncells=ncells)
    cvs = proc.calc_net_cvs(cell_spikes, time_limits=t_limits,
                            nspikes_min=nspikes_min, avg_result=True)
    # Combine the result
    res = {'rates': rates, 'cvs': cvs, 't_limits_r': t_limits,
           'nspikes_min': nspikes_min}
    return res

def calc_trace_stats(
        sim,   # NetPyNE sim object obtained after a simulation
        trace_name: str,
        t_limits: tuple[float, float] | None = None,   # time window used for calculation
        ) -> dict:
    if t_limits is None:
        t_limits = (0, sim.cfg.duration / 1000)
    # Convert NetPyNE object to a dict (same as stored in pkl files)
    sim_result = utils.prepare_sim_result(sim)
    # Extract traces
    X = utils.get_trace_xr(sim_result, trace_name, t_limits, ms=False)
    # Calculate stats
    res = {'min': {}, 'max': {}, 'mean': {}, 'std': {}, 'median': {}, 
           't_limits_v': t_limits}
    for pop, Xmat in X.items():
        if Xmat is None:
            continue
        x = Xmat.values.ravel()
        res['min'][pop] = x.min()
        res['max'][pop] = x.max()
        res['mean'][pop] = np.mean(x)
        res['std'][pop] = np.std(x)
        res['median'][pop] = np.median(x)
    return res

def calc_v_stats(
        sim,   # NetPyNE sim object obtained after a simulation
        t_limits: tuple[float, float] | None = None,   # time window used for calculation
        med_win: float = 0.1,   # time window of the median filter,
        thresh: float = -40   # upper limit of voltages used for std calculation
        ) -> dict:
    if t_limits is None:
        t_limits = (0, sim.cfg.duration / 1000)
    # Convert NetPyNE object to a dict (same as stored in pkl files)
    sim_result = utils.prepare_sim_result(sim)
    # Extract voltage traces
    V = utils.get_voltages_xr(sim_result, t_limits, ms=False)
    # Calculate voltage stats
    res = {
        'v_med_min': {}, 'v_med_max': {}, 'v_med_avg': {},
        'v_avg': {}, 'v_std': {}, 'v_thresh_avg': {}, 'v_thresh_std': {},
        'v_min': {}, 'v_max': {},
        't_limits_v': t_limits, 'med_win': med_win, 'thresh': thresh
    }
    dt = utils.get_timestep(sim_result)
    for pop, Vmat in V.items():
        if Vmat is None:
            continue
        Vmed = median_filter(Vmat.values, size=(1, int(med_win / dt)))
        res['v_med_min'][pop] = Vmed.ravel().min()
        res['v_med_max'][pop] = Vmed.ravel().max()
        res['v_med_avg'][pop] = Vmed.ravel().mean()
        Vmat_ = Vmat.values.ravel()
        res['v_avg'][pop] = Vmat_.mean()
        res['v_std'][pop] = Vmat_.std()
        res['v_thresh_avg'][pop] = Vmat_[Vmat_ < thresh].mean()
        res['v_thresh_std'][pop] = Vmat_[Vmat_ < thresh].std()
        res['v_min'][pop] = Vmat_.min()
        res['v_max'][pop] = Vmat_.max()
    return res


def calc_rate_dynamics(
        sim,   # dict | NetPyNE sim object obtained after a simulation
        t_limits: tuple[float | None, float | None] = (None, None),
        dt_bin: float = 5e-3,   # firing rate time bin
        tau_smooth: float | None = None,
        pops_used: list[str] | None = None
        ) -> dict:
    
    if isinstance(sim, dict):
        sim_res = sim
    else:
        # Convert NetPyNE object to a dict (same as stored in pkl files)
        sim_res = utils.prepare_sim_result(sim)

    # Calculation time window
    t1 = t_limits[0] or 0
    t2 = t_limits[1] or utils.get_sim_duration(sim_res)

    # Extract spikes
    pops_used = pops_used or utils.get_pop_names(sim_res)
    net_spikes = utils.get_net_spikes(sim_res, pop_names=pops_used)
    ncells = utils.get_net_size(sim_res)
    
    # Rate dynamics
    r_data = proc.calc_net_rate_dynamics(
        net_spikes, time_range=(t1, t2), dt_bin=dt_bin,
        tau_smooth=tau_smooth, ncells=ncells)
    
    return r_data