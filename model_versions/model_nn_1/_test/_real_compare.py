import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path('/home/nnovikov/repo/A1-OUinp')
MODEL = ROOT / 'model_versions' / 'model_nn_1'
sys.path.insert(0, str(MODEL))

import netParams as workflow

with open(MODEL / 'netParams_example.json') as f:
    ref_outer = json.load(f)
reference = ref_outer['net']['params'] if 'net' in ref_outer else ref_outer
produced = workflow.netParams.todict()


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


def normalize_conn(c):
    c = json.loads(json.dumps(c))
    for cond_key in ['preConds', 'postConds']:
        conds = c.get(cond_key)
        if isinstance(conds, dict) and isinstance(conds.get('pop'), str):
            conds['pop'] = [conds['pop']]
    return c


def analyze_conn_patterns(generated, reference):
    common = sorted(set(generated['connParams']) & set(reference['connParams']))
    patterns = Counter()
    weight_ratios = Counter()
    matched_after_norm = 0
    matched_after_norm_and_x4 = 0
    examples = {}
    for k in common:
        gc = normalize_conn(generated['connParams'][k])
        rc = normalize_conn(reference['connParams'][k])
        if gc == rc:
            matched_after_norm += 1
            continue
        gcx = json.loads(json.dumps(gc))
        if isinstance(gcx.get('weight'), (int, float)):
            gcx['weight'] = gcx['weight'] * 4
        if gcx == rc:
            matched_after_norm_and_x4 += 1
            continue
        diffs = []
        for f in sorted(set(gcx) | set(rc)):
            if gcx.get(f) != rc.get(f):
                diffs.append(f)
        patterns[tuple(diffs)] += 1
        examples.setdefault(tuple(diffs), {'key': k, 'generated': gcx, 'reference': rc})
        if isinstance(gc.get('weight'), (int, float)) and isinstance(rc.get('weight'), (int, float)) and gc.get('weight'):
            weight_ratios[round(rc['weight'] / gc['weight'], 6)] += 1
    return {
        'common': len(common),
        'matched_after_norm': matched_after_norm,
        'matched_after_norm_and_x4': matched_after_norm_and_x4,
        'remaining_after_norm_and_x4': len(common) - matched_after_norm - matched_after_norm_and_x4,
        'pattern_counts': patterns.most_common(10),
        'weight_ratios': weight_ratios.most_common(10),
        'pattern_examples': {
            '|'.join(k): v for k, v in list(examples.items())[:5]
        },
    }


def analyze_iclamp(generated, reference):
    def normalize_targets(d):
        out = []
        for name, val in d.items():
            if not name.startswith('IClamp'):
                continue
            out.append((val['conds']['pop'], val.get('sec'), val.get('loc')))
        return sorted(out)

    def normalize_sources(d):
        out = []
        for name, val in d.items():
            if not name.startswith('IClamp'):
                continue
            out.append((val.get('amp'), val.get('dur'), val.get('delay', 0.0)))
        return sorted(out)

    return {
        'source_multiset_equal': normalize_sources(generated['stimSourceParams']) == normalize_sources(reference['stimSourceParams']),
        'target_multiset_equal': normalize_targets(generated['stimTargetParams']) == normalize_targets(reference['stimTargetParams']),
        'generated_iclamp_sources': len(normalize_sources(generated['stimSourceParams'])),
        'reference_iclamp_sources': len(normalize_sources(reference['stimSourceParams'])),
        'generated_iclamp_targets': len(normalize_targets(generated['stimTargetParams'])),
        'reference_iclamp_targets': len(normalize_targets(reference['stimTargetParams'])),
    }

report = {}
report['counts_generated'] = {k: len(produced.get(k, {})) for k in ['popParams', 'connParams', 'stimSourceParams', 'stimTargetParams', 'synMechParams', 'subConnParams']}
report['counts_reference'] = {k: len(reference.get(k, {})) for k in ['popParams', 'connParams', 'stimSourceParams', 'stimTargetParams', 'synMechParams', 'subConnParams']}
report['section_results'] = {
    sec: compare_maps(produced.get(sec, {}), reference.get(sec, {}))
    for sec in ['popParams', 'connParams', 'stimSourceParams', 'stimTargetParams', 'synMechParams', 'subConnParams']
}
report['samples'] = {
    'popParams': sample_section_diffs('popParams', produced, reference, report['section_results']['popParams']['diff_keys']),
    'connParams': sample_section_diffs('connParams', produced, reference, report['section_results']['connParams']['diff_keys']),
    'stimSourceParams': sample_section_diffs('stimSourceParams', produced, reference, report['section_results']['stimSourceParams']['diff_keys']),
    'stimTargetParams': sample_section_diffs('stimTargetParams', produced, reference, report['section_results']['stimTargetParams']['diff_keys']),
    'synMechParams': sample_section_diffs('synMechParams', produced, reference, report['section_results']['synMechParams']['diff_keys']),
}
report['conn_analysis'] = analyze_conn_patterns(produced, reference)
report['iclamp_analysis'] = analyze_iclamp(produced, reference)

with open(MODEL / '_test' / '_real_compare_report.json', 'w') as f:
    json.dump(report, f, indent=2)

summary = {
    'counts_generated': report['counts_generated'],
    'counts_reference': report['counts_reference'],
    'sections': {k: {kk: vv for kk, vv in v.items() if kk not in ['only_generated', 'only_reference', 'diff_keys']} for k, v in report['section_results'].items()},
    'conn_analysis': report['conn_analysis'],
    'iclamp_analysis': report['iclamp_analysis'],
}
print(json.dumps(summary, indent=2))
