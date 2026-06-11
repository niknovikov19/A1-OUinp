import json, sys, math
from pathlib import Path
import pandas as pd
from statistics import median
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
        secs = list(secs_all.values()) if change['sec']=='all' else [secs_all[change['sec']]]
        for sec in secs:
            sec['mechs'][change['mech']][change['par']] *= change['mult']
            sec['mechs'][change['mech']][change['par']] += change['add']

def apply_target_sections(netParams):
    with open(MODEL / 'target_sec_1.json') as f:
        target_sec = json.load(f)
    warnings=[]
    for conn_name, conn in netParams.connParams.items():
        pop_pre = conn['preConds'].get('pop'); pop_post = conn['postConds'].get('pop')
        conn['sec'] = None
        for target_rule in target_sec.values():
            if pop_pre in target_rule['pops_pre'] and pop_post in target_rule['pops_post']:
                conn['sec'] = target_rule['sec']; break
        if conn['sec'] is None: warnings.append(conn_name)
    return warnings

def resolve_cfg_path(path_like):
    if not path_like: return None
    path = Path(path_like)
    return path if path.is_absolute() else MODEL / path

def build_subnet(cfg, netParams):
    desc = SubnetDesc(); desc.pops_active = cfg.subnet_params['pops_active']; desc.conns_frozen = cfg.subnet_params['conns_frozen']; desc.conns_split = cfg.subnet_params['conns_split']
    fpath = resolve_cfg_path(cfg.subnet_params.get('fpath_frozen_rates'))
    df = pd.read_csv(fpath if fpath and fpath.exists() else MODEL / 'target_state_1.csv')
    pop_names = df['pop_name'].tolist(); frozen_rates = df.set_index('pop_name')['target_rate'].to_dict(); frozen_cvs = df.set_index('pop_name')['target_cv'].to_dict() if 'target_cv' in df.columns else {p:1.0 for p in pop_names}
    base_seed = cfg.subnet_params.get('global_seed', cfg.seeds['stim']); desc.inp_surrogates = {}
    for pop in pop_names:
        desc.inp_surrogates[pop] = {'type':'irregular','rate':frozen_rates[pop],'noise':frozen_cvs[pop],'seed': base_seed + sum(ord(ch) for ch in pop)}
    spb = SubnetParamBuilder2(); return specs.NetParams(spb.build(json.loads(json.dumps(netParams.todict())), desc))

def parse_split_pairs(cfg):
    raw_pairs = cfg.subnet_params.get('conns_split', {}).keys(); out=set()
    for pair in raw_pairs:
        a,b=[part.strip() for part in pair.split(',',1)]; out.add((a,b))
    return out

def apply_split_synmech_labels(cfg, netParams):
    split_pairs = parse_split_pairs(cfg)
    for conn in netParams.connParams.values():
        kind, pops_pre_base, pops_post = _rule_kind_and_base_pops(conn)
        if kind is None: continue
        if any((a,b) in split_pairs for a in pops_pre_base for b in pops_post):
            _relabel_conn_synmech(netParams, conn, kind)
base = create_net_params(cfg); apply_mech_changes(cfg, base); apply_target_sections(base); final = build_subnet(cfg, base); apply_split_synmech_labels(cfg, final)
g = final.todict()
with open(MODEL / 'netParams_example.json') as f: r=json.load(f)['net']['params']
common=sorted(set(g['connParams']) & set(r['connParams']))
weight_ratios=[]; only_repr=0; other=0; repr_and_weight=0
examples=[]
for k in common:
    gc = g['connParams'][k]; rc = r['connParams'][k]
    diffs=[]
    for field in sorted(set(gc)|set(rc)):
        if gc.get(field)!=rc.get(field): diffs.append(field)
    repr_only_fields=[]
    real_fields=[]
    for field in diffs:
        gv=gc.get(field); rv=rc.get(field)
        if field in ('preConds','postConds'):
            # normalize singleton pop strings to list
            def norm(x):
                if isinstance(x, dict) and 'pop' in x:
                    y=dict(x)
                    if isinstance(y['pop'], str): y['pop']=[y['pop']]
                    return y
                return x
            if norm(gv)==norm(rv):
                repr_only_fields.append(field)
            else:
                real_fields.append(field)
        else:
            real_fields.append(field)
    if not real_fields and repr_only_fields:
        only_repr += 1
    else:
        if diffs == ['weight'] or real_fields == ['weight'] or (set(real_fields)=={'weight'} and repr_only_fields):
            repr_and_weight += 1 if repr_only_fields else 0
        else:
            other += 1
            if len(examples)<10:
                examples.append((k,diffs,{f:{'g':gc.get(f),'r':rc.get(f)} for f in diffs}))
    if 'weight' in diffs:
        gv=gc.get('weight'); rv=rc.get('weight')
        if isinstance(gv,(int,float)) and isinstance(rv,(int,float)) and gv!=0:
            weight_ratios.append(rv/gv)

print('common', len(common))
print('only_repr', only_repr)
print('with_weight_ratio_count', len(weight_ratios))
# summarize ratios with rounding buckets
from collections import Counter
rounded=Counter(round(x,6) for x in weight_ratios)
print('top ratios', rounded.most_common(10))
print('other example count', other)
print(json.dumps(examples[:5], indent=2)[:20000])
