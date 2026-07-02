from copy import deepcopy
import json
import pickle

import numpy as np

from netpyne.batchtools import specs


def _get_pulse_seq_param_list(cfg):
    """Return configured pulse sequence params as a list."""
    pulse_seq_params = cfg.pulse_seq_params
    if isinstance(pulse_seq_params, dict):
        return [pulse_seq_params]
    return list(pulse_seq_params)


def _get_pulse_starts(par):
    """Return pulse starts from explicit tpulse or regular timing params."""
    if 'tpulse' in par:
        starts = list(par['tpulse'])
        if len(starts) != par['n_pulses']:
            raise ValueError(
                f"Pulse sequence {par['name']} has inconsistent tpulse length"
            )
        return starts

    t0, T = par['t0'], par['period']
    return [
        t0 + n * T
        for n in range(par['n_pulses'])
    ]


def _expand_pulse_rates(rates, n_pulses):
    """Expand scalar pulse rates for NetPyNE VecStim pulse windows."""
    if np.isscalar(rates):
        return [rates] * n_pulses
    return list(rates)


def _add_pulse_sequence(netParams, par):
    """Add one VecStim pulse sequence and its target connection."""
    name = par['name']
    pulse_starts = _get_pulse_starts(par)
    rates = _expand_pulse_rates(par['rates'], len(pulse_starts))
    pop_out = par['pop']

    # Keep only target populations present in this netParams object
    if isinstance(pop_out, str):
        pop_out = [pop_out]
    pop_out = [pop for pop in pop_out if pop in netParams.popParams]
    pop_out_str = '_'.join(pop_out)

    # Add the VecStim population carrying the time-windowed pulses
    netParams.popParams[name] = {
        'cellModel': 'VecStim',
        'numCells': par['n_cells'],
        'params': {
            'rate': 0.001,   # very small bkg (required)
            'pulses': [
                {
                    'start': t_start,
                    'end': t_start + par['width'],
                    'rate': rates[n],
                    'noise': 1.0,
                }
                for n, t_start in enumerate(pulse_starts)
            ],
        },
    }

    # Connect the pulse population to the configured target populations
    netParams.connParams[f'{name}->{pop_out_str}'] = {
        'preConds': {'pop': name},
        'postConds': {'pop': pop_out},
        #'connList': [[i, i] for i in range(n_post)],
        'convergence': par['convergence'],
        'sec': 'soma',
        'loc': 0.5,
        'weight': par['weight'],
        'delay': 1,
        'synMech': par.get('mech', 'AMPA'),
        'synsPerConn': 1
    }


