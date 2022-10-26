# Generate text file to be used by Sequence Diagram 

import json
import os
import re
import copy

DIRECTORY = '/Users/caio/Development/integra/flow/source'
IAC_FILE = 'integration-002.json'

# Execute remap
REMAP = True

def process_flow_01(module, modules, vectors, sequence_diagram):
    loops = []
    # Keep processing while there is next_hop
    while True:
        # Keep track of loops open in the branch
        if ((module['subtype'] in ['do', 'for']) and (module['operation'] == 'start')):
            loops.append(module['module_id'])
        # Keep track of closing loops in the branch
        if ((module['subtype'] in ['do', 'for']) and (module['operation'] in ['while', 'end'])):
            # Remove the top loop start
            try:
                loops.pop()
            except:
                # loops were empty which means do/for was opened on an outside branch
                # Return itself
                return [module]
        # Process the module
        if module['type'] == "trigger":
            process_trigger(module, sequence_diagram)
        elif module['type'] == "tool":
            process_tool(module, sequence_diagram)
        elif module['type'] == "connector":
            process_connector(module, sequence_diagram)
        
        if len(module['next']) > 1:
            joint_next = []
            #For each next hop
            for next_module in module['next']:
                #Find the module 
                for n_mod in modules:
                    if n_mod['module_id'] == next_module['id']:
                        break
                # Check if next_hop is a joint/end loop so we must
                # process alternative path 
                if (len(vectors[n_mod['module_id']]) > 1):
                    joint_next.append(n_mod)
                # Start over from there
                else:
                    if next_module['type'] == 'true':
                        # Next module will be on the TRUE path
                        sequence_diagram.append('else TRUE')
                    elif next_module['type'] == 'false':
                        # Next module will be on the FALSE path
                        sequence_diagram.append('else FALSE')
                    joint_next.extend(process_flow_01(n_mod,
                                                      modules,
                                                      vectors,
                                                      sequence_diagram))
            # joint_next may have multiple copies of next_hop
            cons = [mod["module_id"] for mod in joint_next]
            consolidated = set(cons)
            # If they are all equal
            if len(consolidated) == 1:
                #We're safe to move on and can CLOSE multiple path
                sequence_diagram.append('end')
                module = joint_next[0]
            else:
                print ("Error: unconsolidated next-hop", consolidated)
                #sys.exit(0)
                return([])
            
        elif len(module['next']) == 1:
            #Find the module
            for n_mod in modules:
                if n_mod['module_id'] == module['next'][0]['id']:
                    break
            if len(vectors[n_mod['module_id']]) > 1:
                return [n_mod]
            module = n_mod
        # We have reached the end
        elif (not module['next']):          
            return([])
        
        

def pre_process(modules):
    # Header Lines
    connectors = []
    # Flow parameter lines
    param_lines = []
    # vectors
    vectors = {}
    # Process Modules
    for module in modules:
        update_vectors(module, vectors)
        if module['type'] == "connector":
            connectors.append (module['name'])
        elif module ['type'] == "parameters":
            param_lines.append(process_flow_parms(module))
    # Extract duplicated elements
    connectors = list(set(connectors))
    connectors = connectors[:1] + ['Integra'] + connectors[1:]
    return (connectors, vectors, param_lines)

def remap(modules):
    # Map for new Modules ID
    id_map = { 'connector' : [],
               'trigger' : [],
               'tool' : [],
               'parameter' : []
               }
    new_modules = []
    # Build the mapping table
    for module in modules:
        build_id_table(module, id_map)
    # Replace 
    for module in modules:
        replace_id_table(module, id_map, new_modules)
    return (new_modules)
        
    #for each in id_map.keys():
    #    print(each, "\t", id_map[each])

