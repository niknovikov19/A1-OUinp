# Adapted from: https://github.com/BlueBrain/neurodamus/blob/2c7052096c22fb5183fdef120d080608748da48d/neurodamus/core/stimuli.py#L271

#import json
from math import sqrt, exp

#import h5py.h5d
import matplotlib.pyplot as plt
from neuron import h
import numpy as np

from rate_ctrl import make_rate_controller


def generate_ou_signal(tau, sigma, mean, duration, dt=0.025,
                       seed=100000, plotFig=False,
                       invert_output=True, cutoff=1E-9,
                       verbose=False,
                       ramp_par=None,
                       ):
    """
    Generate an Ornstein-Uhlenbeck process with given correlation time,
    standard deviation and mean value.

    tau: correlation time [ms], white noise if zero
    sigma: standard deviation
    mean: mean value
    duration: duration of signal [ms]
    dt: timestep [ms]
    invert_output: return signal or 1/signal
    cutoff: lower cutoff value
    verbose: print debug info flag
    ramp_offset, ramp_mult, ramp_dur - initial ramp to suppress transients
    """

    # Create a default RNG, currently based on ACG
    rng = h.Random(seed)

    #print('generate_ou_signal(): create tvec and svec', flush=True)
    tvec_np = np.linspace(0, duration, int(duration / dt))
    tvec = h.Vector(tvec_np)
    ntstep = len(tvec)  # total number of timesteps
    svec = h.Vector(ntstep, 0)  # stim vector

    #print('generate_ou_signal(): create gaussian noise', flush=True)
    noise = h.Vector(ntstep)  # Gaussian noise
    rng.normal(0.0, 1.0)
    noise.setrand(rng)  # generate Gaussian noise

    if tau < 1e-9:
        svec = noise.mul(sigma)  # white noise
    else:
        mu = exp(-dt / tau)  # auxiliar factor [unitless]
        A = sigma * sqrt(1 - mu * mu)  # amplitude [uS]
        noise.mul(A)  # scale noise by amplitude [uS]
        # Generate zero-mean OU
        #print('generate_ou_signal(): generate OU signal', flush=True)
        for n in range(1, ntstep):
            svec.x[n] = svec[n - 1] * mu + noise[n]  # signal [uS]

    # Shift the signal by the mean value [uS]
    #print(f'generate_ou_signal(): add the mean (type={type(mean)})', flush=True)
    svec.add(mean)

    svec_np = np.array(svec, dtype=np.float64)

    # Ramp
    if (ramp_par is not None) and (ramp_par['dur'] is not None):
        t0, T = ramp_par['t0'], ramp_par['dur']
        tmask = (t0 <= tvec_np) & (tvec_np <= (t0 + T))
        ramp_len = np.sum(tmask)
        if ramp_par['type'] == 'down':
            ramp_off_vec = np.linspace(ramp_par['offset'], 0, ramp_len)
            ramp_mult_vec = np.linspace(ramp_par['mult'], 1, ramp_len)
        elif ramp_par['type'] == 'up':
            ramp_off_vec = np.linspace(0, ramp_par['offset'], ramp_len)
            ramp_mult_vec = np.linspace(1, ramp_par['mult'], ramp_len)
        elif ramp_par['type'] == 'up_down':
            len1 = ramp_len // 2
            len2 = ramp_len - len1
            ramp_off_vec = np.concatenate((
                np.linspace(0, ramp_par['offset'], len1),
                np.linspace(ramp_par['offset'], 0, len2)
            ))
            ramp_mult_vec = np.concatenate((
                np.linspace(1, ramp_par['mult'], len1),
                np.linspace(ramp_par['mult'], 1, len2)
            ))
        else:
            raise ValueError('Unknown ramp type')
        svec_np[tmask] = svec_np[tmask] * ramp_mult_vec + ramp_off_vec

    # Remove small and negative values from the noise
    # (clamp to a small positive number smin)
    if cutoff:
        #print('generate_ou_signal(): cutoff', flush=True)
        mask_neg = (svec_np < cutoff)
        svec_np[mask_neg] = cutoff
        if verbose:
            print(f'Proportion of clamped OU values: {np.mean(mask_neg)}')

    if verbose:
        print(f'generate_ou_signal(): '
              f'mean={np.mean(svec_np)}, std={np.std(svec_np)}',
              flush=True)

    # Take the inverse of the signal if needed
    if invert_output:
        #print('generate_ou_signal(): inverse', flush=True)
        svec_np = 1. / svec_np
    svec = h.Vector(svec_np)

    """ if plotFig:
        import matplotlib.pyplot as plt
        plt.figure(figsize=(30, 5))
        plt.plot(list(tvec), list(svec), 'k')
        plt.savefig('test_fig_vec_OrnsteinUhlenbeck.png')

        plt.figure(figsize=(30, 5))
        plt.plot(list(tvec)[0:1000], list(svec)[0:1000], 'k')
        plt.savefig('test_fig_vec_OrnsteinUhlenbeck_slice.png')

        plt.figure()
        plt.hist(list(svec), 100)
        plt.savefig('test_fig_vec_OrnsteinUhlenbeck_hist.png') """
    
    #print('generate_ou_signal(): done', flush=True)

    return tvec, svec


