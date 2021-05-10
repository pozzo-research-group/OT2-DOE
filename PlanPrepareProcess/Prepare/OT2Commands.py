import glob
import os
import json
import opentrons.simulate as simulate

# All logic is based on api 2.2+ from opentrons, please read: https://docs.opentrons.com/OpentronsPythonAPIV2.pdf
# Keep in mind the following: All row based (while OT2 'default' is column based), all sequential (i.e sample 100 will be sample 4 in 96 well plate 2 of 2.) and many arugments are hardcoded to pull from a csv templete (hesistate to change template csv, can add but try not take away). 

#### Load in custom labware dictionry if necessary #####
def custom_labware_dict(labware_dir_path): 
    """Given the path of a folder of custom labware .json files will create dict
    of key = name and value = labware definition to be loaded using protocol.load_labware_from_definition 
    versus typical protocol.load_labware"""
    labware_dict = {}
    for file in glob.glob(labware_dir_path + '/**/*.json', recursive=True):
        with open(file) as labware_file:
            labware_name = os.path.splitext(file)[0] # removes the .json extnesion
            labware_def = json.load(labware_file)
            labware_dict[labware_name] = labware_def
    return labware_dict 


##### These next functions will help you create a labware dictionary which will contain all information tied to protocol object to run a protocol. The four main things are: source/destination labware, pipettes and tipracks #####
def object_to_object_list(protocol, stock_object_names, stock_object_slots):
    """Loads the labware specfied in the list arguments with the respective slots. This labware is tied 
    to the loaded protocol (global)."""
    
    labware_objects = [] # labware objects
    for labware_name, labware_slot in zip(stock_object_names, stock_object_slots):
        labware_object = protocol.load_labware(labware_name, labware_slot) # this is where the well information is being pulled from a OT2/added native library
        labware_objects.append(labware_object)
   
    return labware_objects

def object_list_to_well_list(labware_objects):
    """Labware list loaded is made into concatenated list of the all labwares
    in order of the object in the initally loaded list."""
    
    all_wells_row_order = [] 
    for labware in labware_objects:
        rows = [well for row in labware.rows() for well in row]
        all_wells_row_order = all_wells_row_order + rows
    
    return all_wells_row_order

def loading_labware(protocol, experiment_dict):
    """ Loads the required labware given information from a loaded csv dictionary. The labware, which
    include pipettes, plates and tipracks are tied to the protocol object argurment. Returned is a dcitonary 
    containing the important object instances to be used in subsequent functions alongside the original protocol instance."""
    
    protocol.home() 
      
    # Loading labwares: All concatenated list of wells in order of the provided name/slot
    
    dest_labware_names = experiment_dict['OT2 Destination Labwares']
    dest_labware_slots = experiment_dict['OT2 Destination Labware Slots']
    dest_labware_objects = object_to_object_list(protocol, dest_labware_names, dest_labware_slots)
    dest_wells = object_list_to_well_list(dest_labware_objects)
    
    stock_labware_names = experiment_dict['OT2 Stock Labwares']
    stock_labware_slots = experiment_dict['OT2 Stock Labware Slots']
    stock_labware_objects = object_to_object_list(protocol, stock_labware_names, stock_labware_slots)
    stock_wells = object_list_to_well_list(stock_labware_objects)
    
    # Loading pipettes and tipracks
    
    right_tiprack_names = experiment_dict['OT2 Right Tipracks']
    right_tiprack_slots = experiment_dict['OT2 Right Tiprack Slots']
    right_tipracks = object_to_object_list(protocol, right_tiprack_names, right_tiprack_slots)
    right_tiprack_wells = object_list_to_well_list(right_tipracks)

    right_pipette = protocol.load_instrument(experiment_dict['OT2 Right Pipette'], 'right', tip_racks = right_tipracks)
    right_pipette.flow_rate.aspirate = experiment_dict['OT2 Right Pipette Aspiration Rate (uL/sec)']
    right_pipette.flow_rate.dispense = experiment_dict['OT2 Right Pipette Dispense Rate (uL/sec)']    
    right_pipette.well_bottom_clearance.dispense = experiment_dict['OT2 Bottom Dispensing Clearance (mm)']

    left_tiprack_names = experiment_dict['OT2 Left Tipracks']
    left_tiprack_slots = experiment_dict['OT2 Left Tiprack Slots']
    left_tipracks = object_to_object_list(protocol, left_tiprack_names, left_tiprack_slots)
    left_tiprack_wells = object_list_to_well_list(left_tipracks)

    
    left_pipette = protocol.load_instrument(experiment_dict['OT2 Left Pipette'], 'left', tip_racks = left_tipracks) # is there a way to ensure the correct tiprack is laoded? maybe simple simualtion test a function
    left_pipette.flow_rate.aspirate = experiment_dict['OT2 Left Pipette Aspiration Rate (uL/sec)']
    left_pipette.flow_rate.dispense = experiment_dict['OT2 Left Pipette Dispense Rate (uL/sec)']   
    left_pipette.well_bottom_clearance.dispense = experiment_dict['OT2 Bottom Dispensing Clearance (mm)']
    
    loaded_labware_dict = {'Destination Wells': dest_wells, 
                           'Stock Wells': stock_wells,
                           'Left Pipette': left_pipette,
                           'Left Tiprack Wells': left_tiprack_wells,
                           'Right Pipette': right_pipette,
                           'Right Tiprack Wells': right_tiprack_wells
                           }

    loaded_labware_dict = determine_pipette_resolution(loaded_labware_dict)
    
    return loaded_labware_dict

