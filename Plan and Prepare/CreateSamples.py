import numpy as np
import pandas as pd
from opentrons import simulate, execute, protocol_api
import os
import csv
import ast
import datetime
from pytz import timezone
import csv

"""Common terms/info: 
    wtf = weight fraction
    2D list or nested list = [[a,b,c], [e,f,g]]
    
    Unless otherwise stated:
    - The order of list or array should be assumed to match that of its naming list or arrays. For example if stock_concentrations = [0.1, 0.5, 1] with stock_names = [A, B, C], stock_unit = ['wtf', 'wtf', 'wtf'] then stock A = 1 wtf, B = 0.5 wtf and so on.
    - Volumes are defaulted to microliters (default unit of opentrons) 
    

    
    Other notes: 
       - Currently each component has its own respective stock that only has most one solvent. Working on modifying the component logic to allow for automatic search of components and match them with respective stock, issue I can already see arising is when one component is present in more than one stock how to assign proirity. 
       - Could make add information to the final wrapper dictionary of component order like entries like "component sample order" and "component array units" - shows for future use of allowing more units - something slowly working on through looking at flowthrough. 
       - To keep general do not use wrappers to wrap multiple functions unless it is something simple thing like reordering that you do not want to clog up. 
       - Have the information from the CSV clear what format it should be in
      
       - Work on looking at the flowthrough and how you would add geenralizations, what is currently constrained? What units can be come what units and what cannot be
       converted and how will effect/how will you need to change the functions you currently have? Are there specfic cases that one should avoid or are difficult to exper. 
       - Once you do this you will see how you will need to change the notation and names of vairables to unrestrict

       go through and add quick explanation up here for her function 

    """

def get_experiment_plan(filepath):
    """
    Parse a .csv file to create a dictionary of instructions.
    """
    with open(filepath, newline='') as csvfile:
        reader = csv.reader(csvfile)
        plan_dict = {}
        for i, row in enumerate(reader):
            assert len(row) == 2
            plan_dict[row[0]] = ast.literal_eval(row[1])

    return plan_dict

def check_for_volume_unit(name):
    """Calculate the dictionay which where key is unit string and key is the unit/L conversion, 
    i.e. mL number base will be 1000."""
    unit_dict = {' L':1, 'mL':1000, 'uL':1000000} # need to add space to prevent L picking up uL?
    unit_dict_keys = unit_dict.keys()
    
    for unit in unit_dict_keys:
        if unit in name:
            return {unit:unit_dict[unit]}

def convert_to_liter(df):
    """Will convert any volume units in a dataframe to base of liter. 
    Make sure no dtypes are mixed (i.e. not object). Units between columns in dataframe can be mixed."""
    for name in df:
        unit_dict = check_for_volume_unit(name)
        unit = next(iter(unit_dict))
        conversion_value = unit_dict[unit]
        
        new_name = name.replace(unit," L")
        df[new_name] = df[name]/conversion_value
        df.drop([name], axis=1, inplace = True)
    return df

def convert_volume_unit(df, unit):
    # to convert we will multiply desired_conversion_value/current_conversion_value 
    desired_unit = unit 
    desired_unit_dict = check_for_volume_unit(desired_unit)
    desired_conversion_value = desired_unit_dict[desired_unit]
    
    for name in df:
        current_unit_dict = check_for_volume_unit(name)
        current_unit = next(iter(current_unit_dict))
        current_conversion_value = current_unit_dict[current_unit] # from liter
        
        new_name = name.replace(desired_unit,''+desired_unit)
        df[new_name] = df[name]*(desired_conversion_value/current_conversion_value)
        df.drop([name], axis=1, inplace = True)
    return df
        
def check_unit_congruence(df):
    """Ensures all units in a dataframe are the same. Useful when applying dataframe wide operations."""
    cols = df.columns
    units = []
    for col in cols:
        unit = check_for_volume_unit(col)
        units.append(unit)
    if all_same(units) == False:
        raise AssertionError('All units of columns are not identical, please convert all units and associated names to equal units.')
              
def all_same(items):
    "Checks whether all elements are identical in type and value, using the initial entry as the basis of comparison"
    return all(x == items[0] for x in items)

def combine_df(df1,df2):
    df3 = pd.concat([df1,df2], axis=1)
    return df3

