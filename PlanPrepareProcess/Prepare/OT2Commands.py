import glob
import os
import json
import opentrons.simulate as simulate

def custom_labware_dict(labware_dir_path): 
    """Given the path of a folder of custom labware .json files will create dict
    of key = name and value = labware definition to be loaded using protocol.load_labware_from_definition 
    versus typical protocol.load_labware"""
    original_working_dir = os.getcwd()
    os.chdir(labware_dir_path) 
    labware_dict = {}
    for file in glob.glob("*.json"):
        with open(file) as labware_file:
            labware_name = os.path.splitext(file)[0] # removes the .json extnesion
            labware_def = json.load(labware_file)
            labware_dict[labware_name] = labware_def
    os.chdir(original_working_dir)
    return labware_dict 

def object_to_well_list(protocol, labware_object_names, labware_object_slots):
    """Loads the labware specfied in the list arguments with the respective slots. This labware is tied 
    to the loaded protocol (global). Once the labware is loaded a concatenated list of the all labwares is created
    in order of the object in the initally loaded list."""
    
    labware_objects = [] # labware objects
    for labware_name, labware_slot in zip(labware_object_names, labware_object_slots):
        labware_object = protocol.load_labware(labware_name, labware_slot)
        labware_objects.append(labware_object)
    
    all_wells_row_order = [] 
    for labware in labware_objects:
        rows = [well for row in labware.rows() for well in row]
        all_wells_row_order = all_wells_row_order + rows
    
    return all_wells_row_order

def object_to_object_list(protocol, stock_object_names, stock_object_slots):
    """Loads the labware specfied in the list arguments with the respective slots. This labware is tied 
    to the loaded protocol (global)."""
    
    labware_objects = [] # labware objects
    for labware_name, labware_slot in zip(stock_object_names, stock_object_slots):
        labware_object = protocol.load_labware(labware_name, labware_slot) # this is where the well information is being pulled from a OT2/added native library
        labware_objects.append(labware_object)
   
    return labware_objects

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

def stock_well_ranges(volume_df, limit):
    """Given a dataframe of stocks volumes to pipette, will return the ranges of indexes for the volumes
    seperated in such a way to satisfy the volume limitation of current stock labware. Ranges of the indexes are 
    provide in a 2D list with each entry consisting of a lower and a upper_well_index index. 
    A stock is identified by having the term stock or Stock in its df column.
    Note: dataframe/series indexing is a little different than list indexing """
    
    col_names = [name for name in volume_df.columns if "stock" in name]
    ranges = []
    for col_name in col_names:
        series = volume_df[col_name]
        series_cs = series.cumsum()
        multiplier = 1
        range_list = [0]
        for index, entry in enumerate(series_cs):
            limit_m = limit*multiplier
            if entry>limit_m:
                multiplier = multiplier + 1
                range_list.append(index)
                range_list.append(index)
        range_list.append(len(series_cs))
        range_list_2D = [range_list[i:i+2] for i in range(0, len(range_list), 2)]
        ranges.append(range_list_2D)

    counter = 0
    range_complete_positions = []
    for stock_ranges, name in zip(ranges, volume_df.columns): 
        range_position =[]
        for r in stock_ranges: 
            counter += 1
            range_position.append(counter)
        range_complete_positions.append(range_position)
        print(name + ' position(s) = ' + str(range_position) + ' for wells ' + str(stock_ranges))

    return ranges


def determine_pipette_resolution(loaded_dict):
    """Given the opentrons only uses two pipettes one as always designated as a small or large pipette to ensure a wide range 
    of volumes is covered. We designate one as small and one as large to ensure we are using the highest precision possible"""
    
    left_pipette = loaded_dict['Left Pipette']
    right_pipette = loaded_dict['Right Pipette']

    if left_pipette.max_volume < right_pipette.max_volume:
        small_pipette = left_pipette 
        large_pipette = right_pipette

    if left_pipette.max_volume > right_pipette.max_volume:
        small_pipette = right_pipette
        large_pipette = left_pipette

    loaded_dict['Small Pipette'] = small_pipette
    loaded_dict['Large Pipette'] = large_pipette

    return loaded_dict

def pipette_check(volumes_df, pipette_1, pipette_2):
    """Given volumes along with two pipettes in use, will ensure the volumes of the pipette ranges are able to be cover the volumes"""
    volume_df_checked = volume_df[(volume_df==0)|(volume_df > pipette_1.min)|(volume_df < pipette_1.max)|(volume_df > pipette_2.min)|(volume_df < pipette_2.max)]
    
    assert len(volume_df) == len(volume_df_checked), 'Pipettes do not cover appropiate volumes'


def labware_check():
    """Will check prior to simulation if labware is appropiate for volumes"""