def stock_well_ranges(volume_df, loaded_dict, limit):
    """Given a dataframe of stocks volumes to pipette, will return the ranges of indexes for the volumes
    seperated in such a way to satisfy the volume limitation of current stock labware. Ranges of the indexes are 
    provide in a 2D list with each entry consisting of a lower and a upper_well_index index. 
    A stock is identified by having the term stock or Stock in its df column.
    Note: dataframe/series indexing is a little different than list indexing """
    
    # will only require protocol if you want to call the 
    col_names = [name for name in volume_df.columns if "stock" in name]
    stock_info_to_pull = {}
    
    for col_name in col_names:
        series = volume_df[col_name]
        series_cs = series.cumsum()
        multiplier = 1
        range_list = [0]
        for index, entry in enumerate(series_cs):
            limit_m = limit*multiplier
            if entry>limit_m:
                multiplier = multiplier + 1
                range_list.append(index) # doubled on purpose
                range_list.append(index)
        range_list.append(len(series_cs))
        range_list_2D = [range_list[i:i+2] for i in range(0, len(range_list), 2)]
        stock_info_to_pull[col_name]= {'Ranges':range_list_2D}

    
    
    # Now let us add the information of stock position  
    stock_labware_wells = loaded_dict['Stock Wells']
    stock_position_index = 0
    for col in col_names:
        add_positions_dict = stock_info_to_pull[col]
        ranges = add_positions_dict['Ranges']
        stock_wells_to_pull = []
        for r in ranges:
            stock_well = stock_labware_wells[stock_position_index]
            stock_wells_to_pull.append(stock_well)
            stock_position_index += 1
        add_positions_dict['Stock Wells'] = stock_wells_to_pull
 
    return stock_info_to_pull

def create_sample_making_directions(volume_df, stock_position_info, loaded_labware_dict):    
    volume_df = isolate_common_column(volume_df, 'stock')
    destination_wells = loaded_labware_dict['Destination Wells']
    stock_wells = loaded_labware_dict['Stock Wells'] # might not be needed
    
    # checking if labware and pipette is appropiate before moving forward
    labware_check_enough_wells(volume_df, loaded_labware_dict)
    labware_check_enough_volume(volume_df, loaded_labware_dict)
    pipette_check(volume_df, loaded_labware_dict['Left Pipette'], loaded_labware_dict['Right Pipette'])

    sample_making_dict = {}
    for i, row in volume_df.iterrows():
        single_sample_stock_volumes = row
        well_index = i # same as sample index  # could add sample + i 
        destination_well = destination_wells[well_index]
        sample_making_dict[i] = {}
        single_sample_dict = sample_making_dict[i]
        
        for stock_index, column_name in enumerate(volume_df.columns): 
            stock_name = column_name
            single_sample_dict[stock_name] = {}
            single_stock_direction_entry = single_sample_dict[stock_name]
            stock_volume_to_pull = single_sample_stock_volumes[stock_name]
            stock_position = find_stock_to_pull(stock_name, well_index, stock_position_info)

            single_stock_direction_entry['Stock Position'] = stock_position
            single_stock_direction_entry['Destination Well Position'] = destination_well
            single_stock_direction_entry['Stock Volume'] = stock_volume_to_pull

    return sample_making_dict

def determine_pipette_tiprack(volume, small_pipette, large_pipette, small_tiprack=None, large_tiprack=None): 
    if small_pipette.min_volume <= volume <= small_pipette.max_volume or volume == 0:
        pipette = small_pipette
        if small_tiprack:
            tiprack = small_tiprack
            return pipette, tiprack
    elif large_pipette.min_volume <= volume:
        pipette = large_pipette   
        if large_tiprack:   
            tiprack = large_tiprack
            return pipette, tiprack

    else:
        raise AssertionError('Volumes not suitable for pipettes') # but is that so? 
    return pipette