# also naming notation should more be "uniform" versus "lattice"
def generate_candidate_lattice_concentrations(experiment_csv_dict, unity_filter = False, expose_unfiltered_df = False):
    """Given the complete csv dictionary of instruction, uses the n component linspaces of equivalent concentration units which summmation equal one (i.e. volf or wtf). 
    The number of linspaces used are to equal the total number of components - 1. Once a 2D list of component concentration candidates are generated the canidates (of length total # of components - 1) are subsequently filtered/completed by sample_sum_filter. 
    All entry additions follow the order of linspaces from the experiment_csv_dict."""
    
    component_units = experiment_csv_dict['Component Concentration Unit']
    component_names = experiment_csv_dict['Component Shorthand Names']
    component_conc_linspaces = experiment_csv_dict['Component Concentrations [min, max, n]']
    component_spacing_type = experiment_csv_dict['Component Spacing']

    # Checks
    assert len(component_units) == len(component_names), 'Number of component names not equal to number of provided units'
    assert all_same(component_units), 'Unit of components are not identical, currently all units must be identical.'    
    

    conc_range_list = [] # will hold flattened linspaces (component spacing) of possible concentration for each component given the spacing method 
    for conc_linspace in component_conc_linspaces:
        if component_spacing_type == "linear": 
            conc_range_list.append(np.linspace(*conc_linspace))
        elif component_spacing_type == "random": # ensure space searching small enough or resoluiton high enough. 
            conc_range_list.append(np.random.uniform(*conc_linspace))
        else:
            type_list = ["linear","random"] 
            assert component_spacing_type in type_list, "spacing_type was not specified in the experiment plan, or the the requested method is not implemented."
    
    conc_grid = np.meshgrid(*conc_range_list) # Setup for every combination of the flattened linspaces with meshgrid.

    component_conc_dict = {} 
    for i in range(len(conc_grid)): 
        component_name = component_names[i]
        component_unit = component_units[i]
        component_conc_dict[component_name + " " + component_unit] = conc_grid[i].ravel()
    concentration_df = pd.DataFrame.from_dict(component_conc_dict)

    # Here is where we can incorperate different types of filters, such as this unity filter. 
    if unity_filter == True: 
        assert len(component_names) != len(component_conc_linspaces), "The provided experimental instructions are overspecified." # Add one for underspecified, perhaps should have these in their own functions as to quickly use in other processes 
        if component_units[0] in ('wtf','volf','molf'):
            assert len(component_units) != len(component_conc_linspaces) - 1, 'Concentrations are either over- or under- defined' 
        
            completing_index = len(component_names)-1
            completing_component_name = component_names[completing_index]
            completing_component_unit = component_units[completing_index]
            completing_entry_name = completing_component_name + " " + completing_component_unit
            concentration_df[completing_entry_name] = (1 - concentration_df.sum(axis=1)) 
        
            unfiltered_concentration_df = concentration_df # used to catch errors when concentration_df after fully defined concentration produces no suitable canidates
            concentration_df = concentration_df[concentration_df[completing_entry_name] > 0]
            concentration_df.reset_index(drop=True, inplace=True)
        
            if expose_unfiltered_df == True:
                return unfiltered_concentration_df

            assert not concentration_df.empty, 'No suitable samples were found, please change your concentration space. Most likely this means you have your linspaces set too close together at all high concentrations (close to 1) resulting in impossible samples (wtf/volf>1). Turn on expose_df to return unfiltered dataframe'
        
        else:
            raise AssertionError("Component " + str(component_units[0]) + " unit not currently supported")
        
    return concentration_df

def generate_candidate_lattice_stocks(experiment_csv_dict): # work on trying to get this into one function with generate_candidate_lattice_concentrations
    """Mirror of function generate_candidate_lattice_concentrations expect for the case of looking through multiple stocks and creating combinations of stock concentrations from the csv provided stock concentration linspaces. The major diffierences is the lack of optional 0 concentration handling and unity filter as the concentrations of stocks are independent from on another unlike the concentrations of a components in a singular sample. Returns a 2D array of stock concnetration combinations. Again 1D order is order of stock name and linspace."""
    
    stock_name_list = experiment_csv_dict['Stock Names']
    stock_units = experiment_csv_dict['Stock Concentration Units']
    stock_concs_linspaces_list = experiment_csv_dict['Stock Search Concentrations [min, max, n]']

    assert len(stock_units) == len(stock_name_list), 'Number of component names not equal to number of provided units' 
    
    stock_ranges_list = []

    for stock_range in stock_concs_linspaces_list:
        stock_ranges_list.append(np.linspace(*stock_range))
        
    conc_grid = np.meshgrid(*stock_ranges_list)
    
    stock_conc_dict = {}
    for i in range(len(conc_grid)): 
        stock_name = stock_name_list[i]
        stock_unit = stock_units[i] # support all units unlike completing concentration case
        stock_conc_dict[stock_name + " " + stock_unit] = conc_grid[i].ravel()
    stock_concentration_df = pd.DataFrame.from_dict(stock_conc_dict)

    assert not stock_concentration_df.empty, 'No suitable samples were found, please change your concentration space. Most likely this means you have your linspaces set too close together at all high concentrations (close to 1) resulting in impossible samples (wtf/volf>1). Turn on expose_df to return unfiltered dataframe'
    stock_concentration_array = stock_concentration_df.values 

    return stock_concentration_array


