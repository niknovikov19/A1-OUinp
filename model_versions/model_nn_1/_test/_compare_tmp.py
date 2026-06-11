import json
import sys
from pathlib import Path

import pandas as pd
from netpyne.batchtools import specs

ROOT = Path('/home/nnovikov/repo/A1-OUinp')
MODEL = ROOT / 'model_versions' / 'model_nn_1'
sys.path.insert(0, str(MODEL))

import cfg as cfg_mod
from create_net_params_local import create_net_params
from subnet_builder import SubnetDesc, SubnetParamBuilder2
from syn_mech_relabel import _relabel_conn_synmech, _rule_kind_and_base_pops

cfg = cfg_mod.cfg


def apply_mech_changes(cfg, netParams):
    for change in cfg.mech_changes.values():
        secs_all = netParams.cellParams[change['pop']]['secs']
        secs = list(secs_all.values()) if change['sec'] == 'all' else [secs_all[change['sec']]]
        for sec in secs:
            sec['mechs'][change['mech']][change['par']] *= change['mult']
            sec['mechs'][change['mech']][change['par']] += change['add']


def apply_target_sections(netParams):
    warnings = []
    with open(MODEL / 'target_sec_1.json', 'r') as fid:
        target_sec = json.load(fid)
    for conn_name, conn in netParams.connParams.items():
        pop_pre = conn['preConds'].get('pop')
        pop_post = conn['postConds'].get('pop')
        if pop_pre is None or pop_post is None:
            raise ValueError(f'Pre or post pop is not specified for connection rule {conn_name}')
        conn['sec'] = None
        for target_rule in target_sec.values():
            if pop_pre in target_rule['pops_pre'] and pop_post in target_rule['pops_post']:
                conn['sec'] = target_rule['sec']
                break
        if conn['sec'] is None:
            warnings.append(conn_name)
    return warnings


def resolve_cfg_path(path_like):
    if not path_like:
        return None
    path = Path(path_like)
    return path if path.is_absolute() else MODEL / path


def build_subnet(cfg, netParams):
    desc = SubnetDesc()
    desc.pops_active = cfg.subnet_params['pops_active']
    desc.conns_frozen = cfg.subnet_params['conns_frozen']
    if 'conns_split' in cfg.subnet_params:
        desc.conns_split = cfg.subnet_params['conns_split']

    fpath_frozen_rates = resolve_cfg_path(cfg.subnet_params.get('fpath_frozen_rates'))
    if fpath_frozen_rates and fpath_frozen_rates.exists():
        df = pd.read_csv(fpath_frozen_rates)
    else:
        df = pd.read_csv(MODEL / 'target_state_1.csv')

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
    par_sub = spb.build(json.loads(json.dumps(netParams.todict())), desc)
    return specs.NetParams(par_sub)


def parse_split_pairs(cfg):
    split_cfg = getattr(cfg, 'subnet_params', {}).get('conns_split', {})
    raw_pairs = split_cfg.keys() if isinstance(split_cfg, dict) else split_cfg
    split_pairs = set()
    for pair in raw_pairs:
        if isinstance(pair, str):
            pop_pre, pop_post = [part.strip() for part in pair.split(',', 1)]
        else:
            pop_pre, pop_post = pair
        split_pairs.add((pop_pre, pop_post))
    return split_pairs


def apply_split_synmech_labels(cfg, netParams):
    if not getattr(cfg, 'fader_on', 0):
        return
    split_pairs = parse_split_pairs(cfg)
    if not split_pairs:
        return
    for conn in netParams.connParams.values():
        kind, pops_pre_base, pops_post = _rule_kind_and_base_pops(conn)
        if kind is None:
            continue
        needs_split = any((pop_pre, pop_post) in split_pairs for pop_pre in pops_pre_base for pop_post in pops_post)
        if needs_split:
            _relabel_conn_synmech(netParams, conn, kind)