def determine_pipette_resolution(loaded_labware_dict):
    """Given the opentrons only uses two pipettes one as always designated as a small or large pipette to ensure a wide range 
    of volumes is covered. We designate one as small and one as large to ensure we are using the highest precision possible"""
    
    left_pipette = loaded_labware_dict['Left Pipette']
    left_tiprack = loaded_labware_dict['Left Tiprack Wells']
    right_pipette= loaded_labware_dict['Right Pipette']
    right_tiprack = loaded_labware_dict['Right Tiprack Wells']


    if left_pipette.max_volume < right_pipette.max_volume:
        small_pipette = left_pipette 
        small_tiprack = left_tiprack
        large_pipette = right_pipette
        large_tiprack = right_tiprack

    if left_pipette.max_volume > right_pipette.max_volume:
        small_pipette = right_pipette
        small_tiprack = right_tiprack
        large_pipette = left_pipette
        large_tiprack = left_tiprack

    loaded_labware_dict['Small Pipette'] = small_pipette
    loaded_labware_dict['Large Pipette'] = large_pipette
    loaded_labware_dict['Small Tiprack'] = small_tiprack
    loaded_labware_dict['Large Tiprack'] = large_tiprack

    return loaded_labware_dict


def find_stock_to_pull(stock_name, well_index, stocks_position_dict): # could generalize and could work for pipette tips
    stock_position_info = stocks_position_dict[stock_name]
    well_ranges = stock_position_info['Ranges']
    stock_positions = stock_position_info['Stock Wells']
    
    for stock_position, well_range in zip(stock_positions, well_ranges): 
        if well_range[0] <= well_index <= well_range[1]: # so even though potentially two true results the first one always wins beceause list of ranges in order, see if you can make it so only one true result exist
            return stock_position
    else:
        raise AssertionError('Well is not covered by current stock, please verify stock well ranges.')


def pipette_volumes_sample_wise(protocol, directions, loaded_labware_dict):    
    protocol.home()
    small_pipette = loaded_labware_dict['Small Pipette']
    small_tiprack = loaded_labware_dict['Small Tiprack']
    large_pipette = loaded_labware_dict['Large Pipette']
    large_tiprack = loaded_labware_dict['Large Tiprack']
    
    for sample_index, stock_instruction in directions.items():
        for stock_index, (stock_name, single_stock_instructions) in enumerate(stock_instruction.items()):
            stock_volume_to_pull = single_stock_instructions['Stock Volume']
            stock_position_to_pull = single_stock_instructions['Stock Position']
            destination_well = single_stock_instructions['Destination Well Position']

            # Now the three pieces of info available volume, destination, source.
            
            pipette, tiprack_wells = determine_pipette_tiprack(stock_volume_to_pull, small_pipette, large_pipette, small_tiprack, large_tiprack)
            pipette.pick_up_tip(tiprack_wells[stock_index])
            pipette.transfer(stock_volume_to_pull, stock_position_to_pull, destination_well, new_tip='never', air_gap=20)
            protocol.delay(seconds=5)
            pipette.return_tip()

    for line in protocol.commands(): 
        print(line)  

def pipette_volumes_component_wise(protocol, directions, loaded_labware_dict, stock_to_pipette_order=None):    
    protocol.home()
    small_pipette = loaded_labware_dict['Small Pipette']
    small_tiprack = loaded_labware_dict['Small Tiprack']
    large_pipette = loaded_labware_dict['Large Pipette']
    large_tiprack = loaded_labware_dict['Large Tiprack']
    
    if stock_to_pipette_order is None:
        stock_to_pipette_order = directions[0].keys()
    
    for stock_name in stock_to_pipette_order:
        small_pipette.pick_up_tip()
        large_pipette.pick_up_tip()
        for stock_index, stock_instructions in directions.items():
            single_stock_instructions = stock_instructions[stock_name]
            stock_volume_to_pull = single_stock_instructions['Stock Volume']
            stock_position_to_pull = single_stock_instructions['Stock Position']
            destination_well = single_stock_instructions['Destination Well Position']

            if small_pipette.min_volume <= stock_volume_to_pull <= small_pipette.max_volume or stock_volume_to_pull==0:
                pipette = small_pipette
            elif large_pipette.min_volume <= stock_volume_to_pull:
                pipette = large_pipette
            else: 
                raise AssertionError('Pipettes not suitable for volume', stock_volume_to_pull)
            pipette.transfer(stock_volume_to_pull, stock_position_to_pull, destination_well, new_tip='never', air_gap=20)
            protocol.delay(seconds=3)
        small_pipette.return_tip()
        large_pipette.return_tip()
    for line in protocol.commands(): 
        print(line)  