def prepare_stock_search(stock_canidates, experiment_csv_dict, wtf_sample_canidates, min_instrument_vol, max_instrument_vol):
    """
    Used to create a dictionary containing volume and fractional concnetration (currently only wtf and not volf notation wise) of sample canidates which are based on a groups of stock canidates. Also provides useful information in the stock_text_list entry like which stock combination was used and the number of samples possible with the specfic stock combination and concentration canidates. Essentially this runs through the process of creating a bunch of plausible cases given the single component canidates with the each of the previously created stock combination canidates. 
    
    Stock_canidates is a 2D array of stock_canidates provided from generate_candidate_lattice_stocks
    wtf_sample_canidates is the 2D array of wtf_canidates provided from generate_candidate_lattice
    max/min_instrument_vol is the max/min volume to be used by current instrumentation (this will change with instrumentation)
    
    """
    
    stock_names = experiment_csv_dict['Stock Names']
    stock_units = experiment_csv_dict['Stock Concentration Units']
    
    filtered_wtf_list = []
    filtered_volumes_list = []
    stock_text_list = []
    
    for stock_canidate in stock_canidates:
        
        volume_canidates = calculate_ouzo_volumes_from_wtf(wtf_sample_canidates, experiment_csv_dict, stock_searching=True, stock_searching_concentration=stock_canidate) # note the searching option here is important as we want to use a stock candiate from the stock_canidates_list rather than from the csv directly. ATM once you make your actual stocks you will need to go into the csv and change the "Stock Final Concentrations", it is not an input in a python cell as it needs to recorded down somewhere permanent like the csv instructions. 
        
        filtered_wtf_samples, filtered_volumes_samples, min_sample_volume, max_sample_volume = filter_samples(wtf_sample_canidates, volume_canidates, min_instrument_vol, max_instrument_vol)
        
        filtered_wtf_list.append(filtered_wtf_samples)
        filtered_volumes_list.append(filtered_volumes_samples)
        
        stock_text = ['', 'Stock Information']
        
        for i, stock_name in enumerate(stock_names): # adding information on which stock was used
            additional_stock_text = stock_name + ' ' + str(stock_canidate[i]) + ' ' + stock_units[i]
            stock_text.append(additional_stock_text) 
        
        # adding information of what resulted from using this specfic stock
        stock_text.append('Number of samples = ' + str(len(filtered_wtf_samples)))
        stock_text.append('Miniumum Sample Volume =' + str(min_sample_volume) + 'uL')
        stock_text.append('Maximum Sample Volume =' + str(min_sample_volume) + 'uL')
        stock_text_list.append(stock_text)
    
    prepare_stock_dict = {'stocks_wtf_lists': filtered_wtf_list, 
                          'stocks_volumes_lists': filtered_volumes_list, 
                          'stock_text_info': stock_text_list}
  
    return prepare_stock_dict




    
