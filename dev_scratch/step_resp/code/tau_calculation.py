# Calculate synaptic time constants for L2 population pairs
# Based on create_base_cfg.py and create_net_params.py

import numpy as np
import xarray as xr
import matplotlib.pyplot as plt

# Synaptic time constants (tau2 - decay time constant in ms)
tau_AMPA = 5.3  # tau2 from create_net_params.py (5.3 * AMPATau2Factor=1.0)
tau_NMDA = 150  # tau2NMDA from create_net_params.py
tau_GABAA = 18.2  # tau2 from create_net_params.py
tau_GABAA_VIP = 6.4  # tau2 from create_net_params.py (for VIP cells)
tau_GABAASlow = 100  # tau2 from create_net_params.py (for SOM cells)
tau_GABABCtx = 642  # tau2 from data/cfg_base.json

# Synaptic weight fractions from data/cfg_base.json
# Format: [receptor1_fraction, receptor2_fraction]
synWeightFractionEE = [0.5, 0.5]  # E->E: [AMPA, NMDA]
synWeightFractionEI = [0.5, 0.5]  # E->I (general): [AMPA, NMDA]
synWeightFractionENGF = [0.834, 0.166]  # E->NGF: [AMPA, NMDA]
synWeightFractionSOM_E = [0.9, 0.2]  # SOM->E: [GABAASlow, GABABCtx]
synWeightFractionNGF_E = [0.5, 1.0]  # NGF->E: [GABAA, GABABCtx]

# Helper function to calculate effective tau
def calc_tau_eff(tau_list, weight_fraction):
    """Calculate effective tau as weighted average of decay time constants
    
    Formula: tau_eff = sum(tau_i * w_i) where w_i = weight_i / sum(weights)
    For E->projections: tau = (1-k)*tau_AMPA + k*tau_NMDA, where k = NMDA/(AMPA+NMDA)
    For I->projections: tau = (1-k)*tau_GABAA + k*tau_GABAB, where k = GABAB/(GABAA+GABAB)
    """
    total = sum(weight_fraction)
    weight_norm = [w/total for w in weight_fraction]
    return sum(t * w for t, w in zip(tau_list, weight_norm))

# Function to get tau for a specific pre->post connection
def get_tau_syn(pre_pop, post_pop):
    """Get effective synaptic time constant for a population pair"""
    # Determine cell types
    pre_is_E = pre_pop in ['IT2']
    post_is_E = post_pop in ['IT2']
    
    if pre_is_E and post_is_E:
        # E->E
        return calc_tau_eff([tau_AMPA, tau_NMDA], synWeightFractionEE)
    elif pre_is_E and not post_is_E:
        # E->I
        if 'NGF' in post_pop:
            return calc_tau_eff([tau_AMPA, tau_NMDA], synWeightFractionENGF)
        else:
            return calc_tau_eff([tau_AMPA, tau_NMDA], synWeightFractionEI)
    elif not pre_is_E and post_is_E:
        # I->E
        if 'SOM' in pre_pop:
            return calc_tau_eff([tau_GABAASlow, tau_GABABCtx], synWeightFractionSOM_E)
        elif 'NGF' in pre_pop:
            return calc_tau_eff([tau_GABAA, tau_GABABCtx], synWeightFractionNGF_E)
        elif 'VIP' in pre_pop:
            return tau_GABAA_VIP
        elif 'PV' in pre_pop:
            return tau_GABAA
    else:
        # I->I
        if 'SOM' in pre_pop:
            return tau_GABAASlow
        elif 'VIP' in pre_pop:
            return tau_GABAA_VIP
        else:  # PV or NGF
            return tau_GABAA

# Example usage with L2_POPS (assumes L2_POPS is defined in your notebook)
# L2_POPS = ['IT2', 'PV2', 'SOM2', 'VIP2', 'NGF2']

def create_tau_matrix(pops):
    """Create tau matrix for given population list"""
    tau_mat_data = np.zeros((len(pops), len(pops)))
    for i, pre in enumerate(pops):
        for j, post in enumerate(pops):
            tau_mat_data[i, j] = get_tau_syn(pre, post)
    
    # Create xarray DataArray for tau matrix
    tau_mat = xr.DataArray(
        tau_mat_data,
        dims=['pop_pre', 'pop_post'],
        coords={'pop_pre': pops, 'pop_post': pops},
        name='tau_syn'
    )
    return tau_mat

def plot_tau_matrix(tau_mat, title='Synaptic time constants (ms)'):
    """Plot tau matrix similar to plot_mat function"""
    fig, ax = plt.subplots(1, 1, figsize=(6, 5))
    
    # Plot with viridis colormap (or use your preferred colormap)
    im = ax.imshow(tau_mat.T.values, aspect='auto', cmap='viridis', origin='lower')
    plt.colorbar(im, ax=ax, label='tau (ms)')
    
    pops = list(tau_mat.pop_pre.values)
    ax.set_xticks(range(len(pops)))
    ax.set_xticklabels(pops, rotation=45, ha='right')
    ax.set_yticks(range(len(pops)))
    ax.set_yticklabels(pops)
    ax.set_xlabel('Pre')
    ax.set_ylabel('Post')
    ax.set_title(title)
    
    # Add text annotations with tau values
    for i in range(len(pops)):
        for j in range(len(pops)):
            text = ax.text(j, i, f'{tau_mat.values[j, i]:.1f}',
                          ha="center", va="center", color="w", fontsize=9)
    
    plt.tight_layout()
    return fig, ax

# Print summary of synapse types
print("Synaptic mechanisms and time constants:")
print(f"  AMPA:         tau2 = {tau_AMPA} ms")
print(f"  NMDA:         tau2 = {tau_NMDA} ms")
print(f"  GABAA:        tau2 = {tau_GABAA} ms")
print(f"  GABAA_VIP:    tau2 = {tau_GABAA_VIP} ms")
print(f"  GABAASlow:    tau2 = {tau_GABAASlow} ms")
print(f"  GABABCtx:     tau2 = {tau_GABABCtx} ms")
print("\nEffective tau for connection types:")
print(f"  E->E:         {calc_tau_eff([tau_AMPA, tau_NMDA], synWeightFractionEE):.2f} ms")
print(f"  E->I (PV):    {calc_tau_eff([tau_AMPA, tau_NMDA], synWeightFractionEI):.2f} ms")
print(f"  E->NGF:       {calc_tau_eff([tau_AMPA, tau_NMDA], synWeightFractionENGF):.2f} ms")
print(f"  PV->E:        {tau_GABAA:.2f} ms")
print(f"  SOM->E:       {calc_tau_eff([tau_GABAASlow, tau_GABABCtx], synWeightFractionSOM_E):.2f} ms")
print(f"  VIP->E:       {tau_GABAA_VIP:.2f} ms")
print(f"  NGF->E:       {calc_tau_eff([tau_GABAA, tau_GABABCtx], synWeightFractionNGF_E):.2f} ms")
