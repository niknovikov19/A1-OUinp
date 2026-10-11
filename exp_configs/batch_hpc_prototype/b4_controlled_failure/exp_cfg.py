from pathlib import Path


EXP_NAME = 'hpc_b4_controlled_failure'
POP_MAIN = 'IT2'
SIM_DURATION = 1000
T0_CALC = 500
DEFAULT_STIM_SEED = 1501
FAIL_STIM_SEED = 1502
RXE = 10000
RXI = 100
WXE = 0.1
WXI = 0.05
RUN_ATTEMPT = 1


def apply_exp_cfg(cfg):
    """Configure one short reproducible cell for the B4 failure test. """
    cfg.duration = SIM_DURATION
    cfg.t0_calc = T0_CALC
    cfg.stim_seed = DEFAULT_STIM_SEED
    cfg.seeds['stim'] = cfg.stim_seed

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

    # Use fixed-shape background inputs with the batch-selected seed
    cfg.addBkgConn = 0
    cfg.add_bkg_spike_input = 1
    cfg.replace_bkg_spikes_by_ou = 0
    cfg.bkg_spike_inputs = {
        POP_MAIN: {
            'exc': {'r': RXE, 'w': WXE, 'sec': 'apic'},
            'inh': {'r': RXI, 'w': WXI, 'sec': 'soma'},
        },
    }

    # Retain only compact data needed by the prototype
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
    """Return the descriptive result directory for the controlled failure. """
    t0 = cfg.t0_calc / 1000
    t1 = cfg.duration / 1000
    inp = cfg.bkg_spike_inputs[POP_MAIN]
    return (
        f'exp_{EXP_NAME}_nseed_2'
        f'_t_{t0}_{t1}'
        f'_rx_{inp["exc"]["r"]}_{inp["inh"]["r"]}'
        f'_wx_{inp["exc"]["w"]}_{inp["inh"]["w"]}'
        f'_n_1_attempt_{RUN_ATTEMPT}'
    )


def get_batch_completion_files(child_key, parameters):
    """Return the completion file owned by one BatchTools child. """
    if set(parameters) != {'stim_seed'}:
        raise ValueError('Unexpected B4 batch parameters')
    return [f'results/{child_key}.json']


def post_run(sim):
    """Fail one reviewed coordinate and retain the other child result. """
    cfg = sim.cfg
    if cfg.stim_seed == FAIL_STIM_SEED:
        raise RuntimeError('B4 intentional child failure for stim_seed 1502')
    dirpath_parent = Path(cfg.saveFolder)
    dirpath_result = dirpath_parent / gen_exp_name_sub(cfg)
    dirpath_result.mkdir(parents=True, exist_ok=True)

    # Move standard child artifacts into non-colliding result locations
    destinations = {
        'cfg.json': Path('cfg') / f'{cfg.simLabel}.json',
        'netParams.json': Path('netpar') / f'{cfg.simLabel}.json',
        'params.json': Path('params') / f'{cfg.simLabel}.json',
        'result.json': Path('results') / f'{cfg.simLabel}.json',
    }
    outputs = []
    for suffix, relpath in destinations.items():
        source = dirpath_parent / f'{cfg.simLabel}_{suffix}'
        if not source.exists():
            continue
        destination = dirpath_result / relpath
        destination.parent.mkdir(exist_ok=True)
        source.replace(destination)
        if suffix == 'result.json':
            outputs.append(relpath.as_posix())
    expected = get_batch_completion_files(
        cfg.simLabel,
        {'stim_seed': cfg.stim_seed},
    )
    if outputs != expected:
        raise FileNotFoundError('B4 child completion file was not produced')
    return outputs