# when calculating volumes need to add "catchers" to allow user to be informed of why search/exe failed (not enough of component b, volume to small etc..)  
# In reality this should be called something like mixing with common solvents, but sure since other volume calculating function in place to deal with non common solvent mixing cases
def calculate_ouzo_volumes_from_wtf(sample_conc_df, experiment_csv_dict, stock_searching = False, stock_searching_concentration = None):
    """ This specfic volume function uses the stock concentration and sample concentration to calculate volumes for each stock to create a sample.
    For this case of Ouzo calculations, it is assumed the 2nd to last entry (in all things name, unit, concentration value) is the common solvent for all things prior to the second to last entry,
    while the final entry is assumed to be an indepedently added volume of a component. In the case of a typical emuslion the common sovlent is an alochol and the last completing component is water. 
    """ 
    
    total_sample_mass = experiment_csv_dict['Sample Amount']
    sample_unit = experiment_csv_dict['Sample Unit'] 
    assert sample_unit == 'g', 'Incorrect sample unit for wtf sample calculations, to calculate wtfs of components correctly a mass (grams) must be used. Check experiment plan CSV.'

    # component information, [component1, component2, component3...]
    component_names = experiment_csv_dict['Component Shorthand Names']
    component_units = experiment_csv_dict['Component Concentration Unit'] # never used? 
    component_densities = experiment_csv_dict['Component Density (g/mL)']
    component_mws = experiment_csv_dict['Component MW (g/mol)']
    
    stock_names = experiment_csv_dict['Stock Names']
    stock_concentrations_units = experiment_csv_dict['Stock Concentration Units']
    
    #stock_components_list = experiment_csv_dict['Stock Makeup (Component Wise)'] # could be useful future when automating mixing sequences 

    if stock_searching == True:
        stock_concentrations = stock_searching_concentration
    else: 
        stock_concentrations = experiment_csv_dict['Final Selected Stock Concentrations']
    

    #ensuring the df of sample names and units match
    check_components = [name + " " + unit for name, unit in zip(component_names, component_units)]
    assert check_components == list(sample_conc_df.columns), 'Component names and unit during sample concentration generation does not match the names and units for volume calulation.'
    sample_conc_canidates = sample_conc_df.values # ideally you would not be doing this and applying expessions to the columns, but since component volumes are dependent on each other...could create the whole and filter out negative values


    # From here, not generalized at all and very Ouzo case specfic. 
    good_solvent_index = experiment_csv_dict['Component Good Solvent Index (Only Ouzo)']-1 
    poor_solvent_index = experiment_csv_dict['Component Poor Solvent Index (Only Ouzo)']-1 

 
    all_sample_stock_volumes = []
    for sample in sample_conc_canidates: # sample refers to the sample component concentrations, since iterating order will match component_names
        total_good_solvent_wtf = sample[good_solvent_index]
        total_good_solvent_mass = total_sample_mass*total_good_solvent_wtf
        total_good_solvent_appx_volume = total_good_solvent_mass*ethanol_wtf_water_to_density(total_good_solvent_wtf) # in mL
        # the reason the total good solvent volume is needed is due to it being shared with other stocks needing to keep track of the volume used

        stock_volumes = [] # volume of each respective stock at the respective index
        component_volumes = [] # volume for shared component which in this case is a solvent
        
        for i, component_conc in enumerate(sample):
            component_stock_conc = stock_concentrations[i]
            if i not in (good_solvent_index, poor_solvent_index): # All components are suspended in the good solvent
                stock_unit = stock_concentrations_units[i]
                if  stock_unit == 'molarity': # currently only use case for lipids
                    component_mw = component_mws[i]
                    component_mass = component_conc*total_sample_mass
                    component_volume = 0
                    component_moles = component_mass/component_mw
                    component_stock_volume = component_moles*1000/component_stock_conc
                if stock_unit == 'wtf': # use case for everything except lipids and pure solvents
                    stock_density = experiment_csv_dict['Stock Appx Density (g/mL)'][i]
                    component_density = experiment_csv_dict['Component Density (g/mL)'][i]
                    component_mass = component_conc*total_sample_mass
                    component_volume = component_mass/component_density # lipids are assumed to have 0 volume, but must account for oil. 
                    component_volumes.append(component_volume)
                    component_stock_mass = component_mass/component_stock_conc
                    component_stock_volume = component_stock_mass/stock_density 
                stock_volumes.append(component_stock_volume)
                
            elif i == good_solvent_index and component_stock_conc == 1: # good solvent should always be pure to complete the compositional requirement before addition of poor solvent
                #print('sum', np.sum(component_volumes))
                good_solvent_volume_added = np.sum(stock_volumes)-np.sum(component_volumes) # is it possible for negative values?
                component_stock_volume = total_good_solvent_appx_volume - good_solvent_volume_added
                stock_volumes.append(component_stock_volume)

            elif i == poor_solvent_index and component_stock_conc == 1: # poor solvent always to be added last, but does not matter here only when using the results with OT2 volume
                stock_density = experiment_csv_dict['Stock Appx Density (g/mL)'][i]
                component_mass = component_conc*total_sample_mass
                component_stock_volume = component_mass/stock_density 
                stock_volumes.append(component_stock_volume)

            else: 
                print(i, len(sample), 'something went wrong')
        all_sample_stock_volumes.append((stock_volumes)) # still in mL
    all_sample_stock_volumes_ith_rearranged = np.asarray(rearrange_2D_list(all_sample_stock_volumes)) # may not be needed could just call as list comprehension in when making stock_dictionary


    ### Back to generalized

    stock_volumes_dict = {}
    for i in range(len(all_sample_stock_volumes_ith_rearranged)):
        stock_name = stock_names[i]
        stock_volumes_dict[stock_name] = all_sample_stock_volumes_ith_rearranged[i].ravel() # how to make this unit generalized
    stock_volumes_df = pd.DataFrame.from_dict(stock_volumes_dict) # incorperate this with the other df and instead of arrays make the inputs to functions dfs. 
    stock_volumes_df["Total Sample Volume"] = stock_volumes_df.sum(axis=1)
    stock_volumes_array = stock_volumes_df.values

    # here is where you can add logic for different units 
    unit = 'uL'
    stock_volumes_df = stock_volumes_df*1000
    unit_added_col_names = [stock_name + " " + unit for stock_name in stock_volumes_df.columns]
    stock_volumes_df.columns = unit_added_col_names
    
    return stock_volumes_df # output in uL



def total_volume_restriction_df(df, max_total_volume):
    column_names = df.columns
    total_column_name = [column_name for column_name in column_names if "Total Sample Volume" in column_name][0]
    df_unfiltered = df.copy()
    df = df[df[total_column_name] <= max_total_volume]
    if df.empty is True:
        raise AssertionError("No suitable samples available to create due to TOTAL SAMPLE VOLUME being too high, reconsider labware or total sample mass/volume", df_unfiltered[total_column_name])
    return df
 