def add_noise_gclamp(sim):
    """Generate and play OU conductance signal(s) for every cell. """

    vecs_dict = {}
    OUFlags = {}

    #ramp_dur = sim.cfg.ou_ramp_dur if hasattr(sim.cfg, 'ou_ramp_dur') else None
    #ramp_offset = sim.cfg.ou_ramp_offset if hasattr(sim.cfg, 'ou_ramp_offset') else 0
    #ramp_mult = sim.cfg.ou_ramp_mult if hasattr(sim.cfg, 'ou_ramp_mult') else 0
    #raise NotImplementedError('Ramp not supported for g OU')

    # Generate OU signal(s)
    #print(f'add_noise_gclamp(): create OU inputs (dt={sim.cfg.dt})', flush=True)
    for cell_ind, cell in enumerate(sim.net.cells):

        pop = cell.tags['pop']
        if pop not in OUFlags:
            OUFlags[pop] = True
        vecs_dict.update({cell_ind: {'tvecs': {}, 'svecs': {}}})
        #cell_seed = (sim.cfg.seeds['stim'] + cell.gid) * 2

        for stim_ind, stim in enumerate(cell.stims):
            if 'NoiseOU' in stim['label']:
                inp_name = stim['label'][len('NoiseOU_target_'):]
                ou_par = sim.net.params.NoiseOUParams[inp_name]

                mean = ou_par['mean']
                sigma = ou_par['sigma']
                tau = ou_par.get('tau', sim.cfg.ou_tau)
                    
                seed = sim.cfg.seeds['stim'] + cell.gid * 1000 + stim_ind

                verbose = (cell_ind == 0) and (sim.rank == 0)
                if verbose:
                    print(f'====== {inp_name} ======')
                    print(f'Params: mean={mean}, std={sigma}')

                tvec, svec = generate_ou_signal(
                    tau=tau,
                    sigma=sigma,
                    mean=mean,
                    duration=stim['dur1'],
                    dt=sim.cfg.dt,
                    seed=seed,
                    plotFig=False,
                    verbose=verbose
                )

                """ if (cell_ind == 0) and (stim_ind == 0):
                    print(f'mean = {mean}')
                    print(f'sigma = {sigma}')
                    print(f'duration = {stim["dur1"]}') """

                if any(val < 0.0 for val in svec):
                    raise ValueError('Negative values in the conductance signal are not allowed')
                else:
                    vecs_dict[cell_ind]['tvecs'].update({inp_name: tvec})
                    vecs_dict[cell_ind]['svecs'].update({inp_name: svec})

    # Play the OU signals to the cells
    # (via "rs" variable of ConductanceSource.mod)
    #print(f'add_noise_gclamp(): play OU inputs', flush=True)
    for cell_ind, cell in enumerate(sim.net.cells):
        pop = cell.tags['pop']
        if not OUFlags[pop]:
            continue
        for stim_ind, stim in enumerate(cell.stims):
            if 'NoiseOU' in stim['label']:
                inp_name = stim['label'][len('NoiseOU_target_'):]
                stim_vec = vecs_dict[cell_ind]['svecs'][inp_name]
                stim_vec.play(
                    stim['hObj']._ref_rs,
                    vecs_dict[cell_ind]['tvecs'][inp_name]
                )
                #if (cell_ind == 0) and (stim_ind == 0):
                #    print('play()')

    return sim, vecs_dict, OUFlags


