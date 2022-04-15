import glob
import os
import json
import opentrons.simulate as simulate
import pandas as pd
import numpy as np
import time

from OT2_DOE.Plan.CreateSamples import isolate_common_column

# All logic is based on api 2.2+ from opentrons, please read:
# https://docs.opentrons.com/OpentronsPythonAPIV2.pdf
# Keep in mind the following:
# - All row based (while OT2 'default' is column based),
# - All sequential (i.e sample 100 will be sample 4 in 96 well plate 2 of 2.)
# - Arugments are at times hardcoded to pull from a csv template
#  (hesistate to change template csv, can add but try not take away).

# Load in custom labware dictionry if necessary #


def custom_labware_dict(labware_dir_path):
    """
    Given the path of a folder of custom labware .json files will create dict
    of key = name and value = labware definition to be loaded using
    protocol.load_labware_from_definition versus typical protocol.load_labware

    Parameters
    -----------

    labware_dir_path : str
        Path to the folder containing the labware .json files.

    Returns
    --------

    labware_dict: dict
        Dictionary contianing infomration about the labware calibration.
        There include: size, # of wells, well size, height, etc.

    """
    labware_dict = {}
    for file in glob.glob(labware_dir_path + '/**/*.json', recursive=True):
        with open(file) as labware_file:
            # removes the .json extnesion
            labware_name = os.path.splitext(file)[0]
            labware_def = json.load(labware_file)
            labware_dict[labware_name] = labware_def
    return labware_dict


# These next functions will help you create a labware dictionary
# This will contain all information tied to protocol object to run a protocol.
# The four main things are: source/destination labware, pipettes and tipracks #


def object_to_object_list(protocol, stock_object_names, stock_object_slots,
                          offset=None):
    """
    Loads the labware specfied in the list arguments with the respective slots.
    This labware is tied to the loaded protocol (global).

    Parameters
    -----------

    protocol: opentrons.protocol_api.protocol_context.ProtocolContext
        Protocol object from the robot
    stock_object_names: List
        List containing string representing the labware to use for the protocol
    stock_object_slots: List
        List containing string representing the OT-2 deck slots each labware
        will be placed on during the experiment.

    Returns
    --------

    labware_objects : List
        List containing all the labware objects
            [opentrons.protocol_api.labware.Labware]
    """

    labware_objects = []  # labware objects
    if offset:
        for labware_name, labware_slot, offset_coord in zip(
                                              stock_object_names,
                                              stock_object_slots,
                                              offset):
            labware_object = protocol.load_labware(labware_name,
                                                   labware_slot)
            labware_object.set_offset(x=offset_coord[0],
                                      y=offset_coord[1],
                                      z=offset_coord[2])
            # this is where the well information is being pulled from
            # a OT2/added native library
            labware_objects.append(labware_object)

    else:
        for labware_name, labware_slot in zip(
                                              stock_object_names,
                                              stock_object_slots):
            labware_object = protocol.load_labware(labware_name,
                                                   labware_slot)
            # this is where the well information is being pulled from
            # a OT2/added native library
            labware_objects.append(labware_object)

    return labware_objects


def object_list_to_well_list(labware_objects, well_order='row'):
    """
    Labware list loaded is made into concatenated list of the all labwares
    in order of the object in the initally loaded list.

    Parameters
    -----------

    labware_objects : List
        List containing all the labware objects
            [opentrons.protocol_api.labware.Labware]
    well_order: 'row' or 'column'
        String indicating the order in which the wells will be accessed by
        the robot

    Returns
    --------

    all_wells_order : List
        List containing all the well information (well name, labware name, and
        deck position) for each labware found in the labware object list.

    """

    all_wells_order = []
    for labware in labware_objects:
        if well_order == 'row':
            wells = [well for row in labware.rows() for well in row]
        if well_order == 'column':
            wells = [well for columns in labware.columns() for well in columns]

        all_wells_order = all_wells_order + wells

    return all_wells_order