def transfer_from_destination_to_final(protocol, loaded_labware_dict, experiment_dict, number_of_samples):
    """This function will take the already loaded dictionary and load more labware, specfically made for a final transfer from the destination sample plates to another plate. 
    The reaason for this final transfer is to allow samples to be made at any volume or at least a close enough volume and then moved to a secondary plate to be analyzed at the sample 
    quantity (important for things like path lengths). This could theoretically be used independently from an initial sample creation, would just need to initialize the loading of labware. 
    The reason why this could be useful is because the deck is limited in space so creating the samples and having their final transfer labware all on the deck at the same time could pose a constraint, 
    however unlikely as typically you will be transfering into a smaller vessel with more wells than the original synthesis vessel."""
    
    dest_wells = loaded_labware_dict['Destination Wells']
    stock_wells = loaded_labware_dict['Stock Wells']
    small_pipette = loaded_labware_dict['Small Pipette']
    large_pipette = loaded_labware_dict['Large Pipette']
 

    # Loading the final transfer labware

    final_transfer_plate_names = experiment_dict['OT2 Single Transfer From Dest Labwares']
    final_transfer_plate_slots = experiment_dict['OT2 Single Transfer From Dest Slots']
    
    final_transfer_plates_objects = object_to_object_list(protocol, final_transfer_plate_names , final_transfer_plate_slots)
    final_transfer_wells = object_list_to_well_list(final_transfer_plates_objects) 
    transfer_volume = float(experiment_dict['OT2 Single Transfer From Dest Volume (uL)'])

    assert len(final_transfer_wells) >= number_of_samples, 'The number of samples is exceeds the number of final destination wells'

    pipette = determine_pipette_tiprack(transfer_volume, small_pipette, large_pipette)
        
    pipette.flow_rate.aspirate = experiment_dict['OT2 Single Transfer Pipette Aspiration Rate (uL/sec)']
    pipette.flow_rate.dispense = experiment_dict['OT2 Single Transfer Pipette Dispense Rate (uL/sec)']
    pipette.well_bottom_clearance.dispense = experiment_dict['OT2 Single Transfer From Dest Bottom Dispensing Clearance (mm)']
    pipette.well_bottom_clearance.aspirate = experiment_dict['OT2 Single Transfer From Dest Bottom Aspirating Clearance (mm)']

    sample_final_location = []
    
    for well_index in range(number_of_samples):
        pipette.transfer(transfer_volume, dest_wells[well_index], final_transfer_wells[well_index], new_tip = 'always') 
        sample_final_location.append(final_transfer_wells[well_index])
    for line in protocol.commands(): 
        print(line)
    return sample_final_location




def rearrange_2D_list(nth_list):
    """Rearranges information from a 2D_list of length m with entries of length n to an outer array of length n, with entries of length m. Each entry now holds the ith entry of original entry in a new entry.
   [[a1,b1,c1],[a2,b2,c2]] => [[a1,a2],[b1,b2],[c1,c2]], making it easier to handle for cases like dataframes. 
 
    """
    list_rearranged = []
    for i in range(len(nth_list[0])): 
        ith_of_each_sublist = [sublist[i] for sublist in nth_list]
        list_rearranged.append(ith_of_each_sublist)
    return list_rearranged

def check_for_distribute(list1, min_val, max_val): 
    return(all(max_val >= x >= min_val or x == 0 for x in list1)) 

def pipette_check(volume_df, pipette_1, pipette_2):
    """Given volumes along with two pipettes in use, will ensure the volumes of the pipette ranges are able to be cover the volumes"""
    volume_df = isolate_common_column(volume_df, 'stock')
    if pipette_1.max_volume < pipette_2.max_volume:
        small_pipette = pipette_1
        large_pipette = pipette_2

    if pipette_1.max_volume > pipette_2.max_volume:
        small_pipette = pipette
        large_pipette = pipette_1
    assert volume_df[(volume_df == 0)| (volume_df >= small_pipette.min_volume)].notnull().all().all(), 'Pipettes do not cover appropiate volume ranges'

def labware_check_enough_wells(volumes, loaded_labware_dict):
    """Will check prior to simulation if labware is appropiate in terms of total volume and if enough wells are available. 
    Volumes to be in dataframe. Assumes all of destination labware are the same."""

    destination_wells = loaded_labware_dict['Destination Wells']
    assert len(destination_wells) >= len(volumes), 'There is not enough wells available to make ' + str(len(volumes)) + ' samples. There are only ' + str(len(destination_wells)) + ' wells available.'

def labware_check_enough_volume(volumes_df, loaded_labware_dict):
    """Will check prior to simulation if labware is appropiate in terms of total volume and if enough wells are available. 
    Volumes to be in dataframe. Assumes all of destination labware are the same."""

    destination_wells = loaded_labware_dict['Destination Wells']
    well = str(destination_wells[0])
    well_volume = float(determine_well_volume(well))
    total_sample_volumes = volumes_df.sum(axis=1)

    assert (total_sample_volumes < well_volume).all(), 'Sample volumes are exceeding max destination well volume of ' + str(well_volume) + 'uL'

def determine_well_volume(well):
    well_volume = well.split(' ')[-4]
    return well_volume


def isolate_common_column(df, common_string):
    cols = df.columns
    common_string_cols = [col for col in cols if common_string in col]
    final_df = df.copy()[common_string_cols]
    return final_df
###################################### Require Further Testing ###################################################################################




def range_gap(small_pipette, pipette_2):
    if p1_max >= p2_min:
        print('Pipette range complete')
    else: 
        print('Pipette Range Incomplete, gap exist between following volumes:', p1_max, 'and', p2_min)


# so the small_pipette max should be within or at least at the edge of the large_pipette_min, and