def general_max_restriction(df, max_value, column_name):
    df_unfiltered = df.copy()
    df = df[df[column_name] <= max_value]
    if df.empty is True:
        raise AssertionError("No suitable samples available to create due to general filter being to low")
    return df

def pipette_volume_restriction_df(df, min_pipette_volume, max_pipette_volume, pipette_restriction_YN = False):
    column_names = df.columns
    stock_column_names = [column_name for column_name in column_names if "stock" in column_name]
    df_unfiltered = df.copy()
    
    for i, stock_column in enumerate(stock_column_names):
        df = df[df[stock_column] >= 0] # filtering all samples less than 0 
        if df.empty is True:
                raise AssertionError(stock_column + ' volumes contains only negative volumes. df series printed below', df_unfiltered[stock_column])

        df = df[(df[stock_column] >= min_pipette_volume) | (df[stock_column] == 0)] # filtering all samples that are less than miniumum pipette value and are NOT zero
        if df.empty is True:
            raise AssertionError(stock_column + ' volumes are below the pipette minimum of' + str(min_pipette_volume) + 'df series printed below', df_unfiltered[stock_column])

        if pipette_restriction_YN == False:
            df = df[df[stock_column] <= max_pipette_volume] # filtering for the max_volume of a pipette
            if df.empty is True:
                raise AssertionError(stock_column + ' volumes are above the pipette max of' + str(max_pipette_volume) + 'df series printed below', df_unfiltered[stock_column])

        if pipette_restriction_YN == len(stock_column_names):
            YN = pipette_restriction_YN[i]
            if YN == 'Y':
                df = df[df[stock_column] <= max_pipette_volume]
                if df.empty is True:
                    raise AssertionError(stock_column + ' volumes are above the pipette max of' + str(max_pipette_volume) + 'df series printed below', df_unfiltered[stock_column])            
     
    return df 



def ethanol_wtf_water_to_density(ethanol_wtf): # MOD 
    """Converts wtf of ethanol in a binary mixture with water to density using a polyfit of 4. The results are mainly used in the calculation of volume from a weight fraction. 
    UPDATE: need to cite or create potential user entry."""
    
    # Current information pulled from NIST T = @ 25C
    ethanol_wtfs = np.asarray([x for x in range(101)])/100
    ethanol_water_densities = np.asarray([0.99804, 0.99636, 0.99453, 0.99275, 0.99103, 0.98938, 0.9878, 0.98627, 0.98478 , 0.98331 , 0.98187, 0.98047, 0.9791, 0.97775, 0.97643, 0.97514, 0.97387, 0.97259, 0.97129, 0.96997, 0.96864, 0.96729, 0.96592, 0.96453, 0.96312, 0.96168, 0.9602, 0.95867, 0.9571, 0.95548, 0.95382, 0.95212, 0.95038, 0.9486, 0.94679 ,0.94494, 0.94306, 0.94114, 0.93919, 0.9372, 0.93518, 0.93314, 0.93107, 0.92897, 0.92685, 0.92472, 0.92257, 0.92041, 0.91823, 0.91604, 0.91384, 0.9116, 0.90936, 0.90711, 0.90485, 0.90258, 0.90031, 0.89803, 0.89574, 0.89344, 0.89113, 0.88882, 0.8865, 0.88417, 0.88183, 0.87948, 0.87713, 0.87477, 0.87241, 0.87004, 0.86766, 0.86527, 0.86287, 0.86047, 0.85806, 0.85564, 0.85322, 0.85079, 0.84835, 0.8459, 0.84344, 0.84096, 0.83848, 0.83599, 0.83348, 0.83095, 0.8284, 0.82583, 0.82323, 0.82062, 0.81797, 0.81529, 0.81257, 0.80983, 0.80705, 0.80424, 0.80138, 0.79846, 0.79547, 0.79243, 0.78934])   # another way is to use only wtf or state the molarity is calculated as sums of the volumes and not the final volume 
    coeffs = np.polyfit(ethanol_wtfs, ethanol_water_densities,4)
    fit = np.polyval(coeffs, ethanol_wtf)
    return fit
                

def calculate_stock_volumes(experiment_csv_dict, sample_volumes): # need to further generalize
    """Used to calculate stock volumes for a given experimental run"""
    rearranged_by_component_volumes = rearrange_2D_list(sample_volumes)
    summed_stock_volumes = [sum(stock_volumes) for stock_volumes in rearranged_by_component_volumes]
    stock_names = experiment_csv_dict['Stock Names']
    stock_concentrations = experiment_csv_dict['Final Selected Stock Concentrations']
    stock_units = experiment_csv_dict['Stock Concentration Units']
    
    
    for i in range(len(summed_stock_volumes)):
        string = str(summed_stock_volumes[i]/1000) + ' mL of ' + stock_names[i] + ' w/ conc of ' + str(stock_concentrations[i]) + ' ' + stock_units[i]
        print(string)
                   
