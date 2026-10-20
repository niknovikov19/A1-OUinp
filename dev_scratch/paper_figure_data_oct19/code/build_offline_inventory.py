"""Build checks, statistics, and comparison plots using only local snapshots. """

import ast
import json
import os
from pathlib import Path

# Keep the plotting cache inside the task folder
os.environ['MPLCONFIGDIR'] = str(Path(__file__).resolve().parents[1] / '.runtime/matplotlib_cache')

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xarray as xr


DIR_TASK = Path(__file__).resolve().parents[1]
DIR_DATA = DIR_TASK / 'data'
DIR_INVENTORIES = DIR_DATA / 'inventories'
DIR_TABLES = DIR_DATA / 'tables'
DIR_PLOTS = DIR_TASK / 'plots'
BATCH_FADE = 'net_newsec_ee_fade_var_seed'
BATCH_A1 = 'net_newsec_var_seed'
THAL_POPS = ['TC', 'HTC', 'TI', 'IRE', 'TCM', 'TIM', 'IREM']


def main():
    """Validate the cached small files and export offline review artifacts. """
    # Create the generated output folder when starting from a fresh checkout
    DIR_PLOTS.mkdir(parents=True, exist_ok=True)

    rates = pd.read_csv(DIR_TABLES / 'population_rates.csv')
    cfgs = json.loads((DIR_INVENTORIES / 'saved_cfg_summary.json').read_text())
    manifest = json.loads((DIR_INVENTORIES / 'experiment_manifest.json').read_text())
    checks = {}

    # Check rates and input parameters without reading the result mounts
    for label, cfg in cfgs.items():
        selected = rates[rates['experiment'] == label]
        batch = Path(manifest[label]['path']).parts[2]
        target_path = DIR_DATA / 'inputs' / f'{batch}__target_state_1.csv'
        target = pd.read_csv(target_path).set_index('pop_name')['target_rate']
        snapshot = DIR_DATA / 'snapshots' / label / 'cfg_00000_seed_1000.json'
        saved_cfg = json.loads(snapshot.read_text())['simConfig']
        xbkg_path = DIR_DATA / 'inputs' / f'{batch}__rx_bkg_mid_sm_ctx21_thal41.csv'
        xbkg = pd.read_csv(xbkg_path).set_index('pop')
        input_match = True
        for pop, inputs in saved_cfg['bkg_spike_inputs'].items():
            row = xbkg.loc[pop]
            for kind, prefix in [('exc', 'xe'), ('inh', 'xi')]:
                expected = [max(row[f'r{prefix}'], 1e-3), row[f'w{prefix}']]
                actual = [inputs[kind]['r'], inputs[kind]['w']]
                input_match &= bool(np.allclose(actual, expected, rtol=0, atol=1e-10))
                input_match &= inputs[kind]['sec'] == row[f'{prefix}_sec']
        checks[label] = {
            'seeds_in_summary_filenames': sorted(selected['seed'].unique().tolist()),
            'modeled_populations': int(selected['pop'].nunique()),
            'summary_windows_s': selected[['t0_s', 't1_s']].drop_duplicates().values.tolist(),
            'targets_match_local_csv': all(target[p] == v for p, v in cfg['target_rates'].items()),
            'background_inputs_match_local_csv': input_match,
            'seed1000_cfg_has_expected_seeds': cfg['seeds']['stim'] == 1000
                and cfg['seeds']['conn'] == 2000
                and cfg['subnet_params']['global_seed'] == 3000,
        }
    (DIR_INVENTORIES / 'validation.json').write_text(json.dumps(checks, indent=2) + '\n')

    # Export descriptive fingerprints for each population and source experiment
    stats = rates.groupby(['experiment', 'pop'])['error_hz'].describe()
    stats.to_csv(DIR_TABLES / 'rate_error_statistics.csv')
    correction_path = DIR_DATA / 'snapshots/thal_own/ibkg_ctrl_1.json'
    if not correction_path.is_file():
        correction_path = DIR_DATA / 'inputs' / f'{BATCH_A1}__ibkg_ctrl_1.json'
    corrections = json.loads(correction_path.read_text())
    controller_info = json.loads((DIR_INVENTORIES / 'controller_file_inventory.json').read_text())
    controller_names = controller_info['files']
    rows = []
    for pop in THAL_POPS:
        values = corrections['I_per_job'][pop]
        z_values = corrections['z_per_job'][pop]
        for index, (current, z) in enumerate(zip(values, z_values)):
            controller_name = controller_names[index]
            seed = int(controller_name.removesuffix('.pkl').split('_seed_')[-1])
            rows.append({
                'pop': pop, 'trial_index': index, 'seed': seed, 'z_locked_hz': z,
                'I_correction_nA': current,
                'I_median_nA': corrections['I_median'][pop],
                'source_export': 'data/snapshots/thal_own/ibkg_ctrl_1.json',
                'original_controller_file': controller_info['path'] + '/' + controller_name,
            })
        assert np.isclose(np.median(values), corrections['I_median'][pop])
        assert np.allclose(values, np.asarray(z_values) * corrections['metadata']['mu_gain'])
    pd.DataFrame(rows).to_csv(DIR_TABLES / 'thalamic_corrections.csv', index=False)

    # Reuse the notebook's original boxplot function against local snapshots
    source_path = DIR_TASK / 'evidence/notebooks/notebook_cell4_source.txt'
    tree = ast.parse(source_path.read_text())
    tree.body = [node for node in tree.body if not isinstance(node, ast.For)]
    target_path = DIR_DATA / 'inputs' / f'{BATCH_FADE}__target_state_1.csv'
    context = {'plt': plt, 'np': np, 'xr': xr,
               'df': pd.read_csv(target_path).set_index('pop_name'), 'R_all': {}}
    for label in cfgs:
        selected = rates[rates['experiment'] == label]
        table = selected.pivot(index='pop', columns='seed', values='rate_hz')
        context['R_all'][label] = xr.DataArray(
            table.values, dims=['pop', 'trial'],
            coords={'pop': table.index.tolist(), 'trial': table.columns.tolist()})
    exec(compile(tree, str(source_path), 'exec'), context)
    groups = [context['PYR_POPS'] + context['NGF_POPS'],
              context['PV_POPS'] + context['SOM_POPS'], context['VIP23_POPS']]
    for figure, labels in [('cortex_surr_full', ['ctx_surr', 'ctx_full']),
                           ('cortex_ee_surr_fade', ['ctx_ee_surr', 'ctx_ee_fade'])]:
        for index, pops in enumerate(groups):
            context['plot_rates'](pops, labels, center=True, title=False,
                                  figsize=(max(len(pops) * 0.55, 3), 3))
            plt.tight_layout()
            plt.savefig(DIR_PLOTS / f'check_{figure}_group{index}.png', dpi=140)
            plt.close()

    # Compare the newly mounted thalamic summaries and recovered corrections
    labels = ['thal_surr', 'thal_orig', 'thal_own', 'thal_med']
    context['plot_rates'](THAL_POPS, labels, center=True, title=False, figsize=(8, 3))
    plt.tight_layout()
    plt.savefig(DIR_PLOTS / 'check_thalamus_errors.png', dpi=140)
    plt.close()
    fig, ax = plt.subplots(figsize=(8, 3))
    for index, pop in enumerate(THAL_POPS):
        values = corrections['z_per_job'][pop]
        ax.boxplot([values], positions=[index], widths=0.5,
                   patch_artist=True, boxprops={'facecolor': 'lightgreen'})
        ax.scatter([index] * len(values), values, color='tab:green', s=12)
        median = np.median(values)
        ax.plot([index - 0.3, index + 0.3], [median, median], color='red')
    ax.set_xticks(range(len(THAL_POPS)), THAL_POPS)
    ax.set_ylabel('Locked controller output z, Hz')
    fig.tight_layout()
    fig.savefig(DIR_PLOTS / 'check_thalamus_corrections.png', dpi=140)
    plt.close(fig)
    print(json.dumps(checks, indent=2))
    print('Correction medians and current/output conversion verified for all seven populations')


if __name__ == '__main__':
    main()
