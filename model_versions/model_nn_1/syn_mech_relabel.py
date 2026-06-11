



def _as_list(x):
    if x is None:
        return []
    return x if isinstance(x, list) else [x]


def _strip_frz(pop):
    return pop[:-3] if isinstance(pop, str) and pop.endswith('frz') else pop


def _dup_synmech_label(params, old_label, suffix):
    new_label = f'{old_label}_{suffix}'
    if new_label not in params.synMechParams:
        params.synMechParams[new_label] = dict(params.synMechParams[old_label])
    return new_label


def _relabel_conn_synmech(params, conn, suffix):
    sm = conn['synMech']
    if isinstance(sm, str):
        conn['synMech'] = _dup_synmech_label(params, sm, suffix)
    elif isinstance(sm, list):
        conn['synMech'] = [_dup_synmech_label(params, x, suffix) for x in sm]
    else:
        raise TypeError(f"Unsupported synMech type: {type(sm)}")


def _rule_kind_and_base_pops(conn, verbose=False):
    pops_pre = _as_list(conn['preConds'].get('pop'))
    pops_post = _as_list(conn['postConds'].get('pop'))

    if not pops_pre or not pops_post:
        return None, [], []

    pre_is_frz = [p.endswith('frz') for p in pops_pre if isinstance(p, str)]
    if verbose:
        print('pops_pre: ', pops_pre)
        print('type(pops_pre): ', type(pops_pre))
        print('type(pops_pre[0]): ', type(pops_pre[0]))

    if len(pre_is_frz) != len(pops_pre):
        raise ValueError(f"Non-string pre pop in rule: {conn}")

    if all(pre_is_frz):
        kind = 'frz'
    elif not any(pre_is_frz):
        kind = 'rec'
    else:
        raise ValueError(
            f"Mixed recurrent/frozen pre pops in one conn rule are not supported: {pops_pre}"
        )

    pops_pre_base = [_strip_frz(p) for p in pops_pre]
    return kind, pops_pre_base, pops_post