import json
from pathlib import Path

from hpc_job import normalize_json


EXP_NAME = 'hpc_b1_smoke'
POP_MAIN = 'IT2'
SIM_DURATION = 1000
T0_CALC = 500
STIM_SEED = 1201
RXE = 10000
RXI = 100
WXE = 0.1
WXI = 0.05


def apply_exp_cfg(cfg):
    """Configure one short reproducible single-cell simulation."""
    cfg.duration = SIM_DURATION
    cfg.t0_calc = T0_CALC
    cfg.seeds['stim'] = STIM_SEED

    # Keep only one unconnected cortical cell
    cfg.singleCellPops = 1
    cfg.pops_active = [POP_MAIN]
    cfg.allpops = list(cfg.pops_active)
    cfg.addConn = 0
    cfg.addSubConn = 0
    cfg.subnet_build_flag = 0

    # Disable unrelated external inputs
    cfg.ICThalInput = False
    cfg.cochlearThalInput = False
    cfg.addIClamp = 0
    cfg.addRIClamp = 0
    cfg.add_ou_current = 0
    cfg.add_ou_conductance = 0

    # Use one fixed-seed excitatory and inhibitory background input
    cfg.addBkgConn = 0
    cfg.add_bkg_spike_input = 1
    cfg.replace_bkg_spikes_by_ou = 0
    cfg.bkg_spike_inputs = {
        POP_MAIN: {
            'exc': {'r': RXE, 'w': WXE, 'sec': 'apic'},
            'inh': {'r': RXI, 'w': WXI, 'sec': 'soma'},
        },
    }

    # Retain only compact data needed by the smoke test
    cfg.need_run = 1
    cfg.recordCells = [(POP_MAIN, [0])]
    cfg.recordTraces = {}
    cfg.printPopAvgRates = [0, cfg.duration]
    cfg.savePickle = False
    cfg.saveJson = False
    cfg.analysis['plotRaster'] = False
    cfg.analysis['plotSpikeStats'] = False
    cfg.analysis['plotTraces'] = False


def gen_exp_name_sub(cfg):
    """Return the descriptive result directory for this configuration."""
    inp = cfg.bkg_spike_inputs[POP_MAIN]
    t0 = cfg.t0_calc / 1000
    t1 = cfg.duration / 1000
    return (
        f'exp_{EXP_NAME}_seed_{cfg.seeds["stim"]}'
        f'_t_{t0}_{t1}'
        f'_rx_{inp["exc"]["r"]}_{inp["inh"]["r"]}'
        f'_wx_{inp["exc"]["w"]}_{inp["inh"]["w"]}'
        '_n_1'
    )


def post_run(sim):
    """Move retained artifacts and write the compact completion record."""
    cfg = sim.cfg
    dirpath_parent = Path(cfg.saveFolder)
    dirpath_result = dirpath_parent / gen_exp_name_sub(cfg)
    dirpath_result.mkdir(parents=True, exist_ok=True)

    # Move standard run_exp.py artifacts into the descriptive result directory
    suffixes = ('cfg.json', 'netParams.json', 'params.json', 'data.pkl', 'result.json')
    for suffix in suffixes:
        source = dirpath_parent / f'{cfg.simLabel}_{suffix}'
        destination = dirpath_result / source.name
        if source.exists():
            source.replace(destination)

    # Publish one small file used as the HPC completion condition
    rates = sim.analysis.popAvgRates(
        tranges=[cfg.t0_calc, cfg.duration],
        show=False,
    )
    filename = f'result_00000_seed_{cfg.seeds["stim"]}.json'
    relpath = Path('results') / filename
    dirpath_output = dirpath_result / relpath.parent
    dirpath_output.mkdir(exist_ok=True)
    result = {
        'schema_version': 1,
        'experiment': EXP_NAME,
        'population': POP_MAIN,
        'stim_seed': cfg.seeds['stim'],
        'duration_ms': cfg.duration,
        'calculation_window_ms': [cfg.t0_calc, cfg.duration],
        'rates_hz': normalize_json(rates),
    }
    with open(dirpath_result / relpath, 'x') as fid:
        json.dump(result, fid, indent=2, sort_keys=True)
        fid.write('\n')
    return [relpath.as_posix()]