def loading_labware(protocol, experiment_dict,
                    well_order='row', load_cleaning=False):
    """
    Loads the required labware given information from a loaded csv dictionary.
    The labware, which include pipettes, plates and tipracks are tied to the
    protocol object argurment. Returned is a dictonary containing the important
    object instances to be used in subsequent functions alongside the original
    protocol instance.

    Parameters
    -----------

    protocol: opentrons.protocol_api.protocol_context.ProtocolContext
        Protocol object from the robot
    experiment_dict: Dict
        Dictionary containig all the experimental parameters
    well_order: 'row' or 'column'
        String indicating the order in which the wells will be accessed by
        the robot
    load_cleaning: Bool
        True, the code will look for the labware, deck position to be used for
        a cleaning protocol

    Returns
    --------

    loaded_dict : Dict
        Dictionary containg all labware, pipette, tipracks and protocol
        information

    """
    protocol.home()
    # Check for labware offset info in protocol file
    protocol_keys = list(experiment_dict.keys())

    # Loading labwares:
    # All concatenated list of wells in order of the provided name/slot

################ Destination Labware ######################
    dest_labware_names = experiment_dict['OT2 Destination Labwares']
    dest_labware_slots = experiment_dict['OT2 Destination Labware Slots']

    if 'OT2 Destination Labwares Offset' in protocol_keys:
        dest_labware_offset =\
            experiment_dict['OT2 Destination Labwares Offset']
        dest_labware_objects = object_to_object_list(
            protocol, dest_labware_names, dest_labware_slots,
            offset=dest_labware_offset)
    else:
        dest_labware_objects = object_to_object_list(
            protocol, dest_labware_names, dest_labware_slots)

    dest_wells = object_list_to_well_list(
        dest_labware_objects, well_order=well_order)

################ Stock Labware ######################
    stock_labware_names = experiment_dict['OT2 Stock Labwares']
    stock_labware_slots = experiment_dict['OT2 Stock Labware Slots']

    if 'OT2 Stock Labwares Offset' in protocol_keys:
        stock_labware_offset =\
            experiment_dict['OT2 Stock Labwares Offset']

        stock_labware_objects = object_to_object_list(
            protocol, stock_labware_names, stock_labware_slots,
            offset=stock_labware_offset)

    else:
        stock_labware_objects = object_to_object_list(
            protocol, stock_labware_names, stock_labware_slots)

    stock_wells = object_list_to_well_list(
        stock_labware_objects, well_order=well_order)

################ Pipettes & Tipracks ######################

    right_tiprack_names = experiment_dict['OT2 Right Tipracks']
    right_tiprack_slots = experiment_dict['OT2 Right Tiprack Slots']

    if 'OT2 Right Tipracks Offset' in protocol_keys:
        right_tiprack_offset =\
            experiment_dict['OT2 Right Tipracks Offset']

        right_tipracks = object_to_object_list(
            protocol, right_tiprack_names, right_tiprack_slots,
            offset= right_tiprack_offset)

    else:
        right_tipracks = object_to_object_list(
            protocol, right_tiprack_names, right_tiprack_slots)

    right_tiprack_wells = object_list_to_well_list(
        right_tipracks, well_order=well_order)

    #### Right Pipette ####
    right_pipette = protocol.load_instrument(
        experiment_dict['OT2 Right Pipette'],
        'right', tip_racks=right_tipracks)
    right_pipette.flow_rate.aspirate = experiment_dict[
        'OT2 Right Pipette Aspiration Rate (uL/sec)']
    right_pipette.flow_rate.dispense = experiment_dict[
        'OT2 Right Pipette Dispense Rate (uL/sec)']
    right_pipette.well_bottom_clearance.dispense = experiment_dict[
        'OT2 Bottom Dispensing Clearance (mm)']

    left_tiprack_names = experiment_dict['OT2 Left Tipracks']
    left_tiprack_slots = experiment_dict['OT2 Left Tiprack Slots']

    if 'OT2 Left Tipracks Offset' in protocol_keys:
        left_tiprack_offset =\
            experiment_dict['OT2 Left Tipracks Offset']
        left_tipracks = object_to_object_list(
            protocol, left_tiprack_names, left_tiprack_slots,
            offset= left_tiprack_offset)
    else:
        left_tipracks = object_to_object_list(
            protocol, left_tiprack_names, left_tiprack_slots)

    left_tiprack_wells = object_list_to_well_list(
        left_tipracks, well_order=well_order)

    left_pipette = protocol.load_instrument(
        experiment_dict['OT2 Left Pipette'],
        'left', tip_racks=left_tipracks)
    left_pipette.flow_rate.aspirate = experiment_dict[
        'OT2 Left Pipette Aspiration Rate (uL/sec)']
    left_pipette.flow_rate.dispense = experiment_dict[
        'OT2 Left Pipette Dispense Rate (uL/sec)']
    left_pipette.well_bottom_clearance.dispense = experiment_dict[
        'OT2 Bottom Dispensing Clearance (mm)']

    loaded_labware_dict = {'Destination Wells': dest_wells,
                           'Stock Wells': stock_wells,
                           'Left Pipette': left_pipette,
                           'Left Tiprack Wells': left_tiprack_wells,
                           'Right Pipette': right_pipette,
                           'Right Tiprack Wells': right_tiprack_wells,
                           'Protocol': protocol}

    # Load in extra labware like cleaning labware
    if load_cleaning is True:
        cleaning_labware_names = experiment_dict['OT2 Cleaning Labwares']
        cleaning_labware_slots = experiment_dict['OT2 Cleaning Labware Slots']
        cleaning_labware_objects = object_to_object_list(
            protocol, cleaning_labware_names, cleaning_labware_slots)
        cleaning_wells = object_list_to_well_list(
            cleaning_labware_objects, well_order=well_order)

        loaded_labware_dict['Cleaning Wells'] = cleaning_wells

    loaded_labware_dict = determine_pipette_resolution(loaded_labware_dict)

    return loaded_labware_dict


