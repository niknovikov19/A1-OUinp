import numpy as np


def _validate_wavelet_inputs(x, t, f, n_cycles):
    """Validate shared local-estimator inputs. """
    x = np.asarray(x, dtype=float)
    t = np.asarray(t, dtype=float)

    # Validate the shared arrays
    if x.ndim != 1 or t.ndim != 1:
        raise ValueError('x and t must be 1D')
    if x.shape != t.shape:
        raise ValueError('x and t must have the same shape')
    if x.size < 2:
        raise ValueError('x and t must have length at least 2')
    if not np.isfinite(f) or f <= 0:
        raise ValueError('f must be positive and finite')
    if not np.isfinite(n_cycles) or n_cycles <= 0:
        raise ValueError('n_cycles must be positive and finite')
    if not np.all(np.isfinite(t)):
        raise ValueError('t must contain only finite values')

    dt_all = np.diff(t)
    if not np.all(dt_all > 0):
        raise ValueError('t must be strictly increasing')

    dt_sample = dt_all[0]
    if not np.allclose(dt_all, dt_sample, rtol=1e-7, atol=1e-12):
        raise ValueError('t must have a fixed time step')

    return x, t, float(dt_sample)

def _morlet_support_params(dt_sample, f, n_cycles):
    """Compute the Gaussian support. """
    sigma_t = n_cycles / (2.0 * np.pi * f)
    half_width = 4.0 * sigma_t
    full_support_samples = 2 * int(np.ceil(half_width / dt_sample)) + 1
    return sigma_t, half_width, full_support_samples

def _validate_min_valid_mass_frac(min_valid_mass_frac):
    """Validate the minimum valid mass fraction. """
    if (
        not np.isfinite(min_valid_mass_frac)
        or min_valid_mass_frac < 0.0
        or min_valid_mass_frac > 1.0
    ):
        raise ValueError('min_valid_mass_frac must be finite and lie in [0, 1]')
    return float(min_valid_mass_frac)

def _validate_nan_norm(nan_norm):
    """Validate the Morlet NaN normalization mode. """
    if nan_norm is None:
        return None

    aliases = {
        'coherent': 'coherent',
        'envelope': 'coherent',
        'envelope_mass': 'coherent',
        'noise': 'noise',
        'energy': 'noise',
        'none': None,
        'raw': None,
    }
    if not isinstance(nan_norm, str):
        raise ValueError("nan_norm must be None or one of: 'coherent', 'noise', 'none'")

    key = nan_norm.lower()
    if key not in aliases:
        raise ValueError("nan_norm must be one of: 'coherent', 'noise', 'none'")
    return aliases[key]

def _validate_power_mode(power_mode):
    """Validate the Morlet power mode. """
    aliases = {
        'coherent': 'coherent',
        'coherent_coeff': 'coherent',
        'envelope': 'coherent',
        'envelope_mass': 'coherent',
        'noise': 'noise',
        'noise_coeff': 'noise',
        'energy': 'noise',
        'amplitude2': 'amp2',
        'amp2': 'amp2',
        'a2': 'amp2',
        'A2': 'amp2',
    }
    if not isinstance(power_mode, str):
        raise ValueError("power_mode must be one of: 'coherent', 'noise', 'amp2'")

    key = power_mode if power_mode == 'A2' else power_mode.lower()
    if key not in aliases:
        raise ValueError("power_mode must be one of: 'coherent', 'noise', 'amp2'")
    return aliases[key]

def _validate_freq_grid(f0, fband, df):
    """Validate and build the frequency grid. """
    if not np.isfinite(f0) or f0 <= 0:
        raise ValueError('f0 must be positive and finite')
    if not np.isfinite(fband) or fband < 0:
        raise ValueError('fband must be finite and non-negative')
    if not np.isfinite(df) or df <= 0:
        raise ValueError('df must be positive and finite')

    f_min = f0 - fband
    f_max = f0 + fband
    if f_min <= 0:
        raise ValueError('f0 - fband must be positive')

    ff = np.arange(f_min, f_max + 0.5 * df, df, dtype=float)
    if ff.size == 0:
        raise ValueError('frequency grid is empty')
    return ff

