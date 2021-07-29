import glob
import os
import json
import opentrons.simulate as simulate
import pandas as pd
import time

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

def object_list_to_well_list(labware_objects, well_order = 'row'):
    """Labware list loaded is made into concatenated list of the all labwares
    in order of the object in the initally loaded list."""

    all_wells_order = []
    for labware in labware_objects:
        if well_order == 'row':
            wells = [well for row in labware.rows() for well in row]
        if well_order == 'column':
            wells = [well for columns in labware.columns() for well in columns]

        all_wells_order = all_wells_order + wells

    return all_wells_order

def loading_labware(protocol, experiment_dict, well_order = 'row',  load_cleaning = False):
    """ Loads the required labware given information from a loaded csv dictionary. The labware, which
    include pipettes, plates and tipracks are tied to the protocol object argurment. Returned is a dcitonary
    containing the important object instances to be used in subsequent functions alongside the original protocol instance."""

    protocol.home()

    # Loading labwares: All concatenated list of wells in order of the provided name/slot

    dest_labware_names = experiment_dict['OT2 Destination Labwares']
    dest_labware_slots = experiment_dict['OT2 Destination Labware Slots']
    dest_labware_objects = object_to_object_list(protocol, dest_labware_names, dest_labware_slots)
    dest_wells = object_list_to_well_list(dest_labware_objects, well_order = well_order)

    stock_labware_names = experiment_dict['OT2 Stock Labwares']
    stock_labware_slots = experiment_dict['OT2 Stock Labware Slots']
    stock_labware_objects = object_to_object_list(protocol, stock_labware_names, stock_labware_slots)
    stock_wells = object_list_to_well_list(stock_labware_objects, well_order = well_order)

    # Loading pipettes and tipracks

    right_tiprack_names = experiment_dict['OT2 Right Tipracks']
    right_tiprack_slots = experiment_dict['OT2 Right Tiprack Slots']
    right_tipracks = object_to_object_list(protocol, right_tiprack_names, right_tiprack_slots)
    right_tiprack_wells = object_list_to_well_list(right_tipracks, well_order = well_order)

    right_pipette = protocol.load_instrument(experiment_dict['OT2 Right Pipette'], 'right', tip_racks = right_tipracks)
    right_pipette.flow_rate.aspirate = experiment_dict['OT2 Right Pipette Aspiration Rate (uL/sec)']
    right_pipette.flow_rate.dispense = experiment_dict['OT2 Right Pipette Dispense Rate (uL/sec)']
    right_pipette.well_bottom_clearance.dispense = experiment_dict['OT2 Bottom Dispensing Clearance (mm)']


    left_tiprack_names = experiment_dict['OT2 Left Tipracks']
    left_tiprack_slots = experiment_dict['OT2 Left Tiprack Slots']
    left_tipracks = object_to_object_list(protocol, left_tiprack_names, left_tiprack_slots)
    left_tiprack_wells = object_list_to_well_list(left_tipracks, well_order = well_order)

    left_pipette = protocol.load_instrument(experiment_dict['OT2 Left Pipette'], 'left', tip_racks = left_tipracks) # is there a way to ensure the correct tiprack is laoded? maybe simple simualtion test a function
    left_pipette.flow_rate.aspirate = experiment_dict['OT2 Left Pipette Aspiration Rate (uL/sec)']
    left_pipette.flow_rate.dispense = experiment_dict['OT2 Left Pipette Dispense Rate (uL/sec)']
    left_pipette.well_bottom_clearance.dispense = experiment_dict['OT2 Bottom Dispensing Clearance (mm)']

    loaded_labware_dict = {'Destination Wells': dest_wells,
                       'Stock Wells': stock_wells,
                       'Left Pipette': left_pipette,
                       'Left Tiprack Wells': left_tiprack_wells,
                       'Right Pipette': right_pipette,
                       'Right Tiprack Wells': right_tiprack_wells,
                       'Protocol': protocol}

    # Load in extra labware like cleaning labware, or maybe pull this out into its own function that adds generally a labware to loaded_dict
    if load_cleaning == True:
        cleaning_labware_names = experiment_dict['OT2 Cleaning Labwares']
        cleaning_labware_slots = experiment_dict['OT2 Cleaning Labware Slots']
        cleaning_labware_objects = object_to_object_list(protocol, cleaning_labware_names, cleaning_labware_slots)
        cleaning_wells = object_list_to_well_list(cleaning_labware_objects, well_order = well_order)

        loaded_labware_dict['Cleaning Wells'] = cleaning_wells

    loaded_labware_dict = determine_pipette_resolution(loaded_labware_dict)

    return loaded_labware_dict