def find_max_dest_volume_labware(experiment_csv_dict, custom_labware_dict=None): # can i just simulate hardcode , custom_labware_dict
    """Using the stock labware name from the csv, loads the appropiate labware from both 
    a custom and the native libary and determines the maximum volume for one stock labware well. Assumes all labware is all identical."""
    if custom_labware_dict: # Protocol encapsulated as only need an instance to simualte and toss
        protocol = simulate.get_protocol_api('2.0', extra_labware=custom_labware_dict) # encapsulated as only need an instance to simualte and toss
    else: 
        protocol = simulate.get_protocol_api('2.0') 
    stock_plate = protocol.load_labware(experiment_csv_dict['OT2 Destination Labwares'][0], experiment_csv_dict['OT2 Destination Labware Slots'][0])
    stock_plate_rows = [well for row in stock_plate.rows() for well in row]
    stock_plate_well_volume = stock_plate.__dict__['_well_definition']['A1']['totalLiquidVolume'] 
    return stock_plate_well_volume

def find_max_stock_volume_labware(experiment_csv_dict, custom_labware_dict=None): # can i just simulate hardcode , custom_labware_dict
    """Using the stock labware name from the csv, loads the appropiate labware from both 
    a custom and the native libary and determines the maximum volume for one stock labware well. Assumes all labware is all identical."""
    if custom_labware_dict: # Protocol encapsulated as only need an instance to simualte and toss
        protocol = simulate.get_protocol_api('2.0', extra_labware=custom_labware_dict) # encapsulated as only need an instance to simualte and toss
    else: 
        protocol = simulate.get_protocol_api('2.0') 
    stock_plate = protocol.load_labware(experiment_csv_dict['OT2 Stock Labwares'][0], experiment_csv_dict['OT2 Stock Labware Slots'][0])
    stock_plate_rows = [well for row in stock_plate.rows() for well in row]
    stock_plate_well_volume = stock_plate.__dict__['_well_definition']['A1']['totalLiquidVolume'] 
    return stock_plate_well_volume



######################################### NO LONGER IN USE DOCUMENT OR DELETE #####################################################################
def pipette_volumes_component_wise_broken(protocol, loaded_dict, stock_volumes_df, stock_ranges):
    """ Given the protocol used to set up the loaded labware dict, along with the volumes to pipette will send transfer commands to the ot2.
    The volumes fed as a 2D list where each sublist is the the volumes for one stock. Ranges are fed similar """
    
    dest_wells = loaded_dict['Destination Wells']
    stock_wells = loaded_dict['Stock Wells']
    left_pipette = loaded_dict['Left Pipette']
    right_pipette = loaded_dict['Right Pipette']

    # Label pipettes to know which is ideal, higher resolution always desired (i.e smaller pipette if allowable), this might become its own function
    if left_pipette.max_volume < right_pipette.max_volume:
        small_pipette = left_pipette 
        large_pipette = right_pipette

    if left_pipette.max_volume > right_pipette.max_volume:
        small_pipette = right_pipette
        large_pipette = left_pipette

    
    ## function to check prior if volumes are inbetween .min/max_volume and pipettes are appropiate
    stock_volumes = rearrange_2D_list(stock_volumes_df.values) # change so it grabs per column and not have to use this function
    info_list = []
    stock_well_index = 0 # quick fix since need to move to next everytime a range is called, could reorganize but will do it later
    for stock_tracker, (stock_volume, stock_range) in enumerate(zip(stock_volumes, stock_ranges)): # each iteration is one stock but it is not one stock position
        complete_volumes_of_one_stock = stock_volume
        for well_range in stock_range:
            lower_well_index = well_range[0]
            upper_well_index = well_range[1]
            wells_to_dispense = dest_wells[lower_well_index:upper_well_index]
            volumes_to_pipette = complete_volumes_of_one_stock[lower_well_index:upper_well_index]
            
            stock_to_pull = stock_wells[stock_well_index] # will just stick to one need to add and move on
            stock_well_index = stock_well_index+1 # so now next time we assign a stock to pull it will be one higher than the next
            

            # First initialize pipette and pickup tip, by checking the small pipette first, resolution is ideal
            initial_volume = volumes_to_pipette[0]
            if small_pipette.min_volume <= initial_volume <= small_pipette.max_volume or initial_volume == 0:
                pipette = small_pipette
            elif large_pipette.min_volume <= initial_volume <= large_pipette.max_volume:
                pipette = large_pipette        
                
            pipette.pick_up_tip() # verify whether this is running on 2.1 vs 2.2 logic 
            
            # here is where you do conditionals like if all within this range then just use distribbute
            if check_for_distribute(volumes_to_pipette, pipette.min_volume, pipette.max_volume) == True: # the issue with this it might be very wasteful and require more stock since buffers, we already delt with ranges so we should be good on that
               pipette.distribute(volumes_to_pipette, stock_to_pull, dest_wells[lower_well_index:upper_well_index], new_tip = 'never')
              
            else:
                for well_to_dispense, volume in zip(wells_to_dispense, volumes_to_pipette):
                    # nonswitching cases
                    if (small_pipette.min_volume <= volume <= small_pipette.max_volume or volume==0) and pipette == small_pipette:
                        pipette.transfer(volume, stock_to_pull, well_to_dispense, new_tip = 'never') 

                    elif (large_pipette.min_volume < volume) and pipette == large_pipette: # only greater than as we can do larger transfer in splits, if you only want to add once, should fil
                        pipette.transfer(volume, stock_to_pull, well_to_dispense, new_tip = 'never')

                    # switching cases
                    elif (small_pipette.min_volume <= volume <= small_pipette.max_volume or volume==0) and pipette == large_pipette:
                        pipette.return_tip()
                        pipette = small_pipette
                        pipette.pick_up_tip()
                        pipette.transfer(volume, stock_to_pull, well_to_dispense, new_tip = 'never')

                    elif (large_pipette.min_volume < volume) and pipette == small_pipette: # only greater than as we can do larger transfer in splits
                        pipette.return_tip()
                        pipette = large_pipette
                        pipette.pick_up_tip()
                        pipette.transfer(volume, stock_to_pull, well_to_dispense, new_tip = 'never')

            info = wells_to_dispense
            info_list.append(info)
            pipette.drop_tip()
    for line in protocol.commands(): # Remember that this command prints all of the previous stuff with it so if in a loop will print the whole history
        print(line)     
    return info_list[0]



