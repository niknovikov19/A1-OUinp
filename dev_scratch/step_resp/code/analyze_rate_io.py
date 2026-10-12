import json
import os
import pickle
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import xarray as xr
from scipy.optimize import curve_fit

DIR_REPO = Path.cwd().parents[1] if 'analysis' in Path.cwd().parts else Path.cwd()
if str(DIR_REPO) not in sys.path:
    sys.path.insert(0, str(DIR_REPO))


# Configuration
EXP_LABEL = (
    'exp_pre_ctx_post_ctx_nseed_5_npre_36_t_5.0_20.0_tri_t0_5000_T_7500_rmax_10xbkg_500_ictrl_wmult_0.25_ee_0.5'
)
CFG_PARAM_FIELDS = {'pop_pre': 'pop_pre', 'seed': 'seed_main'}

# Time interval of spike extraction
spike_t_limits = (1, 20.0)

# Params of rate dynamics
dt_bin = 2e-3
tau_smooth = 10e-3

# Time range used in fitting
t_limits_used = (5, None)

# Additional rate smoothing
smooth_win_s = 0.2

# Per-dimension chunk sizes for the rate dynamics nc-file
rate_chunks = {'pop_pre': 1, 'seed': 1}

NEED_PLOT = 0


# Paths
#dirpath_exp = Path('X:') / EXP_LABEL
dirpath_exp = (DIR_REPO / 'exp_results' / 'batch_rxbkg_unconn_state1_mech1' /
               'net_inpsur_rsweep_newsec_var_seed_pre' / EXP_LABEL)
dirpath_cfg = dirpath_exp / 'cfg'
dirpath_work = dirpath_exp / 'combined'
dirpath_cache = dirpath_work / 'data_proc'
dirpath_res = dirpath_work / 'results'
dirpath_plots = dirpath_res / f'fit_pngs_tau_{smooth_win_s}'

# Create output directories
os.makedirs(dirpath_cache, exist_ok=True)
os.makedirs(dirpath_res, exist_ok=True)
os.makedirs(dirpath_plots, exist_ok=True)


def richards(x, A, K, B, M, nu):
    """Richards function: f(x) = A + (K - A) / (1 + exp(-B * (x - M))) ** (1/nu)"""
    return A + (K - A) / (1 + np.exp(-B * (x - M))) ** (1 / nu)


def richards_derivative(x, A, K, B, M, nu):
    """Compute derivative of Richards function: dR/dx = (K - A) * B * exp(-B(x-M)) / (nu * (1 + exp(-B(x-M)))^(1 + 1/nu))"""
    exp_term = np.exp(-B * (x - M))
    base = (1 + exp_term)
    return (K - A) * B * exp_term / (nu * base ** (1 + 1/nu))


def fit_richards_function(X_fit, Y_fit):
    """Fit Richards function to data and return optimal parameters."""
    # Initial parameter guesses
    A_init = np.min(Y_fit)  # lower asymptote
    K_init = np.max(Y_fit)  # upper asymptote
    B_init = 1.0            # growth rate
    M_init = np.median(X_fit)  # inflection point
    nu_init = 1.0           # shape parameter

    p0 = [A_init, K_init, B_init, M_init, nu_init]

    try:
        # Fit the Richards function
        popt, pcov = curve_fit(richards, X_fit, Y_fit, p0=p0, maxfev=10000)
        return popt, pcov, True
    except Exception as e:
        return None, None, False