def add_labware_to_dict(loaded_dict, labware_key, labware_names_list, labware_slots_list, well_order = 'row'):
    protocol = loaded_dict['Protocol']
    labware_objects = object_to_object_list(protocol, labware_names_list, labware_slots_list)
    wells = object_list_to_well_list(labware_objects, well_order = well_order)
    loaded_dict[labware_key] = wells

def stock_well_ranges(volume_df, stock_labware_wells, volume_buffer_pct= 10):
    """Given a dataframe of stocks volumes to pipette, will return the ranges of indexes for the volumes
    seperated in such a way to satisfy the volume limitation of current stock labware. Ranges of the indexes are
    provide in a 2D list with each entry consisting of a lower and a upper_well_index index.
    A stock is identified by having the term stock or Stock in its df column.
    Note: dataframe/series indexing is a little different than list indexing """

    # will only require protocol if you want to call the
    volume_df = pd.DataFrame(volume_df)
    limit = float(stock_labware_wells[0].max_volume)*(100-volume_buffer_pct)/100
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
        stock_info_to_pull[col_name]= {'Ranges':range_list_2D, 'Total Volume': series.sum()}

    # Now let us add the information of stock position
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

def create_sample_making_directions(volume_df, stock_position_info, loaded_labware_dict, start_position=0):
    if not isinstance(volume_df, pd.DataFrame):
        volume_df = pd.DataFrame(volume_df)
    volume_df = volume_df.reset_index(drop=True)
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
        destination_well = destination_wells[well_index+start_position]
        sample_making_dict[i] = {}
        single_sample_dict = sample_making_dict[i]

        for stock_index, column_name in enumerate(volume_df.columns):
            stock_name = column_name
            single_sample_dict[stock_name] = {}
            single_stock_direction_entry = single_sample_dict[stock_name]
            stock_volume_to_pull = float(single_sample_stock_volumes[stock_name])
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

def cleaning_tip_protocol(loaded_dict, cleaning_cycles = 1):
    """Assumes cleaning labware has already been loaded into loaded_dict with the Key of 'Cleaning Labware' """

    cleaning_wells = loaded_dict['Cleaning Wells']
    cleaning_dict = {}
    for i in range(cleaning_cycles):
        cleaning_dict_entry = {}
        well_index = input('Enter Well Index ')
        cleaning_well = cleaning_wells[int(well_index)]
        cleaning_dict_entry['well'] = cleaning_well
        print("Adding " + str(cleaning_well) + ' for washing step')

        cleaning_delay = input('Enter Cleaning Delay (sec) ')
        cleaning_dict_entry['delay'] = float(cleaning_delay)
#         print("Volume to swish " + str(volume_to_swish) + ' for washing step')

        mix_n = input('Enter Times Wanting to mix ')
        cleaning_dict_entry['mix_n'] = int(mix_n)
#         print("Mixing " + str(mix_n) + ' times')

        cleaning_dict['Cleaning ' + str(i)] = cleaning_dict_entry
    loaded_dict['Cleaning Protocol'] = cleaning_dict
    return cleaning_dict

def execute_cleaning_protocol(loaded_labware_dict, pipette, protocol):

    cleaning_protocol = loaded_labware_dict['Cleaning Protocol']
    for key, cleaning_n_protocol in cleaning_protocol.items():
        cleaning_well = cleaning_n_protocol['well']
        cleaning_mix_n = cleaning_n_protocol['mix_n']
        cleaning_delay = cleaning_n_protocol['delay']

        pipette.mix(cleaning_mix_n, pipette.max_volume, cleaning_well)
        pipette.blow_out(cleaning_well)
        protocol.delay(cleaning_delay)
    pipette.blow_out(protocol.fixed_trash['A1'])