def add_noise_iclamp(sim):
    """Generate and play OU current signal(s) for every cell. """

    vecs_dict = {}
    if sim.rank == 0:
        print('add_noise_iclamp(): create OU inputs '
            f'(dt={sim.cfg.dt}, ou_tau={sim.cfg.ou_tau})', flush=True)
    
    ramp_par = {
        't0': sim.cfg.ou_ramp_t0 if hasattr(sim.cfg, 'ou_ramp_t0') else 0,
        'dur': sim.cfg.ou_ramp_dur if hasattr(sim.cfg, 'ou_ramp_dur') else None,
        'offset': sim.cfg.ou_ramp_offset if hasattr(sim.cfg, 'ou_ramp_offset') else 0,
        'mult': sim.cfg.ou_ramp_mult if hasattr(sim.cfg, 'ou_ramp_mult') else 0,
        'type': sim.cfg.ou_ramp_type if hasattr(sim.cfg, 'ou_ramp_type') else 'down',
        'pops': sim.cfg.ou_ramp_pops if hasattr(sim.cfg, 'ou_ramp_pops') else None
    }

    for cell_ind, cell in enumerate(sim.net.cells):

        vecs_dict.update({cell_ind: {'tvecs': {}, 'svecs': {}}})

        for stim_ind, stim in enumerate(cell.stims):
            if 'NoiseOU' in stim['label']:
                pop = cell.tags['pop']
                mean = sim.net.params.NoiseOUParams[pop]['mean']
                sigma = sim.net.params.NoiseOUParams[pop]['sigma']

                seed = sim.cfg.seeds['stim'] + cell.gid * 1000 + stim_ind

                if (sim.rank == 0) and (cell_ind == 0) and (stim_ind == 0):
                    print(f'Create OU ({pop}): mean = {mean}, sigma = {sigma}', flush=True)

                # Relative cell "position" in the pop (0 to 1)
                pop_gids = sim._pop_gid_range[pop]
                #print(f'GIDS: {pop_gids}')
                cell_pos = (cell.gid - pop_gids[0]) / (pop_gids[1] - pop_gids[0])

                # If OU mean/sigma is given by 2 values - interpolate between them across cells
                if not np.isscalar(mean):
                    mean = mean[0] + cell_pos * (mean[1] - mean[0])
                if not np.isscalar(sigma):
                    sigma = sigma[0] + cell_pos * (sigma[1] - sigma[0])

                ramp_par_ = ramp_par
                if ramp_par and (ramp_par['pops'] is not None):
                    if pop not in ramp_par['pops']:
                        ramp_par_ = None

                # Generate OU noise
                tvec, svec = generate_ou_signal(
                    tau=sim.cfg.ou_tau,
                    sigma=sigma,
                    mean=mean,
                    duration=stim['dur'],
                    dt=sim.cfg.dt,
                    seed=seed,
                    invert_output=False,
                    cutoff=None,   # don't prune negative values
                    plotFig=False,
                    ramp_par=ramp_par_
                )

                # Store the noise and time bins
                vecs_dict[cell_ind]['tvecs'].update({stim_ind: tvec})
                vecs_dict[cell_ind]['svecs'].update({stim_ind: svec})

                # Play OU noise to the cell
                vecs_dict[cell_ind]['svecs'][stim_ind].play(
                    stim['hObj']._ref_amp,
                    vecs_dict[cell_ind]['tvecs'][stim_ind],
                    True   # continuous
                )
    
    return sim, vecs_dict


def make_controlled_iclamps(sim, cells, ctrl):
    for n, c in enumerate(cells):
        # Create IClamp mech
        soma = c.secs['soma']['hObj']
        clamp = h.NoiseIClampControlled2(soma(0.5))
        clamp.mu_gain = sim.cfg.ou_ctrl_params['mu_gain']

        # Set the control input signal
        h.setpointer(ctrl._ref_z, 'pctrl', clamp)

        # Record the received ctrl signal
        if (sim.rank == 0) and (n == 0):
            tvec = h.Vector()
            tvec.record(h._ref_t)
            zvec = h.Vector()
            #zvec.record(clamp._ref_ctrl)
            #zvec.record(clamp._ref_i)
            zvec.record(c.secs['soma']['hObj'](0.5)._ref_v)
        else:
            tvec = None
            zvec = None

        # Store refs to avoid GC
        c.secs['soma'].setdefault('stims', []).append(
            {'type': 'NoiseIClampControlled', 'hObj': clamp, 'tvec': tvec, 'zvec': zvec}
        )