def selected_down(array, lower_index, upper_index):
    array = array[lower_index:upper_index]
    return array

def create_csv(destination, info_list, wtf_samples, experiment_csv_dict):  
    """Creates a CSV which contains sample information in addition tieing a unique ID to the row of information. Each row in the created csv corresponds to one sample and the unique ID contains date and well information. Information is gathered from the printed commands of the OT2 either when executing or simulating. Given the type of execution in current code, this only supports the case of consecutive sample making (i.e. samples made in well order, with no skipping of wells)."""
    
    time = str(datetime.datetime.now(timezone('US/Pacific')).date()) # should be embaded once you run
    component_names = experiment_csv_dict['Component Shorthand Names']
    UID_header = ['UID']
    slot_header = ['Slot']
    labware_header = ['Labware']
    well_header =['Well']
    general_component_header = []
    experiment_component_header = []

    for i in range(len(component_names)):
        general_component_header.append('Component ' + str(i+1) + ' wtf')
        experiment_component_header.append(component_names[i] + ' wtf')

    complete_header = UID_header + general_component_header + slot_header + labware_header + well_header
    complete_experiment_header = UID_header + experiment_component_header + slot_header + labware_header + well_header


    wells = []
    labwares = []
    slots = []
    info_cut = info_list[0:len(wtf_samples)] #info only being used of length of number of samples
    for info in info_cut:
        str_info = str(info)
        spacing_index = []
        for i, letter in enumerate(str_info):
            if letter == ' ':
                spacing_index.append(i)
        well = str_info[0:spacing_index[0]]
        wells.append(well)
        labware = str_info[spacing_index[1]+1:spacing_index[8]]
        labwares.append(labware)
        slot = str_info[spacing_index[9]+1:]
        slots.append(slot)

    csv_entries = []
    ## Adding unique id and other information into one sublist to be fed as row into writer
    for component_wtfs, slot, labware, well in zip(wtf_samples, slots, labwares, wells):
        UID = time + "_" +experiment_csv_dict['Component Shorthand Names'][experiment_csv_dict['Component Graphing X Index']]+ "_" + experiment_csv_dict['Component Shorthand Names'][experiment_csv_dict['Component Graphing Y Index']] + "_" + well
        csv_entry = [UID] + component_wtfs.tolist() + [slot] + [labware] + [well]
        csv_entries.append(csv_entry)

    with open(destination, 'w', newline='',encoding='utf-8') as csvfile:
        csvwriter = csv.writer(csvfile, delimiter = ",")
        csvwriter.writerow(complete_header)
        csvwriter.writerow(complete_experiment_header) # so what 

        for row in csv_entries:
            csvwriter.writerow(row)

def rearrange_2D_list(nth_list):
    """Rearranges information from a 2D_list of length m with entries of length n to an outer array of length n, with entries of length m. Each entry now holds the ith entry of original entry in a new entry.
   [[a1,b1,c1],[a2,b2,c2]] => [[a1,a2],[b1,b2],[c1,c2]], making it easier to handle for cases like dataframes. 
 
    """
    list_rearranged = []
    for i in range(len(nth_list[0])): 
        ith_of_each_sublist = [sublist[i] for sublist in nth_list]
        list_rearranged.append(ith_of_each_sublist)
    return list_rearranged

def stock_molarity(total_volume, concentration, solute_mw, solute_density, solvent_density):
    """Calculates the mass of solutese and solvents for a stock solution with a given concentration given in terms of molarity.
    Currently only binary mixtures, will generalize by making solute dtypes list. 
    Volume = L, mw = g/mol, density = g/L."""
    
#     for solute_mw, solute_density, solute_conc # need to make conc a list argument
    print(total_volume*1000)
    solute_moles = concentration*total_volume # mol/L * L
    solute_mass = solute_moles*solute_mw # mol*(g/mol)
    
    if solute_density == 'Negligible':
        solute_volume = 0
    else: 
        solute_volume = solute_mass/solute_density # g/(g/L)
    
    solvent_volume = total_volume - solute_volume
    solvent_mass = solvent_volume*solvent_density
    
    return {'solute mass g': solute_mass,
           'solute volume L': solute_volume,
           'solvent mass g': solvent_mass,
           'solvent volume L': solvent_volume}    

def stock_wtf(total_mass, solute_wtf, solvent_wtf, solute_density, solvent_density):
    """Calculates the mass and volumes of solutes and solvents of stock solution with concentration in terms of wtf.
    Currently only binary mixtures, will generalize by making solute information list.
    Volume = L, mw = g/mol, density = g/L."""
    solute_mass = total_mass*solute_wtf # in g
    solvent_mass = total_mass*solvent_wtf
    
    solute_volume = solute_mass/solute_density # in L
    solvent_volume = solvent_mass/solvent_density
    
    return {'solute mass g': solute_mass,
           'solute volume L': solute_volume,
           'solvent mass g': solvent_mass,
           'solvent volume L': solvent_volume}