def pipette_volumes_sample_wise(protocol, directions, loaded_labware_dict, reuse_tips = True, clean_tips = False, after_delay_sec = 0, **kwargs):  # need to add kwargs for the transfer function
    protocol.home()
    start = time.time()

    small_pipette = loaded_labware_dict['Small Pipette']
    small_tiprack = loaded_labware_dict['Small Tiprack']
    large_pipette = loaded_labware_dict['Large Pipette']
    large_tiprack = loaded_labware_dict['Large Tiprack']

    if reuse_tips == True: # Case when making alot of samples
        for sample_index, stock_instruction in directions.items():
            for stock_index, (stock_name, single_stock_instructions) in enumerate(stock_instruction.items()):
                stock_volume_to_pull = single_stock_instructions['Stock Volume']
                stock_position_to_pull = single_stock_instructions['Stock Position']
                destination_well = single_stock_instructions['Destination Well Position']
                if stock_volume_to_pull == 0:
                    pass
                else:
                    # Now the three pieces of info available volume, destination, source.
                    pipette, tiprack_wells = determine_pipette_tiprack(stock_volume_to_pull, small_pipette, large_pipette, small_tiprack, large_tiprack)

                    if pipette.has_tip: # Checking if the machine has tips attached prior
                        pipette.drop_tip()
                    pipette.pick_up_tip(tiprack_wells[stock_index])
                    # addition of delay before or after transfer??? i feel like delay should only be after a transfer
                    pipette.transfer(stock_volume_to_pull, stock_position_to_pull, destination_well, new_tip='never', **kwargs)
                    protocol.delay(seconds=after_delay_sec)
                    if clean_tips == True: # Mix components or do other contiminatin features.
                        execute_cleaning_protocol(loaded_labware_dict, pipette, protocol)

                    pipette.return_tip()

    if reuse_tips == False: # case when making only a few samples
        for sample_index, stock_instruction in directions.items():
            for stock_index, (stock_name, single_stock_instructions) in enumerate(stock_instruction.items()):
                stock_volume_to_pull = single_stock_instructions['Stock Volume']
                stock_position_to_pull = single_stock_instructions['Stock Position']
                destination_well = single_stock_instructions['Destination Well Position']
                if stock_volume_to_pull == 0:
                    pass
                else:
                    # Now the three pieces of info available volume, destination, source.
                    pipette, tiprack_wells = determine_pipette_tiprack(stock_volume_to_pull, small_pipette, large_pipette, small_tiprack, large_tiprack)

                    if pipette.has_tip: # Checking if the machine has tips attached prior
                        pipette.drop_tip()

                    pipette.transfer(stock_volume_to_pull, stock_position_to_pull, destination_well, new_tip='always', **kwargs)

    for line in protocol.commands():
        print(line)

    ### Keeping track of execution time. Will print total run time in minutes
    end = time.time()
    time_consumed = end-start
    print("This protocol took {} minutes to execute".format(np.round(time/60, 3)))