def add_noise_iclamp_ctrl(sim):
    """Generate and play rate-controlled OU current signal(s) for every cell. """

    # Create rate-controlling feedbacks
    ctrl_dict = {}
    for pop_name in sim.net.pops:
        if pop_name in sim.net.params.NoiseOUParams:
            ctrl_dict[pop_name] = make_rate_controller(sim, pop_name)
            print(f'>>> {sim.rank} {pop_name} ctrl keys: ', ctrl_dict[pop_name].keys(), flush=True)

    vecs_dict = {}

    for cell_ind, cell in enumerate(sim.net.cells):

        pop_name = cell.tags['pop']

        vecs_dict.update({cell_ind: {'tvecs': {}, 'svecs': {}}})
        cell_seed = sim.cfg.seeds['stim'] + cell.gid

        if pop_name in sim.net.params.NoiseOUParams:
            # Test mech receiving ctrl signal
            """ soma = cell.secs['soma']['hObj']
            debug_inp = h.NoiseIClampControlled2(soma(0.5))
            debug_inp.mu_gain = 1e-3
            vecs_dict[cell_ind]['debug_inp'] = debug_inp """
            
            # Connect the feedback controller
            #ctrl = ctrl_dict[pop_name]['ctrl_mech']
            #h.setpointer(ctrl._ref_z, 'p_ctrl', stim['hObj'])
            #h.setpointer(ctrl._ref_z, 'p_ctrl', debug_inp)

            # Record the ctrl-receiving mech
            """ if 'debug_rec' not in ctrl_dict[pop_name]:
                ctrl_tvec = h.Vector()
                ctrl_tvec.record(h._ref_t)
                ctrl_vec = h.Vector()
                ctrl_vec.record(debug_inp._ref_i)
                ctrl_dict[pop_name]['debug_rec'] = {
                    'tvec': ctrl_tvec, 'ctrl_vec': ctrl_vec} """

        for stim_ind, stim in enumerate(cell.stims):
            if 'NoiseOU' in stim['label']:
                # Generate zero-mean noise with unit amplitude
                tvec, svec = generate_ou_signal(
                    tau=sim.cfg.ou_tau,
                    sigma=1,
                    mean=0,
                    duration=sim.cfg.duration,
                    dt=sim.cfg.dt,
                    seed=cell_seed,
                    invert_output=False,
                    cutoff=None,   # don't prune negative values
                    plotFig=False
                )
                # Store the noise signal
                vecs_dict[cell_ind]['tvecs'].update({stim_ind: tvec})
                vecs_dict[cell_ind]['svecs'].update({stim_ind: svec})

                # Play the noise via NoiseIClampControlled2 mech
                vecs_dict[cell_ind]['svecs'][stim_ind].play(
                    stim['hObj']._ref_noise,
                    #stim['hObj']._ref_amp,
                    vecs_dict[cell_ind]['tvecs'][stim_ind],
                    True   # continuous
                )

                # Connect a feedback controller
                ctrl = ctrl_dict[pop_name]['ctrl_mech']
                h.setpointer(ctrl._ref_z, 'pctrl', stim['hObj'])
    
    return sim, vecs_dict, ctrl_dict


if __name__ == '__main__':

    # Load input resistances
    import json
    from pathlib import Path
    dirpath_self = Path(__file__).resolve().parent
    fpath_resist = dirpath_self / 'data' / 'inputResistances.json'
    with open(fpath_resist, 'rb') as f:
        inp_res = json.load(f)

    ou_amp = 1 * 1e-4
    ou_std = 1 * 1e-4

    pop = 'ITP4'    
    #Gin = 1 / inp_res[pop]
    Gin = 1

    tvec, svec = generate_ou_signal(
        tau=10,
        sigma=ou_std * Gin,
        mean=ou_amp * Gin,
        duration=3000,
        dt=0.05,
        seed=1111111,
        plotFig=False,
        invert_output=False,
        cutoff = -0.0001,
        verbose=True
    )
    tvec = np.array(tvec)
    svec = np.array(svec)

    print(f'Mean: {svec.mean() * 1e4}')
    print(f'Std: {svec.std() * 1e4}')
    print(f'Min.: {svec.min() * 1e4}')
    print(f'Max.: {svec.max() * 1e4}')
