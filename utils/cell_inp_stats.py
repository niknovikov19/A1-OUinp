import json

import numpy as np
import xarray as xr

from external.sim_data_analyzer.data_proc_utils import calc_pop_cv, calc_pop_rate
from utils.cell_inp_ratio import (
    DEFAULT_RATIO_TOL,
    merge_ratio_summaries,
    update_ratio_summary,
    validate_ratio_summaries,
)


# Optional receptor-mixture guardrail
CHECK_RECEPTOR_WEIGHT_RATIOS = 1


# MPI communication
def _allgather(sim, value):
    """All-gather one compact Python value."""
    if sim.nhosts == 1:
        return [value]
    return sim.pc.py_allgather(value)


def _gather_root(sim, value):
    """Gather one compact Python value to rank 0 only."""
    if sim.nhosts == 1:
        return [value]

    # py_alltoall becomes a root gather when only destination 0 gets a value
    send = [None] * sim.nhosts
    send[0] = value
    received = sim.pc.py_alltoall(send)
    sim.pc.barrier()
    return received if sim.rank == 0 else None


def _get_pop_names(sim, include_frz):
    """Resolve analyzed post- and presynaptic population names."""
    pops_post = list(sim.cfg.pops_used)
    pops_pre = list(pops_post)

    # Add only existing frozen counterparts of analyzed populations
    if include_frz:
        pops_pre.extend(
            f'{pop}frz' for pop in pops_post
            if f'{pop}frz' in sim.net.pops
        )
    return pops_post, pops_pre


# Per-cell spike statistics
def _calc_activity(cells, spkid, spkt, t_limits, nspikes_min, pops_cv):
    """Calculate cell rates and CVs using the standard interval rules."""
    t0, t1 = t_limits
    if t1 <= t0:
        raise ValueError(f'Invalid cell-input statistics interval: {t_limits}')

    # Index all in-window local spikes in one pass
    gids = {int(cell.gid) for cell in cells}
    spikes = {gid: [] for gid in gids}
    for gid, time_ms in zip(spkid, spkt):
        gid = int(gid)
        time = float(time_ms) / 1000
        if gid in spikes and t0 <= time <= t1:
            spikes[gid].append(time)

    # Reuse sim_data_analyzer for the repository-standard rate/CV definitions
    activity = {}
    for cell in cells:
        gid = int(cell.gid)
        times = np.sort(np.asarray(spikes[gid], dtype=float))
        rate = calc_pop_rate([times], t_limits)
        cv = np.nan
        if cell.tags['pop'] in pops_cv and len(times) >= nspikes_min:
            cv = calc_pop_cv([times], t_limits, nspikes_min=nspikes_min)
        activity[gid] = {
            'rate': float(rate),
            'cv': float(cv),
        }
    return activity


# Local connection aggregation
def _scan_local_cells(post_cells, gid_info, local_activity,
                      check_weight_ratios):
    """Scan local incoming connections once and form sparse per-cell summaries."""
    missing_gid = object()
    rows = []
    ratio_summaries = {}

    # Every incoming connection is owned by and scanned with its local post cell
    for cell in post_cells:
        pop_post = str(cell.tags['pop'])
        post_gid = int(cell.gid)

        # Group contacts by presynaptic GID
        weights_by_pre_gid = {}
        mech_weights_by_pre_gid = {} if check_weight_ratios else None
        for conn in cell.conns:
            pre_gid = conn['preGid']
            if pre_gid == 'NetStim':
                continue
            source = gid_info.get(pre_gid, missing_gid)
            if source is missing_gid:
                raise ValueError(
                    f'Connection to GID {post_gid} has unresolved preGid {pre_gid}'
                )
            if source is None:
                continue

            pre_gid = int(pre_gid)
            weight = float(conn['weight'])
            weights_by_pre_gid[pre_gid] = (
                weights_by_pre_gid.get(pre_gid, 0) + weight
            )
            if check_weight_ratios:
                syn_mech = str(conn['synMech'])
                mech_weights = mech_weights_by_pre_gid.setdefault(pre_gid, {})
                mech_weights[syn_mech] = mech_weights.get(syn_mech, 0) + weight

        # Finalize sparse population summaries and ratio diagnostics together
        metrics = {}
        for pre_gid, weight in weights_by_pre_gid.items():
            pop_pre, rate = gid_info[pre_gid]
            pop_metrics = metrics.setdefault(pop_pre, {
                'n_pre': 0,
                'rate_sum': 0,
                'w_sum': 0,
                'wr_sum': 0,
            })
            pop_metrics['n_pre'] += 1
            pop_metrics['rate_sum'] += rate
            pop_metrics['w_sum'] += weight
            pop_metrics['wr_sum'] += weight * rate
            if check_weight_ratios:
                update_ratio_summary(
                    ratio_summaries,
                    (pop_pre, pop_post),
                    (pre_gid, post_gid),
                    mech_weights_by_pre_gid[pre_gid],
                )

        rows.append({
            'gid': post_gid,
            'pop_post': pop_post,
            'rate': local_activity[post_gid]['rate'],
            'cv': local_activity[post_gid]['cv'],
            'metrics': metrics,
        })
    return rows, ratio_summaries


