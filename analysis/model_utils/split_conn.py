import json
import copy
from pathlib import Path

from netpyne import specs


def split_conn_by_sections(netParams, conn_name):
    """
    Split a connection into multiple connections, one for each section in the target section list.
    
    Parameters
    ----------
    netParams : NetParams object
        The network parameters object containing connection and cell parameters
    conn_name : str
        The name/label of the connection to be split
        
    Returns
    -------
    dict
        Dictionary with removed connection and newly created connections
        
    Notes
    -----
    This function: 
    1. Finds the connection in connParams and extracts post-synaptic population and section list
    2. Loads the corresponding cell params JSON file for the post-synaptic population
    3. Reads section lengths from the cell params file
    4.  Removes the original connection and replaces it with multiple connections
       (one per section), with probabilities weighted by section lengths
    """
    
    # Step 1: Find the connection and extract post-synaptic population and section list
    if conn_name not in netParams. connParams:
        raise ValueError(f"Connection '{conn_name}' not found in netParams. connParams")    
    conn = netParams.connParams[conn_name]
    
    # Get post-synaptic population
    if 'postConds' not in conn:
        raise ValueError(f"Connection '{conn_name}' does not have 'postConds'")    
    if 'pop' in conn['postConds']:
        post_pop = conn['postConds']['pop']
    elif 'cellType' in conn['postConds']: 
        # If 'pop' is not specified, use 'cellType' as a fallback
        post_pop = conn['postConds']['cellType']
    else:
        raise ValueError(f"Connection '{conn_name}' postConds does not have 'pop' or 'cellType'")
    
    # Handle case where post_pop might be a list
    if isinstance(post_pop, list):
        if len(post_pop) != 1:
            raise ValueError(f"Connection '{conn_name}' has multiple post-synaptic populations.  "
                              "This function only works with single post-synaptic population.")
        post_pop = post_pop[0]
    
    # Get target section list
    if 'sec' not in conn:
        raise ValueError(f"Connection '{conn_name}' does not have 'sec' field")    
    sec_list_name = conn['sec']
    
    # Get original probability
    if 'probability' not in conn and 'weight' not in conn:
        raise ValueError(f"Connection '{conn_name}' does not have 'probability' or 'weight' field")
    original_probability = conn.get('probability', 1.0)
    
    # Step 2: Load the cell params file
    cell_params_file = f"cells/{post_pop}_reduced_cellParams.json"    
    try:
        with open(cell_params_file, 'r') as f:
            cell_params = json.load(f)
    except FileNotFoundError: 
        raise FileNotFoundError(f"Cell params file not found:  {cell_params_file}")
    
    # Step 3: Get section list and calculate section lengths
    if 'secLists' not in cell_params: 
        raise ValueError(f"Cell params file {cell_params_file} does not contain 'secLists'")    
    if sec_list_name not in cell_params['secLists']:
        raise ValueError(f"Section list '{sec_list_name}' not found in cell params")    
    section_names = cell_params['secLists'][sec_list_name]
    
    # Get section lengths
    section_lengths = {}
    if 'secs' not in cell_params: 
        raise ValueError(f"Cell params file {cell_params_file} does not contain 'secs'")    
    for sec_name in section_names: 
        if sec_name not in cell_params['secs']:
            raise ValueError(f"Section '{sec_name}' not found in cell params 'secs'")        
        if 'geom' not in cell_params['secs'][sec_name]:
            raise ValueError(f"Section '{sec_name}' does not have 'geom' field")        
        if 'L' not in cell_params['secs'][sec_name]['geom']:
            raise ValueError(f"Section '{sec_name}' does not have length 'L' in geom")        
        section_lengths[sec_name] = cell_params['secs'][sec_name]['geom']['L']
    
    # Calculate total length for normalization
    total_length = sum(section_lengths.values())    
    if total_length == 0:
        raise ValueError(f"Total section length is zero for section list '{sec_list_name}'")
    
    # Step 4: Remove original connection and create new ones
    # Store the original connection for reference
    original_conn = copy.deepcopy(conn)
    
    # Remove original connection
    del netParams.connParams[conn_name]
    
    # Create new connections - one for each section
    new_conns = {}
    for sec_name, sec_length in section_lengths.items():
        # Calculate probability weighted by section length
        sec_probability = original_probability * (sec_length / total_length)
        
        # Create new connection name
        new_conn_name = f"{conn_name}_{sec_name}"
        
        # Create new connection (deep copy of original)
        new_conn = copy.deepcopy(original_conn)
        
        # Modify section and probability
        new_conn['sec'] = sec_name
        new_conn['probability'] = sec_probability
        
        # Add to netParams
        netParams.connParams[new_conn_name] = new_conn
        new_conns[new_conn_name] = new_conn
    
    # Return summary
    result = {
        'removed_conn': {conn_name: original_conn},
        'new_conns': new_conns,
        'post_pop': post_pop,
        'sec_list_name': sec_list_name,
        'section_lengths': section_lengths,
        'total_length': total_length
    }    
    return result


if __name__ == "__main__":
    # Load from json
    fpath_in = ('/ddn/niknovikov19/repo/A1_OUinp/exp_results'
                '/single_rxbkg_unconn_state1_mech1/subcon_test'
                '/exp_it2_som2_rx_250_1_wx_1.25_5_conn_1_subcon_0'
                '_t_0.3_1.0_vrest_-70_wmult_0.25_ee_0.5/subcon_test_netParams.json')
    with open(fpath_in) as fid:
        netpar_dict = json.load(fid)['net']['params']
    netParams = specs.NetParams(netpar_dict)

    # Transform
    split_conn_by_sections(netParams, 'EE_IT2_IT2_2')

    # Save to json
    fpath_out = Path(fpath_in).parent / 'subcon_test_netParams_splitcon.json'
    with open(fpath_out, 'w') as fid:
        json.dump({'net': {'params': netParams.todict()}}, fid, indent=4)
