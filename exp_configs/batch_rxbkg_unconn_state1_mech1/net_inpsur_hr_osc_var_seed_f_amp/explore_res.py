from pathlib import Path
import sys

dirpath_root = Path(__file__).resolve().parents[3]
sys.path.append(str(dirpath_root))

import matplotlib.pyplot as plt
import numpy as np
import xarray as xr


EXP_NAME_BASE = 'batch_rxbkg_unconn_state1_mech1'
EXP_NAME = 'net_inpsur_hr_osc_var_seed_f_amp'


def get_default_fpath() -> Path:
    dirpath_res = dirpath_root / 'exp_results' / EXP_NAME_BASE / EXP_NAME
    fpaths = sorted(dirpath_res.glob('*/rvec_xr/*.nc'))
    if not fpaths:
        raise FileNotFoundError(f'No rvec_xr netcdf files found in {dirpath_res}')
    return fpaths[-1]


def fit_sinusoid_fixed_freq(rr, osc_f, osc_t0):
    tt = np.asarray(rr.time.values, dtype=float)
    yy = np.asarray(rr.values, dtype=float)
    mask = tt >= osc_t0
    tt = tt[mask]
    yy = yy[mask]
    phase = 2 * np.pi * float(osc_f) * (tt - float(osc_t0))
    X = np.column_stack([
        np.sin(phase),
        np.cos(phase),
        np.ones_like(phase),
    ])
    coef, _, _, _ = np.linalg.lstsq(X, yy, rcond=None)
    a_sin, a_cos, offset = coef
    yfit = a_sin * np.sin(phase) + a_cos * np.cos(phase) + offset
    z_out = a_cos - 1j * a_sin
    return tt, yfit, z_out, float(offset)


def print_transfer_coeffs(rates_xr, pops_vis):
    osc_t0 = float(rates_xr.attrs['OSC_T0'])
    osc_f = float(rates_xr.attrs['OSC_F'])
    osc_amp = float(rates_xr.attrs['OSC_AMP'])
    if osc_amp == 0:
        raise ValueError('OSC_AMP is zero, transfer coefficient is undefined')

    z_in = -1j * osc_amp
    print(f'OSC_T0 = {osc_t0}')
    print(f'OSC_F = {osc_f}')
    print(f'OSC_AMP = {osc_amp}')
    print('Transfer coefficients:')
    fit_data = {}
    for pop in pops_vis:
        rr = rates_xr.sel(pop=pop)
        tt_fit, yfit, z_out, offset = fit_sinusoid_fixed_freq(rr, osc_f, osc_t0)
        H = z_out / z_in
        fit_data[pop] = (tt_fit, yfit)
        print(
            f'  {pop}: H = {H.real:+.6g}{H.imag:+.6g}j '
            f'|H| = {abs(H):.6g} phase = {np.angle(H):.6g} rad '
            f'offset = {offset:.6g}'
        )
    return fit_data


def main():
    fpath_in = Path(sys.argv[1]) if len(sys.argv) > 1 else get_default_fpath()
    print(f'Loading: {fpath_in}')

    rates_xr = xr.open_dataarray(fpath_in)
    pops_vis = [str(pop) for pop in rates_xr.pop.values if 'frz' not in str(pop)]
    fit_data = print_transfer_coeffs(rates_xr, pops_vis)

    colors = plt.rcParams['axes.prop_cycle'].by_key()['color']
    plt.figure(figsize=(14, 8))
    for n, pop in enumerate(pops_vis):
        rr = rates_xr.sel(pop=pop)
        col = colors[n % len(colors)]
        plt.plot(rr.time.values, rr.values, label=pop, color=col)
        tt_fit, yfit = fit_data[pop]
        plt.plot(tt_fit, yfit, '--', color=col, alpha=0.8)

    plt.xlabel('Time')
    plt.ylabel('Firing rate')
    plt.legend(bbox_to_anchor=(1, 1))
    plt.tight_layout()
    plt.show()


if __name__ == '__main__':
    main()
