import numpy as np


def _to_list(x):
    return np.atleast_1d(x).tolist()

def _lists_intersect(list1, list2):
    return bool(set(list1) & set(list2))


def get_all_pops(sim):
    return list(sim.net.params.popParams.keys())

def get_all_conns(sim):
    return list(sim.net.params.connParams.keys())

def get_cond_pops(sim, conds: dict) -> list[str]:
    """Return a list of populations that meet the conditions conds. """
    # Note: could return a superset of the actual list
    if 'pop' in conds:
        return _to_list(conds['pop'])
    elif 'cellType' in conds:
        pops = []
        for pop, par in sim.netpar_full['popParams'].items():
            if 'cellType' in par:
                if par['cellType'] in _to_list(conds['cellType']):
                    pops.append(pop)
        return pops
    else:
        s = f'Conditions should contain "pop" or "cellType"\n{conds}'
        #raise ValueError(s)
        print(s)
        return []

def get_conn_pops_presyn(sim, conn: str) -> list[str]:
    conds = sim.net.params.connParams[conn]['preConds']
    return get_cond_pops(sim, conds)
        
def get_conn_pops_postsyn(sim, conn: str) -> list[str]:
    conds = sim.net.params.connParams[conn]['postConds']
    return get_cond_pops(sim, conds)

def get_2pop_conns(
        sim,
        pops_pre: str | list[str],
        pops_post: str | list[str]
        ) -> list[str]:
    """Find connections between two sets of pops in the full model. """
    conns = []
    if isinstance(pops_pre, str):
        pops_pre = [pops_pre]
    if isinstance(pops_post, str):
        pops_post = [pops_post]
    for conn in get_all_conns(sim):
        pops_pre_ = get_conn_pops_presyn(sim, conn)
        pops_post_ = get_conn_pops_postsyn(sim, conn)
        if (_lists_intersect(pops_pre, pops_pre_) and
            _lists_intersect(pops_post, pops_post_)):
            conns.append(conn)
    return conns