def create_samples(protocol, experiment_dict, sample_volumes, transfer = False, custom_labware_dict = {}):
    """NO LONGER IN USE
    
    A function which uses a protocol object from the OT2 API V2 module which along with calculated and rearranged volumes
    will produce commands for the OT2. Additionally, information regarding the wells, slot and labware in use will be returned 
    for use in information storage. Volume argument must be rearranged component wise (i.e. a total of n component lists should be fed). 
    Volumes will be compared to available pipette's volume restriction and will be selected to optimize the number of commands. 
    Returning of pipette tips is built in for when pipettes needs to be switched but will eventually switch back. """
    
    ### Initializing run according to API ###
    
    api_level = '2.0'
    
    metadata = {
    'protocolName': experiment_dict['Protocol Version'],
    'author': experiment_dict['Experimenter'],
    'description': experiment_dict['Project Tag'],
    'apiLevel': api_level}

    protocol.home()

    ### Setting up destination plates (sample plates) ### make a module out of this for use with any list of labware
    
    dest_plate_names = experiment_dict['OT2 Destination Labwares']
    dest_plate_slots = experiment_dict['OT2 Destination Labware Slots']
    dest_wells_row_order = stock_object_to_well_list(protocol, dest_plate_names, dest_plate_slots)


    # checks like this might be better out as there own function or method - makes it cleaner and easier to follow code
    # call function enough_wells, volume_check, stock_volume_check, etc...

    if len(sample_volumes)>len(dest_wells_row_order):
        needed_wells = str(len(sample_volumes) - len(dest_wells_row_order))
        raise ValueError('Too many samples for given destination plates, need ' + needed_wells + ' more wells') 
           
    ### Reordering sample list into component wise list to iterate over for pipetting [[1,2,3],[1,2,3]] => [[1,1], [2,2], [3,3]] ###
    
    stock_volumes_lists = [] 
    for i in range(len(sample_volumes[0])): 
        component_volumes = []
        for sample in sample_volumes:
            component_volume = sample[i]
            component_volumes.append(component_volume)
        stock_volumes_lists.append(component_volumes)
        
    ### Setting up tipracks and pipette labware ### 
    
    right_tiprack_names = experiment_dict['OT2 Right Tipracks']
    right_tiprack_slots = experiment_dict['OT2 Right Tiprack Slots']
    
    left_tiprack_names = experiment_dict['OT2 Left Tipracks']
    left_tiprack_slots = experiment_dict['OT2 Left Tiprack Slots']
    
    right_tipracks = []
    for name, slot in zip(right_tiprack_names, right_tiprack_slots):
        right_tiprack_i = custom_or_native_labware(protocol, name, slot, custom_labware_dict)
        right_tipracks.append(right_tiprack_i)
            
    left_tipracks = []
    for name, slot in zip(left_tiprack_names, left_tiprack_slots):
        left_tiprack_i = custom_or_native_labware(protocol, name, slot, custom_labware_dict)
        (name, slot)
        left_tipracks.append(left_tiprack_i)

    right_pipette = protocol.load_instrument(experiment_dict['OT2 Right Pipette'], 'right', tip_racks = right_tipracks)
    right_pipette.flow_rate.aspirate = experiment_dict['OT2 Right Pipette Aspiration Rate (uL/sec)']
    right_pipette.flow_rate.dispense = experiment_dict['OT2 Right Pipette Dispense Rate (uL/sec)']    
    right_pipette.well_bottom_clearance.dispense = experiment_dict['OT2 Bottom Dispensing Clearance (mm)'] 

    left_pipette = protocol.load_instrument(experiment_dict['OT2 Left Pipette'], 'left', tip_racks = left_tipracks)
    left_pipette.flow_rate.aspirate = experiment_dict['OT2 Left Pipette Aspiration Rate (uL/sec)']
    left_pipette.flow_rate.dispense = experiment_dict['OT2 Left Pipette Dispense Rate (uL/sec)']   
    left_pipette.well_bottom_clearance.dispense = experiment_dict['OT2 Bottom Dispensing Clearance (mm)']
    
    ### Deciding pipette ordering for upcoming logic based commands, which require pipette_1 = lower volume constrained pipette ### 
    
    if left_pipette.max_volume < right_pipette.max_volume:
        pipette_1 = left_pipette 
        pipette_2 = right_pipette
        
    if left_pipette.max_volume > right_pipette.max_volume:
        pipette_1 = right_pipette 
        pipette_2 = left_pipette
    stock_labware_names = experiment_dict['OT2 Stock Labwares']
    stock_labware_slots = experiment_dict['OT2 Stock Labware Slots'],
    stock_plate_rows = stock_object_to_well_list(protocol, stock_labware_names, stock_labware_slots)
    
    ### here is the actual pipetting

    info_list = []
    for stock_index, stock_volumes in enumerate(stock_volumes_lists):
        
        if stock_volumes[0] <= pipette_1.max_volume: #initializing pipette for first stock volume in list of stock volumes
            pipette = pipette_1

        elif stock_volumes[0] > pipette_1.max_volume: #initializing pipette with tip for a component
            pipette = pipette_2
        
        pipette.pick_up_tip()
        
        for well_index, volume in enumerate(stock_volumes):
            info = dest_wells_row_order[well_index]
            info_list.append(info)
            if volume<pipette_1.max_volume and pipette == pipette_1:
                pipette.transfer(volume, stock_plate_rows[stock_index], dest_wells_row_order[well_index], new_tip = 'never') 

            elif volume>pipette_1.max_volume and pipette == pipette_2:
                pipette.transfer(volume, stock_plate_rows[stock_index], dest_wells_row_order[well_index], new_tip = 'never')

            elif volume<pipette_1.max_volume and pipette == pipette_2:
                pipette.return_tip()
                pipette = pipette_1
                pipette.pick_up_tip()
                pipette.transfer(volume, stock_plate_rows[stock_index], dest_wells_row_order[well_index], new_tip = 'never')

            elif volume>pipette_1.max_volume and pipette == pipette_1: 
                pipette.return_tip()
                pipette = pipette_2
                pipette.pick_up_tip()
                pipette.transfer(volume, stock_plate_rows[stock_index], dest_wells_row_order[well_index], new_tip = 'never')
        pipette.drop_tip()




    ### Transfer as an optional last step from sample/dest plate to another plate ### 
    
    if transfer == True:
        
        transfer_volume = experiment_dict['OT2 Dependent Transfer Volume (uL)']
        transfer_dest_labware_names = experiment_dict['OT2 Dependent Transfer Dest Labwares']
        transfer_dest_labware_slots = experiment_dict['OT2 Dependent Transfer Dest Slots']

        # Setting up list of trasnfer destination labwares in order to create final row ordered list of labware wells
        transfer_dest_labwares = []
        for name, slot in zip(transfer_dest_labware_names, transfer_dest_labware_slots):
            transfer_dest_labware = custom_or_native_labware(protocol, name, slot, custom_labware_dict)
            transfer_dest_labwares.append(transfer_dest_labware)
        
        transfer_dest_wells = []
        for dest_labware in transfer_dest_labwares:
            rows = [well for row in dest_labware.rows() for well in row]
            transfer_dest_wells = transfer_dest_wells + rows
            
        if len(transfer_dest_wells) < len(sample_volumes):
            raise ValueError('Not enough wells for final transfer, missing ' + str(len(sample_volumes)-len(transfer_dest_wells)) + ' number of wells')

        if pipette_1.min_volume <= transfer_volume <= pipette_1.max_volume: # allows for best specficity since higher res on volume constrained pipette
            pipette = pipette_1
    
        elif pipette_2.min_volume < transfer_volume < pipette_2.max_volume:
            pipette = pipette_2
        
        for well_index in range(len(sample_volumes)):
            pipette.transfer(transfer_volume, dest_wells_row_order[well_index], transfer_dest_wells[well_index])
                             
    for line in protocol.commands():
        print(line)
    
    return {'command info': info_list} # left as dictionary as will be able to extract more useful information in the future 