def add_labware_to_dict(loaded_dict, labware_key,
                        labware_names_list, labware_slots_list,
                        well_order='row'):
    """
    Function used to load a new labware and determine its specifications, such
    as deck position, labware name and well names. Once the labware it is
    loaded, the well order will be defined. The final labware form will be
    added to the experimental protocol.

    Parameters
    -----------

    loaded_dict: dict
        Dictionary containing all the exeprimental details relevent to the
        sample design space (optional), labware specs, deck slots, pipettes
        pipette tip.
    labware_key: str
        Strin indicating the key of the labware
    labware_names_list: list
        List of sample labware to use as destination wells.
    labware_slots_list: list
        List of deck slots to use for each labware. Note that the lenght of the
        labware_slots_list needs to be the same as the labware_names_list.
    well_order: 'row' or 'column'
        String indicating the order in which the wells will be accessed by
        the robot

    Returns
    --------

    loaded_dict : Dict
        Dictionary containg all labware, pipette, tipracks and protocol
        information and the new labware

    """
    protocol = loaded_dict['Protocol']
    labware_objects = object_to_object_list(
        protocol, labware_names_list, labware_slots_list)
    wells = object_list_to_well_list(
        labware_objects, well_order=well_order)
    loaded_dict[labware_key] = wells


def stock_well_ranges(volume_df, stock_labware_wells, volume_buffer_pct=10):
    """
    Given a dataframe of stocks volumes to be pipetted, it will return the
    ranges of sample indexes for the volumes seperated in such a way to satisfy
    the volume limitation of current stock labware.
    Ranges of the indexes are provide in a 2D list with each entry consisting
    of a lower and a upper_well_index index. A stock is identified by having
    the term stock or Stock in its column name.
    Note: dataframe/series indexing is a little different than list indexing.

    Parameters
    -----------

    volume_df: pd.DataFrame
        Dataframe containing all the species volumes composing each sample.
    stock_labware_wells: str
        String identifying the well name (i.e A1), the labware name and the
        dock slot position
    volume_buffer_pct: int
        Percentage of volume to use as buffer. This will be use to ensure that
        the robot will have enough volume to pipette out of the stock source.

    Returns
    --------

    stock_volume_to_pull: dict
        Dictionary cotaining information about the stocks and sample index
        details for each of them. The key of the dictionary are the stock
        names.

    """

    volume_df = pd.DataFrame(volume_df)
    limit = float(stock_labware_wells[0].max_volume)*(
        100-volume_buffer_pct)/100
    col_names = [name for name in volume_df.columns if "stock" in name]
    stock_info_to_pull = {}

    for col_name in col_names:
        series = volume_df[col_name]
        series_cs = series.cumsum()
        multiplier = 1
        range_list = [0]
        for index, entry in enumerate(series_cs):
            limit_m = limit*multiplier
            if entry > limit_m:
                multiplier = multiplier + 1
                range_list.append(index)  # doubled on purpose
                range_list.append(index)
        range_list.append(len(series_cs))
        range_list_2D = [range_list[i:i+2] for i in range(0,
                                                          len(range_list), 2)]
        stock_info_to_pull[col_name] = {'Ranges': range_list_2D,
                                        'Total Volume': series.sum()}

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