def stock_mgperml(total_volume, solute_wtf, solvent_wtf, solute_density, solvent_density):
    """Calculates the mass and volumes of solutes and solvents of stock solution with concentration in terms of mg/mL.
    Currently only binary mixtures, will generalize by making solute information list.
    Volume = L, mw = g/mol, density = g/L."""
    pass

def stock_volf(total_volume, solute_wtf, solvent_wtf, solute_density, solvent_density):
    """Calculates the mass and volumes of solutes and solvents of stock solution with concentration in terms of volf.
    Currently only binary mixtures, will generalize by making solute information list.
    Volume = L, mw = g/mol, density = g/L."""
    pass

def stock_molf(total_volume, solute_wtf, solvent_wtf, solute_density, solvent_density):
    """Calculates the mass and volumes of solutes and solvents of stock solution with concentration in terms of molf.
    Currently only binary mixtures, will generalize by making solute information list.
    Volume = L, mw = g/mol, density = g/L."""
    pass
    
def bimixture_density_wtf(comp1_wtf, comp1_density, comp2_density):
    """This is only to be used a very rough estimate if not density data is available for a binary mixture. 
    The information is useful in cases when calculating mass estimate for wtf calculation, since you need to convert a 
    total volume to mass, for purposes of stock making, which is compeltely valid since you just want to know roughly how much
    stock to create."""
    density = comp1_wtf*comp1_density + (1-comp1_wtf)*comp2_density
    return density

def stock_components(stock_name):
    """The stock name is required to be in the form 'solute n-solvent-stock' where the entry prior to the keyword stock are solvent
    and anything prior to that is assumed a solute. Will return a dictionary of the solvent and solute while pulling information from """
    stock_components = stock_name.split('-')
    stock_solutes = stock_components[:-2] # will always be a list
    stock_solvents = stock_components[-2]
    
    return stock_solutes, stock_solvents


def calculate_stock_prep_df(experiment_dict, volume_df, chem_database_path, buffer_pct = 10):
    
    # Isolate all stock volume entries in dataframe
    cols = volume_df.columns
    stock_cols = [col for col in cols if "stock" in col]
    stock_df = volume_df.copy()[stock_cols]
    
    # Compound volumes and add buffer
    stock_df.loc['Total Volume'] = stock_df.sum(numeric_only=True, axis=0)*(1+(buffer_pct/100))
    prep_df = pd.DataFrame(stock_df.loc['Total Volume']).T
    
    # Ensure all unit are same then convet to liters for calculations, latter is not 100% necessary
    check_unit_congruence(prep_df)
    prep_df = convert_to_liter(prep_df)
    
    # Add the concentration and respective units (may have this be arguments instead since only would be +1)
    prep_df.loc['Final Selected Stock Concentrations'] = experiment_dict['Final Selected Stock Concentrations']
    prep_df.loc['Stock Concentration Units'] = experiment_dict['Stock Concentration Units']
    
    chem_database_df = pd.read_excel(chem_database_path)
    
    prep_dicts = {}
    for stock in prep_df:
        total_volume = prep_df[stock]['Total Volume']
        stock_unit = prep_df[stock]['Stock Concentration Units']
        stock_conc = prep_df[stock]['Final Selected Stock Concentrations']
        solutes, solvent = stock_components(stock) # currently only one solvent and solute supported

        #All stocks will obvi have a solvent, but the solute is optional
        solvent_component_info = chem_database_df.loc[chem_database_df['Component Abbreviation'] == solvent]
        solvent_density = solvent_component_info['Density (g/L)'].iloc[0]

        if not solutes: # if no solutes present
            solute_mass = 0
            solute_volume = 0
            solvent_volume = total_volume
            solvent_mass = solvent_volume*solvent_density
            prep_dict = {'solute mass g': solute_mass,
               'solute volume L': solute_volume,
               'solvent mass g': solvent_mass,
               'solvent volume L': solvent_volume}

        if solutes: 
            solute = solutes[0]
            solute_component_info = chem_database_df.loc[chem_database_df['Component Abbreviation'] == solute] # add assertion to ensure component in database

            if stock_unit == 'molarity':
                solute_mw = solute_component_info['Molecular Weight (g/mol)'].iloc[0] # only call info if needed, if common between units then pull up one level
                solute_density = solute_component_info['Density (g/L)'].iloc[0]
                prep_dict = stock_molarity(total_volume, stock_conc, solute_mw, solute_density, solvent_density)

            if stock_unit == 'wtf':
                # since no density data available at the moment need to rough estimate, does not matter since the mass is scaled according to wtf, so long as more.
                solute_density = solute_component_info['Density (g/L)'].iloc[0]
                density_mix = bimixture_density_wtf(stock_conc, solute_density, solvent_density)
                total_mass = total_volume*density_mix
                prep_dict = stock_wtf(total_mass, stock_conc, 1-stock_conc, solute_density, solvent_density)
        prep_dicts[stock] = prep_dict
    stock_prep_df = pd.DataFrame.from_dict(prep_dicts) # add total volumes
    stock_complete_df = pd.concat([prep_df,stock_prep_df])
    return stock_prep_df