def _validate_drop_win(drop_win):
    """Validate the optional exclusion window. """
    if drop_win is None:
        return None, None

    drop_win = np.asarray(drop_win, dtype=float).ravel()
    if drop_win.size != 2:
        raise ValueError('drop_win must be None or have length 2')
    if not np.all(np.isfinite(drop_win)):
        raise ValueError('drop_win must contain only finite values')

    t_pre, t_post = float(drop_win[0]), float(drop_win[1])
    if t_pre > t_post:
        raise ValueError('drop_win must satisfy t_pre <= t_post')
    return t_pre, t_post

def _build_eval_centers(t, dt_sample, f_ref, n_cycles, overlap):
    """Build shared evaluation centers for sliding power. """
    if not np.isfinite(overlap) or overlap < 0.0 or overlap > 1.0:
        raise ValueError('overlap must be finite and lie in [0, 1]')

    _, _, full_support_samples = _morlet_support_params(dt_sample, f_ref, n_cycles)
    step_samples = max(1, int(round(full_support_samples * (1.0 - overlap))))
    idx_eval = np.arange(0, t.size, step_samples, dtype=int)
    if idx_eval[-1] != t.size - 1:
        idx_eval = np.append(idx_eval, t.size - 1)
    return t[idx_eval].copy()

def _validate_fit_options(t0, fit_intercept, exclude_edges, min_valid_mass_frac):
    """Validate fit-specific options. """
    if not np.isfinite(t0):
        raise ValueError('t0 must be finite')
    if not isinstance(fit_intercept, (bool, np.bool_)):
        raise ValueError('fit_intercept must be True or False')
    if not isinstance(exclude_edges, (bool, np.bool_)):
        raise ValueError('exclude_edges must be True or False')
    _validate_min_valid_mass_frac(min_valid_mass_frac)

def _empty_sinusoid_fit_result():
    """Return a failed-fit result. """
    return {'a': np.nan, 'b': np.nan, 'c': np.nan, 'phase': np.nan, 'amp': np.nan,
            'amp2': np.nan, 'osc_power': np.nan, 'weighted_fit_power': np.nan,
            'valid_mass_frac': np.nan, 'n_valid': 0, 'rank': 0,
            'residual_sse': np.nan}

def _failed_sinusoid_fit_result(**updates):
    """Return a failed-fit result with selected fields filled. """
    out = _empty_sinusoid_fit_result()
    out.update(updates)
    return out


def _morlet_local_terms(
    x, t, t0, f, n_cycles,
    subtract_local_mean=False, exclude_edges=False,
    min_valid_mass_frac=0,
):
    """Compute reusable local Morlet terms. """
    x, t, dt_sample = _validate_wavelet_inputs(x, t, f, n_cycles)
    min_valid_mass_frac = _validate_min_valid_mass_frac(min_valid_mass_frac)

    # Validate the target time
    if not np.isfinite(t0):
        raise ValueError('t0 must be finite')

    # Build the local support window
    sigma_t, half_width, _ = _morlet_support_params(dt_sample, f, n_cycles)
    if exclude_edges and ((t0 - half_width) < t[0] or (t0 + half_width) > t[-1]):
        return None

    dtau = t - t0
    support = np.abs(dtau) <= half_width
    if not np.any(support):
        return None

    g_support = np.exp(-0.5 * (dtau[support] / sigma_t) ** 2)
    full_mass = np.sum(g_support)
    full_energy = np.sum(g_support**2)
    if full_mass <= np.finfo(float).eps or full_energy <= np.finfo(float).eps:
        return None

    # Keep only valid samples inside the window
    valid = support & np.isfinite(x)
    if not np.any(valid):
        return None

    g_valid = np.exp(-0.5 * (dtau[valid] / sigma_t) ** 2)
    valid_mass = np.sum(g_valid)
    valid_energy = np.sum(g_valid**2)
    if valid_mass <= np.finfo(float).eps or valid_energy <= np.finfo(float).eps:
        return None

    valid_mass_frac = valid_mass / full_mass
    if valid_mass_frac < min_valid_mass_frac:
        return None

    x_valid = x[valid]
    if subtract_local_mean:
        # Remove the local weighted mean
        x_valid = x_valid - np.sum(g_valid * x_valid) / valid_mass

    # Build the valid complex wavelet samples
    psi_valid = np.exp(2j * np.pi * f * dtau[valid]) * g_valid
    coef_raw = dt_sample * np.sum(x_valid * np.conj(psi_valid))
    if np.abs(coef_raw) <= np.finfo(float).eps:
        return None

    return {'coef_raw': coef_raw, 'dt_sample': dt_sample, 'full_mass': full_mass,
            'valid_mass': valid_mass, 'full_energy': full_energy,
            'valid_energy': valid_energy, 'valid_mass_frac': valid_mass_frac}


