import json
import pickle
from copy import deepcopy
from pathlib import Path

import numpy as np

from netpyne.batchtools import specs


DIRPATH_SELF = Path(__file__).resolve().parent


def _asset_path(*parts):
    """Resolve a bundled model asset inside model_nn_1."""
    return DIRPATH_SELF.joinpath(*parts)


def _cfg_path(path_like):
    """Resolve an optional cfg path relative to model_nn_1."""
    path = Path(path_like)
    if path.is_absolute():
        return path
    return DIRPATH_SELF / path


def create_net_params(cfg):
    """Create netParams based on a config, common for all parameter sets. """

    # Reject unsupported standalone branches
    if getattr(cfg, 'addBkgConn', False):
        raise NotImplementedError('model_nn_1 does not carry addBkgConn into the standalone workflow')
    if getattr(cfg, 'cochlearThalInput', False):
        raise NotImplementedError('model_nn_1 does not carry cochlearThalInput into the standalone workflow')
    if getattr(cfg, 'ICThalInput', False):
        raise NotImplementedError('model_nn_1 does not carry ICThalInput into the standalone workflow')
    if getattr(cfg, 'add_ou_current', False) or getattr(cfg, 'add_ou_conductance', False):
        raise NotImplementedError('model_nn_1 does not carry OU-based inputs into the standalone workflow')
    if getattr(cfg, 'replace_bkg_spikes_by_ou', False):
        raise NotImplementedError('model_nn_1 does not carry OU replacement for background spikes')

    #------------------------------------------------------------------------------
    # Load netParams from json file instead of creating them
    #------------------------------------------------------------------------------
    if hasattr(cfg, 'netpar_force_load') and cfg.netpar_force_load:
        with open(_cfg_path(cfg.netpar_fpath_json), 'r') as f:
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
        netParams.loadCellParamsRule(
            label=ruleLabel,
            fileName=str(_asset_path('cells', f'{ruleLabel}_cellParams.json')),
        )


    #------------------------------------------------------------------------------
    # Population parameters
    #------------------------------------------------------------------------------

    ## Load densities
    with open(_asset_path('cells', 'cellDensity.pkl'), 'rb') as fileObj:
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
    with open(_asset_path('conn', 'conn.pkl'), 'rb') as fileObj:
        connData = pickle.load(fileObj)
    pmat = connData['pmat']
    lmat = connData['lmat']
    wmat = deepcopy(connData['wmat'])
    bins = connData['bins']
    connDataSource = connData['connDataSource']

    # Apply active global weight multiplier to raw conn.pkl weights
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
        setupRIClamp(cfg.RIClamp)

    #------------------------------------------------------------------------------
    # NetStim E-I background inputs
    #------------------------------------------------------------------------------
    
    if cfg.add_bkg_spike_input:
        mech_default = {'exc': 'AMPA', 'inh': 'GABAA'}
        for pop, inp in cfg.bkg_spike_inputs.items():
            for s, inp_ in inp.items():
                rx = inp_['r']
                wx = inp_['w']
                inp_name = f'{pop}_{s}'
                syn_mech_name = inp_.get('mech', mech_default.get(s, 'AMPA'))
                if syn_mech_name not in netParams.synMechParams:
                    raise KeyError(f'Unknown synaptic mechanism for background input: {syn_mech_name}')
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
        par = cfg.pulse_seq_params
        name = par['name']
        t0, T = par['t0'], par['period']
        pop_out = par['pop']
        #n_post = netParams.popParams[pop_out]['numCells']

        if isinstance(pop_out, str):
            pop_out = [pop_out]
        pop_out = [pop for pop in pop_out if pop in netParams.popParams]
        pop_out_str = '_'.join(pop_out)
        
        netParams.popParams[name] = {
            'cellModel': 'VecStim',
            'numCells': par['n_cells'],
            'params': {
                'rate': 0.001,   # very small bkg (required)
                'pulses': [
                    { 
                    'start': t0 + n * T, 
                    'end':   t0 + n * T + par['width'],
                    'rate':  par['rates'][n],
                    'noise': 1.0,
                    }
                    for n in range(par['n_pulses'])
                ]
            }
        }
        netParams.connParams[f'{name}->{pop_out_str}'] = {
            'preConds':  {'pop': name},
            'postConds': {'pop': pop_out},
            #'connList': [[i, i] for i in range(n_post)],
            'convergence': par['convergence'],
            'sec': 'soma',
            'loc': 0.5,
            'weight': par['weight'],
            'delay': 1,
            'synMech': 'AMPA',
            'synsPerConn': 1
        }

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
