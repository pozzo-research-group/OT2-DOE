import numpy as np
import pandas as pd
import os
import csv
import ast
import datetime
from pytz import timezone
import csv


def get_experiment_plan(filepath, chemical_database_path):
    """
    Parse a .csv file to create a dictionary of instructions.
    """
    with open(filepath, newline='') as csvfile:
        reader = csv.reader(csvfile)
        plan_dict = {}
        for i, row in enumerate(reader):
            assert len(row) == 2
            plan_dict[row[0]] = ast.literal_eval(row[1])
    
    input_file = csv.DictReader(open(chemical_database_path))
    chem_database_dict = {}
    for i, row in enumerate(input_file):
        component_name = row['Component Abbreviation']
        chem_database_dict[component_name] = row

    plan_dict['Chemical Database'] = chem_database_dict
    
    return plan_dict

def component_order_dictionary(plan):
    """Would hold a nested dictionary for each component for the case of maintaining the order and not having to repeat the calling 
    of list, this will make it less prone to errors when looking at names, units and linspace."""
    component_order_dict = {}
    for key, value in plan.items():
        if 'Component' in key:
            component_order_dict[key] = value

    return component_order_dict


##### Create the concentrations dataframe from components (or if simple case the stocks themselves) #####

def determine_concentration_path(concentration_variable, variable_type):
    # could do the thing were just blatantly state which thing, csv, excel, linspace, list... maybe use of kwargs will simplify this.
    if 'variable_type' == 'csv':
        return concentration_variable
    elif 'variable_type' == 'excel':
        return concentration_variable
    elif variable_type == 'linspace':
        pass
    elif variable_type == 'sublists':
        pass

def concentration_from_linspace(plan, unity_filter = False):
    """ Uses linspaces to create a mesh of component concentrations
    """
    component_linspaces = plan['Component Concentration Linspaces [min, max, n]']
    component_spacing_type = 'linear'

    conc_range_list = [] 
    for conc_linspace in component_linspaces:
        if component_spacing_type == "linear": 
            conc_range_list.append(np.linspace(*conc_linspace))
    conc_grid = np.meshgrid(*conc_range_list)
    
    component_names = plan['Component Shorthand Names']
    component_units = plan['Component Concentration Units']
    component_conc_dict = {} 
    for i in range(len(conc_grid)): 
        component_name = component_names[i]
        component_unit = component_units[i]
        component_values = conc_grid[i].ravel()
        component_conc_dict[component_name + " " + 'concentration' + " " + component_unit] = conc_grid[i].ravel()
    concentration_df = pd.DataFrame.from_dict(component_conc_dict)


    # this is only here for linspaces as why? it should just be an option for all of them
    if unity_filter == True:
        unity_filter_df(concentration_df, component_names, component_units)

    return concentration_df

def concentration_from_csv(csv_path):
    concentration_df = pd.read_csv(csv_path)
    return concentration_df 

def concentration_from_excel(excel_path):
    concentration_df = pd.read_excel(excel_path)
    return concentration_df

def concentration_from_list_samplewise(plan, conc_sublists):
    
    component_names = plan['Component Shorthand Names']
    concentration_df = pd.DataFrame(data=conc_sublists)
    concentration_df.columns = component_names

    return concentration_df

def concentration_from_list_componentwise(plan, conc_sublists):
    
    component_names = plan['Component Shorthand Names']
    concentration_df = pd.DataFrame(data=conc_sublists).T
    concentration_df.columns = component_names

    return concentration_df

def unity_filter_df(concentration_df, component_names, component_units):
    """For units which sum to one, will create an additional column to represent the final component. This will require 
    that the input information such as sample names have this completing component as the last entry. Currently no general way 
    to verify if sample is under of overspecified, must verify yourself.
    """
        
    completing_index = len(component_names)-1
    completing_component_name = component_names[completing_index]
    completing_component_unit = component_units[completing_index]
    completing_entry_name = completing_component_name + " " + 'concentration' + " " + completing_component_unit
    concentration_df[completing_entry_name] = (1 - concentration_df.sum(axis=1)) 
        
    unfiltered_concentration_df = concentration_df # used to catch errors when concentration_df after fully defined concentration produces no suitable canidates
    
    concentration_df = concentration_df[concentration_df[completing_entry_name] > 0]
    concentration_df.reset_index(drop=True, inplace=True)

    assert not concentration_df.empty, 'No suitable samples were found, please change your concentration space. Most likely this means you have your linspaces set too close together at all high concentrations (close to 1) resulting in impossible samples (wtf/volf>1). Turn on expose_df to return unfiltered dataframe'
    return concentration_df

mass_dictionary = {g:1} # should build a dictionary of units people can add to such that not restricted to hardcoded ones

def determine_unit_pathway(plan, concentration_df):
    components_concentration_units = plan['Component Concentration Units']

    for cib



