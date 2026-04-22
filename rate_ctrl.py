from dataclasses import dataclass

import matplotlib.pyplot as plt
from neuron import h
import numpy as np


TRACE_KEY_MAP = {
    'z': 'zvec',
    'rate': 'rvec',
    's': 'svec',
    'u': 'uvec',
    'm': 'mvec',
    'e': 'evec',
    'q': 'qvec',
}
CTRL_VEC_KEYS = ('tvec', *TRACE_KEY_MAP.values())


@dataclass(frozen=True)
class ControllerSpec:
    mech_name: str
    param_map: tuple[tuple[str, str], ...]   # (mech_param, cfg_param)
    trace_names: tuple[str, ...]             # names of RANGE vars to record


CONTROLLER_SPECS = {
    'RateController': ControllerSpec(
        mech_name='RateController',
        param_map=(
            ('tau', 'tau_ctrl'),
            ('taus', 'taus_ctrl'),
            ('r0', 'target_rates'),
            ('k', 'k_ctrl'),
            ('kp', 'kp_ctrl'),
            ('z0', 'z0'),
            ('t0', 't0'),
            ('tlock', 'tlock'),
        ),
        trace_names=('z', 'rate', 's', 'u'),
    ),
    'RateController2': ControllerSpec(
        mech_name='RateController2',
        param_map=(
            ('tau', 'tau_rate_ctrl'),
            ('taum', 'taum_ctrl'),
            ('tauu', 'tauu_ctrl'),
            ('r0', 'target_rates'),
            ('ks', 'ks_ctrl'),
            ('ku', 'ku_ctrl'),
            ('epsm', 'epsm_ctrl'),
            ('z0', 'z0'),
            ('t0', 't0'),
            ('tlock', 'tlock'),
        ),
        trace_names=('z', 'rate', 's', 'u', 'm', 'e', 'q'),
    ),
}


def get_controller_spec(ctrl_par):
    mech_name = ctrl_par['controller_mod']
    try:
        return CONTROLLER_SPECS[mech_name]
    except KeyError:
        raise ValueError(
            f'Unknown controller_mod={mech_name!r}. '
            f'Expected one of {list(CONTROLLER_SPECS)}'
        )

def empty_ctrl_dict():
    return {
        'ctrl_mech': None,
        'ctrl_name': None,
        'netcon_list': [],
        'r0': None,
        **{k: None for k in CTRL_VEC_KEYS},
    }

def ctrl_cfg_value(ctrl_par, cfg_name, pop_name):
    val = ctrl_par[cfg_name]
    return val[pop_name] if cfg_name == 'target_rates' else val

def apply_ctrl_params(ctrl, spec, ctrl_par, pop_name):
    for mech_par, cfg_name in spec.param_map:
        setattr(ctrl, mech_par, ctrl_cfg_value(ctrl_par, cfg_name, pop_name))

# Helper: local cells by pop
def _get_local_cells(sim, pop_name):
    return [c for c in sim.net.cells if c.tags['pop'] == pop_name]

# Helper: all gids by pop (global)
def _get_all_gids(sim, pop_name):
    """Global list of GIDs for a population, on every rank."""
    local = sim.net.pops[pop_name].cellGids
    all_lists = sim.pc.py_allgather(local)          # list-of-lists on every rank
    return [g for sub in all_lists for g in sub]    # flatten

def _decimate(vec, n):
    if vec is None:
        return None
    return [vec.x[i] for i in range(0, int(vec.size()), n)]

def _get_ctrl_for_gather(ctrl_dict):
    res = {}
    n = 500
    for pop, d in ctrl_dict.items():
        res[pop] = {
            'ctrl_name': d.get('ctrl_name'),
            'r0': d.get('r0'),
        }
        for k in CTRL_VEC_KEYS:
            res[pop][k] = _decimate(d.get(k), n)
    return res


def record_ctrl_traces(ctrl, spec):
    out = {k: None for k in CTRL_VEC_KEYS}

    out['tvec'] = h.Vector()
    out['tvec'].record(h._ref_t)

    for trace_name in spec.trace_names:
        ref_name = f'_ref_{trace_name}'
        vec_key = TRACE_KEY_MAP[trace_name]

        if hasattr(ctrl, ref_name):
            vec = h.Vector()
            vec.record(getattr(ctrl, ref_name))
            out[vec_key] = vec

    return out