def replace_id_table(module, id_map, new_modules):
    # Append new module on the new list
    n_mod = copy.deepcopy(module)
    new_modules.append(n_mod)
    if n_mod['type'] == 'parameters':
        for parm in n_mod['parameters']:
            match = re.search(r'[\{\[<][\]\}>](\w+) : ([\w.]+)[\{\[<]/[\]\}>]', parm['id'])
            if match:
                # Replace the id by the new ID mapped on id_map
                parm['id'] = parm['id'].replace(match[1], id_map[match[1]])
    else:
        # Replace the module id
        n_mod['module_id'] = id_map[n_mod['module_id']]
        # Replace the parameters
        for parm in n_mod['parameters']:
            if 'value' in parm.keys():
                if type(parm['value']) == str:
                    # Search for the parameter format
                    match = re.search(r'[\{\[<][\]\}>](\w+) : ([\w.]+)[\{\[<]/[\]\}>]', parm['value'])
                    if match:
                        old_id = match[1]
                    # It may also be the whole string    
                    elif parm['value'] in id_map.keys():
                        old_id = parm['value']
                    else:
                        # There is nothing here: skip to next
                        continue
                    parm['value'] = parm['value'].replace(old_id, id_map[old_id])
            if 'smop' in parm.keys():
                for parmN in parm['smop'].keys():
                    # We get also the operations in the loop but this shouldn't matter
                    # Search for the parameter format
                    match = re.search(r'[\{\[<][\]\}>](\w+) : ([\w.]+)[\{\[<]/[\]\}>]', parm['smop'][parmN])
                    if match:
                        old_id = match[1]
                    # It may also be the whole string    
                    elif parm['smop'][parmN] in id_map.keys():
                        old_id = parm['smop'][parmN]
                    else:
                        # There is nothing here: skip to next
                        continue
                    parm['smop'][parmN] = parm['smop'][parmN].replace(old_id, id_map[old_id])
                                        
        # Replace the next-hop
        for n_hop in n_mod['next']:
            n_hop['id'] = id_map[n_hop['id']]

def build_id_table(module, id_map):
    # Choose the right name prefix and vector
    if module['type'] == 'connector':
        map_list = id_map['connector']
        m_type = 'CN'
    elif module['type'] == 'tool':
        map_list = id_map['tool']
        m_type = 'TL'
    elif module['type'] == 'trigger':
        map_list = id_map ['trigger']
        m_type = 'TR'
    elif module['type'] == 'parameters':
        build_par_table(module['parameters'], id_map)
        return
    else:
        # Return for flow parameters
        return
    # Create new entry on the module type
    map_list.append(module['module_id'])
    # Create a new mapping for the module
    id_map[module['module_id']] = m_type + str(len(map_list)).zfill(3)
    return

def build_par_table(parameters, id_map):
    for parm in parameters:
        match = re.search(r'[\{\[<][\]\}>](\w+) : ([\w.]+)[\{\[<]/[\]\}>]', parm['id'])
        id_map['parameter'].append(match[1])
        id_map[match[1]] = 'PM' + str(len(id_map['parameter'])).zfill(3)

def process_flow_parms(module):
    line = "note over Integra#lightgray:--**"
    line = line + module['name'] + " [" + module['subtype'] + ']' + "\\n"
    line = line + module['information'] + "**\\n"
    # Walkthrough parameters
    for param in module['parameters']:
        id_name = re.search(r'\[\](\w+) : ([\w.]+)\[/\]', param['id'])
        line = line + '** ' + param['name'] 
        line = line + '""[' + id_name[1] + ']' 
        line = line + ' :** ' + '[' + param['type'] + ']""' + "\\n"
        line = line + "    " + param['description'] + "\\n"
    return line


# Build a list of vector reaching any node in the graph
def update_vectors(module, vectors):
    for next_hop in module['next']:
        # only for not end modules
        if (module['next']) :
            # if the next_hop module already exists on the dictionary
            if next_hop['id'] in vectors.keys():
                # update the next_hop with the current module
                vectors[next_hop['id']].append(module['module_id'])
            else:
                # create the next_hop on the dictionary with current module
                vectors[next_hop['id']] = [module['module_id']]