def create_net_params(cfg):
    """Create netParams based on a config, common for all parameter sets. """

    #------------------------------------------------------------------------------
    # Load netParams from json file instead of creating them
    #------------------------------------------------------------------------------
    if hasattr(cfg, 'netpar_force_load') and cfg.netpar_force_load:
        with open(cfg.netpar_fpath_json, 'r') as f:
            netParamsDict = json.load(f)
        return specs.NetParams(netParamsDict)

    netParams = specs.NetParams()   # object of class NetParams to store the network parameters

    #------------------------------------------------------------------------------
    # VERSION
    #------------------------------------------------------------------------------
    netParams.version = 45

    #------------------------------------------------------------------------------
    #
    # NETWORK PARAMETERS
    #
    #------------------------------------------------------------------------------

    #------------------------------------------------------------------------------
    # General network parameters
    #------------------------------------------------------------------------------

    netParams.scale = cfg.scale # Scale factor for number of cells # NOT DEFINED YET! 3/11/19 # How is this different than scaleDensity?
    netParams.sizeX = cfg.sizeX # x-dimension (horizontal length) size in um
    netParams.sizeY = cfg.sizeY # y-dimension (vertical height or cortical depth) size in um
    netParams.sizeZ = cfg.sizeZ # z-dimension (horizontal depth) size in um
    netParams.shape = 'cylinder' # cylindrical (column-like) volume

    #------------------------------------------------------------------------------
    # General connectivity parameters
    #------------------------------------------------------------------------------
    netParams.scaleConnWeight = 1.0 # Connection weight scale factor (default if no model specified)
    netParams.scaleConnWeightModels = { 'HH_reduced': 1.0, 'HH_full': 1.0} #scale conn weight factor for each cell model
    netParams.scaleConnWeightNetStims = 1.0 #0.5  # scale conn weight factor for NetStims
    netParams.defaultThreshold = 0.0 # spike threshold, 10 mV is NetCon default, lower it for all cells
    netParams.defaultDelay = 2.0 # default conn delay (ms)
    netParams.propVelocity = 500.0 # propagation velocity (um/ms)
    netParams.probLambda = 100.0  # length constant (lambda) for connection probability decay (um)

    #------------------------------------------------------------------------------
    # Cell parameters
    #------------------------------------------------------------------------------

    Etypes = ['IT', 'ITS4', 'PT', 'CT']
    Itypes = ['PV', 'SOM', 'VIP', 'NGF']
    cellModels = ['HH_reduced', 'HH_full'] # List of cell models

    # II: 100-950, IV: 950-1250, V: 1250-1550, VI: 1550-2000
    layer = {'1': [0.00, 0.05], '2': [0.05, 0.08], '3': [0.08, 0.475], '4': [0.475, 0.625],
            '5A': [0.625, 0.667], '5B': [0.667, 0.775], '6': [0.775, 1], 'thal': [1.2, 1.4],
            'cochlear': [1.6, 1.601]} # normalized layer boundaries

    #------------------------------------------------------------------------------
    ## Load cell rules previously saved using netpyne format (DOES NOT INCLUDE VIP, NGF and spiny stellate)
    ## include conditions ('conds') for each cellRule
    cellParamLabels = ['IT2_reduced', 'IT3_reduced', 'ITP4_reduced', 'ITS4_reduced',
                        'IT5A_reduced', 'CT5A_reduced', 'IT5B_reduced',
                        'PT5B_reduced', 'CT5B_reduced', 'IT6_reduced', 'CT6_reduced',
                        'PV_reduced', 'SOM_reduced', 'VIP_reduced', 'NGF_reduced',
                        'RE_reduced', 'TC_reduced', 'HTC_reduced', 'TI_reduced']

    # Load cellParams for each of the above cell subtype
    for ruleLabel in cellParamLabels:
        netParams.loadCellParamsRule(label=ruleLabel, fileName='cells/' + ruleLabel + '_cellParams.json')


    #------------------------------------------------------------------------------
    # Population parameters
    #------------------------------------------------------------------------------

    ## Load densities
    with open('cells/cellDensity.pkl', 'rb') as fileObj:
        density = pickle.load(fileObj)['density']
    density = {k: [x * cfg.scaleDensity for x in v] for k, v in density.items()} # Scale densities

    def set_pop_params():
        ### LAYER 1:
        netParams.popParams['NGF1'] = {'cellType': 'NGF', 'cellModel': 'HH_reduced','ynormRange': layer['1'],   'density': density[('A1','nonVIP')][0]}

        ### LAYER 2:
        netParams.popParams['IT2'] =     {'cellType': 'IT',  'cellModel': 'HH_reduced',  'ynormRange': layer['2'],   'density': density[('A1','E')][1]}     # cfg.cellmod for 'cellModel' in M1 netParams.py
        netParams.popParams['SOM2'] =    {'cellType': 'SOM', 'cellModel': 'HH_reduced',   'ynormRange': layer['2'],   'density': density[('A1','SOM')][1]}
        netParams.popParams['PV2'] =     {'cellType': 'PV',  'cellModel': 'HH_reduced',   'ynormRange': layer['2'],   'density': density[('A1','PV')][1]}
        netParams.popParams['VIP2'] =    {'cellType': 'VIP', 'cellModel': 'HH_reduced',   'ynormRange': layer['2'],   'density': density[('A1','VIP')][1]}
        netParams.popParams['NGF2'] =    {'cellType': 'NGF', 'cellModel': 'HH_reduced',   'ynormRange': layer['2'],   'density': density[('A1','nonVIP')][1]}

        ### LAYER 3:
        netParams.popParams['IT3'] =     {'cellType': 'IT',  'cellModel': 'HH_reduced',  'ynormRange': layer['3'],   'density': density[('A1','E')][1]} ## CHANGE DENSITY
        netParams.popParams['SOM3'] =    {'cellType': 'SOM', 'cellModel': 'HH_reduced',   'ynormRange': layer['3'],   'density': density[('A1','SOM')][1]} ## CHANGE DENSITY
        netParams.popParams['PV3'] =     {'cellType': 'PV',  'cellModel': 'HH_reduced',   'ynormRange': layer['3'],   'density': density[('A1','PV')][1]} ## CHANGE DENSITY
        netParams.popParams['VIP3'] =    {'cellType': 'VIP', 'cellModel': 'HH_reduced',   'ynormRange': layer['3'],   'density': density[('A1','VIP')][1]} ## CHANGE DENSITY
        netParams.popParams['NGF3'] =    {'cellType': 'NGF', 'cellModel': 'HH_reduced',   'ynormRange': layer['3'],   'density': density[('A1','nonVIP')][1]}

        ### LAYER 4:
        netParams.popParams['ITP4'] =	 {'cellType': 'IT', 'cellModel': 'HH_reduced',  'ynormRange': layer['4'],   'density': 0.5*density[('A1','E')][2]}      ## CHANGE DENSITY #
        netParams.popParams['ITS4'] =	 {'cellType': 'IT', 'cellModel': 'HH_reduced', 'ynormRange': layer['4'],  'density': 0.5*density[('A1','E')][2]}      ## CHANGE DENSITY
        netParams.popParams['SOM4'] = 	 {'cellType': 'SOM', 'cellModel': 'HH_reduced',   'ynormRange': layer['4'],  'density': density[('A1','SOM')][2]}
        netParams.popParams['PV4'] = 	 {'cellType': 'PV', 'cellModel': 'HH_reduced',   'ynormRange': layer['4'],   'density': density[('A1','PV')][2]}
        netParams.popParams['VIP4'] =	 {'cellType': 'VIP', 'cellModel': 'HH_reduced',   'ynormRange': layer['4'],  'density': density[('A1','VIP')][2]}
        netParams.popParams['NGF4'] =    {'cellType': 'NGF', 'cellModel': 'HH_reduced',   'ynormRange': layer['4'],  'density': density[('A1','nonVIP')][2]}

        ### LAYER 5A:
        netParams.popParams['IT5A'] =     {'cellType': 'IT',  'cellModel': 'HH_reduced',   'ynormRange': layer['5A'], 	'density': 0.5*density[('A1','E')][3]}
        netParams.popParams['CT5A'] =     {'cellType': 'CT',  'cellModel': 'HH_reduced',   'ynormRange': layer['5A'],   'density': 0.5*density[('A1','E')][3]}  # density is [5] because we are using same numbers for L5A and L6 for CT cells?
        netParams.popParams['SOM5A'] =    {'cellType': 'SOM', 'cellModel': 'HH_reduced',    'ynormRange': layer['5A'],	'density': density[('A1','SOM')][3]}
        netParams.popParams['PV5A'] =     {'cellType': 'PV',  'cellModel': 'HH_reduced',    'ynormRange': layer['5A'],	'density': density[('A1','PV')][3]}
        netParams.popParams['VIP5A'] =    {'cellType': 'VIP', 'cellModel': 'HH_reduced',    'ynormRange': layer['5A'],   'density': density[('A1','VIP')][3]}
        netParams.popParams['NGF5A'] =    {'cellType': 'NGF', 'cellModel': 'HH_reduced',    'ynormRange': layer['5A'],   'density': density[('A1','nonVIP')][3]}

        ## LAYER 5B:
        netParams.popParams['IT5B'] =     {'cellType': 'IT',  'cellModel': 'HH_reduced',   'ynormRange': layer['5B'], 	'density': (1/3)*density[('A1','E')][4]}
        netParams.popParams['CT5B'] =     {'cellType': 'CT',  'cellModel': 'HH_reduced',   'ynormRange': layer['5B'],   'density': (1/3)*density[('A1','E')][4]}  # density is [5] because we are using same numbers for L5B and L6 for CT cells?
        netParams.popParams['PT5B'] =     {'cellType': 'PT',  'cellModel': 'HH_reduced',   'ynormRange': layer['5B'], 	'density': (1/3)*density[('A1','E')][4]}
        netParams.popParams['SOM5B'] =    {'cellType': 'SOM', 'cellModel': 'HH_reduced',    'ynormRange': layer['5B'],   'density': density[('A1', 'SOM')][4]}
        netParams.popParams['PV5B'] =     {'cellType': 'PV',  'cellModel': 'HH_reduced',    'ynormRange': layer['5B'],	'density': density[('A1','PV')][4]}
        netParams.popParams['VIP5B'] =    {'cellType': 'VIP', 'cellModel': 'HH_reduced',    'ynormRange': layer['5B'],   'density': density[('A1','VIP')][4]}
        netParams.popParams['NGF5B'] =    {'cellType': 'NGF', 'cellModel': 'HH_reduced',    'ynormRange': layer['5B'],   'density': density[('A1','nonVIP')][4]}

        ### LAYER 6:
        netParams.popParams['IT6'] =     {'cellType': 'IT',  'cellModel': 'HH_reduced',  'ynormRange': layer['6'],   'density': 0.5*density[('A1','E')][5]}
        netParams.popParams['CT6'] =     {'cellType': 'CT',  'cellModel': 'HH_reduced',  'ynormRange': layer['6'],   'density': 0.5*density[('A1','E')][5]}
        netParams.popParams['SOM6'] =    {'cellType': 'SOM', 'cellModel': 'HH_reduced',   'ynormRange': layer['6'],   'density': density[('A1','SOM')][5]}
        netParams.popParams['PV6'] =     {'cellType': 'PV',  'cellModel': 'HH_reduced',   'ynormRange': layer['6'],   'density': density[('A1','PV')][5]}
        netParams.popParams['VIP6'] =    {'cellType': 'VIP', 'cellModel': 'HH_reduced',   'ynormRange': layer['6'],   'density': density[('A1','VIP')][5]}
        netParams.popParams['NGF6'] =    {'cellType': 'NGF', 'cellModel': 'HH_reduced',   'ynormRange': layer['6'],   'density': density[('A1','nonVIP')][5]}

        ### THALAMIC POPULATIONS (from prev model)
        thalDensity = density[('A1', 'PV')][2] * 1.25  # temporary estimate (from prev model)
        netParams.popParams['TC'] =     {'cellType': 'TC',  'cellModel': 'HH_reduced',  'ynormRange': layer['thal'],   'density': 0.75*thalDensity}
        netParams.popParams['TCM'] =    {'cellType': 'TC',  'cellModel': 'HH_reduced',  'ynormRange': layer['thal'],   'density': thalDensity}
        netParams.popParams['HTC'] =    {'cellType': 'HTC', 'cellModel': 'HH_reduced',  'ynormRange': layer['thal'],   'density': 0.25*thalDensity}
        netParams.popParams['IRE'] =    {'cellType': 'RE',  'cellModel': 'HH_reduced',  'ynormRange': layer['thal'],   'density': thalDensity}
        netParams.popParams['IREM'] =   {'cellType': 'RE', 'cellModel': 'HH_reduced',   'ynormRange': layer['thal'],   'density': thalDensity}
        netParams.popParams['TI'] =     {'cellType': 'TI',  'cellModel': 'HH_reduced',  'ynormRange': layer['thal'],   'density': 0.33 * thalDensity} ## Winer & Larue 1996; Huang et al 1999
        netParams.popParams['TIM'] =    {'cellType': 'TI',  'cellModel': 'HH_reduced',  'ynormRange': layer['thal'],   'density': 0.33 * thalDensity} ## Winer & Larue 1996; Huang et al 1999

    set_pop_params()

    if cfg.singleCellPops:
        for pop in netParams.popParams.values():
            pop['numCells'] = 1

    if cfg.reducedPop:
        for pop in netParams.popParams.values():
            pop['numCells'] = cfg.reducedPop

    # List of E and I pops to use later on
    Epops = ['IT2', 'IT3', 'ITP4', 'ITS4', 'IT5A', 'CT5A', 'IT5B', 'CT5B' , 'PT5B', 'IT6', 'CT6']  # all layers
    Ipops = ['NGF1',                            # L1
            'PV2', 'SOM2', 'VIP2', 'NGF2',      # L2
            'PV3', 'SOM3', 'VIP3', 'NGF3',      # L3
            'PV4', 'SOM4', 'VIP4', 'NGF4',      # L4
            'PV5A', 'SOM5A', 'VIP5A', 'NGF5A',  # L5A
            'PV5B', 'SOM5B', 'VIP5B', 'NGF5B',  # L5B
            'PV6', 'SOM6', 'VIP6', 'NGF6']      # L6

    # Remove unused pops
    if hasattr(cfg, 'pops_active') and cfg.pops_active:
        pop_params_new = {}
        for pop in cfg.pops_active:
            if pop in netParams.popParams:
                pop_params_new[pop] = netParams.popParams[pop]
            else:
                print(f"Warning: pop '{pop}' not found in netParams.popParams")
        netParams.popParams = pop_params_new
    
    # Selecting a subset of pops is not supported in some cases
    if hasattr(cfg, 'pops_active') and cfg.pops_active:
        #if cfg.addConn:
        #    raise ValueError("cfg.pops_active is not supported for connected networks.")
        if cfg.cochlearThalInput:
            raise ValueError("cfg.pops_active is not supported for cochlear thalamic input.")
    
    #------------------------------------------------------------------------------
    # Synaptic mechanism parameters
    #------------------------------------------------------------------------------

    SYN_MECH, SYN_MECH_NMDA = 'MyExp2SynBBModulated', 'MyExp2SynNMDABBModulated'
    #SYN_MECH, SYN_MECH_NMDA = 'MyExp2SynBB', 'MyExp2SynNMDABB'

    cfg.GABABThal['mod'] = SYN_MECH
    cfg.GABABCtx['mod'] = SYN_MECH

    ### From M1 detailed netParams.py
    netParams.synMechParams['NMDA'] = {'mod': SYN_MECH_NMDA, 'tau1NMDA': 15, 'tau2NMDA': 150, 'e': 0}
    netParams.synMechParams['AMPA'] = {'mod': SYN_MECH, 'tau1': 0.05, 'tau2': 5.3*cfg.AMPATau2Factor, 'e': 0}
    netParams.synMechParams['GABABThal'] =  cfg.GABABThal
    netParams.synMechParams['GABABCtx'] = cfg.GABABCtx
    netParams.synMechParams['GABAA'] = {'mod': SYN_MECH, 'tau1': 0.07, 'tau2': 18.2, 'e': -80}
    netParams.synMechParams['GABAA_VIP'] = {'mod': SYN_MECH, 'tau1': 0.3, 'tau2': 6.4, 'e': -80}  # Pi et al 2013
    netParams.synMechParams['GABAASlow'] = {'mod': SYN_MECH,'tau1': 2, 'tau2': 100, 'e': -80}
    netParams.synMechParams['GABAASlowSlow'] = {'mod': SYN_MECH, 'tau1': 200, 'tau2': 400, 'e': -80}

    ESynMech = ['AMPA', 'NMDA']
    SOMESynMech = ['GABAASlow','GABABCtx']
    SOMISynMech = ['GABAASlow']
    PVSynMech = ['GABAA']
    VIPSynMech = ['GABAA_VIP']
    NGFESynMech = ['GABAA', 'GABABCtx']
    NGFISynMech = ['GABAA']
    ThalIESynMech = ['GABAASlow', 'GABABThal']
    ThalIISynMech = ['GABAASlow']

    #------------------------------------------------------------------------------
    # Local connectivity parameters
    #------------------------------------------------------------------------------

    ## Load data from conn pre-processing file
    with open('conn/conn.pkl', 'rb') as fileObj:
        connData = pickle.load(fileObj)
    pmat = connData['pmat']
    lmat = connData['lmat']
    wmat = connData['wmat']
    bins = connData['bins']
    connDataSource = connData['connDataSource']

    wmat = cfg.wmat

    # Apply global weight multiplier
    for pre in wmat.keys():
        for post in wmat[pre].keys():
            wmat[pre][post] *= cfg.wmult
    
    SKIP_ZERO_PROB = 1

    def wireCortex():
        layerGainLabels = ['1', '2', '3', '4', '5A', '5B', '6']
        #------------------------------------------------------------------------------
        ## E -> E
        if cfg.EEGain > 0.0:
            for pre in Epops:
                for post in Epops:
                    for l in layerGainLabels:  # used to tune each layer group independently
                        scaleFactor = 1.0
                        if (pmat[pre][post] == 0) and SKIP_ZERO_PROB: continue
                        if connDataSource['E->E/I'] in ['Allen_V1', 'Allen_custom']:
                            prob = '%f * exp(-dist_2D/%f)' % (pmat[pre][post], lmat[pre][post])
                        else:
                            prob = pmat[pre][post]
                        if pre=='ITS4' or pre=='ITP4':
                            if post=='IT3':
                                scaleFactor = cfg.L4L3E
                        netParams.connParams['EE_'+pre+'_'+post+'_'+l] = { 
                            'preConds': {'pop': pre}, 
                            'postConds': {'pop': post, 'ynorm': layer[l]},
                            'synMech': ESynMech,
                            'probability': prob,
                            'weight': wmat[pre][post] * cfg.EEGain * cfg.EELayerGain[l] * cfg.EEPopGain[post] * scaleFactor, 
                            'synMechWeightFactor': cfg.synWeightFractionEE,
                            'delay': 'defaultDelay+dist_3D/propVelocity',
                            'synsPerConn': 1,
                            'sec': 'dend_all'
                        }
        #------------------------------------------------------------------------------
        ## E -> I       ## MODIFIED FOR NMDAR MANIPULATION!! 
        if cfg.EIGain > 0.0:
            for pre in Epops:
                for post in Ipops:
                    for postType in Itypes:
                        if postType in post: # only create rule if celltype matches pop
                            for l in layerGainLabels:  # used to tune each layer group independently
                                scaleFactor = 1.0
                                if (pmat[pre][post] == 0) and SKIP_ZERO_PROB: continue
                                if connDataSource['E->E/I'] in ['Allen_V1', 'Allen_custom']:
                                    prob = '%f * exp(-dist_2D/%f)' % (pmat[pre][post], lmat[pre][post])
                                else:
                                    prob = pmat[pre][post]              
                                if 'NGF' in post:
                                    synWeightFactor = cfg.synWeightFractionENGF   
                                elif 'PV' in post:
                                    synWeightFactor = cfg.synWeightFractionEI_CustomCort
                                else:
                                    synWeightFactor = cfg.synWeightFractionEI #cfg.synWeightFractionEI_CustomCort  #cfg.synWeightFractionEI   
                                if 'NGF1' in post:
                                    scaleFactor = cfg.ENGF1  
                                if pre=='ITS4' or pre=='ITP4':
                                    if post=='PV3':
                                        scaleFactor = cfg.L4L3PV#25
                                    elif post=='SOM3':
                                        scaleFactor = cfg.L4L3SOM
                                    elif post=='NGF3':
                                        scaleFactor = cfg.L4L3NGF#25
                                    elif post=='VIP3':
                                        scaleFactor = cfg.L4L3VIP#25
                                netParams.connParams['EI_'+pre+'_'+post+'_'+postType+'_'+l] = { 
                                    'preConds': {'pop': pre}, 
                                    'postConds': {'pop': post, 'cellType': postType, 'ynorm': layer[l]},
                                    'synMech': ESynMech,
                                    'probability': prob,
                                    'weight': wmat[pre][post] * cfg.EIGain * cfg.EICellTypeGain[postType] * cfg.EILayerGain[l] * cfg.EIPopGain[post] * scaleFactor, 
                                    'synMechWeightFactor': synWeightFactor,
                                    'delay': 'defaultDelay+dist_3D/propVelocity',
                                    'synsPerConn': 1,
                                    'sec': 'proximal'
                                }
        #------------------------------------------------------------------------------
        ## I -> E
        if cfg.IEGain > 0.0:
            if connDataSource['I->E/I'] == 'Allen_custom':
                for pre in Ipops:
                    for preType in Itypes:
                        if preType in pre:  # only create rule if celltype matches pop
                            for post in Epops:
                                for l in layerGainLabels:  # used to tune each layer group independently
                                    if (pmat[pre][post] == 0) and SKIP_ZERO_PROB: continue
                                    prob = '%f * exp(-dist_2D/%f)' % (pmat[pre][post], lmat[pre][post])
                                    synWeightFactor = cfg.synWeightFractionIE
                                    if 'SOM' in pre:
                                        synMech = SOMESynMech
                                        synWeightFactor = cfg.synWeightFractionSOM['E']
                                    elif 'PV' in pre:
                                        synMech = PVSynMech
                                    elif 'VIP' in pre:
                                        synMech = VIPSynMech
                                    elif 'NGF' in pre:
                                        synMech = NGFESynMech
                                        synWeightFactor = cfg.synWeightFractionNGF['E']
                                    netParams.connParams['IE_'+pre+'_'+preType+'_'+post+'_'+l] = { 
                                        'preConds': {'pop': pre}, 
                                        'postConds': {'pop': post, 'ynorm': layer[l]},
                                        'synMech': synMech,
                                        'probability': prob,
                                        'weight': wmat[pre][post] * cfg.IEGain * cfg.IECellTypeGain[preType] * cfg.IELayerGain[l], 
                                        'synMechWeightFactor': synWeightFactor,
                                        'delay': 'defaultDelay+dist_3D/propVelocity',
                                        'synsPerConn': 1,
                                        'sec': 'proximal'
                                    }
        #------------------------------------------------------------------------------
        ## I -> I
        if cfg.IIGain > 0.0:
            if connDataSource['I->E/I'] == 'Allen_custom':
                for pre in Ipops:
                    for post in Ipops:
                        for l in layerGainLabels:
                            if (pmat[pre][post] == 0) and SKIP_ZERO_PROB: continue
                            prob = '%f * exp(-dist_2D/%f)' % (pmat[pre][post], lmat[pre][post])
                            synWeightFactor = cfg.synWeightFractionII
                            if 'SOM' in pre:
                                synMech = SOMISynMech
                                synWeightFactor = cfg.synWeightFractionSOM['I']
                            elif 'PV' in pre:
                                synMech = PVSynMech
                            elif 'VIP' in pre:
                                synMech = VIPSynMech
                            elif 'NGF' in pre:
                                synMech = NGFISynMech
                                synWeightFactor = cfg.synWeightFractionNGF['I']                          
                            netParams.connParams['II_'+pre+'_'+post+'_'+l] = { 
                                'preConds': {'pop': pre}, 
                                'postConds': {'pop': post,  'ynorm': layer[l]},
                                'synMech': synMech,
                                'probability': prob,
                                'weight': wmat[pre][post] * cfg.IIGain * cfg.IILayerGain[l], 
                                'synMechWeightFactor': synWeightFactor,
                                'delay': 'defaultDelay+dist_3D/propVelocity',
                                'synsPerConn': 1,
                                'sec': 'proximal'
                            }

    if cfg.addConn and cfg.wireCortex:
        wireCortex()

    #------------------------------------------------------------------------------
    # Thalamic connectivity parameters
    #------------------------------------------------------------------------------

    #------------------------------------------------------------------------------
    ## Intrathalamic

    TEpops = ['TC', 'TCM', 'HTC']
    TIpops = ['IRE', 'IREM', 'TI', 'TIM']

    def IsThalamicCore (ct):
        return ct == 'TC' or ct == 'HTC' or ct == 'IRE' or ct == 'TI'
    
    def wireThal():
        # set intrathalamic connections
        for pre in TEpops+TIpops:
            for post in TEpops+TIpops:
                if post not in pmat[pre]:
                    continue
                if (pmat[pre][post] == 0) and SKIP_ZERO_PROB: continue
                gain = cfg.intraThalamicGain
                # for syns use ESynMech, ThalIESynMech and ThalIISynMech
                if pre in TEpops:     # E->E/I
                    syn = ESynMech
                    synWeightFactor = cfg.synWeightFractionEE
                    if post in TEpops:
                        if IsThalamicCore(pre) and IsThalamicCore(post):                      
                            gain *= cfg.intraThalamicCoreEEGain
                        else:
                            gain *= cfg.intraThalamicEEGain
                    else:
                        if IsThalamicCore(pre) and IsThalamicCore(post):                      
                            gain *= cfg.intraThalamicCoreEIGain
                        else:
                            gain *= cfg.intraThalamicEIGain
                elif post in TEpops:  # I->E
                    syn = ThalIESynMech
                    synWeightFactor = cfg.synWeightFractionThal['Thal']['I']['E']
                    if IsThalamicCore(pre) and IsThalamicCore(post):                                        
                        gain *= cfg.intraThalamicCoreIEGain
                    else:
                        gain *= cfg.intraThalamicIEGain
                else:                  # I->I
                    syn = ThalIISynMech
                    synWeightFactor = cfg.synWeightFractionThal['Thal']['I']['I']
                    if IsThalamicCore(pre) and IsThalamicCore(post):
                        gain *= cfg.intraThalamicCoreIIGain
                    else:
                        gain *= cfg.intraThalamicIIGain
                # use spatially dependent wiring between thalamic core neurons
                if IsThalamicCore(pre) and IsThalamicCore(post):
                    prob = '%f * exp(-dist_x/%f)' % (pmat[pre][post], cfg.ThalamicCoreLambda)
                else:
                    prob = pmat[pre][post]
                # print('wireThal:',pre,post)
                netParams.connParams['ITh_'+pre+'_'+post] = { 
                    'preConds': {'pop': pre}, 
                    'postConds': {'pop': post},
                    'synMech': syn,
                    'probability': prob,
                    'weight': wmat[pre][post] * gain,
                    'synMechWeightFactor': synWeightFactor,
                    'delay': 'defaultDelay+dist_3D/propVelocity',
                    'synsPerConn': 1,
                    'sec': 'soma'
                }

    if cfg.addConn and cfg.addIntraThalamicConn:
        wireThal()

    #------------------------------------------------------------------------------
    ## Corticothalamic
    def connectCortexToThal ():
        # corticothalamic connections
        for pre in Epops:
            for post in TEpops+TIpops:
                if post not in pmat[pre]:
                    continue
                if (pmat[pre][post] == 0) and SKIP_ZERO_PROB: continue
                if IsThalamicCore(post): # use spatially dependent wiring for thalamic core
                    prob = '%f * exp(-dist_x/%f)' % (pmat[pre][post], cfg.ThalamicCoreLambda)
                else:
                    prob = pmat[pre][post]              
                netParams.connParams['CxTh_'+pre+'_'+post] = { 
                    'preConds': {'pop': pre}, 
                    'postConds': {'pop': post},
                    'synMech': ESynMech,
                    'probability': prob,
                    'weight': wmat[pre][post] * cfg.corticoThalamicGain, 
                    'synMechWeightFactor': cfg.synWeightFractionEE,
                    'delay': 'defaultDelay+dist_3D/propVelocity',
                    'synsPerConn': 1,
                    'sec': 'soma'
                }

    if cfg.addConn and cfg.addCorticoThalamicConn:
        connectCortexToThal()

    #------------------------------------------------------------------------------
    ## Thalamocortical - this was added from Christoph Metzner's branch
    def connectThalToCortex():
        # thalamocortical connections, some params added from Christoph Metzner's branch
        for pre in TEpops+TIpops:
            for post in Epops+Ipops:
                if post not in pmat[pre]:
                    continue
                if (pmat[pre][post] == 0) and SKIP_ZERO_PROB: continue
                scaleFactor = 1.0
                if IsThalamicCore(pre): # use spatially dependent wiring for thalamic core
                    prob = '%f * exp(-dist_x/%f)' % (pmat[pre][post], cfg.ThalamicCoreLambda) # NB: should check if this is ok 
                else:
                    prob = '%f * exp(-dist_2D/%f)' % (pmat[pre][post], lmat[pre][post]) # NB: check what the 2D inverse distance based on. lmat from conn/conn.pkl
                # for syns use ESynMech, SOMESynMech and SOMISynMech 
                if pre in TEpops:     # E->E/I
                    if post=='PV4':
                        syn = ESynMech
                        synWeightFactor = cfg.synWeightFractionEE
                        scaleFactor = cfg.thalL4PV#25
                    elif post=='SOM4':
                        syn = ESynMech
                        synWeightFactor = cfg.synWeightFractionEE
                        scaleFactor = cfg.thalL4SOM
                    elif post=='ITS4':
                        syn = ESynMech
                        synWeightFactor = cfg.synWeightFractionEE
                        scaleFactor = cfg.thalL4E#25
                    elif post=='ITP4':
                        syn = ESynMech
                        synWeightFactor = cfg.synWeightFractionEE
                        scaleFactor = cfg.thalL4E#25
                    elif post=='NGF4':
                        syn = ESynMech
                        synWeightFactor = cfg.synWeightFractionEE
                        scaleFactor = cfg.thalL4NGF#25
                    elif post=='VIP4':
                        syn = ESynMech
                        synWeightFactor = cfg.synWeightFractionEE
                        scaleFactor = cfg.thalL4VIP#25
                    elif post=='NGF1':
                        syn = ESynMech
                        synWeightFactor = cfg.synWeightFractionEE
                        scaleFactor = cfg.thalL1NGF#25
                    else:
                        syn = ESynMech
                        synWeightFactor = cfg.synWeightFractionEE
                elif post in Epops:  # I->E
                    syn = ThalIESynMech
                    synWeightFactor = cfg.synWeightFractionThal['Ctx']['I']['E']
                else:                  # I->I
                    syn = ThalIISynMech
                    synWeightFactor = cfg.synWeightFractionThal['Ctx']['I']['I']
                # print('thal->ctx ', pre, post)
                netParams.connParams['ThCx_'+pre+'_'+post] = { 
                    'preConds': {'pop': pre}, 
                    'postConds': {'pop': post},
                    'synMech': syn,
                    'probability': prob,
                    'weight': wmat[pre][post] * cfg.thalamoCorticalGain * scaleFactor, 
                    'synMechWeightFactor': synWeightFactor,
                    'delay': 'defaultDelay+dist_3D/propVelocity',
                    'synsPerConn': 1,
                    'sec': 'soma'
                }

    if cfg.addConn and cfg.addThalamoCorticalConn:
        connectThalToCortex()

    #------------------------------------------------------------------------------
    # Subcellular connectivity (synaptic distributions)
    #------------------------------------------------------------------------------
    # Set target sections (somatodendritic distribution of synapses)
    # From Billeh 2019 (Allen V1) (fig 4F) and Tremblay 2016 (fig 3)

    def addSubConn ():
        #------------------------------------------------------------------------------
        # E -> E2/3,4: soma,dendrites <200um
        netParams.subConnParams['E->E2,3,4'] = {
                'preConds': {'cellType': ['IT', 'ITS4', 'PT', 'CT']}, 
                'postConds': {'pop': ['IT2', 'IT3', 'ITP4', 'ITS4']},
                'sec': 'proximal',
                'groupSynMechs': ESynMech, 
                'density': 'uniform'} 
        #------------------------------------------------------------------------------
        # E -> E5,6: soma,dendrites (all)
        netParams.subConnParams['E->E5,6'] = {
                'preConds': {'cellType': ['IT', 'ITS4', 'PT', 'CT']}, 
                'postConds': {'pop': ['IT5A', 'CT5A', 'IT5B', 'PT5B', 'CT5B', 'IT6', 'CT6']},
                'sec': 'all',
                'groupSynMechs': ESynMech, 
                'density': 'uniform'}
        #------------------------------------------------------------------------------
        # E -> I: soma, dendrite (all)
        netParams.subConnParams['E->I'] = {
                'preConds': {'cellType': ['IT', 'ITS4', 'PT', 'CT']}, 
                'postConds': {'cellType': ['PV','SOM','NGF', 'VIP']},
                'sec': 'all',
                'groupSynMechs': ESynMech, 
                'density': 'uniform'} 
        #------------------------------------------------------------------------------
        # NGF1 -> E: apic_tuft
        netParams.subConnParams['NGF1->E'] = {
                'preConds': {'pop': ['NGF1']}, 
                'postConds': {'cellType': ['IT', 'ITS4', 'PT', 'CT']},
                'sec': 'apic_tuft',
                'groupSynMechs': NGFESynMech, 
                'density': 'uniform'} 
        #------------------------------------------------------------------------------
        # NGF2,3,4 -> E2,3,4: apic_trunk
        netParams.subConnParams['NGF2,3,4->E2,3,4'] = {
                'preConds': {'pop': ['NGF2', 'NGF3', 'NGF4']}, 
                'postConds': {'pop': ['IT2', 'IT3', 'ITP4', 'ITS4']},
                'sec': 'apic_trunk',
                'groupSynMechs': NGFESynMech, 
                'density': 'uniform'} 
        #------------------------------------------------------------------------------
        # NGF2,3,4 -> E5,6: apic_uppertrunk
        netParams.subConnParams['NGF2,3,4->E5,6'] = {
                'preConds': {'pop': ['NGF2', 'NGF3', 'NGF4']}, 
                'postConds': {'pop': ['IT5A', 'CT5A', 'IT5B', 'PT5B', 'CT5B', 'IT6', 'CT6']},
                'sec': 'apic_uppertrunk',
                'groupSynMechs': NGFESynMech, 
                'density': 'uniform'} 
        #------------------------------------------------------------------------------
        # NGF5,6 -> E5,6: apic_lowerrunk
        netParams.subConnParams['NGF5,6->E5,6'] = {
                'preConds': {'pop': ['NGF5A', 'NGF5B', 'NGF6']}, 
                'postConds': {'pop': ['IT5A', 'CT5A', 'IT5B', 'PT5B', 'CT5B', 'IT6', 'CT6']},
                'sec': 'apic_lowertrunk',
                'groupSynMechs': NGFESynMech, 
                'density': 'uniform'} 
        #------------------------------------------------------------------------------
        #  SOM -> E: all_dend (not close to soma)
        netParams.subConnParams['SOM->E'] = {
                'preConds': {'cellType': ['SOM']}, 
                'postConds': {'cellType': ['IT', 'ITS4', 'PT', 'CT']},
                'sec': 'dend_all',
                'groupSynMechs': SOMESynMech, 
                'density': 'uniform'} 
        #------------------------------------------------------------------------------
        #  PV -> E: proximal
        netParams.subConnParams['PV->E'] = {
                'preConds': {'cellType': ['PV']}, 
                'postConds': {'cellType': ['IT', 'ITS4', 'PT', 'CT']},
                'sec': 'proximal',
                'groupSynMechs': PVSynMech, 
                'density': 'uniform'} 
        #------------------------------------------------------------------------------
        #  TC -> E: proximal
        netParams.subConnParams['TC->E'] = {
                'preConds': {'cellType': ['TC', 'HTC']}, 
                'postConds': {'cellType': ['IT', 'ITS4', 'PT', 'CT']},
                'sec': 'proximal',
                'groupSynMechs': ESynMech, 
                'density': 'uniform'} 
        #------------------------------------------------------------------------------
        #  TCM -> E: apical
        netParams.subConnParams['TCM->E'] = {
                'preConds': {'cellType': ['TCM']}, 
                'postConds': {'cellType': ['IT', 'ITS4', 'PT', 'CT']},
                'sec': 'apic',
                'groupSynMechs': ESynMech, 
                'density': 'uniform'}

    if cfg.addConn and cfg.addSubConn:
        addSubConn()

    #------------------------------------------------------------------------------
    # Background inputs
    #------------------------------------------------------------------------------
    if cfg.addBkgConn:

        # Add bkg sources for E and I cells
        netParams.stimSourceParams['excBkg'] = {
            'type': 'NetStim',
            'start': cfg.startBkg,
            'rate': cfg.rateBkg['exc'],
            'noise': cfg.noiseBkg,
            'number': 1e9
        }
        netParams.stimSourceParams['inhBkg'] = {
            'type': 'NetStim',
            'start': cfg.startBkg,
            'rate': cfg.rateBkg['inh'],
            'noise': cfg.noiseBkg,
            'number': 1e9
        }
        
        if cfg.cochlearThalInput:
            from input import cochlearSpikes
            readDcoch = False
            if 'readDcoch' in cfg.cochlearThalInput and len(cfg.cochlearThalInput['readDcoch']) > 0:
                try:
                    dcoch = pickle.load(open(cfg.cochlearThalInput['readDcoch'],'rb'))
                    readDcoch = True
                except:
                    print('could not load dcoch from ', cfg.cochlearThalInput['readDcoch'])
            if not readDcoch:
                dcoch = cochlearSpikes(
                    freqRange = cfg.cochlearThalInput['freqRange'],
                    numCenterFreqs=cfg.cochlearThalInput['numCenterFreqs'],
                    loudnessScale=cfg.cochlearThalInput['loudnessScale'],
                    lfnwave=cfg.cochlearThalInput['lfnwave'],
                    lonset=cfg.cochlearThalInput['lonset'],
                    fracHSRMSRLSR=dconf['net']['fracHSRMSRLSR'],
                    simDuration=cfg.duration,
                    autoSilence=cfg.cochlearThalInput['autoSilence'],
                    useLinearCF=cfg.cochlearThalInput['useLinearCF']
                )
            if 'saveDcoch' in cfg.cochlearThalInput:
                try:
                    fn = 'data/'+dconf['sim']['name']+'dcoch.pkl'
                    pickle.dump(dcoch, open(fn,'wb'))
                except:
                    print('could not save dcoch to', cfg.cochlearThalInput['saveDcoch'])
            if 'spkT' in dcoch:    
                cochlearSpkTimes = dcoch['spkT']
                cfg.cochlearCenterFreqs = cochlearCenterFreqs = dcoch['cf']
                cfg.numCochlearCells = numCochlearCells = len(cochlearCenterFreqs)
                netParams.popParams['cochlea'] = {'cellModel': 'VecStim', 'numCells': numCochlearCells, 'spkTimes': cochlearSpkTimes, 'ynormRange': layer['cochlear']}
            # print('len(cochlearSpkTimes):',len(cochlearSpkTimes))
            # netParams.popParams['cochlea']['gridSpacing'] = 1
            # netParams.popParams['cochlea']['sizeX'] = 100000 # numCochlearCells + 1
            # netParams.popParams['cochlea']['sizeY'] = netParams.popParams['cochlea']['sizeZ'] = 1

        if cfg.ICThalInput:
            # load file with IC output rates
            from scipy.io import loadmat

            data = loadmat(cfg.ICThalInput['file'])
            fs = data['RsFs'][0][0]
            ICrates = data['BE_sout_population'].tolist()
            ICrates = [x + [0] for x in ICrates] # add trailing zero to avoid long output from inh_poisson_generator() 
            ICtimes = list(np.arange(0, cfg.duration, 1000./fs))  # list with times to set each time-dep rate
            
            ICrates = ICrates * 4 # 200 cells
            
            numCells = len(ICrates)

            # these next two parameters are derived, so should be set here in case used by batch/optimization; because cfg.py
            # gets copied as a .json file without re-interpreting the other variables
            cfg.ICThalInput['weightEMatrix'] = cfg.ICThalInput['weightECore'] * cfg.ICThalInput['MatrixCoreFactor']
            cfg.ICThalInput['weightIMatrix'] = cfg.ICThalInput['weightICore'] * cfg.ICThalInput['MatrixCoreFactor']        

            # Option 1: create population of DynamicNetStims with time-varying rates
            #netParams.popParams['IC'] = {'cellModel': 'DynamicNetStim', 'numCells': numCells, 'ynormRange': layer['cochlear'],
            #    'dynamicRates': {'rates': ICrates, 'times': ICtimes}}

            # Option 2:
            from input import inh_poisson_generator
            
            maxLen = min(len(ICrates[0]), len(ICtimes))

            ### ADDED BY EYG 9/23/2022 TO ALLOW FOR MULTIPLE START TIMES (TEST)
            if type(cfg.ICThalInput['startTime']) == list:
                from collections import OrderedDict
                spkTimesDict = OrderedDict()
                startTimes = cfg.ICThalInput['startTime']
                for startTime in startTimes:
                    keyName = 'startTime_' + str(startTime)
                    print('KEY NAME: ' + keyName)
                    spkTimesDict[keyName] = [[x+startTime for x in inh_poisson_generator(ICrates[i][:maxLen], ICtimes[:maxLen], cfg.duration, cfg.ICThalInput['seed']+i)] for i in range(len(ICrates))]

                spkTimes = [None] * len(ICrates) #[]

                for i in range(len(ICrates)):
                    for key in spkTimesDict.keys():
                        if spkTimes[i] is None:
                            spkTimes[i] = spkTimesDict[key][i]
                        else:
                            spkTimes[i] = spkTimes[i] + spkTimesDict[key][i]

            else:
                ## Can change the t_stop arg in the inh_poisson_generator fx from cfg.duration to the length of the BBN stimulus (>100 ms)
                spkTimes = [[x+cfg.ICThalInput['startTime'] for x in inh_poisson_generator(ICrates[i][:maxLen], ICtimes[:maxLen], cfg.duration, cfg.ICThalInput['seed']+i)] for i in range(len(ICrates))]

            netParams.popParams['IC'] = {
                'cellModel': 'VecStim', 'numCells': numCells, 'ynormRange': layer['cochlear'],
                'spkTimes': spkTimes
            }

        OLD_BKG = 0

        if OLD_BKG:
            # excBkg/I -> thalamus + cortex
            with open('cells/bkgWeightPops.json', 'r') as f:
                weightBkg = json.load(f)
            pops = list(cfg.allpops)
            if 'cochlea' in pops:
                pops.remove('cochlea')
            if 'IC' in pops:
                pops.remove('IC')

            for pop in ['TC', 'TCM', 'HTC']:
                weightBkg[pop] *= cfg.EbkgThalamicGain
            for pop in ['IRE', 'IREM', 'TI', 'TIM']:
                weightBkg[pop] *= cfg.IbkgThalamicGain

            # Define bkg targets
            for pop in pops:
                netParams.stimTargetParams['excBkg->'+pop] =  {     
                    'source': 'excBkg',
                    'conds': {'pop': pop},
                    'sec': 'apic',
                    'loc': 0.5,
                    'synMech': ESynMech,
                    'weight': weightBkg[pop],
                    'synMechWeightFactor': cfg.synWeightFractionEE,
                    'delay': cfg.delayBkg
                }
                netParams.stimTargetParams['inhBkg->'+pop] =  {
                    'source': 'inhBkg',
                    'conds': {'pop': pop},
                    'sec': 'proximal',
                    'loc': 0.5,
                    'synMech': 'GABAA',
                    'weight': weightBkg[pop],
                    'delay': cfg.delayBkg
                }
               
        # cochlea/IC -> thal
        if cfg.ICThalInput:
            # IC -> thalamic core
            netParams.connParams['IC->ThalECore'] = { 
                'preConds': {'pop': 'IC'}, 
                'postConds': {'pop': ['TC', 'HTC']},
                'sec': 'soma', 
                'loc': 0.5,
                'synMech': ESynMech,
                'probability': cfg.ICThalInput['probECore'],
                'weight': cfg.ICThalInput['weightECore'],
                'synMechWeightFactor': cfg.synWeightFractionEE,
                'delay': cfg.delayBkg}        
            netParams.connParams['IC->ThalICore'] = { 
                'preConds': {'pop': 'IC'}, 
                'postConds': {'pop': ['IRE', 'TI']},
                'sec': 'soma', 
                'loc': 0.5,
                'synMech': 'GABAA',
                'probability': cfg.ICThalInput['probICore'],
                'weight': cfg.ICThalInput['weightICore'],
                'delay': cfg.delayBkg}
            # IC -> thalamic matrix
            netParams.connParams['IC->ThalEMatrix'] = { 
                'preConds': {'pop': 'IC'}, 
                'postConds': {'pop': ['TCM']},
                'sec': 'soma', 
                'loc': 0.5,
                'synMech': ESynMech,
                'probability': cfg.ICThalInput['probEMatrix'],
                'weight': cfg.ICThalInput['weightEMatrix'],
                'synMechWeightFactor': cfg.synWeightFractionEE,
                'delay': cfg.delayBkg}        
            netParams.connParams['IC->ThalIMatrix'] = { 
                'preConds': {'pop': 'IC'}, 
                'postConds': {'pop': ['IREM', 'TIM']},
                'sec': 'soma', 
                'loc': 0.5,
                'synMech': 'GABAA',
                'probability': cfg.ICThalInput['probIMatrix'],
                'weight': cfg.ICThalInput['weightIMatrix'],
                'delay': cfg.delayBkg}

    #------------------------------------------------------------------------------
    # Cochlear inputs
    #------------------------------------------------------------------------------

    def prob2conv(prob, npre):
        # probability to convergence; prob is connection probability, npre is number of presynaptic neurons
        return int(0.5 + prob * npre)

    # Cochlea -> thal
    def connectCochleaToThal ():
        print('connecting cochlea to thal')
        # these next two parameters are derived, so should be set here in case used by batch/optimization; because cfg.py
        # gets copied as a .json file without re-interpreting the other variables
        cfg.cochlearThalInput['weightEMatrix'] = cfg.cochlearThalInput['weightEMatrix']
        cfg.cochlearThalInput['weightIMatrix'] = cfg.cochlearThalInput['weightIMatrix']
        # cochlea to thalamic core uses topographic wiring, cochlea to matrix uses random wiring
        # cochlea -> Thal Core E neurons
        prob = '%f * exp(-dist_x/%f)' % (cfg.cochlearThalInput['probECore'], cfg.ThalamicCoreLambda)
        print('coch to thal E core prob:', prob)
        netParams.connParams['cochlea->ThalECore'] = { 
            'preConds': {'pop': 'cochlea'}, 
            'postConds': {'pop': ['TC','HTC']},
            'sec': 'soma', 
            'loc': 0.5,
            'synMech': ESynMech,
            'probability': prob,
            'weight': cfg.cochlearThalInput['weightECore'],
            'synMechWeightFactor': cfg.synWeightFractionEE,
            'delay': cfg.delayBkg}
        print('np:',netParams.connParams['cochlea->ThalECore'])
        prob = '%f * exp(-dist_x/%f)' % (cfg.cochlearThalInput['probICore'], cfg.ThalamicCoreLambda)
        # prob = cfg.cochlearThalInput['probICore'] # debug
        print('coch to thal prob:', prob)    
        netParams.connParams['cochlea->ThalICore'] = { 
            'preConds': {'pop': 'cochlea'}, 
            'postConds': {'pop': ['IRE', 'TI']},
            'sec': 'soma', 
            'loc': 0.5,
            'synMech': ESynMech,
            'probability': prob,
            'weight': cfg.cochlearThalInput['weightICore'],
            'synMechWeightFactor': cfg.synWeightFractionEI,
            'delay': cfg.delayBkg}  
        # cochlea -> Thal Matrix
        netParams.connParams['cochlea->ThalEMatrix'] = { 
            'preConds': {'pop': 'cochlea'}, 
            'postConds': {'pop': 'TCM'},
            'sec': 'soma', 
            'loc': 0.5,
            'synMech': ESynMech,
            'convergence': prob2conv(cfg.cochlearThalInput['probEMatrix'], numCochlearCells), 
            'weight': cfg.cochlearThalInput['weightEMatrix'],
            'synMechWeightFactor': cfg.synWeightFractionEE,
            'delay': cfg.delayBkg}
        netParams.connParams['cochlea->ThalIMatrix'] = { 
            'preConds': {'pop': 'cochlea'}, 
            'postConds': {'pop': ['IREM','TIM']},
            'sec': 'soma', 
            'loc': 0.5,
            'synMech': ESynMech,
            'convergence': prob2conv(cfg.cochlearThalInput['probIMatrix'], numCochlearCells),
            'weight': cfg.cochlearThalInput['weightIMatrix'],
            'synMechWeightFactor': cfg.synWeightFractionEI,
            'delay': cfg.delayBkg}

    if cfg.cochlearThalInput:
        connectCochleaToThal()

    #------------------------------------------------------------------------------
    # Current inputs (IClamp)
    #------------------------------------------------------------------------------
    
    def setupIClamp(d):
        # print('setupIClamp : ', d)
        # d[pop] can be a single dict or a list of dicts (multiple IClamps per pop)
        idx = 0
        for pop in d.keys():
            entries = d[pop] if isinstance(d[pop], list) else [d[pop]]
            for entry in entries:
                src = 'IClamp' + str(idx)
                netParams.stimSourceParams[src] = {
                    'type': 'IClamp',
                    'delay': entry.get('delay', 0.0),
                    'dur': entry.get('dur', 1e6),
                    'amp': entry['amp']
                }
                # Connect stim source to target
                netParams.stimTargetParams[src+'_'+pop] =  {
                    'source': src, 
                    'conds': {'pop': pop},
                    'sec': entry.get('sec', 'soma'), 
                    'loc': entry.get('loc', 0.5)
                }
                idx+=1

    if cfg.addIClamp:
        setupIClamp(cfg.IClamp)

    def setupRIClamp (d): # rhythmic iclamp
        # print('setupIClamp : ', d)
        idx = 0
        for pop in d.keys():
            # add stim source
            dur, amp, number = d[pop]['dur'], d[pop]['amp'], d[pop]['number']
            startt = d[pop]['delay']
            # print(pop,dur,amp)
            if dur <= 0.0 or amp == 0.0 or number <= 0.0: continue
            for jdx in range(d[pop]['number']):
                src = 'RIClamp' + str(idx)
                netParams.stimSourceParams[src] = {'type': 'IClamp', 'delay': startt, 'dur': dur, 'amp': amp}
                # connect stim source to target
                netParams.stimTargetParams[src+'_'+pop] =  {
                    'source': src, 
                    'conds': {'pop': pop},
                    'sec': d[pop]['sec'], 
                    'loc': d[pop]['loc']}
                idx+=1
                startt += d[pop]['interval']

    if cfg.addRIClamp:
        setupIClamp(cfg.RIClamp)

    #------------------------------------------------------------------------------
    # OU current / conductance inputs
    #------------------------------------------------------------------------------

    if cfg.add_ou_current and cfg.add_ou_conductance:
        raise ValueError('You should choose either cfg.add_ou_current=1 '
                         'or cfg.add_ou_current=1, not both')

    if cfg.add_ou_current or cfg.add_ou_conductance:

        # Load input resistances
        with open('data/inputResistances.json', 'rb') as f:
            inpRes = json.load(f)
        
        #print('create_net_params()')
        #print(f'\tcfg.add_ou_current = {cfg.add_ou_current}')
        #print(f'\tcfg.add_ou_conductance = {cfg.add_ou_conductance}')

        def _multiply(x, y):
            if np.isscalar(x):
                return x * y
            else:
                return [x_ * y for x_ in x]
        
        netParams.NoiseOUParams = {}
        
        for pop in cfg.allpops:
                        
            # Set OU parameters: common or per population
            if cfg.ou_common:
                ou_amp = _multiply(cfg.OUamp, 0.01)
                ou_std = _multiply(cfg.OUstd, 0.01)
            else:
                if pop in cfg.ou_pop_inputs:
                    ou_amp = _multiply(cfg.ou_pop_inputs[pop]['ou_mean'], 0.01)
                    ou_std = _multiply(cfg.ou_pop_inputs[pop]['ou_std'], 0.01)
                else:
                    ou_amp = 0
                    ou_std = 0
            
            # Reference value (ou_amp and ou_sigma are defined as percentage of it)
            if cfg.add_ou_conductance:
                K = 1 / inpRes[pop]
            elif cfg.add_ou_current:
                K = 70 / inpRes[pop]   # arbitrary multiplier (70 mV), for unit consistency

            mean = _multiply(ou_amp, K)
            sigma = _multiply(ou_std, K)

            #print(f'\tou_amp = {ou_amp}')
            #print(f'\tou_std = {ou_std}')
            #print(f'\tmean = {mean}')
            #print(f'\tsigma = {sigma}')
            
            # print('pop is: '  + pop + ' Input resistance is: ' + str(inpRes[pop]) + ' input conductance is: ' + str(Gin) + '   g0 is:  ' + str(g0))
            netParams.NoiseOUParams[pop] = {
                'mean': mean,
                'sigma': sigma
            }

            # Duration
            if cfg.add_ou_conductance and hasattr(cfg, 'NoiseConductanceDur'):
                duration = cfg.NoiseConductanceDur   # for compatibility with previous version
            else:
                duration = cfg.ou_noise_duration

            # Source params
            if cfg.add_ou_conductance:
                src_par = {
                    'type': 'ConductanceSource',
                    'dur1': duration,
                    'amp1': 0
                }
            elif cfg.add_ou_current:
                if hasattr(cfg, 'ou_ctrl_params'):
                #if False:
                    par = cfg.ou_ctrl_params
                    src_par = {
                        'type': 'NoiseIClampControlled2',
                        'mu0': mean,
                        'sigma0': sigma,
                        'mu_gain': par['mu_gain'],
                        'sigma_gain': par['sigma_gain'],
                        'noise': 0   # zero-mean noise will be played here later
                    }
                else:
                    src_par = {
                        'type': 'IClamp',
                        'dur': duration,
                        'amp': 0
                    }

            netParams.stimSourceParams[f'NoiseOU_source_{pop}'] = deepcopy(src_par)
            netParams.stimTargetParams[f'NoiseOU_target_{pop}'] = {
                'source': f'NoiseOU_source_{pop}',
                'sec': getattr(cfg, 'ou_sec', 'soma'),
                'loc': 0.5,
                'conds': {'pop': pop}
            }

    #------------------------------------------------------------------------------
    # NetStim E-I background inputs
    #------------------------------------------------------------------------------
    
    if cfg.add_bkg_spike_input:
        mech_default = {'exc': 'AMPA', 'inh': 'GABAA'}
        
        # Replace Netstim's by equivalent OU conductances
        if hasattr(cfg, 'replace_bkg_spikes_by_ou'):
            use_ou_bkg = cfg.replace_bkg_spikes_by_ou
        else:
            use_ou_bkg = False
        
        if use_ou_bkg:
            netParams.NoiseOUParams = {}

        for pop, inp in cfg.bkg_spike_inputs.items():
            for s, inp_ in inp.items():
                rx = inp_['r']
                wx = inp_['w']
                inp_name = f'{pop}_{s}'
                syn_mech_name = inp_.get('mech', mech_default.get(s, 'AMPA'))
                syn_mech = netParams.synMechParams[syn_mech_name]                

                if not use_ou_bkg:
                    netParams.stimSourceParams[f'bkg_src_{inp_name}'] = {
                        'type': 'NetStim',
                        'rate': rx,
                        'noise': inp_.get('noise', 1.0),
                        'start': inp_.get('start', 0),
                        'seed': inp_.get('seed', cfg.seeds['stim'])
                    }
                    netParams.stimTargetParams[f'bkg_targ_{inp_name}'] =  {
                        'source': f'bkg_src_{inp_name}',
                        'conds': {'pop': pop},
                        'sec': inp_.get('sec', 'soma'),
                        'loc': 0.5,
                        'synMech': syn_mech_name,
                        'weight': wx
                    }
                
                else:
                    if syn_mech.get('mod', None) != 'MyExp2SynBB':
                        raise ValueError('For replacing NetStim bkg by OU conductance, '
                                         'synaptic mechanism must be MyExp2SynBB')
                    tau = syn_mech['tau2']
                    e_rev = syn_mech['e']

                    mu = wx * rx * tau * 0.001 * 1e-3
                    sigma = wx * np.sqrt(rx * tau * 0.001 / 2) * 1e-3
                    netParams.NoiseOUParams[inp_name] = {'mean': mu, 'sigma': sigma}

                    cfg.add_ou_conductance = True
                    
                    netParams.stimSourceParams[f'NoiseOU_source_{inp_name}'] = {
                        'type': 'ConductanceSource2',
                        'dur1': cfg.duration,
                        'amp1': e_rev
                    }
                    netParams.stimTargetParams[f'NoiseOU_target_{inp_name}'] = {
                        'source': f'NoiseOU_source_{inp_name}',
                        'conds': {'pop': pop},
                        'sec': inp_.get('sec', 'soma'),
                        'loc': 0.5
                    }

    #------------------------------------------------------------------------------
    # NetStim inputs (to simulate short external stimuli; not bkg)
    #------------------------------------------------------------------------------
    if cfg.addNetStim:
        for key in [k for k in dir(cfg) if k.startswith('NetStim')]:
            params = getattr(cfg, key, None)
            [pop, ynorm, sec, loc, synMech, synMechWeightFactor, start, interval, noise, number, weight, delay, rate] = [
                params[s] for s in ['pop', 'ynorm', 'sec', 'loc', 'synMech', 'synMechWeightFactor', 'start',
                                    'interval', 'noise', 'number', 'weight', 'delay', 'rate']
            ] 

            # add stim source
            netParams.stimSourceParams[key] = {
                'type': 'NetStim', 'start': start, 'interval': interval, 'noise': noise, 'number': number, 
                'rate': rate
            }
            if not isinstance(pop, list): pop = [pop]
            for eachPop in pop:
                # connect stim source to target 
                # print('Adding NetStim',key, eachPop, 'ynorm',ynorm)
                netParams.stimTargetParams[key+'_'+eachPop] =  {
                    'source': key, 
                    'conds': {'pop': eachPop}, #, 'ynorm': ynorm},
                    'sec': sec, 
                    'loc': loc,
                    'synMech': synMech,
                    'weight': weight,
                    'synMechWeightFactor': synMechWeightFactor,
                    'delay': delay
                }

    # Pulse sequence
    if hasattr(cfg, 'add_pulses') and cfg.add_pulses:
        for par in _get_pulse_seq_param_list(cfg):
            _add_pulse_sequence(netParams, par)

    #------------------------------------------------------------------------------
    # Description
    #------------------------------------------------------------------------------

    netParams.description = """
    v7 - Added template for connectivity
    v8 - Added cell types
    v9 - Added local connectivity
    v10 - Added thalamic populations from prev model
    v11 - Added thalamic conn from prev model
    v12 - Added CT cells to L5B
    v13 - Added CT cells to L5A
    v14 - Fixed L5A & L5B E cell densities + added CT5A & CT5B to 'Epops'
    v15 - Added cortical and thalamic conn to CT5A and CT5B 
    v16 - Updated multiple cell types
    v17 - Changed NGF -> I prob from strong (1.0) to weak (0.35)
    v18 - Fixed bug in VIP cell morphology
    v19 - Added in 2-compartment thalamic interneuron model 
    v20 - Added TI conn and updated thal pop
    v21 - Added exc+inh bkg inputs specific to each cell type
    v22 - Made exc+inh bkg inputs specific to each pop; automated calculation
    v23 - IE/II specific layer gains and simplified code (assume 'Allen_custom')
    v24 - Fixed bug in IE/II specific layer gains
    v25 - Fixed subconnparams TC->E and NGF1->E; made IC input deterministic
    v26 - Changed NGF AMPA:NMDA ratio 
    v27 - Split thalamic interneurons into core and matrix (TI and TIM)
    v28 - Set recurrent TC->TC conn to 0
    v29 - Added EI specific layer gains
    v30 - Added EE specific layer gains; and split combined L1-3 gains into L1,L2,L3
    v31 - Added EI postsyn-cell-type specific gains; update ITS4 and NGF
    v32 - Added IE presyn-cell-type specific gains
    v33 - Fixed bug in matrix thalamocortical conn (were very low)
    v34 - Added missing conn from cortex to matrix thalamus IREM and TIM
    v35 - Parametrize L5B PT Ih and exc cell K+ conductance (to simulate NA/ACh modulation) 
    v36 - Looped speech stimulus capability added for cfg.ICThalInput
    v37 - Adding in code to modulate t-type calcium conductances in thalamic and cortical cells
    v38 - Adding in code to modulate NMDA synaptic weight from E --> I populations 
    v39 - Changed E --> I cfg.NMDARfactor such that weight is not a list, but instead a single value 
    v40 - added parameterizations from Christoph Metzner for localizing the large L1 sink
    v41 - modifying cochlea to Thal -> A1 for tonotopic gradient, adding functions
    """
    #v42 - Changed inhibitory receptor ratios for GABAB and NGF as well as altering the cochlear -> thalamic connections (prob and wieght)
    #v43 - Updated intrathalamic IE and EI parameters to create a more gradual reduction in TC cell mV over the course of stims 
    #v44 - Increased EEGain and decreased IEGain to increase the evoked activity in cortical pops
    #v45 - Updated background -> Ctx E and Ctx I pops and Bkg - > Thalamic E pops
    
    return netParams


if __name__ == '__main__':
    cfg = specs.SimConfig()
    cfg.netpar_force_load = 0
    cfg.netpar_fpath_json = (
        '/ddn/niknovikov19/repo/A1_OUinp/exp_configs'
        '/subnet/single'
        '/single_g_ou_subnet_wmult_0.005_som4_ire_netpar'
        '/par_sub_g_ouinp_wmult_0.005_som4_ire.json'
    )
    create_net_params(cfg)