def _normalize_morlet_coef(terms, nan_norm):
    """Normalize a Morlet coefficient for missing samples. """
    if terms is None:
        return np.nan

    nan_norm = _validate_nan_norm(nan_norm)
    coef = terms['coef_raw']
    if nan_norm == 'coherent':
        coef = coef * (terms['full_mass'] / terms['valid_mass'])
    elif nan_norm == 'noise':
        coef = coef * np.sqrt(terms['full_energy'] / terms['valid_energy'])

    if np.abs(coef) <= np.finfo(float).eps:
        return np.nan
    return coef


def _morlet_local_coef(
    x, t, t0, f, n_cycles, nan_norm='coherent',
    subtract_local_mean=False, exclude_edges=False,
    min_valid_mass_frac=0.0,
):
    """Compute the local Morlet coefficient. """
    terms = _morlet_local_terms(
        x, t, t0, f, n_cycles, subtract_local_mean=subtract_local_mean,
        exclude_edges=exclude_edges, min_valid_mass_frac=min_valid_mass_frac,
    )
    return _normalize_morlet_coef(terms, nan_norm)


def morlet_phase_local(
    x, t, t0, f, n_cycles,
    subtract_local_mean=False, exclude_edges=False,
    min_valid_mass_frac=0.0,
):
    """Compute local Morlet phase. """
    # Reduce the coefficient to phase
    coef = _morlet_local_coef(
        x, t, t0, f, n_cycles, nan_norm='coherent',
        subtract_local_mean=subtract_local_mean,
        exclude_edges=exclude_edges,
        min_valid_mass_frac=min_valid_mass_frac,
    )
    return np.nan if not np.isfinite(coef) else float(np.angle(coef))


def morlet_power_local(
    x, t, t0, f, n_cycles,
    power_mode='coherent',
    subtract_local_mean=False, exclude_edges=False,
    min_valid_mass_frac=0
):
    """Compute local Morlet power. """
    power_mode = _validate_power_mode(power_mode)
    terms = _morlet_local_terms(
        x, t, t0, f, n_cycles,
        subtract_local_mean=subtract_local_mean,
        exclude_edges=exclude_edges,
        min_valid_mass_frac=min_valid_mass_frac
    )
    if terms is None:
        return np.nan

    # Convert the coefficient to the requested power summary
    if power_mode == 'coherent':
        coef = _normalize_morlet_coef(terms, 'coherent')
        return np.nan if not np.isfinite(coef) else float(np.abs(coef) ** 2)
    if power_mode == 'noise':
        coef = _normalize_morlet_coef(terms, 'noise')
        return np.nan if not np.isfinite(coef) else float(np.abs(coef) ** 2)
    amp = 2.0 * np.abs(terms['coef_raw']) / (terms['dt_sample'] * terms['valid_mass'])
    return float(amp**2)


def morlet_power(
    x, t, f, n_cycles, overlap=1.0,
    power_mode='coherent',
    subtract_local_mean=False, exclude_edges=False,
    min_valid_mass_frac=0
):
    """Compute sliding Morlet power. """
    x, t, dt_sample = _validate_wavelet_inputs(x, t, f, n_cycles)

    # Build the sparse center grid
    power_mode = _validate_power_mode(power_mode)
    _validate_min_valid_mass_frac(min_valid_mass_frac)
    t_power = _build_eval_centers(t, dt_sample, f, n_cycles, overlap)

    # Evaluate local power at each center
    power = np.full(t_power.shape, np.nan, dtype=float)
    for i, t0 in enumerate(t_power):
        power[i] = morlet_power_local(
            x, t, t0, f, n_cycles, power_mode=power_mode,
            subtract_local_mean=subtract_local_mean, exclude_edges=exclude_edges,
            min_valid_mass_frac=min_valid_mass_frac,
        )
    return t_power, power