def loading_labware(protocol, experiment_dict):
    """ Loads the required labware given information from a loaded csv dictionary. The labware, which
    include pipettes, plates and tipracks are tied to the protocol object argurment. Returned is a dcitonary 
    containing the important object instances to be used in subsequent functions alongside the original protocol instance."""
    
    protocol.home() 
      
    api_level = '2.0'
    
    metadata = {
    'protocolName': experiment_dict['Protocol Version'],
    'author': experiment_dict['Experimenter'],
    'description': experiment_dict['Project Tag'],
    'apiLevel': api_level}

    # Loading labwares: All concatenated list of wells in order of the provided name/slot
    
    dest_plate_names = experiment_dict['OT2 Destination Labwares']
    dest_plate_slots = experiment_dict['OT2 Destination Labware Slots']
    dest_wells = object_to_well_list(protocol, dest_plate_names, dest_plate_slots)
    
    stock_labware_names = experiment_dict['OT2 Stock Labwares']
    stock_labware_slots = experiment_dict['OT2 Stock Labware Slots']
    stock_wells = object_to_well_list(protocol, stock_labware_names, stock_labware_slots)
    
    # Loading pipettes and tipracks
    
    right_tiprack_names = experiment_dict['OT2 Right Tipracks']
    right_tiprack_slots = experiment_dict['OT2 Right Tiprack Slots']
    right_tipracks = object_to_object_list(protocol, right_tiprack_names, right_tiprack_slots)
    
    right_pipette = protocol.load_instrument(experiment_dict['OT2 Right Pipette'], 'right', tip_racks = right_tipracks)
    right_pipette.flow_rate.aspirate = experiment_dict['OT2 Right Pipette Aspiration Rate (uL/sec)']
    right_pipette.flow_rate.dispense = experiment_dict['OT2 Right Pipette Dispense Rate (uL/sec)']    
    right_pipette.well_bottom_clearance.dispense = experiment_dict['OT2 Bottom Dispensing Clearance (mm)'] 
    
    left_tiprack_names = experiment_dict['OT2 Left Tipracks']
    left_tiprack_slots = experiment_dict['OT2 Left Tiprack Slots']
    left_tipracks = object_to_object_list(protocol, left_tiprack_names, left_tiprack_slots)
    
    left_pipette = protocol.load_instrument(experiment_dict['OT2 Left Pipette'], 'left', tip_racks = left_tipracks) # is there a way to ensure the correct tiprack is laoded? maybe simple simualtion test a function
    left_pipette.flow_rate.aspirate = experiment_dict['OT2 Left Pipette Aspiration Rate (uL/sec)']
    left_pipette.flow_rate.dispense = experiment_dict['OT2 Left Pipette Dispense Rate (uL/sec)']   
    left_pipette.well_bottom_clearance.dispense = experiment_dict['OT2 Bottom Dispensing Clearance (mm)']
    
    loaded_labware_dict = {'Destination Wells': dest_wells, 
                           'Stock Wells': stock_wells,
                           'Left Pipette': left_pipette,
                           'Right Pipette': right_pipette}
    
    return loaded_labware_dict # even if there was a way to call from protocol object would need to rename all over aagin


def pipette_volumes_component_wise(protocol, loaded_dict, stock_volumes_df, stock_ranges):
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
                
            pipette.pick_up_tip()
            
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


def pipette_volumes_sample_wise(protocol, volumes_df, loaded_dict):
    """A pipetting strategy which results in samples being made one by one rather than a component being added completely to all samples first.
    The component is added single and has its pipette parked back to use for the other samples."""



def transfer_from_destination_to_final(protocol, loaded_dict, experiment_dict, number_of_samples):
    """This function will take the already loaded dictionary and load more labware, specfically made for a final transfer from the destination sample plates to another plate. 
    The reaason for this final transfer is to allow samples to be made at any volume or at least a close enough volume and then moved to a secondary plate to be analyzed at the sample 
    quantity (important for things like path lengths). This could theoretically be used independently from an initial sample creation, would just need to initialize the loading of labware. 
    The reason why this could be useful is because the deck is limited in space so creating the samples and having their final transfer labware all on the deck at the same time could pose a constraint, 
    however unlikely as typically you will be transfering into a smaller vessel with more wells than the original synthesis vessel."""
    
    dest_wells = loaded_dict['Destination Wells']
    stock_wells = loaded_dict['Stock Wells']
    left_pipette = loaded_dict['Left Pipette']
    right_pipette = loaded_dict['Right Pipette']

    left_pipette.flow_rate.dispense = experiment_dict['OT2 Single Transfer Left Pipette Dispense Rate (uL/sec)']
    right_pipette.flow_rate.dispense = experiment_dict['OT2 Single Transfer Right Pipette Dispense Rate (uL/sec)']

    # Remember we initialize pipettes as large and small is because we want to have the highest precision possible!
    if left_pipette.max_volume < right_pipette.max_volume:
        small_pipette = left_pipette 
        large_pipette = right_pipette 
    
    if left_pipette.max_volume > right_pipette.max_volume:
        small_pipette = right_pipette
        large_pipette = left_pipette

    # Loading the final transfer labware

    final_transfer_plate_names = experiment_dict['OT2 Single Transfer From Dest Labwares']
    final_transfer_plate_slots = experiment_dict['OT2 Single Transfer From Dest Slots']
    final_transfer_wells = object_to_well_list(protocol, final_transfer_plate_names, final_transfer_plate_slots) 

    transfer_volume = float(experiment_dict['OT2 Single Transfer From Dest Volume (uL)'])
    bottom_dispensing_clearence = experiment_dict['OT2 Single Transfer From Dest Bottom Dispensing Clearance (mm)']

    assert len(final_transfer_wells) >= number_of_samples, 'The number of samples is exceeds the number of final destination wells'

    # make this bit into a function since commonly called 
    if small_pipette.min_volume <= transfer_volume <= small_pipette.max_volume or initial_volume == 0:
        pipette = small_pipette
    elif large_pipette.min_volume <= transfer_volume <= large_pipette.max_volume:
        pipette = large_pipette  
        

    sample_final_location = []
    
    for well_index in range(number_of_samples):
        pipette.transfer(transfer_volume, dest_wells[well_index], final_transfer_wells[well_index], new_tip = 'always') 
        sample_final_location.append(final_transfer_wells[well_index])
    for line in protocol.commands(): 
        print(line)
    return sample_final_location

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

