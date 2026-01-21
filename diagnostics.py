from collections import Counter, defaultdict

from neuron import h
import numpy as np


def count_conns(sim):
    # Count NetCon-like connections stored in NetPyNE
    n_conns = sum(len(c.conns) for c in sim.net.cells)
    #print(f'Rank {sim.rank}: nconns={n_conns}', flush=True)
    n_conns_total = sim.pc.allreduce(n_conns, 1)  # 1=sum
    if sim.rank == 0:
        print("Total NetPyNE conns (sum of cell.conns):", n_conns_total, flush=True)

    # Count actual NEURON NetCon objects
    local_netcons = 0
    for c in sim.net.cells:
        for conn in c.conns:
            h = conn.get('hObj', None)
            if h is None:
                continue
            if isinstance(h, list):
                local_netcons += len(h)
            else:
                local_netcons += 1
    total_netcons = sim.pc.allreduce(local_netcons, 1)
    if sim.rank == 0:
        print("Total NEURON NetCons counted via conn['hObj']:", total_netcons)

def count_synmechs(sim):
    local = 0
    for c in sim.net.cells:
        # only for compartmental cells
        if hasattr(c, "secs"):
            for secName, sec in c.secs.items():
                # NetPyNE keeps synMechs list per sec
                if "synMechs" in sec:
                    local += len(sec["synMechs"])
    total = sim.pc.allreduce(local, 1)
    if sim.rank == 0:
        print("Total synMech instances:", total)

def count_netcons_neuron(sim):
    lst = h.List("NetCon")
    n_local = int(lst.count())
    n_total = sim.pc.allreduce(n_local, 1)
    if sim.rank == 0:
        print("Total NEURON NetCons (h.List('NetCon')):", n_total)

def count_pointprocesses(sim):
    lst = h.List("PointProcess")
    n_local = int(lst.count())
    n_total = sim.pc.allreduce(n_local, 1)
    if sim.rank == 0:
        print("Total NEURON PointProcesses:", n_total)

def report_min_delay(sim, default_max_step=10.0):
    local_min = sim.pc.set_maxstep(default_max_step)
    global_min = sim.pc.allreduce(local_min, 2)  # min
    if sim.rank == 0:
        print("Global minDelay (spanning NetCons):", global_min, "ms")


def _build_gid2pop(sim):
    """Call after sim.gatherData(); returns dict on rank 0, None on other ranks."""
    if sim.rank != 0:
        return None
    gid2pop = {}
    for c in getattr(sim.net, 'allCells', []):    # each c is a dict after gather
        gid = c.get('gid')
        if gid is None:
            continue
        # population usually under tags.pop
        pop = None
        tags = c.get('tags')
        if isinstance(tags, dict):
            pop = tags.get('pop')
        if pop is None:
            pop = c.get('pop')
        gid2pop[gid] = pop
    return gid2pop


def _gather_labels_via_broadcast_loop(sim, local_labels_per_group, debug=False):
    nh = sim.nhosts
    rank = sim.rank
    merged_labels = {k: set() for k in local_labels_per_group.keys()}

    for root in range(nh):
        # each root broadcasts its own maps in turn
        if debug and rank == 0:
            print(f"[rank {rank}] broadcasting root {root}")

        # for each sec_group broadcast that group's labels from root
        for sec_group, labels_local in local_labels_per_group.items():
            if rank == root:
                obj = labels_local
            else:
                obj = None
            recv = sim.pc.py_broadcast(obj, root)
            if recv:
                merged_labels[sec_group].update(recv)

    # convert sets to sorted lists
    merged = {k: sorted(v) for k, v in merged_labels.items()}
    return merged