def pipette_volumes_component_wise(protocol, directions, loaded_labware_dict, delay_after=0, **kwargs): # need to add kwargs for the transfer function
    protocol.home()
    start = time.time()

    small_pipette = loaded_labware_dict['Small Pipette']
    small_tiprack = loaded_labware_dict['Small Tiprack']
    large_pipette = loaded_labware_dict['Large Pipette']
    large_tiprack = loaded_labware_dict['Large Tiprack']

    stock_to_pipette_order=None
    if stock_to_pipette_order is None:
        stock_to_pipette_order = directions[0].keys()

    # Checking if the machine has tips attached prior
    if small_pipette.has_tip:
        small_pipette.drop_tip()
    if large_pipette.has_tip:
        large_pipette.drop_tip()
    pipette = small_pipette # setting as initial defualt
    for i, stock_name in enumerate(stock_to_pipette_order):
        for stock_index, stock_instructions in directions.items(): # this is not the stock index fix it it should be i
            single_stock_instructions = stock_instructions[stock_name]
            stock_volume_to_pull = single_stock_instructions['Stock Volume']
            stock_position_to_pull = single_stock_instructions['Stock Position']
            destination_well = single_stock_instructions['Destination Well Position']

            if stock_volume_to_pull == 0: # need to make this a pass?
                pass
            elif small_pipette.min_volume <= stock_volume_to_pull <= small_pipette.max_volume:
                # this small chunk of dropping tip should be made into its own function
                if pipette == large_pipette and pipette.has_tip == True: # Returning tip if other pipette has tip
                    pipette.return_tip()
                pipette = small_pipette
                tiprack = small_tiprack
                if pipette.has_tip == True:
                    pass
                elif pipette.has_tip == False:
                    pipette.pick_up_tip(tiprack[i])
                if 'mix_before' in kwargs.keys():
                    vol_to_mix = kwargs['mix_before'][1]
                    if vol_to_mix > pipette.max_volume:
                        kwargs['mix_before'] = (kwargs['mix_before'][0], pipette.max_volume)
                    else:
                        pass
                if 'mix_after' in kwargs.keys():
                    vol_to_mix = kwargs['mix_after'][1]
                    if vol_to_mix > pipette.max_volume:
                        kwargs['mix_after'] = (kwargs['mix_after'][0], pipette.max_volume)
                    else:
                        pass

                pipette.transfer(stock_volume_to_pull, stock_position_to_pull, destination_well, new_tip='never', **kwargs)
                protocol.delay(seconds=delay_after)
                pipette.blow_out()

                if 'mix_after' in kwargs.keys(): # Mix components or do other contiminatin features.
                    execute_cleaning_protocol(loaded_labware_dict, pipette, protocol)

            elif large_pipette.min_volume <= stock_volume_to_pull:
                if pipette == small_pipette and pipette.has_tip == True:
                    pipette.return_tip()

                tiprack = large_tiprack
                pipette = large_pipette
                if pipette.has_tip == True:
                    pass
                elif pipette.has_tip == False:
                    pipette.pick_up_tip(tiprack[i])

                if 'mix_before' in kwargs.keys():
                    vol_to_mix = kwargs['mix_before'][1]
                    if vol_to_mix > pipette.max_volume:
                        kwargs['mix_before'] = (kwargs['mix_before'][0], pipette.max_volume)
                    else:
                        pass
                if 'mix_after' in kwargs.keys():
                    vol_to_mix = kwargs['mix_after'][1]
                    if vol_to_mix > pipette.max_volume:
                        kwargs['mix_after'] = (kwargs['mix_after'][0], pipette.max_volume)
                    else:
                        pass
                pipette.transfer(stock_volume_to_pull, stock_position_to_pull, destination_well, new_tip='never', **kwargs) # it might be wise to switch to pipette.aspirate and pipette.dispense, give more control and more modular
                protocol.delay(seconds=delay_after)
                ## Consider adding 'blow_out' as argument of the funciton instead of hardcoding it
                pipette.blow_out()

                if 'mix_after' in kwargs.keys(): # Mix components or do other contiminatin features.
                    execute_cleaning_protocol(loaded_labware_dict, pipette, protocol)
            else:
                raise AssertionError('Pipettes not suitable for volume', stock_volume_to_pull)
        if small_pipette.has_tip == True: # these can be made into functions to just check for tip and if so drop
            small_pipette.drop_tip()
        if large_pipette.has_tip == True:
            large_pipette.drop_tip()
    for line in protocol.commands():
        print(line)

    ### Keeping track of execution time. Will print total run time in minutes
    end = time.time()
    time_consumed = end-start
    print("This protocol took {} minutes to execute".format(np.round(time/60, 3)))

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
        small_pipette = pipette_2
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
    # well = str(destination_wells[0])
    well_volume = float(destination_wells[0].max_volume)
    total_sample_volumes = volumes_df.sum(axis=1)

    assert (total_sample_volumes <= well_volume).all(), 'Sample volumes are exceeding max destination well volume of ' + str(well_volume) + 'uL'


# def determine_well_volume(well):
#     # well_volume = str(well).split(' ')[-4]
#     well_string = well.split(' ')
#     for i, sub_string in enumerate(well_string):
#         if 'mL' in sub_string:
#             if len(sub_string) == 2:
#                 well_volume = float(well_string[i-1])*1000
#             elif len(sub_string) > 2:
#                 well_volume = float(sub_string[:-2])*1000
#         elif 'µL' in sub_string:
#             if len(sub_string) == 2:
#                 well_volume = float(well_string[i-1])
#             elif len(sub_string) > 2:
#                 well_volume = float(sub_string[:-2])
#     return well_volume


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

# think about this since essentially your doing something the ot2 already has a code for function seems redundant.
def custom_or_native_labware(protocol, labware_name, labware_slot, custom_labware_dict):
    if labware_name in custom_labware_dict:
        loaded_labware = protocol.load_labware_from_definition(custom_labware_dict[labware_name], labware_slot)
    else:
        loaded_labware = protocol.load_labware(labware_name, labware_slot)
        return loaded_labware