# Rank-0 dataset assembly
def build_cell_inp_dataset(rows, pops_pre, attrs=None):
    """Build the dense xarray dataset from compact per-cell rows."""
    rows = sorted(rows, key=lambda row: row['gid'])
    gids = np.asarray([row['gid'] for row in rows], dtype=np.int64)
    pops_pre = np.asarray(list(pops_pre), dtype=str)
    shape = (len(rows), len(pops_pre))

    # Initialize the specified no-input defaults for the full dense output grid
    n_pre = np.zeros(shape, dtype=np.int64)
    r_pre_mean = np.full(shape, np.nan, dtype=float)
    w_sum = np.zeros(shape, dtype=float)
    wr_sum = np.zeros(shape, dtype=float)
    r_pre_wmean = np.full(shape, np.nan, dtype=float)
    pop_pos = {pop: idx for idx, pop in enumerate(pops_pre)}

    # Fill only population inputs present in each sparse rank result
    for gid_pos, row in enumerate(rows):
        for pop_pre, values in row['metrics'].items():
            pre_pos = pop_pos[pop_pre]
            n_pre[gid_pos, pre_pos] = values['n_pre']
            r_pre_mean[gid_pos, pre_pos] = (
                values['rate_sum'] / values['n_pre']
            )
            w_sum[gid_pos, pre_pos] = values['w_sum']
            wr_sum[gid_pos, pre_pos] = values['wr_sum']
            if values['w_sum'] != 0:
                r_pre_wmean[gid_pos, pre_pos] = (
                    values['wr_sum'] / values['w_sum']
                )

    # Assemble explicit variables and coordinates
    dataset = xr.Dataset(
        data_vars={
            'n_pre': (('gid', 'pop_pre'), n_pre),
            'r_pre_mean': (('gid', 'pop_pre'), r_pre_mean),
            'w_sum': (('gid', 'pop_pre'), w_sum),
            'wr_sum': (('gid', 'pop_pre'), wr_sum),
            'r_pre_wmean': (('gid', 'pop_pre'), r_pre_wmean),
            'rate': ('gid', np.asarray([row['rate'] for row in rows])),
            'cv': ('gid', np.asarray([row['cv'] for row in rows])),
        },
        coords={
            'gid': gids,
            'pop_pre': pops_pre,
            'pop_post': ('gid', np.asarray(
                [row['pop_post'] for row in rows], dtype=str
            )),
        },
        attrs={} if attrs is None else attrs,
    )
    dataset['n_pre'].attrs['description'] = 'Unique connected presynaptic GIDs'
    dataset['r_pre_mean'].attrs['units'] = 'Hz'
    dataset['wr_sum'].attrs['units'] = 'nominal_weight * Hz'
    dataset['r_pre_wmean'].attrs['units'] = 'Hz'
    dataset['rate'].attrs['units'] = 'Hz'
    return dataset


# Public distributed entry point
def calc_cell_inp_stats(sim, include_frz=False, nspikes_min=3,
                        ratio_tolerance=DEFAULT_RATIO_TOL):
    """Calculate distributed per-cell input statistics before NetPyNE gather."""
    t_limits = (sim.cfg.t0_calc / 1000, sim.cfg.duration / 1000)
    pops_post, pops_pre = _get_pop_names(sim, include_frz)

    # Calculate rates only for included sources and CVs only where needed later
    pops_post_set = set(pops_post)
    pops_activity = set(pops_pre)
    post_cells = [
        cell for cell in sim.net.cells
        if cell.tags['pop'] in pops_post_set
    ]
    activity_cells = [
        cell for cell in sim.net.cells
        if cell.tags['pop'] in pops_activity
    ]
    local_activity = _calc_activity(
        activity_cells,
        sim.simData['spkid'],
        sim.simData['spkt'],
        t_limits,
        nspikes_min,
        pops_post_set,
    )

    # Mark included sources with pop/rate and known excluded cells with None
    local_gid_info = {}
    for cell in sim.net.cells:
        gid = int(cell.gid)
        if gid in local_activity:
            local_gid_info[gid] = (
                str(cell.tags['pop']),
                local_activity[gid]['rate'],
            )
        else:
            local_gid_info[gid] = None

    # Exchange the compact source lookup needed by every rank
    gid_info = {}
    for rank_info in _allgather(sim, local_gid_info):
        gid_info.update(rank_info)

    # Stream local connectivity and optionally collect ratio summaries
    local_rows, local_ratio_summaries = _scan_local_cells(
        post_cells,
        gid_info,
        local_activity,
        CHECK_RECEPTOR_WEIGHT_RATIOS,
    )

    # Exchange and validate ratio summaries only when the guardrail is enabled
    if CHECK_RECEPTOR_WEIGHT_RATIOS:
        ratio_summaries = merge_ratio_summaries(
            _allgather(sim, local_ratio_summaries)
        )
        ratio_validation = validate_ratio_summaries(
            ratio_summaries,
            tolerance=ratio_tolerance,
        )
    else:
        ratio_validation = {'status': 'skipped', 'reason': 'disabled'}

    # Gather compact cell rows and assemble the dense result only on rank 0
    row_parts = _gather_root(sim, local_rows)
    if sim.rank != 0:
        return None
    rows = [row for part in row_parts for row in part]

    # Store scalar and JSON metadata that round-trip through NetCDF
    attrs = {
        't_start_s': float(t_limits[0]),
        't_stop_s': float(t_limits[1]),
        'nspikes_min': int(nspikes_min),
        'include_frz': int(bool(include_frz)),
        'weight_semantics': (
            "instantiated nominal conn['weight']; synaptic time constants excluded"
        ),
        'dynamic_modulation': 'ignored',
        'receptor_ratio_tolerance': float(ratio_tolerance),
        'receptor_ratio_validation_json': json.dumps(ratio_validation),
    }
    seed = getattr(sim.cfg, 'seed_main', None)
    if seed is not None:
        attrs['seed_main'] = int(seed)
    return build_cell_inp_dataset(rows, pops_pre, attrs=attrs)
