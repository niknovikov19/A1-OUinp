import json
from pathlib import Path

import pandas as pd
from netpyne.batchtools import specs

from cfg import cfg
from create_net_params_local import create_net_params
from subnet_tuner import SubnetDesc, SubnetParamBuilder2
from syn_mech_relabel import _relabel_conn_synmech, _rule_kind_and_base_pops


DIRPATH_SELF = Path(__file__).resolve().parent


def _apply_mech_changes(cfg, netParams):
    """Apply experiment-specific channel parameter edits."""
    for change in cfg.mech_changes.values():
        secs_all = netParams.cellParams[change['pop']]['secs']
        if change['sec'] == 'all':
            secs = list(secs_all.values())
        else:
            secs = [secs_all[change['sec']]]

        for sec in secs:
            sec['mechs'][change['mech']][change['par']] *= change['mult']
            sec['mechs'][change['mech']][change['par']] += change['add']


def _apply_target_sections(netParams):
    """Retarget connection rules to experiment-specific postsynaptic sections."""
    with open(DIRPATH_SELF / 'target_sec_1.json', 'r') as fid:
        target_sec = json.load(fid)

    for conn_name, conn in netParams.connParams.items():
        pop_pre = conn['preConds'].get('pop')
        pop_post = conn['postConds'].get('pop')
        if pop_pre is None or pop_post is None:
            raise ValueError(
                f'Pre or post pop is not specified for connection rule {conn_name}'
            )

        sec_original = conn.get('sec')
        sec_target = None
        for target_rule in target_sec.values():
            if pop_pre in target_rule['pops_pre'] and pop_post in target_rule['pops_post']:
                sec_target = target_rule['sec']
                break

        if sec_target is None:
            conn['sec'] = sec_original
            print(f'WARNING: No target sec info found for {conn_name}')
        else:
            conn['sec'] = sec_target


def _resolve_cfg_path(path_like):
    """Resolve cfg paths relative to model_nn_1 when needed."""
    if not path_like:
        return None
    path = Path(path_like)
    if path.is_absolute():
        return path
    return DIRPATH_SELF / path


def _build_subnet(cfg, netParams):
    """Convert the full network spec into the surrogate-input subnet variant."""
    desc = SubnetDesc()
    desc.pops_active = cfg.subnet_params['pops_active']
    desc.conns_frozen = cfg.subnet_params['conns_frozen']
    if 'conns_split' in cfg.subnet_params:
        desc.conns_split = cfg.subnet_params['conns_split']

    # Load frozen target rates from the bundled file unless cfg overrides it
    fpath_frozen_rates = _resolve_cfg_path(cfg.subnet_params.get('fpath_frozen_rates'))
    if fpath_frozen_rates and fpath_frozen_rates.exists():
        df = pd.read_csv(fpath_frozen_rates)
    else:
        df = pd.read_csv(DIRPATH_SELF / 'target_state_1.csv')

    pop_names = df['pop_name'].tolist()
    frozen_rates = df.set_index('pop_name')['target_rate'].to_dict()
    if 'frozen_rates_custom' in cfg.subnet_params:
        for pop, rate in cfg.subnet_params['frozen_rates_custom'].items():
            frozen_rates[pop] = rate

    if 'target_cv' in df.columns:
        frozen_cvs = df.set_index('pop_name')['target_cv'].to_dict()
    else:
        frozen_cvs = {pop: 1.0 for pop in pop_names}

    base_seed = cfg.subnet_params.get('global_seed', cfg.seeds['stim'])
    desc.inp_surrogates = {}
    for pop in pop_names:
        pop_offset = sum(ord(ch) for ch in pop)
        seed = base_seed + pop_offset
        desc.inp_surrogates[pop] = {
            'type': 'irregular',
            'rate': frozen_rates[pop],
            'noise': frozen_cvs[pop],
            'seed': seed,
        }

    spb = SubnetParamBuilder2()
    par_sub = spb.build(netParams.__dict__, desc)
    return specs.NetParams(par_sub)


def _parse_split_pairs(cfg):
    """Parse split pairs used by recurrent/frozen fader relabeling."""
    split_cfg = getattr(cfg, 'subnet_params', {}).get('conns_split', {})
    if isinstance(split_cfg, dict):
        raw_pairs = split_cfg.keys()
    else:
        raw_pairs = split_cfg

    split_pairs = set()
    for pair in raw_pairs:
        if isinstance(pair, str):
            pop_pre, pop_post = [part.strip() for part in pair.split(',', 1)]
        else:
            pop_pre, pop_post = pair
        split_pairs.add((pop_pre, pop_post))
    return split_pairs


def _apply_split_synmech_labels(cfg, netParams):
    """Split recurrent and frozen rules onto distinct synMech labels for the fader."""
    if not getattr(cfg, 'fader_on', 0):
        return

    split_pairs = _parse_split_pairs(cfg)
    if not split_pairs:
        return

    for conn in netParams.connParams.values():
        kind, pops_pre_base, pops_post = _rule_kind_and_base_pops(conn)
        if kind is None:
            continue
        needs_split = any(
            (pop_pre, pop_post) in split_pairs
            for pop_pre in pops_pre_base
            for pop_post in pops_post
        )
        if needs_split:
            _relabel_conn_synmech(netParams, conn, kind)


# Build the shared base network from local bundled assets
netParams = create_net_params(cfg)

# Layer in the retained experiment-specific netParams transforms
_apply_mech_changes(cfg, netParams)
_apply_target_sections(netParams)

if getattr(cfg, 'subnet_build_flag', False):
    netParams = _build_subnet(cfg, netParams)

_apply_split_synmech_labels(cfg, netParams)