def create_sample_making_directions(volume_df, stock_position_info,
                                    loaded_labware_dict, start_position=0):
    """
    Function to generate the direction for each sample. This will include total
    volume to be dispensed for each of the stock composing the sample. It will
    also indicate the soruce well for each stock and the sample destination
    well.

    Parameters
    -----------


    Returns
    --------



    """

    if not isinstance(volume_df, pd.DataFrame):
        volume_df = pd.DataFrame(volume_df)
    volume_df = volume_df.reset_index(drop=True)
    volume_df = isolate_common_column(volume_df, 'stock')
    destination_wells = loaded_labware_dict['Destination Wells']
    stock_wells = loaded_labware_dict['Stock Wells']  # might not be needed

    # checking if labware and pipette is appropiate before moving forward
    labware_check_enough_wells(volume_df, loaded_labware_dict)
    labware_check_enough_volume(volume_df, loaded_labware_dict)
    pipette_check(volume_df, loaded_labware_dict['Left Pipette'],
                  loaded_labware_dict['Right Pipette'])

    sample_making_dict = {}
    for i, row in volume_df.iterrows():
        single_sample_stock_volumes = row
        well_index = i  # same as sample index  # could add sample + i
        destination_well = destination_wells[well_index+start_position]
        sample_making_dict[i] = {}
        single_sample_dict = sample_making_dict[i]

        for stock_index, column_name in enumerate(volume_df.columns):
            stock_name = column_name
            single_sample_dict[stock_name] = {}
            single_stock_direction_entry = single_sample_dict[stock_name]
            stock_volume_to_pull = float(
                single_sample_stock_volumes[stock_name])
            stock_position = find_stock_to_pull(
                stock_name, well_index, stock_position_info)

            single_stock_direction_entry['Stock Position'] = stock_position
            single_stock_direction_entry[
                'Destination Well Position'] = destination_well
            single_stock_direction_entry['Stock Volume'] = stock_volume_to_pull

    return sample_making_dict


def determine_pipette_tiprack(volume, small_pipette, large_pipette,
                              small_tiprack=None, large_tiprack=None):
    """


    Parameters
    -----------


    Returns
    --------
    """

    if small_pipette.min_volume <= volume <= small_pipette.max_volume or \
       volume == 0:
        pipette = small_pipette
        if small_tiprack:
            tiprack = small_tiprack
            return pipette, tiprack
    elif small_pipette.max_volume <= volume <= large_pipette.min_volume:
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
        raise AssertionError('Volumes not suitable for pipettes')
    return pipette


def determine_pipette_resolution(loaded_labware_dict):
    """
    Given the opentrons only uses two pipettes one as always designated as a
    small or large pipette to ensure a wide range of volumes is covered.
    We designate one as small and one as large to ensure we are using the
    highest precision possible

    Parameters
    -----------


    Returns
    --------
    """

    left_pipette = loaded_labware_dict['Left Pipette']
    left_tiprack = loaded_labware_dict['Left Tiprack Wells']
    right_pipette = loaded_labware_dict['Right Pipette']
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


def get_pipette_tip_count(small_pipette, large_pipette, volume_df):
    """
    This function will display the number of pipette tips required to run
    the experiment. This function will assume that a new pipette will be
    used to dispense each component for each sample. This could be the case
    if a mixing step is added in the protocol.
    Assessing this tip count, will aloow you to better design the OT2 deck
    layout and ensure that you can make all the planned samples in a single
    run.

    Parameters
    -----------
    small pipette: int
        Integer representing the maximum volume of the smallest pipette
    large pipette: int
        Integer representing the maximum volume of the largest pipette
    volume_df: pd.DataFrame
        Dataframe containing the volumes of each stock for all the samples

    Returns
    --------
    The fuinction will return print statements eith the total number of
    tips and tipracks required for each pipette.
    """
    small_tips = ((volume_df < small_pipette) & (volume_df != 0)).sum().sum()
    small_racks = np.round(small_tips/96, 1)
    print(" \033[1mSmall\033[0m pipette tips: \033[1m{}\033[0m".format(
        small_tips))
    print(" \033[1mSmall\033[0m tipracks: \033[1m{}\033[0m".format(
        small_racks))

    large_tips = ((volume_df > small_pipette)).sum().sum()
    large_racks = np.round(large_tips/96, 2)
    print(" \033[1mLarge\033[0m pipette tips: \033[1m{}\033[0m".format(
        large_tips))
    print(" \033[1mLarge\033[0m tipracks: \033[1m{}\033[0m".format(
        large_racks))


def calculate_total_volumes(volume_df):
    """
    Parameters
    -----------


    Returns
    --------
    """

    total_volumes = isolate_common_column(volume_df, 'stock').sum(axis=0)/1000
    return total_volumes