def morlet_power_freqs(
    x, t, f0, fband, df, n_cycles, overlap=1.0,
    power_mode='coherent',
    subtract_local_mean=False, exclude_edges=False,
    min_valid_mass_frac=0
):
    """Compute sliding Morlet power over a frequency grid. """
    x, t, dt_sample = _validate_wavelet_inputs(x, t, f0, n_cycles)
    ff = _validate_freq_grid(f0, fband, df)
    power_mode = _validate_power_mode(power_mode)
    _validate_min_valid_mass_frac(min_valid_mass_frac)

    # Build one shared center grid from the lowest frequency support
    t_power = _build_eval_centers(t, dt_sample, np.min(ff), n_cycles, overlap)
    power = np.full((ff.size, t_power.size), np.nan, dtype=float)
    for j, f in enumerate(ff):
        for i, t0 in enumerate(t_power):
            power[j, i] = morlet_power_local(
                x, t, t0, f, n_cycles, power_mode=power_mode,
                subtract_local_mean=subtract_local_mean,
                exclude_edges=exclude_edges,
                min_valid_mass_frac=min_valid_mass_frac,
            )
    return t_power, ff, power


def itc(
    x, t, tt_stim, f, n_cycles,
    drop_win=None,
    subtract_local_mean=False, exclude_edges=False,
    min_valid_mass_frac=0
):
    """Compute ITC from local Morlet phases. """
    x = np.asarray(x, dtype=float)
    t = np.asarray(t, dtype=float)
    tt_stim = np.asarray(tt_stim, dtype=float)
    _validate_wavelet_inputs(x, t, f, n_cycles)
    _validate_min_valid_mass_frac(min_valid_mass_frac)

    # Validate the stimulus times and drop window
    if tt_stim.ndim != 1:
        raise ValueError('tt_stim must be 1D')
    if not np.all(np.isfinite(tt_stim)):
        raise ValueError('tt_stim must contain only finite values')
    t_pre, t_post = _validate_drop_win(drop_win)

    # Evaluate a phase at each stimulus time
    phases = np.full(tt_stim.shape, np.nan, dtype=float)
    for i, t0 in enumerate(tt_stim):
        if drop_win is None:
            x_eval = x
        else:
            x_eval = x.copy()
            drop_mask = (t >= t0 + t_pre) & (t <= t0 + t_post)
            x_eval[drop_mask] = np.nan

        phases[i] = morlet_phase_local(
            x_eval, t, t0, f, n_cycles,
            subtract_local_mean=subtract_local_mean,
            exclude_edges=exclude_edges,
            min_valid_mass_frac=min_valid_mass_frac
        )

    # Average the valid phases on the unit circle
    valid = np.isfinite(phases)
    if not np.any(valid):
        return np.nan, np.nan, phases

    phasor_mean = np.mean(np.exp(1j * phases[valid]))
    if np.abs(phasor_mean) <= np.finfo(float).eps:
        return 0.0, np.nan, phases
    return float(np.abs(phasor_mean)), float(np.angle(phasor_mean)), phases