def isolate_common_column(df, common_string):
    cols = df.columns
    common_string_cols = [col for col in cols if common_string in col]
    final_df = df.copy()[common_string_cols]
    return final_df

################### FIX OR INTEGRATE ###########################################################

def add_blank_sample(sample_concs, sample_volumes, blank_total_volume, blank_component_concs):
    """Allows for the addition of a blank sample at the end of both the concentration and volume arrays that one has selected for experimentation, returns both modified arrays. Blank sample units and order of components are assumed to the same as those of other all other samples. Blank total volume left as non-csv-dependent input as this could change with the selected stock conidate/experiment conditions and is up to the user to decide which is the most appropiate.
    
    CSV Pulled Information: make it pulled but dont make it dependent on a wrapper - keep it indepdenent
    - blank_component_wtfs = 'Blank Component Concentrations (wtfs)' : an array of the concentration of the blank sample, which by default will be in the same units as the sample_wtfs. 
   """
    
    blank_component_volumes = []
    for component_composition in blank_component_concs:
        volume = component_composition*blank_total_volume
        blank_component_volumes.append(volume)
    blank_concs_array = np.asarray([blank_component_concs])
    blank_volume_array = np.asarray([blank_component_volumes])
    blank_and_sample_concs = np.concatenate((sample_concs, blank_concs_array))
    blank_and_sample_volumes = np.concatenate((sample_volumes, blank_volume_array))
    return blank_and_sample_concs, blank_and_sample_volumes
    
def calculate_stock_volumes_simple_volf_mix(sample_conc_canidates, experiment_csv_dict):
    total_sample_mass = experiment_csv_dict['Sample Mass (g)']
    component_names = experiment_csv_dict['Component Shorthand Names']
    component_units = experiment_csv_dict['Component Concentration Unit']
    component_densities = experiment_csv_dict['Component Density (g/mL)']
    component_mws = experiment_csv_dict['Component MW (g/mol)']
    component_sol_densities = experiment_csv_dict['Component Solution vol to wt density (g/mL)']
    stock_names = experiment_csv_dict['Stock Names']



def filter_samples(wtf_samples_canidates, volume_sample_canidates, min_vol, max_vol):
    """Filters samples based on volume restriction and matches up with previously created wtf sample canidates, 
    returning an updated list of wtf canidates AND volume canidates"""
    
    filtered_volumes = []
    filtered_wtf = []
    filtered_out = [] # optional just add an append in an else statement
    
    for sample_wtfs, sample_vols in zip(wtf_samples_canidates, volume_sample_canidates):
        if check_volumes(sample_vols, min_vol, max_vol) == True: # could say samples_vols[:-1], essentially two checks at once, check from sample_vols[:-1] if min_vol, max_vol =optional - change in funtion, and also if samples_vols[-1] 
            filtered_volumes.append(sample_vols)
            filtered_wtf.append(sample_wtfs)
    
    volume_checking_list = [sum(volume) for volume in filtered_volumes]
    min_sample_volume = min(volume_checking_list)
    max_sample_volume = max(volume_checking_list)
    

    return (filtered_wtf, filtered_volumes, min_sample_volume, max_sample_volume)
    


def experiment_sample_dict(experiment_plan_path, min_input_volume, max_input_volume): 
    """A wrapper for functions required to create ouzo samples, where final information is presented in returned dictionary. EXPLAIN THE WALKTHROUGH OF THIS STEP BY STEP ALLOWING SOMEONE TO FOLLOW  """
    experiment_plan_dict = get_experiment_plan(experiment_plan_path)
    wtf_sample_canidates = generate_candidate_lattice_concentrations(experiment_plan_dict)
    volume_sample_canidates = calculate_ouzo_volumes_from_wtf(wtf_sample_canidates, experiment_plan_dict)
    
    # now filter volume min no max for all but water, but min and max for water - but should not have to input volume should just be based on pipettes
    
    filtered_wtf_samples, filtered_volume_samples, min_sample_volume, max_sample_volume = filter_samples(wtf_sample_canidates, volume_sample_canidates, min_input_volume, max_input_volume)
    
    experiment_info_dict = {'experiment_plan_dict': experiment_plan_dict,
                           'wtf_sample_canidates': wtf_sample_canidates,
                           'volume_sample_canidates': volume_sample_canidates,
                           'filtered_wtf_samples': filtered_wtf_samples,
                           'filtered_volume_samples': filtered_volume_samples, 
                           'Minimum Sample volume (uL)': min_sample_volume, 
                           'Maximum Sample volume (uL)': max_sample_volume}
    return experiment_info_dict
