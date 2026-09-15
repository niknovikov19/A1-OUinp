# Ratios are O(1); this tolerance admits roundoff but not model-level changes
DEFAULT_RATIO_TOL = 1e-8


def _new_summary():
    """Create one streaming receptor-ratio summary."""
    return {
        'n_pairs': 0,
        'n_zero_weight': 0,
        'first_pair': None,
        'mechs': {},
    }


def _update_range(entry, mech, value, gid_pair):
    """Extend one mechanism's ratio range with one value."""
    gid_pair = tuple(gid_pair)
    if mech not in entry['mechs']:
        entry['mechs'][mech] = {
            'min': float(value),
            'max': float(value),
            'min_pair': gid_pair,
            'max_pair': gid_pair,
        }
        return

    stats = entry['mechs'][mech]
    if value < stats['min']:
        stats['min'] = float(value)
        stats['min_pair'] = gid_pair
    if value > stats['max']:
        stats['max'] = float(value)
        stats['max_pair'] = gid_pair


def update_ratio_summary(summaries, pop_pair, gid_pair, mech_weights):
    """Add one logical cell pair to compact receptor-ratio ranges."""
    entry = summaries.setdefault(pop_pair, _new_summary())
    total_weight = float(sum(mech_weights.values()))
    if total_weight == 0:
        entry['n_zero_weight'] += 1
        return

    ratios = {
        str(mech): float(weight / total_weight)
        for mech, weight in mech_weights.items()
    }

    # A missing receptor component contributes a zero normalized weight
    for mech in entry['mechs']:
        _update_range(entry, mech, ratios.get(mech, 0), gid_pair)

    # A newly discovered component was absent from every earlier pair
    for mech, value in ratios.items():
        if mech in entry['mechs']:
            continue
        if entry['n_pairs']:
            _update_range(entry, mech, 0, entry['first_pair'])
        _update_range(entry, mech, value, gid_pair)

    if entry['first_pair'] is None:
        entry['first_pair'] = tuple(gid_pair)
    entry['n_pairs'] += 1


def merge_ratio_summaries(parts):
    """Merge compact receptor-ratio summaries from all ranks."""
    merged = {}
    for part in parts:
        for pop_pair, source in part.items():
            entry = merged.setdefault(pop_pair, _new_summary())

            # Receptors absent from all pairs on one rank have ratio zero there
            if source['n_pairs']:
                for mech in list(entry['mechs']):
                    if mech not in source['mechs']:
                        _update_range(entry, mech, 0, source['first_pair'])
                for mech, stats in source['mechs'].items():
                    if mech not in entry['mechs'] and entry['n_pairs']:
                        _update_range(entry, mech, 0, entry['first_pair'])
                    _update_range(entry, mech, stats['min'], stats['min_pair'])
                    _update_range(entry, mech, stats['max'], stats['max_pair'])

            if entry['first_pair'] is None:
                entry['first_pair'] = source['first_pair']
            entry['n_pairs'] += source['n_pairs']
            entry['n_zero_weight'] += source['n_zero_weight']
    return merged


def validate_ratio_summaries(summaries, tolerance):
    """Raise on varying receptor mixtures and return compact metadata."""
    failures = []
    max_range = 0
    n_pairs = 0
    n_zero_weight = 0

    # Check every population pair and retain only compact failure details
    for pop_pair in sorted(summaries):
        entry = summaries[pop_pair]
        n_pairs += entry['n_pairs']
        n_zero_weight += entry['n_zero_weight']
        for mech, stats in sorted(entry['mechs'].items()):
            ratio_range = stats['max'] - stats['min']
            max_range = max(max_range, ratio_range)
            if ratio_range <= tolerance:
                continue
            failures.append({'pop_pair': pop_pair, 'mech': mech, **stats})

    # Report a bounded set of representative failures
    if failures:
        details = []
        for failure in failures[:10]:
            pop_pre, pop_post = failure['pop_pair']
            details.append(
                f"{pop_pre} -> {pop_post}, {failure['mech']}: "
                f"[{failure['min']:.9g}, {failure['max']:.9g}], "
                f"pairs {failure['min_pair']} and {failure['max_pair']}"
            )
        suffix = '' if len(failures) <= 10 else f' (+{len(failures) - 10} more)'
        raise ValueError(
            'Non-constant instantiated receptor-weight ratios detected: ' +
            '; '.join(details) + suffix
        )

    return {
        'status': 'passed',
        'population_pairs_checked': sum(
            entry['n_pairs'] > 0 for entry in summaries.values()
        ),
        'cell_pairs_checked': n_pairs,
        'zero_weight_cell_pairs_skipped': n_zero_weight,
        'max_ratio_range': float(max_range),
    }