def make_rate_controller(sim, pop_name):
    """
    Create a feedback controller mech that responds
    to pop. rate deviation from the target value.
    """
    local_cells = _get_local_cells(sim, pop_name)
    gids = _get_all_gids(sim, pop_name)

    if len(local_cells) == 0:
        return empty_ctrl_dict()

    if sim.rank == 0:
        print(f'>>> {pop_name}: ngids={len(gids)}, ncells={len(local_cells)}', flush=True)

    soma = local_cells[0].secs['soma']['hObj']
    ctrl_par = sim.cfg.ou_ctrl_params
    spec = get_controller_spec(ctrl_par)

    ctrl_ctor = getattr(h, spec.mech_name, None)
    if ctrl_ctor is None:
        raise AttributeError(
            f'NEURON mech "{spec.mech_name}" is not available. '
            'Did you compile the mod files?'
        )

    ctrl = ctrl_ctor(soma(0.5))
    apply_ctrl_params(ctrl, spec, ctrl_par, pop_name)

    if sim.rank == 0:
        print(f'>>> {pop_name}: {spec.mech_name} created', flush=True)

    netcon_list = []
    for gid in gids:
        nc_in = sim.pc.gid_connect(gid, ctrl)
        nc_in.weight[0] = 1.0 / len(gids)
        nc_in.delay = 1
        netcon_list.append(nc_in)

    out = empty_ctrl_dict()
    out.update(record_ctrl_traces(ctrl, spec))
    out.update({
        'ctrl_mech': ctrl,
        'ctrl_name': spec.mech_name,
        'netcon_list': netcon_list,
        'r0': ctrl.r0,
    })
    return out


def gather_ctrl_data(sim, ctrl_dict):
    if ctrl_dict is None:
        return None
    
    rank_ctrl_dicts = sim.pc.py_allgather(
        _get_ctrl_for_gather(ctrl_dict))
    
    ctrl_dict_all = {}
    for rank_ctrl_dict in rank_ctrl_dicts:
        for pop, ctrl_data in rank_ctrl_dict.items():
            #print('Gather ctrl data: ', pop, flush=True)
            if ((pop not in ctrl_dict_all) or 
                    (ctrl_dict_all[pop]['tvec'] is None)):
                ctrl_dict_all[pop] = ctrl_data
        #print('----------', flush=True)
    return ctrl_dict_all


def plot_save_ctrl_traces(sim, ctrl_dict):
    for pop_vis, d in ctrl_dict.items():
        tvec = d.get('tvec')
        if tvec is None:
            continue

        t = np.array(tvec)
        r0 = d.get('r0')
        ctrl_name = d.get('ctrl_name', '')

        mask = t > 5000
        t = t[mask]

        has_extra = any(d.get(k) is not None for k in ('mvec', 'evec', 'qvec'))
        nrows = 3 if has_extra else 2

        plt.figure(figsize=(8, 2.8 * nrows)); plt.clf()

        ax = plt.subplot(nrows, 1, 1)
        if d.get('rvec') is not None:
            ax.plot(t, np.array(d['rvec'])[mask], label='rate')
        if r0 is not None:
            ax.plot([0, sim.cfg.duration], [r0, r0], '--', label='r0')
        ax.set_title(f'Controller rate, {pop_vis} ({ctrl_name})')
        ax.legend(loc='best')

        ax = plt.subplot(nrows, 1, 2)
        for key, label in [('zvec', 'z'), ('svec', 's'), ('uvec', 'u')]:
            if d.get(key) is not None:
                ax.plot(t, np.array(d[key])[mask], label=label)
        ax.set_title(f'Controller state, {pop_vis}')
        ax.legend(loc='best')

        if has_extra:
            ax = plt.subplot(nrows, 1, 3)
            for key, label in [('mvec', 'm'), ('evec', 'e'), ('qvec', 'q')]:
                if d.get(key) is not None:
                    ax.plot(t, np.array(d[key])[mask], label=label)
            ax.set_title(f'Controller error split, {pop_vis}')
            ax.legend(loc='best')

        plt.xlabel('Time')
        plt.tight_layout()
        plt.savefig(f'{sim.cfg.saveFolder}/{sim.cfg.simLabel}_ctrl_traces_{pop_vis}.png')