def count_conn_target_secs(sim, sec_groups, pops_pre, pops_post):
    # Count conns by section groups at each rank
    local = defaultdict(int)
    local_labels = {k: [] for k in sec_groups}
    gid2pop = _build_gid2pop(sim)
    gid2pop = sim.pc.py_broadcast(gid2pop, 0)
    if sim.rank == 0:
        print(f'Num. gid2pop elements: {len(gid2pop)}')
        #items = sorted(gid2pop.items())[:100]
        #print("First gid->pop entries:", items, flush=True)
    for c in sim.net.cells:
        if c.tags['pop'] not in pops_post:
            continue
        for conn in c.conns:
            if gid2pop.get(conn.get('preGid')) not in pops_pre:
                continue
            sec = conn.get('sec', None) or conn.get('postSec', None) or 'UNKNOWN'
            #sec_group = 'other'
            for k, names in sec_groups.items():
                if sec in names:
                    #sec_group = k
                    #break
                    local[k] += 1
                    local_labels[k].append(conn.get('label'))
            #local[sec_group] += 1
    
    #print(f'Rank {sim.rank}:')
    for k in local_labels:
        local_labels[k] = list(set(local_labels[k]))
        #print(f'{k}: ', local_labels[k])

    # Collect the counts from all ranks
    total = {}
    for sec_group in sec_groups:
        total[sec_group] = sim.pc.allreduce(local.get(sec_group, 0), 1)  # sum
    
    # Collect labels from all ranks
    """ all_labels = {}
    for sec_group in sec_groups:
        labels_local = local_labels.get(sec_group, [])
        labels_global = sim.pc.py_alltoall(labels_local)
        # Flatten list of lists and unique
        labels_set = set()
        for sublist in labels_global:
            labels_set.update(sublist)
        all_labels[sec_group] = list(labels_set) """
    all_labels = _gather_labels_via_broadcast_loop(sim, local_labels, debug=False)
    
    if sim.rank == 0:
        print('Connection names per section group:')
        for k in all_labels:
            print(f'{k}: ', all_labels[k])

    return total


def conn_distance_percentiles(sim, bins_um=None):
    if bins_um is None:
        bins_um = np.arange(0, 201, 2.5)

    local_counts = np.zeros(len(bins_um) - 1, dtype=np.int64)

    for c in sim.net.cells:
        # Skip if no sections
        if not hasattr(c, 'secs') or not c.secs:
            continue
        
        # Skip if no soma or no NEURON object
        if "soma" not in c.secs:
            continue
        if "hObj" not in c.secs["soma"]:
            continue

        soma = c.secs["soma"]["hObj"]
        h.distance(0, 0.5, sec=soma)  # distance reference = soma(0.5)

        for conn in c.conns:
            secName = conn.get("sec", None)
            loc = conn.get("loc", None)
            if secName is None or loc is None:
                continue
            if secName not in c.secs:
                continue
            if "hObj" not in c.secs[secName]:
                continue

            sec = c.secs[secName]["hObj"]
            d = float(h.distance(loc, sec=sec))  # µm

            j = np.searchsorted(bins_um, d, side="right") - 1
            if 0 <= j < local_counts.size:
                local_counts[j] += 1

    # allreduce bins (scalar allreduce, loop)
    global_counts = np.zeros_like(local_counts)
    for i in range(local_counts.size):
        global_counts[i] = sim.pc.allreduce(int(local_counts[i]), 1)  # sum

    if sim.rank != 0:
        return

    total = int(global_counts.sum())
    if total == 0:
        print("No distances computed - debugging info:")
        print(f"  Number of cells: {len(sim.net. cells)}")
        if sim.net.cells:
            sample_cell = sim.net.cells[0]
            print(f"  Sample cell has secs: {hasattr(sample_cell, 'secs')}")
            print(f"  Sample cell has conns: {hasattr(sample_cell, 'conns')}")
            if hasattr(sample_cell, 'conns'):
                print(f"  Sample cell num conns: {len(sample_cell.conns)}")
            if hasattr(sample_cell, 'secs') and sample_cell.secs:
                print(f"  Sample cell sections: {list(sample_cell. secs.keys())}")
                if 'soma' in sample_cell. secs:
                    print(f"  Soma keys: {list(sample_cell. secs['soma'].keys())}")
        return

    cdf = np.cumsum(global_counts) / total

    def approx_percentile(p):
        # returns left bin edge where CDF crosses p
        idx = int(np.searchsorted(cdf, p))
        idx = min(max(idx, 0), len(bins_um) - 2)
        return float(bins_um[idx])

    p50 = approx_percentile(0.50)
    p90 = approx_percentile(0.90)
    p99 = approx_percentile(0.99)

    #print(f'Distance-to-soma approx percentiles (um): '
    #      f'N={total} p50~{p50:.1f} p90~{p90:.1f} p99~{p99:.1f}')
    print('Dist. counts:\n', global_counts)
