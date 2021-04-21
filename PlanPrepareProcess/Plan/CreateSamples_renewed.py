import numpy as np
import pandas as pd
import os
import csv
import ast
import datetime
from pytz import timezone
import csv


##### Set up the experiment plan dictionary to be referenced for useful information throughout a design of experiments #####

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
    
    chem_data = pd.read_csv(chemical_database_path)
    chem_data_names = chem_data['Component Abbreviation']
    chem_data.index = chem_data_names
    plan_dict['Chemical Database'] = chem_data.T.to_dict()
    
    return plan_dict

def component_order_dictionary(plan):
    """Would hold a nested dictionary for each component for the case of maintaining the order and not having to repeat the calling 
    of list, this will make it less prone to errors when looking at names, units and linspace."""
    component_order_dict = {}
    for key, value in plan.items():
        if 'Component' in key:
            component_order_dict[key] = value

    return component_order_dict


##### Create the concentrations dataframe from components (Or in the simple case of not being concerned with final component concentration, this step would be calculating the percentages of each stock) #####

def concentration_from_csv(csv_path):
    """Given a path to a csv will translate to the information to a dataframe in the default nature of pandas.
    Data is formatted based on column and spacing, hence in a csv the first row will headers seperated by commas and the next row will 
    be respective header values seperated by commas."""
    concentration_df = pd.read_csv(csv_path)
    return concentration_df 

def concentration_from_excel(excel_path):
    """Given a path to an excel file (xlsx) will translate information to a dataframe in the default nature of pandas.
    Data is formatted based on the same row and column order within the excel sheet.
    Ensure the headers match the names of components of a plan as information
    """
    concentration_df = pd.read_excel(excel_path)
    return concentration_df

