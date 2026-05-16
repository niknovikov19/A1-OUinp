import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path


# ---------------------------------------------------------------------------
# Core generators
# ---------------------------------------------------------------------------

def poisson_generator(rate, t_start=0.0, t_stop=1000.0, seed=None):
    """Homogeneous Poisson process. Returns np.ndarray of spike times (ms)."""
    rng = np.random.RandomState(seed)
    if rate <= 0:
        return np.array([])

    n_exp = (t_stop - t_start) / 1000.0 * rate
    n_draw = int(np.ceil(n_exp + 3 * np.sqrt(max(n_exp, 1))))
    n_draw = max(n_draw, 100)

    isi = rng.exponential(1.0 / rate, n_draw) * 1000.0
    spikes = np.cumsum(isi) + t_start

    # Extend if buffer was too short
    while len(spikes) == 0 or spikes[-1] < t_stop:
        extra = rng.exponential(1.0 / rate, n_draw) * 1000.0
        t_last = spikes[-1] if len(spikes) > 0 else t_start
        extra_spikes = np.cumsum(extra) + t_last
        spikes = np.concatenate([spikes, extra_spikes])
        if extra_spikes[-1] > t_stop:
            break

    return spikes[spikes < t_stop]


def inh_poisson_generator(rate, t, t_stop, seed=None):
    """
    Single inhomogeneous Poisson spike train via thinning.

    Parameters
    ----------
    rate   : array-like (N,)  - rate in Hz at each time bin
    t      : array-like (N,)  - bin left-edge times in ms
    t_stop : float            - end time in ms
    seed   : int | None

    Returns
    -------
    list of spike times in ms

    Notes
    -----
    Uses the thinning method (Devroye 1986):
      1. Generate homogeneous Poisson process at rmax = max(rate)
      2. Accept each candidate spike with probability rate(t_spike) / rmax

    Fixes vs original input.py inh_poisson_generator:
      - rate[idx] vectorised look-up instead of slow Python list comprehension
      - correct empty-train early return (original discarded np.array([]))
      - independent RNG seeds for homogeneous process and thinning draws,
        avoiding the correlation introduced by sharing the same seed
    """
    rate = np.asarray(rate, dtype=np.float64)
    t    = np.asarray(t,    dtype=np.float64)

    if t.shape != rate.shape:
        raise ValueError(f'shape mismatch: t {t.shape} vs rate {rate.shape}')

    rmax = np.max(rate)
    if rmax <= 0:
        return []

    # Split into two independent sub-seeds so the homogeneous process and
    # the thinning uniform draws are uncorrelated (bug in original: both
    # used the same seed, causing subtle correlations).
    if seed is None:
        seed_hom = seed_thin = None
    else:
        rng_master = np.random.RandomState(seed)
        seed_hom  = int(rng_master.randint(0, 2**31))
        seed_thin = int(rng_master.randint(0, 2**31))

    ps = poisson_generator(rate=rmax, t_start=float(t[0]),
                           t_stop=t_stop, seed=seed_hom)
    if len(ps) == 0:
        return []

    rng_thin = np.random.RandomState(seed_thin)
    rn = rng_thin.uniform(0.0, 1.0, len(ps))

    # Vectorised rate look-up: find which bin each candidate spike falls in
    idx = np.searchsorted(t, ps, side='right') - 1
    idx = np.clip(idx, 0, len(rate) - 1)
    spike_rate = rate[idx]

    return ps[rn < spike_rate / rmax].tolist()


def generate_trains(rate, t, t_stop, n_cells, base_seed=None):
    """
    Generate independent spike trains for a population of cells.

    Parameters
    ----------
    rate      : array-like (N,) - rate in Hz at each time bin
    t         : array-like (N,) - bin left-edge times in ms
    t_stop    : float           - end time in ms
    n_cells   : int             - number of cells
    base_seed : int | None      - cell i uses seed base_seed+i; None = unseeded

    Returns
    -------
    list of n_cells lists, each containing spike times in ms
    """
    return [
        inh_poisson_generator(
            rate, t, t_stop,
            seed=None if base_seed is None else base_seed + i
        )
        for i in range(n_cells)
    ]