def main():
    t1, t2 = spike_t_limits
    rates_cache_path = dirpath_cache / f'rates_dt_{dt_bin}_tau_{tau_smooth}_t_{t1}_{t2}.nc'
    rates_xr = xr.open_dataarray(rates_cache_path, chunks={})
    rates_xr = rates_xr.sel(time=slice(*t_limits_used))
    
    fname_job_cfg_templ = 'cfg_00000_*.json'
    cfg_paths = sorted(dirpath_cfg.glob(fname_job_cfg_templ))
    with cfg_paths[0].open('r', encoding='utf-8') as f:
        cfg0 = json.load(f)['simConfig']
    r_target = cfg0['target_rates']
    
    # Get all population pairs
    pops_pre = rates_xr.pop_pre.values
    pops_post = [pop for pop in rates_xr.pop.values if 'frz' not in pop]
    
    # Smooth window for moving average
    smooth_win_n = max(1, int(round(smooth_win_s / dt_bin)))
    
    # Dictionary to store all fitted coefficients
    all_coefficients = {}
    
    # Initialize the weight matrix W
    W = np.full((len(pops_pre), len(pops_post)), np.nan)
    
    # Calculate total steps
    total_steps = len(pops_pre) * len(pops_post)
    step = 0
    
    # Loop through all pop_pre
    for i_pre, pop_pre in enumerate(pops_pre):
        # Extract and smooth pre-population rates
        R_pre = rates_xr.sel(pop_pre=pop_pre, pop=f'{pop_pre}frz').compute()
        R_pre_sm = R_pre.rolling(time=smooth_win_n, center=True, min_periods=1).mean()
        
        # Extract and smooth all post-population rates
        R_post = rates_xr.sel(pop_pre=pop_pre, pop=pops_post).compute()
        R_post_sm = R_post.rolling(time=smooth_win_n, center=True, min_periods=1).mean()
        
        r0_pre = r_target.get(pop_pre, None)
        
        # Initialize dictionary for this pre-population
        all_coefficients[pop_pre] = {}
        
        # Process pop_post in groups of 6 for subplots
        num_pops_post = len(pops_post)
        num_figs = (num_pops_post + 5) // 6  # Ceiling division
        
        for fig_idx in range(num_figs):
            if NEED_PLOT:
                fig, axes = plt.subplots(2, 3, figsize=(15, 10))
                axes = axes.flatten()
            
            start_idx = fig_idx * 6
            end_idx = min(start_idx + 6, num_pops_post)
            
            for subplot_idx, pop_post_idx in enumerate(range(start_idx, end_idx)):
                pop_post = pops_post[pop_post_idx]
                j_post = pop_post_idx
                step += 1
                #print(f"\r{step}/{total_steps} {pop_pre}->{pop_post}", end='', flush=True)
                print(f"{step}/{total_steps} {pop_pre}->{pop_post}", flush=True)
                
                # Collapse all seeds together
                X_all = R_pre_sm.values.flatten()
                Y_all = R_post_sm.sel(pop=pop_post).values.flatten()
                
                # Remove NaN values
                mask_valid = ~(np.isnan(X_all) | np.isnan(Y_all))
                X_fit = X_all[mask_valid]
                Y_fit = Y_all[mask_valid]
                
                if NEED_PLOT:
                    # Plot all seed data points
                    ax = axes[subplot_idx]
                    for seed in R_pre_sm.seed.values:
                        ax.plot(R_pre_sm.sel(seed=seed),
                            R_post_sm.sel(seed=seed).sel(pop=pop_post),
                            '.', alpha=0.1)
                    
                    # Add reference lines
                    r0_post = r_target.get(pop_post, None)
                    if r0_post is not None:
                        ax.axhline(r0_post, color='k', linestyle='--', alpha=0.8, linewidth=1)
                    if r0_pre is not None:
                        ax.axvline(r0_pre, color='k', linestyle='--', alpha=0.8, linewidth=1)
                    
                    ax.set_xlabel(f'{pop_pre} rate (Hz)', fontsize=10)
                    ax.set_ylabel(f'{pop_post} rate (Hz)', fontsize=10)
                    ax.set_title(f'{pop_pre} -> {pop_post}', fontsize=11)
                    ax.grid(True, alpha=0.3)
                
                # Fit Richards function
                popt, pcov, success = fit_richards_function(X_fit, Y_fit)
                
                if not success:
                    if NEED_PLOT:
                        ax.text(0.5, 0.5, 'Fit failed', ha='center', va='center', 
                            transform=ax.transAxes)
                    continue
                
                A_fit, K_fit, B_fit, M_fit, nu_fit = popt
                
                # Store coefficients
                all_coefficients[pop_pre][pop_post] = {
                    'A': float(A_fit),
                    'K': float(K_fit),
                    'B': float(B_fit),
                    'M': float(M_fit),
                    'nu': float(nu_fit),
                    'n_points': int(len(X_fit))
                }
                
                # Compute derivative at target rate and store in W matrix
                if r0_pre is not None:
                    dR_dr = richards_derivative(r0_pre, A_fit, K_fit, B_fit, M_fit, nu_fit)
                    W[i_pre, j_post] = dR_dr
                
                if NEED_PLOT:
                    # Plot the fitted Richards curve
                    X_range = np.linspace(X_fit.min(), X_fit.max(), 300)
                    Y_richards = richards(X_range, *popt)
                    ax.plot(X_range, Y_richards, 'k-', linewidth=2, label='Richards fit')
                
                    # Plot tangent line at target rate
                    if r0_pre is not None:
                        r_post_at_target = richards(r0_pre, A_fit, K_fit, B_fit, M_fit, nu_fit)
                        X_tangent = np.linspace(X_fit.min(), X_fit.max(), 100)
                        Y_tangent = dR_dr * (X_tangent - r0_pre) + r_post_at_target
                        ax.plot(X_tangent, Y_tangent, 'k--', linewidth=2)
            
            if NEED_PLOT:
                # Hide unused subplots
                for subplot_idx in range(end_idx - start_idx, 6):
                    axes[subplot_idx].axis('off')
                
                # Save figure
                fig_filename = f'{pop_pre}_{fig_idx + 1}.png'
                fig_path = dirpath_plots / fig_filename
                plt.tight_layout()
                plt.savefig(fig_path, dpi=150, bbox_inches='tight')
                plt.close(fig)
        
        # Save intermediate coefficients after each pop_pre
        coeffs_path = dirpath_res / f'richards_coeffs_tau_{smooth_win_s}.json'
        with open(coeffs_path, 'w') as f:
            json.dump(all_coefficients, f, indent=2)
    
    # Convert W to xarray DataArray
    W_xr = xr.DataArray(
        W, dims=['pop_pre', 'pop_post'],
        coords={'pop_pre': list(pops_pre), 'pop_post': pops_post},
    )
    
    # Save W matrix
    wmat_path = dirpath_res / f'wmat_tau_{smooth_win_s}.json'
    W_xr.to_netcdf(dirpath_res / f'wmat_tau_{smooth_win_s}.nc')
    # Also save as JSON for easier inspection
    W_dict = {'pop_pre': list(pops_pre), 'pop_post': pops_post, 'W': W.tolist()}
    with open(wmat_path, 'w') as f:
        json.dump(W_dict, f, indent=2)
    
    print(f"\n\nDone! Coefficients saved to: {coeffs_path}")
    print(f"W matrix saved to: {wmat_path}")
    total_fits = sum(len(v) for v in all_coefficients.values())
    print(f"Total successful fits: {total_fits}/{total_steps}")


if __name__ == '__main__':
    main()