def sinusoid_fit_local(
    x, t, t0, f, n_cycles, *,
    fit_intercept=True, exclude_edges=True,
    min_valid_mass_frac=0, rcond=None
):
    """Fit a Gaussian-weighted local sinusoid and intercept. """
    x, t, dt_sample = _validate_wavelet_inputs(x, t, f, n_cycles)
    _validate_fit_options(t0, fit_intercept, exclude_edges, min_valid_mass_frac)

    # Build the local fit window
    sigma_t, half_width, _ = _morlet_support_params(dt_sample, f, n_cycles)
    if exclude_edges and ((t0 - half_width) < t[0] or (t0 + half_width) > t[-1]):
        return _empty_sinusoid_fit_result()

    tau = t - t0
    support = np.abs(tau) <= half_width
    if not np.any(support):
        return _empty_sinusoid_fit_result()

    g_support = np.exp(-0.5 * (tau[support] / sigma_t) ** 2)
    full_mass = np.sum(g_support)
    if full_mass <= np.finfo(float).eps:
        return _empty_sinusoid_fit_result()

    # Keep only valid samples inside the window
    valid = support & np.isfinite(x)
    if not np.any(valid):
        return _empty_sinusoid_fit_result()

    tau_v = tau[valid]
    y = x[valid]
    w = np.exp(-0.5 * (tau_v / sigma_t) ** 2)
    valid_mass = np.sum(w)
    if valid_mass <= np.finfo(float).eps:
        return _empty_sinusoid_fit_result()

    valid_mass_frac = valid_mass / full_mass
    if valid_mass_frac < min_valid_mass_frac:
        return _failed_sinusoid_fit_result(
            valid_mass_frac=float(valid_mass_frac), n_valid=int(valid.sum())
        )

    # Build the weighted design matrix
    omega = 2.0 * np.pi * f
    cos_col = np.cos(omega * tau_v)
    sin_col = np.sin(omega * tau_v)
    X = (np.column_stack([cos_col, sin_col, np.ones_like(tau_v)])
         if fit_intercept else np.column_stack([cos_col, sin_col]))
    n_params = 3 if fit_intercept else 2
    if y.size < n_params:
        return _failed_sinusoid_fit_result(
            valid_mass_frac=float(valid_mass_frac), n_valid=int(valid.sum())
        )

    # Solve the weighted least-squares problem
    sqrt_w = np.sqrt(w)
    Xw = X * sqrt_w[:, None]
    yw = y * sqrt_w
    beta, _, rank, _ = np.linalg.lstsq(Xw, yw, rcond=rcond)
    if rank < n_params:
        return _failed_sinusoid_fit_result(
            valid_mass_frac=float(valid_mass_frac), n_valid=int(valid.sum()),
            rank=int(rank),
        )

    # Convert the fit to phase and power summaries
    a = float(beta[0])
    b = float(beta[1])
    c = float(beta[2]) if fit_intercept else 0.0
    amp2 = a * a + b * b
    amp = float(np.sqrt(amp2))
    phase = np.nan if amp <= np.finfo(float).eps else float(np.arctan2(-b, a))
    x_osc_fit = a * cos_col + b * sin_col
    weighted_fit_power = float(np.sum(w * x_osc_fit**2) / valid_mass)
    resid = y - X @ beta
    residual_sse = float(np.sum(w * resid**2))

    return {'a': a, 'b': b, 'c': c, 'phase': phase, 'amp': amp,
            'amp2': float(amp2), 'osc_power': float(0.5 * amp2),
            'weighted_fit_power': weighted_fit_power,
            'valid_mass_frac': float(valid_mass_frac), 'n_valid': int(valid.sum()),
            'rank': int(rank), 'residual_sse': residual_sse}


def sinusoid_fit_phase_local(
    x, t, t0, f, n_cycles, *,
    fit_intercept=True, exclude_edges=True,
    min_valid_mass_frac=0, rcond=None
):
    """Compute local phase from the sinusoid fit. """
    fit = sinusoid_fit_local(
        x, t, t0, f, n_cycles,
        fit_intercept=fit_intercept, exclude_edges=exclude_edges,
        min_valid_mass_frac=min_valid_mass_frac, rcond=rcond
    )
    return float(fit['phase']) if np.isfinite(fit['phase']) else np.nan


def sinusoid_fit_power_local(
    x, t, t0, f, n_cycles, *,
    fit_intercept=True, exclude_edges=True,
    min_valid_mass_frac=0, rcond=None
):
    """Compute local fitted oscillatory power. """
    fit = sinusoid_fit_local(
        x, t, t0, f, n_cycles,
        fit_intercept=fit_intercept, exclude_edges=exclude_edges,
        min_valid_mass_frac=min_valid_mass_frac, rcond=rcond
    )
    value = fit['weighted_fit_power']
    return float(value) if np.isfinite(value) else np.nan


def sinusoid_fit_power(
    x, t, f, n_cycles, overlap=1.0, *,
    fit_intercept=True, exclude_edges=True,
    min_valid_mass_frac=0, rcond=None
):
    """Compute sliding fitted oscillatory power. """
    x, t, dt_sample = _validate_wavelet_inputs(x, t, f, n_cycles)
    # Build the sparse center grid
    t_power = _build_eval_centers(t, dt_sample, f, n_cycles, overlap)

    # Evaluate the local fit at each center
    power = np.full(t_power.shape, np.nan, dtype=float)
    for i, t0 in enumerate(t_power):
        power[i] = sinusoid_fit_power_local(
            x, t, t0, f, n_cycles,
            fit_intercept=fit_intercept, exclude_edges=exclude_edges,
            min_valid_mass_frac=min_valid_mass_frac, rcond=rcond
        )
    return t_power, power