def simple_independent_transfer(protocol, experiment_dict):
    """Simple transfer protocol only referenced when wanting to transfer from plate to plate. Functional with list of plates as 
    well as single plate to plates. Remember to restart with different protocol as everything is to be reinitiliazed """
    
        ### Setting up tipracks and pipette labware ### 
    
    right_tiprack_names = experiment_dict['OT2 Right Tipracks']
    right_tiprack_slots = experiment_dict['OT2 Right Tiprack Slots']
    
    left_tiprack_names = experiment_dict['OT2 Left Tipracks']
    left_tiprack_slots = experiment_dict['OT2 Left Tiprack Slots']
    
    right_tipracks = []
    for name, slot in zip(right_tiprack_names, right_tiprack_slots):
        right_tiprack_i = custom_or_native_labware(protocol, name, slot, custom_labware_dict) 
        right_tipracks.append(right_tiprack_i)
            
    left_tipracks = []
    for name, slot in zip(left_tiprack_names, left_tiprack_slots):
        left_tiprack_i = custom_or_native_labware(protocol, name, slot, custom_labware_dict)
        left_tipracks.append(left_tiprack_i)

    right_pipette = protocol.load_instrument(experiment_dict['OT2 Right Pipette'], 'right', tip_racks = right_tipracks)    
    right_pipette.well_bottom_clearance.dispense = experiment_dict['OT2 Bottom Dispensing Clearance (mm)'] 

    left_pipette = protocol.load_instrument(experiment_dict['OT2 Left Pipette'], 'left', tip_racks = left_tipracks)
    left_pipette.well_bottom_clearance.dispense = experiment_dict['OT2 Bottom Dispensing Clearance (mm)']
    
    
    ### Deciding pipette ordering for upcoming logic based commands, which require pipette_1 = lower volume constrained pipette ### 
    
    if left_pipette.max_volume < right_pipette.max_volume:
        pipette_1 = left_pipette 
        pipette_2 = right_pipette
        
    if left_pipette.max_volume > right_pipette.max_volume:
        pipette_1 = right_pipette 
        pipette_2 = left_pipette
    
    transfer_volume = experiment_dict['OT2 Independent Transfer Volume (uL)']
    
    transfer_source_labware_names = experiment_dict['OT2 Independent Transfer Source Labwares']
    transfer_source_labware_slots = experiment_dict['OT2 Independent Transfer Source Slots']
    
    transfer_dest_labware_names = experiment_dict['OT2 Independent Transfer Dest Labwares']
    transfer_dest_labware_slots = experiment_dict['OT2 Independent Transfer Dest Slots']
    
    transfer_source_labwares = []
    for name, slot in zip(transfer_source_labware_names, transfer_source_labware_slots):
        transfer_source_labware = custom_or_native_labware(protocol, name, slot, custom_labware_dict)
        transfer_source_labwares.append(transfer_source_labware)
    
    transfer_dest_labwares = []
    for name, slot in zip(transfer_dest_labware_names, transfer_dest_labware_slots):
        transfer_dest_labware = custom_or_native_labware(protocol, name, slot, custom_labware_dict)
        transfer_dest_labwares.append(transfer_dest_labware)
    
    transfer_source_wells = []
    for source_labware in transfer_source_labwares:
        rows = [well for row in source_labware.rows() for well in row]
        transfer_source_wells = transfer_source_wells + rows
    
    transfer_dest_wells = []
    for dest_labware in transfer_dest_labwares:
        rows = [well for row in dest_labware.rows() for well in row]
        transfer_dest_wells = transfer_dest_wells + rows
    