def build_intended_netparams(cfg):
    base = create_net_params(cfg)
    apply_mech_changes(cfg, base)
    warnings = apply_target_sections(base)
    final = build_subnet(cfg, base) if getattr(cfg, 'subnet_build_flag', False) else base
    apply_split_synmech_labels(cfg, final)
    return final.todict(), warnings


def load_example():
    with open(MODEL / 'netParams_example.json') as f:
        data = json.load(f)
    return data['net']['params'] if 'net' in data else data


def compare_maps(a, b):
    akeys = set(a)
    bkeys = set(b)
    common = sorted(akeys & bkeys)
    only_a = sorted(akeys - bkeys)
    only_b = sorted(bkeys - akeys)
    equal = []
    diff = []
    for k in common:
        if a[k] == b[k]:
            equal.append(k)
        else:
            diff.append(k)
    return {
        'count_generated': len(a),
        'count_reference': len(b),
        'common': len(common),
        'equal': len(equal),
        'diff': len(diff),
        'only_generated': only_a,
        'only_reference': only_b,
        'diff_keys': diff,
    }


def sample_section_diffs(section_name, generated, reference, diff_keys, limit=10):
    out = []
    for k in diff_keys[:limit]:
        g = generated[section_name][k]
        r = reference[section_name][k]
        entry = {'key': k, 'fields': {}}
        fields = sorted(set(g) | set(r))
        for f in fields:
            if g.get(f) != r.get(f):
                entry['fields'][f] = {'generated': g.get(f), 'reference': r.get(f)}
        out.append(entry)
    return out


report = {}

try:
    if 'netParams' in sys.modules:
        del sys.modules['netParams']
    import netParams as workflow_mod
    report['workflow_import'] = {'ok': True, 'message': 'import succeeded'}
except Exception as exc:
    report['workflow_import'] = {'ok': False, 'type': type(exc).__name__, 'message': str(exc)}

reference = load_example()
report['reference_counts'] = {k: len(reference.get(k, {})) for k in ['popParams','connParams','stimSourceParams','stimTargetParams','synMechParams','subConnParams']}

generated, target_sec_warnings = build_intended_netparams(cfg)
report['intended_build'] = {'ok': True, 'target_sec_warnings': target_sec_warnings}
report['generated_counts'] = {k: len(generated.get(k, {})) for k in ['popParams','connParams','stimSourceParams','stimTargetParams','synMechParams','subConnParams']}

section_results = {}
for section in ['popParams','connParams','stimSourceParams','stimTargetParams','synMechParams','subConnParams']:
    section_results[section] = compare_maps(generated.get(section, {}), reference.get(section, {}))
report['section_results'] = section_results
report['sample_pop_diffs'] = sample_section_diffs('popParams', generated, reference, section_results['popParams']['diff_keys'])
report['sample_conn_diffs'] = sample_section_diffs('connParams', generated, reference, section_results['connParams']['diff_keys'])
report['sample_stim_source_diffs'] = sample_section_diffs('stimSourceParams', generated, reference, section_results['stimSourceParams']['diff_keys'])
report['sample_stim_target_diffs'] = sample_section_diffs('stimTargetParams', generated, reference, section_results['stimTargetParams']['diff_keys'])
report['sample_synmech_diffs'] = sample_section_diffs('synMechParams', generated, reference, section_results['synMechParams']['diff_keys'])

with open(MODEL / '_compare_tmp_report.json', 'w') as f:
    json.dump(report, f, indent=2)
print(json.dumps({
    'workflow_import': report['workflow_import'],
    'generated_counts': report['generated_counts'],
    'reference_counts': report['reference_counts'],
    'section_results_summary': {k: {kk: vv for kk, vv in v.items() if kk not in ['only_generated','only_reference','diff_keys']} for k, v in report['section_results'].items()},
    'target_sec_warnings': report['intended_build']['target_sec_warnings'][:10],
}, indent=2))