def sinusoid_fit_power_freqs(
    x, t, f0, fband, df, n_cycles, overlap=1.0, *,
    fit_intercept=True, exclude_edges=True,
    min_valid_mass_frac=0, rcond=None
):
    """Compute sliding fitted power over a frequency grid. """
    x, t, dt_sample = _validate_wavelet_inputs(x, t, f0, n_cycles)
    ff = _validate_freq_grid(f0, fband, df)

    # Build one shared center grid from the lowest frequency support
    t_power = _build_eval_centers(t, dt_sample, np.min(ff), n_cycles, overlap)
    power = np.full((ff.size, t_power.size), np.nan, dtype=float)
    for j, f in enumerate(ff):
        for i, t0 in enumerate(t_power):
            power[j, i] = sinusoid_fit_power_local(
                x, t, t0, f, n_cycles,
                fit_intercept=fit_intercept,
                exclude_edges=exclude_edges,
                min_valid_mass_frac=min_valid_mass_frac,
                rcond=rcond,
            )
    return t_power, ff, power


def sinusoid_fit_coeff_freqs(
    x, t, f0, fband, df, n_cycles, overlap=1.0, *,
    fit_intercept=True, exclude_edges=True,
    min_valid_mass_frac=0, rcond=None
):
    """Compute sliding fitted complex coefficients over a frequency grid."""
    x, t, dt_sample = _validate_wavelet_inputs(x, t, f0, n_cycles)
    ff = _validate_freq_grid(f0, fband, df)

    # Build one shared center grid from the lowest frequency support
    t_coeff = _build_eval_centers(t, dt_sample, np.min(ff), n_cycles, overlap)
    coeff = np.full((ff.size, t_coeff.size), np.nan + 1j * np.nan,
                    dtype=complex)
    for j, f in enumerate(ff):
        for i, t0 in enumerate(t_coeff):
            fit = sinusoid_fit_local(
                x, t, t0, f, n_cycles,
                fit_intercept=fit_intercept,
                exclude_edges=exclude_edges,
                min_valid_mass_frac=min_valid_mass_frac,
                rcond=rcond,
            )
            if np.isfinite(fit['a']) and np.isfinite(fit['b']):
                coeff[j, i] = fit['a'] - 1j * fit['b']
    return t_coeff, ff, coeff


def sinusoid_fit_itc(
    x, t, tt_stim, f, n_cycles, drop_win=None, *, fit_intercept=True,
    exclude_edges=True, min_valid_mass_frac=0.0, rcond=None,
):
    """Compute stimulus-locked ITC from local sinusoid fits. """
    x = np.asarray(x, dtype=float)
    t = np.asarray(t, dtype=float)
    tt_stim = np.asarray(tt_stim, dtype=float)
    _validate_wavelet_inputs(x, t, f, n_cycles)

    # Validate the stimulus times and drop window
    if tt_stim.ndim != 1:
        raise ValueError('tt_stim must be 1D')
    if not np.all(np.isfinite(tt_stim)):
        raise ValueError('tt_stim must contain only finite values')
    t_pre, t_post = _validate_drop_win(drop_win)

    # Fit a phase at each stimulus time
    phases = np.full(tt_stim.shape, np.nan, dtype=float)
    for i, t0 in enumerate(tt_stim):
        if drop_win is None:
            x_eval = x
        else:
            x_eval = x.copy()
            drop_mask = (t >= t0 + t_pre) & (t <= t0 + t_post)
            x_eval[drop_mask] = np.nan

        phases[i] = sinusoid_fit_phase_local(
            x_eval, t, t0, f, n_cycles,
            fit_intercept=fit_intercept, exclude_edges=exclude_edges,
            min_valid_mass_frac=min_valid_mass_frac, rcond=rcond,
        )

    # Average the valid phases on the unit circle
    valid = np.isfinite(phases)
    if not np.any(valid):
        return np.nan, np.nan, phases

    phasor_mean = np.mean(np.exp(1j * phases[valid]))
    if np.abs(phasor_mean) <= np.finfo(float).eps:
        return 0.0, np.nan, phases
    return float(np.abs(phasor_mean)), float(np.angle(phasor_mean)), phases