def find_stock_to_pull(stock_name, well_index, stocks_position_dict):
    """
    Parameters
    -----------


    Returns
    --------
    """

    stock_position_info = stocks_position_dict[stock_name]
    well_ranges = stock_position_info['Ranges']
    stock_positions = stock_position_info['Stock Wells']

    for stock_position, well_range in zip(stock_positions, well_ranges):
        if well_range[0] <= well_index <= well_range[1]:
            return stock_position
    else:
        raise AssertionError('Well is not covered by current stock,' +
                             ' please verify stock well ranges.')


def cleaning_tip_protocol(loaded_dict, cleaning_cycles=1):
    """
    Assumes cleaning labware has already been loaded into loaded_dict with
    the Key of 'Cleaning Labware'

    Parameters
    -----------


    Returns
    --------
    """

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

        mix_n = input('Enter Times Wanting to mix ')
        cleaning_dict_entry['mix_n'] = int(mix_n)

        cleaning_dict['Cleaning ' + str(i)] = cleaning_dict_entry
    loaded_dict['Cleaning Protocol'] = cleaning_dict
    return cleaning_dict


def execute_cleaning_protocol(loaded_labware_dict, pipette, protocol):
    """
    Parameters
    -----------


    Returns
    --------
    """
    cleaning_protocol = loaded_labware_dict['Cleaning Protocol']
    for key, cleaning_n_protocol in cleaning_protocol.items():
        cleaning_well = cleaning_n_protocol['well']
        cleaning_mix_n = cleaning_n_protocol['mix_n']
        cleaning_delay = cleaning_n_protocol['delay']

        pipette.mix(cleaning_mix_n, pipette.max_volume, cleaning_well)
        pipette.blow_out(cleaning_well)
        protocol.delay(cleaning_delay)
    pipette.blow_out(protocol.fixed_trash['A1'])


def pipette_volumes_sample_wise(protocol, directions, loaded_labware_dict,
                                reuse_tips=True, clean_tips=False,
                                after_delay_sec=0, **kwargs):
    """
    Parameters
    -----------


    Returns
    --------
    """

    protocol.home()
    start = time.time()

    small_pipette = loaded_labware_dict['Small Pipette']
    small_tiprack = loaded_labware_dict['Small Tiprack']
    large_pipette = loaded_labware_dict['Large Pipette']
    large_tiprack = loaded_labware_dict['Large Tiprack']

    if reuse_tips is True:  # Case when making alot of samples
        for sample_index, stock_instruction in directions.items():
            for stock_index, (stock_name, single_stock_instructions) in \
               enumerate(stock_instruction.items()):
                stock_volume_to_pull = single_stock_instructions[
                    'Stock Volume']
                stock_position_to_pull = single_stock_instructions[
                    'Stock Position']
                destination_well = single_stock_instructions[
                    'Destination Well Position']
                if stock_volume_to_pull == 0:
                    pass
                else:
                    # Now the three pieces of info available:
                    # volume, destination, source.
                    pipette, tiprack_wells = determine_pipette_tiprack(
                        stock_volume_to_pull, small_pipette,
                        large_pipette, small_tiprack, large_tiprack)
                    # Checking if the machine has tips attached prior
                    if pipette.has_tip:
                        pipette.drop_tip()
                    pipette.pick_up_tip(tiprack_wells[stock_index])
                    pipette.transfer(stock_volume_to_pull,
                                     stock_position_to_pull,
                                     destination_well,
                                     new_tip='never',
                                     **kwargs)
                    protocol.delay(seconds=after_delay_sec)
                    # Mix components or do other contiminatin features.
                    if clean_tips is True:
                        execute_cleaning_protocol(loaded_labware_dict,
                                                  pipette, protocol)

                    pipette.return_tip()

    if reuse_tips is False:  # case when making only a few samples
        for sample_index, stock_instruction in directions.items():
            for stock_index, (stock_name, single_stock_instructions) in \
             enumerate(stock_instruction.items()):
                stock_volume_to_pull = single_stock_instructions[
                    'Stock Volume']
                stock_position_to_pull = single_stock_instructions[
                    'Stock Position']
                destination_well = single_stock_instructions[
                    'Destination Well Position']
                if stock_volume_to_pull == 0:
                    pass
                else:
                    # Now the three pieces of info available
                    # volume, destination, source.
                    pipette, tiprack_wells = determine_pipette_tiprack(
                        stock_volume_to_pull, small_pipette,
                        large_pipette, small_tiprack, large_tiprack)
                    # Checking if the machine has tips attached prior
                    if pipette.has_tip:
                        pipette.drop_tip()

                    pipette.transfer(stock_volume_to_pull,
                                     stock_position_to_pull,
                                     destination_well,
                                     new_tip='always',
                                     **kwargs)

    for line in protocol.commands():
        print(line)

    # Keeping track of execution time. Will print total run time in minutes
    end = time.time()
    time_consumed = end-start
