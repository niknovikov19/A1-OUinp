from copy import deepcopy


def _as_list(value):
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _suffix_frz(pop_name):
    return f'{pop_name}frz'


def _normalize_pairs(raw_pairs):
    if raw_pairs == 'all':
        return 'all'
    if isinstance(raw_pairs, dict):
        raw_pairs = raw_pairs.keys()
    pairs = set()
    for pair in raw_pairs or []:
        if isinstance(pair, str):
            pop_pre, pop_post = [part.strip() for part in pair.split(',', 1)]
        else:
            pop_pre, pop_post = pair
        pairs.add((pop_pre, pop_post))
    return pairs


def _conn_pops(conn):
    pre_pops = _as_list(conn.get('preConds', {}).get('pop'))
    post_pops = _as_list(conn.get('postConds', {}).get('pop'))
    return pre_pops, post_pops


def _rule_within_active(pre_pops, post_pops, pops_active):
    if not pre_pops or not post_pops:
        return True
    return set(pre_pops).issubset(pops_active) and set(post_pops).issubset(pops_active)


def _rule_matches_pairs(pre_pops, post_pops, pairs):
    if pairs == 'all':
        return bool(pre_pops and post_pops)
    return any((pop_pre, pop_post) in pairs for pop_pre in pre_pops for pop_post in post_pops)


def _copy_targeted_blocks(params_sub, params_in, pops_active):
    # Filter pop-targeted stim rules to keep the standalone subnet self-consistent
    params_sub['stimTargetParams'] = {}
    for name, target in params_in.get('stimTargetParams', {}).items():
        cond_pops = _as_list(target.get('conds', {}).get('pop'))
        if cond_pops and not set(cond_pops).issubset(pops_active):
            continue
        params_sub['stimTargetParams'][name] = deepcopy(target)

    # Filter explicit-pop subconn rules when possible
    params_sub['subConnParams'] = {}
    for name, rule in params_in.get('subConnParams', {}).items():
        pre_pops = _as_list(rule.get('preConds', {}).get('pop'))
        post_pops = _as_list(rule.get('postConds', {}).get('pop'))
        if pre_pops and not set(pre_pops).issubset(pops_active):
            continue
        if post_pops and not set(post_pops).issubset(pops_active):
            continue
        params_sub['subConnParams'][name] = deepcopy(rule)


def _build_surrogate_pop(pop_name, pop_params, surrogate):
    data = {}
    for key in ['density', 'numCells', 'gridSpacing', 'ynormRange', 'xRange', 'yRange', 'zRange']:
        if key in pop_params:
            data[key] = deepcopy(pop_params[key])
    data['cellModel'] = 'NetStim'
    data['rate'] = surrogate['rate']
    data['noise'] = surrogate.get('noise', 1.0)
    data['seed'] = surrogate['seed']
    return data


def _aux_input_pops(pop_params, pops_active):
    aux = set()
    for name, pop in pop_params.items():
        if name in pops_active:
            continue
        if pop.get('cellModel') in {'VecStim', 'NetStim', 'DynamicNetStim'}:
            aux.add(name)
    return aux


class SubnetDesc:
    """Minimal description object for the standalone subnet transformation."""

    def __init__(self):
        self.pops_active = []
        self.conns_frozen = []
        self.conns_split = {}
        self.inp_surrogates = {}


class SubnetParamBuilder2:
    """Standalone replacement for the missing repo-level subnet builder."""

    def build(self, params_in, desc):
        pops_active = set(desc.pops_active or params_in.get('popParams', {}).keys())
        pops_aux = _aux_input_pops(params_in.get('popParams', {}), pops_active)
        pops_kept = pops_active | pops_aux
        pairs_frozen = _normalize_pairs(desc.conns_frozen)
        pairs_split = _normalize_pairs(desc.conns_split)
        params_sub = deepcopy(params_in)

        # Keep active model pops plus bundled auxiliary input pops before adding frozen surrogates
        params_sub['popParams'] = {
            name: deepcopy(pop)
            for name, pop in params_in.get('popParams', {}).items()
            if name in pops_kept
        }

        # Rebuild connection rules with recurrent/frozen duplication
        params_sub['connParams'] = {}
        pops_needed_frozen = set()
        for conn_name, conn in params_in.get('connParams', {}).items():
            pre_pops, post_pops = _conn_pops(conn)
            if not _rule_within_active(pre_pops, post_pops, pops_kept):
                continue

            is_frozen = _rule_matches_pairs(pre_pops, post_pops, pairs_frozen)
            is_split = _rule_matches_pairs(pre_pops, post_pops, pairs_split)

            if not is_frozen:
                params_sub['connParams'][conn_name] = deepcopy(conn)

            if is_frozen or is_split:
                frz_conn = deepcopy(conn)
                frz_pops = [_suffix_frz(pop_name) for pop_name in pre_pops]
                frz_conn['preConds']['pop'] = frz_pops[0] if len(frz_pops) == 1 else frz_pops
                params_sub['connParams'][f'frz_{conn_name}'] = frz_conn
                pops_needed_frozen.update(pre_pops)

        # Keep only targeted auxiliary rules that still point to active pops
        _copy_targeted_blocks(params_sub, params_in, pops_active)

        # Add local surrogate NetStim populations for frozen inputs
        for pop_name in sorted(pops_needed_frozen):
            if pop_name not in params_sub['popParams']:
                continue
            if pop_name not in desc.inp_surrogates:
                raise KeyError(f'Missing surrogate input definition for frozen population {pop_name}')
            params_sub['popParams'][_suffix_frz(pop_name)] = _build_surrogate_pop(
                pop_name,
                params_sub['popParams'][pop_name],
                desc.inp_surrogates[pop_name],
            )

        return params_sub