def concentration_from_linspace(plan, unity_filter = False):
    """ Uses linspaces to create a mesh of component concentrations. The linspaces
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

mass_dictionary = {'g':1} # should build a dictionary of units people can add to such that not restricted to hardcoded ones



def identify_unit(string):
    """Based on a provided string will identify if a unit within a list verified working units"""
    supported_units = ['wtf','volf','molf','mgpermL','molarity', 'g', 'mL', 'g/mL', 'g/mol']
    for unit in supported_units:
        if unit in string:            
            return unit
    raise AssertionError('Unit in ' + string + ' not currently supported, the following units are supported: ', supported_units)
        
def identify_component_name(string):
    """Will pull the first word from the string and return it to be used as the name to look up in a chemical database.
    Can also make this is a checkpoint to ensure the component is in the chemical database to begin with. This allows you 
    to contain all information within a column (component identity, name)"""
    component = string.split(' ', 1)[0]
    return component


def determine_component_mass(total_sample_amount, total_sample_amount_unit, component_values, component_unit, component_info):
    """Determines the mass of a component (series or single value) based on the total sample unit and the component unit. 
    Hence there are a finate number of unit combinations which will work, the easiest way to think about this look the numerator 
    and denominator of the component unit and determine how to remove the denominator."""
    
    if total_sample_amount_unit == 'g' and component_unit == 'wtf':
        component_masses = total_sample_amount*component_values

    elif total_sample_amount_unit == 'mL' and component_unit == 'mgpermL':
        component_masses = total_sample_amount*component_values/1000 # for now default mass = g, volume = mL

    elif total_sample_amount_unit == 'mL' and component_unit == 'molarity':
        molecular_weight = component_info['Molecular Weight (g/mol)']
        component_masses = total_sample_amount*component_values*molecular_weight/1000
    
    else: 
        raise AssertionError(total_sample_amount_unit, 'and', component_unit, 'units are not supported to calculate for mass')
    print('You calculated for component masses given the provided units')
    return component_masses

def determine_component_volumes(total_sample_amount, total_sample_amount_unit, component_values, component_unit, component_info):
    """Determines the volume of a component (series or single value) based on the total sample unit and the component unit. 
    Hence there are a finate number of unit combinations which will work, the easiest way to think about this look the numerator 
    and denominator of the component unit and determine how to remove the denominator."""
    
    if total_sample_amount_unit == 'mL' and component_unit == 'volf':
        component_volume = total_sample_amount*component_values
        print('You calculated for component volumes given the provided units')
        return component_volume


def determine_component_amounts(concentration_df, plan):
    """Based on plan information (Component Names and total sample unit) will determine the amount of each component (mass or volume) 
    required for each sample. Currently only supports mL and g as default units. 
    It is recommended you keep plan lists in order i.e component[2] refers to the third column of components."""
    
    component_info_dict = plan['Chemical Database']
    component_names = plan['Component Shorthand Names']
    total_sample_amount_unit = plan['Sample Unit']
    total_sample_amount = plan['Sample Amount']
    
    for column_name, component_name in zip(concentration_df, component_names): # change to just iterate through column name
        if component_name in column_name: # could just use name to call specfic column versus iterating?
            component_values = concentration_df[column_name]
            component_info = component_info_dict[component_name]
            component_unit = identify_unit(column_name)
            if component_unit == 'wtf' or 'mgpermL' or 'molarity': # these are the unit that lead to mass outcomes
                component_masses = determine_component_mass(total_sample_amount, total_sample_amount_unit, component_values, component_unit, component_info)  
                concentration_df[component_name + ' amount mass ' + total_sample_amount_unit]  = component_masses
            if component_unit == 'volf': # these are the unit that lead to volume outcomes
                component_volume = determine_component_volumes(total_sample_amount, total_sample_amount_unit, component_values, component_unit, component_info)  
                concentration_df[component_name + ' amount volume ' + total_sample_amount_unit]  = component_masses
    return concentration_df


def calculate_component_amount_missing(component_amounts_df, plan):
    chemical_database = plan['Chemical Database']
    
    for amount_col in component_amounts_df:
        component_amount = component_amounts_df[amount_col]
        component = identify_component_name(amount_col)
        component_unit = identify_unit(amount_col)
        component_info = chemical_database[component]
        component_density = component_info['Density (g/mL)']
        
        if 'mass' in amount_col: # could make a small function to deteremine amount type
            component_volumes = component_amount/component_density
            component_amounts_df[amount_col.replace('mass '+ component_unit, 'volume mL')] = component_volumes
            print('You calculated component volumes from a component mass using ' + component  + ' density of ' + str(component_density) + ' g/mL' )
        elif 'volume' in amount_col:
            component_masses = component_amount*component_density
            component_amounts_df[amount_col.replace('volume '+ component_unit, 'mass g')] = component_masses
            print('You calculated component masses from a component volumes using ' + component  + ' density of ' + str(component_density) + ' g/mL' )
#         else: # this wont work as it will call out other columns
#             raise AssertionError('Component amounts not present. Amount headers need to be formatted as ComponentName_amount_volumeormass_unit, example: dppc amount volume mL')

    return component_amounts_df
# be careful not to run this twice as it will overwrite some stuff

def nan_amounts(amounts_df):
    amounts_df_zeroed = amounts_df.fillna(0)
    return amounts_df_zeroed


##################### In progress ##############################

def concentration_from_linspace_all_info(plan, unity_filter = False): # if you go this route you can do whole dataframe operation you just need to verify all component units of the same type
    """ Uses linspaces to create a mesh of component concentrations
    """
    component_linspaces = plan['Component Concentration Linspaces [min, max, n]']
    component_spacing_type = 'linear'

    conc_range_list = [] 
    for conc_linspace in component_linspaces:
        if component_spacing_type == "linear": 
            conc_range_list.append(np.linspace(*conc_linspace))
    conc_grid = np.meshgrid(*conc_range_list)
    
    total_sample_amount = plan['Sample Amount']
    total_sample_amount_unit = plan['Sample Unit']
    component_names = plan['Component Shorthand Names']
    component_units = plan['Component Concentration Units']
    
    data = []
    columns = []
    for component_index in range(len(conc_grid)): 
        n = len(conc_grid[component_index].ravel())
        
        component_name_entry = [component_names[component_index]]*n
        columns.append('Component ' + str(component_index) + ' Name')
        data.append(component_name_entry)
        
        component_unit_entry = [component_units[component_index]]*n
        columns.append('Component ' + str(component_index) + ' Concentration Unit')
        data.append(component_unit_entry)
        
        component_concentration_column = 'Component ' + str(component_index) + ' Concentration Value'
        component_concetration_values = conc_grid[component_index].ravel()
        columns.append(component_concentration_column)
        data.append(component_concetration_values)
        
    component_conc_df = pd.DataFrame(data, columns).T # will terminate here if not needed unity
        
    if unity_filter == True: # generalize this  and make into callable function
        final_component_index = component_index + 1 
        
        component_name_entry = [component_names[final_component_index]]*n
        columns.append('Component ' + str(final_component_index) + ' Name')
        data.append(component_name_entry)
        
        component_unit_entry = [component_units[final_component_index]]*n
        columns.append('Component ' + str(final_component_index) + ' Concentration Unit')
        data.append(component_unit_entry)
        
        concentration_values_isolated = component_conc_df[[col for col in component_conc_df.columns if 'Concentration Value' in col]]
        completing_concentration_values = (1 - concentration_values_isolated.sum(axis=1)).tolist()
        data.append(completing_concentration_values)
        columns.append('Component ' + str(final_component_index) + ' Concentration Value')

    component_conc_df = pd.DataFrame(data, columns).T
    
    component_conc_df.insert(loc=0, column = 'Total Sample Amount Unit', value = [total_sample_amount_unit]*n)
    component_conc_df.insert(loc=0, column = 'Total Sample Amount', value = [total_sample_amount]*n) # this needs to be added at the same amount

    return component_conc_df

def determine_concentration_path(concentration_variable, variable_type):
    """ Determines the appropiate path to handle and create concentration design space... Still in progress requires kwargs
    """
    if 'variable_type' == 'csv':
        return cconcentration_variable
    elif 'variable_type' == 'excel':
        return concentration_variable
    elif variable_type == 'linspace':
        pass
    elif variable_type == 'sublists':
        pass

def determine_unit_pathway(plan, concentration_df):
    components_concentration_units = plan['Component Concentration Units']

    pass