#     print(time_consumed)
    print("\nThis protocol took \033[1m{}\033[0m minutes to execute".format(
        np.round(time_consumed/60, 3)))


def pipette_volumes_component_wise(
        protocol, directions, loaded_labware_dict, delay_after=0,
        cleaning=False, **kwargs):
    """
    Parameters
    -----------


    Returns
    --------
    """
    protocol.home()
    start = time.time()

    small_pipette = loaded_labware_dict['Small Pipette']
    small_tiprack = loaded_labware_dict['Small Tiprack']
    large_pipette = loaded_labware_dict['Large Pipette']
    large_tiprack = loaded_labware_dict['Large Tiprack']

    stock_to_pipette_order = None
    if stock_to_pipette_order is None:
        stock_to_pipette_order = directions[0].keys()

    # Checking if the machine has tips attached prior
    if small_pipette.has_tip:
        small_pipette.drop_tip()
    if large_pipette.has_tip:
        large_pipette.drop_tip()
    pipette = small_pipette
    for i, stock_name in enumerate(stock_to_pipette_order):
        for stock_index, stock_instructions in directions.items():
            single_stock_instructions = stock_instructions[stock_name]
            stock_volume_to_pull = single_stock_instructions[
                'Stock Volume']
            stock_position_to_pull = single_stock_instructions[
                'Stock Position']
            destination_well = single_stock_instructions[
                'Destination Well Position']

            if stock_volume_to_pull == 0:
                pass
            elif small_pipette.min_volume <= stock_volume_to_pull <= \
                    small_pipette.max_volume or small_pipette.max_volume <= \
                    stock_volume_to_pull <= large_pipette.min_volume:

                if pipette == large_pipette and pipette.has_tip is True:
                    # Returning tip if other pipette has tip
                    pipette.return_tip()
                pipette = small_pipette
                tiprack = small_tiprack

                if 'mix_before' in kwargs.keys():
                    vol_to_mix = kwargs['mix_before'][1]
                    if vol_to_mix > pipette.max_volume:
                        kwargs['mix_before'] = (kwargs['mix_before'][0],
                                                pipette.max_volume)
                    else:
                        pass
                if 'mix_after' in kwargs.keys():
                    vol_to_mix = kwargs['mix_after'][1]
                    if vol_to_mix > pipette.max_volume:
                        kwargs['mix_after'] = (kwargs['mix_after'][0],
                                               pipette.max_volume)
                    else:
                        pass

                if kwargs['new_tip'] == 'never':
                    if pipette.has_tip is False:
                        pipette.pick_up_tip(tiprack[i])

                pipette.transfer(stock_volume_to_pull,
                                 stock_position_to_pull,
                                 destination_well,
                                 **kwargs)
                if delay_after != 0:
                    protocol.delay(seconds=delay_after)
                else:
                    pass

                if cleaning:
                    execute_cleaning_protocol(
                        loaded_labware_dict, pipette, protocol)
            # ------------------------------------------------------ #
            elif large_pipette.min_volume <= stock_volume_to_pull:
                if pipette == small_pipette and pipette.has_tip is True:
                    pipette.return_tip()

                tiprack = large_tiprack
                pipette = large_pipette

                if 'mix_before' in kwargs.keys():
                    vol_to_mix = kwargs['mix_before'][1]
                    if vol_to_mix > pipette.max_volume:
                        kwargs['mix_before'] = (kwargs['mix_before'][0],
                                                pipette.max_volume)
                    else:
                        pass
                if 'mix_after' in kwargs.keys():
                    vol_to_mix = kwargs['mix_after'][1]
                    if vol_to_mix > pipette.max_volume:
                        kwargs['mix_after'] = (kwargs['mix_after'][0],
                                               pipette.max_volume)
                    else:
                        pass

                if kwargs['new_tip'] == 'never':
                    if pipette.has_tip is False:
                        pipette.pick_up_tip(tiprack[i])

                pipette.transfer(stock_volume_to_pull,
                                 stock_position_to_pull,
                                 destination_well,
                                 **kwargs)
                if delay_after != 0:
                    protocol.delay(seconds=delay_after)
                else:
                    pass

                if cleaning:
                    execute_cleaning_protocol(
                        loaded_labware_dict, pipette, protocol)
            else:
                raise AssertionError('Pipettes not suitable for volume',
                                     stock_volume_to_pull)
        if small_pipette.has_tip is True:
            small_pipette.drop_tip()
        if large_pipette.has_tip is True:
            large_pipette.drop_tip()

    for line in protocol.commands():
        print(line)

    # Keeping track of execution time. Will print total run time in minutes
    end = time.time()
    time_consumed = end-start
    print("This protocol took \033[1m{}\033[0m minutes to execute".format(
        np.round(time_consumed/60, 3)))