#     transfer_source_labware = protocol.load_labware(experiment_dict['OT2 Transfer Source Labwares'], experiment_dict['OT2 Transfer Source Slot'])
    
    transfer_source_start = experiment_dict['OT2 Independent Transfer Source [Start, Stop]'][0]
    transfer_source_stop = experiment_dict['OT2 Independent Transfer Source [Start, Stop]'][1]

#     transfer_dest_labware = protocol.load_labware(experiment_dict['OT2 Transfer Dest Labwares'], experiment_dict['OT2 Transfer Dest Slot'])
    transfer_dest_start = experiment_dict['OT2 Independent Transfer Dest [Start, Stop]'][0]
    transfer_dest_stop = experiment_dict['OT2 Independent Transfer Dest [Start, Stop]'][1]
    
    if pipette_1.min_volume <= transfer_volume <= pipette_1.max_volume: # allows for best specficity since higher res on volume constrained pipette
        pipette = pipette_1
    
    elif pipette_2.min_volume < transfer_volume < pipette_2.max_volume:
        pipette = pipette_2
    
    else:
        raise ValueError('Transfer volume not appropiate for current pipettes') 
    
    for source, dest in zip(transfer_source_wells[transfer_source_start:transfer_source_stop], transfer_dest_wells[transfer_dest_start:transfer_dest_stop]):
        pipette.transfer(transfer_volume, source, dest)

    for line in protocol.commands():
        print(line)


# think about this since essentially your doing something the ot2 already has a code for function seems redundant. 
def custom_or_native_labware(protocol, labware_name, labware_slot, custom_labware_dict):
    if labware_name in custom_labware_dict:
        loaded_labware = protocol.load_labware_from_definition(custom_labware_dict[labware_name], labware_slot)
    else: 
        loaded_labware = protocol.load_labware(labware_name, labware_slot)     
        return loaded_labware