def process_trigger(module, sequence_diagram):
    line_base =  module['name'] + " [" + module['module_id'] + ']' + "\\n"
    line_base = line_base + module['information'] + "**\\n"            
    line = "abox right of Integra: --**"
    parameters = process_parameters(module['parameters'])
    sequence_diagram.append('activate Integra')
    sequence_diagram.append(line + line_base + parameters)

def process_tool(module, sequence_diagram):
    # Process parameters
    # Commum lines of information
    line_base =  module['name'] + " [" + module['module_id'] + ']' + "\\n"
    line_base = line_base + module['information'] + "**\\n"        
    parameters = process_parameters(module['parameters'])
    # Specific Lines for each module type
    if ((module['subtype'] == 'for') and (module['operation'] == 'start')):
        sequence_diagram.append("group FOR" )
        line = "note over Integra#lightgray:--**"
        sequence_diagram.append(line + line_base + parameters)
    elif ((module['subtype'] == 'do') and (module['operation'] == 'start')):
        sequence_diagram.append("group DO" )
    elif ((module['subtype'] == 'for') and (module['operation'] == 'end')):
        sequence_diagram.append("end" )
    elif ((module['subtype'] == 'do') and (module['operation'] == 'while')):
        line = "note over Integra#lightgray:--**"
        sequence_diagram.append(line + line_base + parameters)
        sequence_diagram.append("end" )
    elif (module['subtype'] == 'if'):
        sequence_diagram.append("alt" )
        line = "note over Integra#lightgray:--**"
        sequence_diagram.append(line + line_base + parameters)
    else:
        line = "rbox over Integra: --**" 
        sequence_diagram.append(line + line_base + parameters)
        

def process_connector(module, sequence_diagram):
    line = "Integra->" + module['name'] + ":--**" 
    line = line + module['name']
    line = line + ' [' + module['module_id'] + ']' + "\\n"
    line = line + module['information'] + "**\\n"    
    parameters = process_parameters(module['parameters'])
    line = line + parameters
    sequence_diagram.append(line)
    line = "activate " + module['name']
    sequence_diagram.append(line)
    line = module['name'] + "->Integra:--**RESPONSE**"
    sequence_diagram.append(line)
    line = "deactivate " + module['name']
    sequence_diagram.append(line)
    
def process_parameters(parameters):
    lines = []
    for parameter in parameters:
        if 'value' in parameter.keys():
            if type(parameter['value']) == str:   
                line = '**' + parameter['name'] + ' :** ""' + parameter['value'] + '""' 
            elif type(parameter['value']) == list:
                line = '**' + parameter['name'] + ' :** ""' + ','.join(parameter['value']) + '""'
            lines.append (line)
        elif 'smop' in parameter.keys():
            line = '**' + parameter['name'] + ' : SMOP**'
            lines.append (line)
            for key in parameter['smop'].keys():
                line = '    **' + key + ' :** ""' + parameter['smop'][key] + '""'
                lines.append(line)
    return ('\\n'.join(lines))
            


# For local test
if __name__ == "__main__":
    # iac
    iac_file = os.path.join(DIRECTORY, IAC_FILE)
    with open(iac_file, 'r') as mensagem:    
        data = mensagem.read()
    # parse file into dictionary
    source_modules = json.loads(data)
    
    modules = []
    
    
    if REMAP:
        # Remap IDs
        cp_modules = copy.deepcopy(source_modules)
        modules = remap(cp_modules)
    else:
        modules = copy.deepcopy(source_modules)
    
    connectors, vectors, param_lines = pre_process(modules)
    sequence_diagram = []
    for module in modules:
        if module['type'] == 'trigger':
            break
    process_flow_01(module, modules, vectors, sequence_diagram)
    for connector in connectors:
        print ("participant", connector)

    for line in param_lines:
        print (line)
    for line in sequence_diagram:
        print (line)
    
    