def transfer_from_destination_to_final(protocol, loaded_labware_dict,
                                       experiment_dict, number_of_samples):
    """
    This function will take the already loaded dictionary and load more
    labware, specfically made for a final transfer from the destination sample
    plates to another plate. The reason for this final transfer is to allow
    samples to be made at any volume or at least a close enough volume and
    then moved to a secondary plate to be analyzed at the sample
    quantity (important for things like path lengths). This could theoretically
    be used independently from an initial sample creation, would just need to
    initialize the loading of labware. The reason why this could be useful is
    because the deck is limited in space so creating the samples and having
    their final transfer labware all on the deck at the same time could pose
    a constraint, however unlikely as typically you will be transfering into
    a smaller vessel with more wells than the original synthesis vessel.

    Parameters
    -----------


    Returns
    --------
    """

    dest_wells = loaded_labware_dict['Destination Wells']
    stock_wells = loaded_labware_dict['Stock Wells']
    small_pipette = loaded_labware_dict['Small Pipette']
    large_pipette = loaded_labware_dict['Large Pipette']

    # Loading the final transfer labware

    final_transfer_plate_names = experiment_dict[
        'OT2 Single Transfer From Dest Labwares']
    final_transfer_plate_slots = experiment_dict[
        'OT2 Single Transfer From Dest Slots']

    final_transfer_plates_objects = object_to_object_list(
        protocol, final_transfer_plate_names, final_transfer_plate_slots)
    final_transfer_wells = object_list_to_well_list(
        final_transfer_plates_objects)
    transfer_volume = float(experiment_dict[
        'OT2 Single Transfer From Dest Volume (uL)'])

    assert len(final_transfer_wells) >= number_of_samples, \
        'The number of samples exceeds the number of final destination wells'

    pipette = determine_pipette_tiprack(
        transfer_volume, small_pipette, large_pipette)

    pipette.flow_rate.aspirate = experiment_dict[
        'OT2 Single Transfer Pipette Aspiration Rate (uL/sec)']
    pipette.flow_rate.dispense = experiment_dict[
        'OT2 Single Transfer Pipette Dispense Rate (uL/sec)']
    pipette.well_bottom_clearance.dispense = experiment_dict[
        'OT2 Single Transfer From Dest Bottom Dispensing Clearance (mm)']
    pipette.well_bottom_clearance.aspirate = experiment_dict[
        'OT2 Single Transfer From Dest Bottom Aspirating Clearance (mm)']

    sample_final_location = []

    for well_index in range(number_of_samples):
        pipette.transfer(transfer_volume, dest_wells[well_index],
                         final_transfer_wells[well_index], new_tip='always')
        sample_final_location.append(final_transfer_wells[well_index])
    for line in protocol.commands():
        print(line)
    return sample_final_location


def rearrange_2D_list(nth_list):
    """
    Rearranges information from a 2D_list of length m with entries of length n
    to an outer array of length n, with entries of length m. Each entry now
    holds the ith entry of original entry in a new entry.
   [[a1,b1,c1],[a2,b2,c2]] => [[a1,a2],[b1,b2],[c1,c2]],
    making it easier to handle for cases like dataframes.

    Parameters
    -----------


    Returns
    --------

    """
    list_rearranged = []
    for i in range(len(nth_list[0])):
        ith_of_each_sublist = [sublist[i] for sublist in nth_list]
        list_rearranged.append(ith_of_each_sublist)
    return list_rearranged


def check_for_distribute(list1, min_val, max_val):
    """
    """
    return(all(max_val >= x >= min_val or x == 0 for x in list1))


def pipette_check(volume_df, pipette_1, pipette_2):
    """
    Given volumes along with two pipettes in use, will ensure the volumes of
    the pipette ranges are able to be cover the volumes

    Parameters
    -----------


    Returns
    --------
    """

    volume_df = isolate_common_column(volume_df, 'stock')
    if pipette_1.max_volume < pipette_2.max_volume:
        small_pipette = pipette_1
        large_pipette = pipette_2

    if pipette_1.max_volume > pipette_2.max_volume:
        small_pipette = pipette_2
        large_pipette = pipette_1
    assert volume_df[(volume_df == 0) | (volume_df >= small_pipette.min_volume)
                     ].notnull().all().all(), \
        'Pipettes do not cover appropiate volume ranges'


def labware_check_enough_wells(volumes, loaded_labware_dict):
    """
    Will check prior to simulation if labware is appropiate in terms of total
    volume and if enough wells are available.
    Volumes to be in dataframe.
    Assumes all of destination labware are the same.

    Parameters
    -----------


    Returns
    --------
    """

    destination_wells = loaded_labware_dict['Destination Wells']
    assert len(destination_wells) >= len(volumes), \
        'There is not enough wells available to make ' + str(len(volumes)) + \
        ' samples. There are only ' + str(len(destination_wells)) + \
        ' wells available.'


def labware_check_enough_volume(volumes_df, loaded_labware_dict):
    """
    Will check prior to simulation if labware is appropiate in terms of total
    volume and if enough wells are available.
    Volumes to be in dataframe.
    Assumes all of destination labware are the same.

    Parameters
    -----------


    Returns
    --------
    """

    destination_wells = loaded_labware_dict['Destination Wells']
    # well = str(destination_wells[0])
    well_volume = float(destination_wells[0].max_volume)
    total_sample_volumes = volumes_df.sum(axis=1)

    assert (total_sample_volumes <= well_volume).all(), \
        'Sample volumes are exceeding max destination well volume of ' + \
        str(well_volume) + 'uL'


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
    """
    Parameters
    -----------


    Returns
    --------
    """
    cols = df.columns
    common_string_cols = [col for col in cols if common_string in col]
    final_df = df.copy()[common_string_cols]
    return final_df

# ##################### Require Further Testing ##################### #


def range_gap(small_pipette, pipette_2):
    """
    Parameters
    -----------


    Returns
    --------
    """
    if p1_max >= p2_min:
        print('Pipette range complete')
    else:
        print('Pipette Range Incomplete, gap exist between following volumes:',
              p1_max, 'and', p2_min)


def find_max_dest_volume_labware(experiment_csv_dict,
                                 custom_labware_dict=None):
    """
    Using the stock labware name from the csv, loads the appropiate labware
    from both a custom and the native libary and determines the maximum volume
    for one stock labware well. Assumes all labware is all identical.

    Parameters
    -----------


    Returns
    --------
    """
    # Protocol encapsulated as only need an instance to simualte and toss
    if custom_labware_dict:
        protocol = simulate.get_protocol_api('2.8',
                                             extra_labware=custom_labware_dict)
    else:
        protocol = simulate.get_protocol_api('2.8')
    stock_plate = protocol.load_labware(
        experiment_csv_dict['OT2 Destination Labwares'][0],
        experiment_csv_dict['OT2 Destination Labware Slots'][0])
    stock_plate_rows = [well for row in stock_plate.rows() for well in row]
    stock_plate_well_volume = stock_plate.__dict__[
        '_well_definition']['A1']['totalLiquidVolume']
    return stock_plate_well_volume


def find_max_stock_volume_labware(experiment_csv_dict,
                                  custom_labware_dict=None):
    """
    Using the stock labware name from the csv, loads the appropiate labware
    from both a custom and the native libary and determines the maximum volume
    for one stock labware well. Assumes all labware is all identical.

    Parameters
    -----------


    Returns
    --------
    """
    # Protocol encapsulated as only need an instance to simualte and toss
    if custom_labware_dict:
        protocol = simulate.get_protocol_api('2.8',
                                             extra_labware=custom_labware_dict)
    else:
        protocol = simulate.get_protocol_api('2.8')
    stock_plate = protocol.load_labware(
        experiment_csv_dict['OT2 Stock Labwares'][0],
        experiment_csv_dict['OT2 Stock Labware Slots'][0])
    stock_plate_rows = [well for row in stock_plate.rows() for well in row]
    stock_plate_well_volume = stock_plate.__dict__[
        '_well_definition']['A1']['totalLiquidVolume']
    return stock_plate_well_volume
