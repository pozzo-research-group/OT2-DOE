import time
import string
import numpy as np
import pandas as pd

def get_Hcell_labware(loaded_dict):

    dest_lab= loaded_dict['Destination Wells']

    h_cell= []
    wellplates=[]
    for row in dest_lab:
        if 'hcell' in str(row):
            h_cell.append(row)
        else:
            wellplates.append(row)

    # Organize the well in the H-cell list to be in a column-wise fashion
    h_cell = rearrange_hcell_wells(h_cell)

    # Group the sample wells corresponding to each H-Cell.
    # In this case, each H-cell compartment has a dedicated row(i.e., row A on plate 1 & plate 2)
    number_of_hcells= len(h_cell)//2

    wellplates = get_Hcell_sample_wells(wellplates, number_of_hcells)


    return h_cell, wellplates

def rearrange_hcell_wells(h_cell):

    order = ['A1', 'B1', 'A2', 'B2']

    h_cell_plates = len(h_cell)//4
    
    new_hcell = []
    for i in range(h_cell_plates):    
        for well in order:
            for well_ in h_cell[i * 4 : (i + 1) * 4]:
                if well in str(well_):
                    new_hcell.append(well_)

    return  new_hcell

def get_Hcell_sample_wells(wellplates, number_of_hcells):
    
    #assuming always using 96 wellplate
    n_plates = len(wellplates)//96
    row_letter = list(string.ascii_uppercase[:8])
        
    sample_wells = []
         
    if number_of_hcells ==4:
        for letter in row_letter:
            wells= []
            for row in wellplates:
                if letter in str(row).split(' ')[0]:
                    wells.append(row)
            sample_wells.append(wells)
    else:
        for i in range(n_plates):
            for letter in row_letter:
                wells= []
                for row in wellplates[i * 96 : (i + 1) * 96]:
                    if letter in str(row).split(' ')[0]:
                        wells.append(row)
                sample_wells.append(wells)

    return sample_wells


def get_time_schedule(total_time, interval_time, interval_frequency):

    assert sum(interval_time)== total_time, 'The total experimental time and interval time indicated do not match'
    assert len(interval_time) == len(interval_frequency), 'The total number of indicated intervals and frequencies do not match.'

    schedule = []
    delays= []
    schedule.append(0)# sample aliquot at time zero
    delays.append(0)# sample aliquot at time zero
    hr= 0
    for i, time in enumerate(interval_time):
        instances = time//interval_frequency[i]
        for n in range(1, instances+1):
            hr= hr+interval_frequency[i]
            schedule.append(hr)
            delays.append(interval_frequency[i])

    return schedule, delays # in hrs

def get_hcell_name(h_cell):

    h_cell_dict= {}
    n_hcell = len(h_cell)//2
    h_cell_name = []
    for i in range(n_hcell):
        h_cell_name.append('H{}_1'.format(i+1))
        h_cell_name.append('H{}_2'.format(i+1))

    for i, cell_well in enumerate(h_cell):
        h_cell_dict[h_cell_name[i]]= cell_well

    return h_cell_name, h_cell_dict

def get_sample_schedule(h_cell_name, sample_wells, time_schedule, delay_time):

    data= {}
    for i, name in enumerate(h_cell_name):
        data[name] = sample_wells[i]
    sample_schedule = pd.DataFrame(data)
    final_schedule = sample_schedule.truncate(after=len(time_schedule)-1)
    final_schedule['Time_Stamp_hr'] = list(map(float,time_schedule))
    final_schedule['Delay_hr'] = list(map(float,delay_time))
    final_schedule['Delay_min'] = [t *60. for t in delay_time]

    return final_schedule

def H_cell_protocol(protocol, loaded_labware_dict,
                    sample_schedule, h_cell_info, aliquot_volume=20,
                    sample_dilution_volume=180,
                    max_stock_vol = 17, log_file_info= {}, log_filename='test',
                    dye_well_name = None, dye_volume = None):
    """
    Parameters
    -----------
    Returns
    --------
    """

    ## Create log file to keep track of the protocol steps

    log_file = open(log_filename+ '.txt', 'a')

    log_file.write('Author: {}\n'.format(log_file_info['author']))
    log_file.write('Sample: {}\n'.format(log_file_info['sample_name']))
    log_file.write('Membrane: {}\n'.format(log_file_info['hcell_membrane']))
    log_file.write('Solvent: {}\n'.format(log_file_info['solvent']))
    log_file.write('Restock: {}\n'.format(log_file_info['restock_solvent']))
    log_file.write('----------------------------------------------------------------\n')

    protocol.home()
    start = time.time()

    start_message = 'experiment started: {}'.format(time.ctime())
    print(start_message)

    log_file.write(start_message)
    log_file.write('\n')

    log_file.close()

    small_pipette = loaded_labware_dict['Small Pipette']
    small_tiprack = loaded_labware_dict['Small Tiprack']
    large_pipette = loaded_labware_dict['Large Pipette']
    large_tiprack = loaded_labware_dict['Large Tiprack']

        # Checking if the machine has tips attached prior
    if small_pipette.has_tip:
        small_pipette.drop_tip()
    if large_pipette.has_tip:
        large_pipette.drop_tip()

    hcell_col= [col for col in sample_schedule.columns.to_list()
                if col.startswith('H') ]

    # variable to keep track of overall water volume already dispensed
    # this is set to avoid using an empty stock well. Will switch after
    # volume is equal to "max_stock_vol"-
    water_vol= 0
    # well # for the stock labware. will switch once volume limit is reached
    ww=0

    h_cell_col = [ col for col in sample_schedule.columns if col.startswith('H') ]

    # placeholder for correct time delay. Will be used to adjust the delay to
    # account for the overall execution time of each iteration
    # This should ensure that the time stamp is taken from the beginning of
    # each aliquot iteration
    elapsed_time= False
    time_stamp_schedule = np.zeros((len(sample_schedule), len(h_cell_col)))
    top_h_cells = [h for h in h_cell_info.keys() if "_1" in h]
    bottom_h_cells = [h for h in h_cell_info.keys() if "_2" in h]
    
    for i in range(len(sample_schedule)):

        iteration_message= '------------------------- Iteration {}-------------------------'.format(i)

        log_file = open(log_filename+ '.txt', 'a')
        log_file.write(iteration_message)
        log_file.write('\n')
        log_file.close()

        print(iteration_message)
        # this will be automatically switched to a different stock well
        # once max volume is reached
        water_well = loaded_labware_dict['Stock Wells'][ww]
        dye_well = loaded_labware_dict['Stock Wells'][dye_well_name]
        sample_wells = sample_schedule.iloc[i]

        # apply delay to sampling
        if elapsed_time != False:
            new_time= (sample_wells['Delay_min']- elapsed_time)
            print('Corrected Delay {:.2f}'.format(new_time)) 
            protocol.delay(minutes=(sample_wells['Delay_min']- elapsed_time))
        else:
            protocol.delay(minutes=sample_wells['Delay_min'])
        
        # Distribute water to the sample wellplate first to ensure that when
        # the sample aliquot is dispensed it will not stick to the aluminum foil
        
        tiprack = large_tiprack
        pipette = large_pipette
        
        s= time.time() # start time of iteration
        
        pipette.pick_up_tip(tiprack[i])
        # this takes care of all the H-cells and no need for a loop

        pipette.transfer(sample_dilution_volume,
                         water_well,
                         [sw.top(-3) for sw in sample_wells[hcell_col].to_list()],
                         new_tip='never', blow_out=True,
                         blowout_location= 'destination well')
        pipette.return_tip()
        # take care of aliquot sampling of H-cell next      
        

        pipette = small_pipette
        tiprack = small_tiprack

        if pipette == large_pipette and pipette.has_tip is True:
                # Returning tip if other pipette has tip
                pipette.return_tip()

                
        #TODO FIX THIS SECTION!!! 
#         if i ==0 and dye_volume != None:
#                 for x in range(len(top_h_cells)):
#                     pipette.transfer(dye_volume,
#                                      dye_well.bottom(10),
#                                      h_cell_info[top_h_cells[x]],
#                                      new_tip= 'always', blow_out=True,
#                                      blowout_location= 'destination well')
                    
#                     dye_message = "Dye added to {} at {}".format(top_h_cells[x], time.ctime())
                    
#                     pipette = small_pipette
#                     tiprack = small_tiprack

#                     pipette.transfer(aliquot_volume, h_cell_info[top_h_cells[x]].top(-60),
#                                      sample_wells[n].top(-7), mix_after=(8,20),
#                                      blow_out=True, blowout_location= 'destination well')
                                          
#                     aliquot_message = 'Aliquot # {} from {} was sampled at {}'.format(
#                         i, top_h_cells[x], time.ctime())
            
#                     time_stamp_schedule[i,m] = time.time()
                

        for m,n in enumerate(h_cell_col):
            # start with the aliquot sampling from ALL the H-cell compartments
            # added a mixing step when samples are dispensed in the sample labware
            # mixing step: aspirate/dispense 20 uL 8 times
            
            
            
            
            
            
            pipette.transfer(aliquot_volume, h_cell_info[n].top(-60),
                             sample_wells[n].top(-7), mix_after=(8,20),
                             blow_out=True, blowout_location= 'destination well')

            aliquot_message = 'Aliquot # {} from {} was sampled at {}'.format(
                i, n, time.ctime())
            
            time_stamp_schedule[i,m] = time.time()
            
            log_file = open(log_filename+ '.txt', 'a')

            log_file.write(aliquot_message)
            log_file.write('\n')
            log_file.close()
            print(aliquot_message)

            water_vol += aliquot_volume

        tiprack = large_tiprack
        pipette = large_pipette

        # replenish H-cell with water using the same aliquot volume amount
        # this takes care of all the H-cells and no need for a loop

        pipette.pick_up_tip(tiprack[i])

        pipette.transfer(aliquot_volume,
                         water_well.bottom(5),
                         [hw.top(-30) for hw in list(h_cell_info.values())],
                         new_tip='never', blow_out=True,
                         blowout_location= 'destination well')

        e = time.time() # end time for the current experimental iteration
        # Total elapsed time  in minutes from the start of the current
        # experimental iteration
        elapsed_time= round(e-s)/60
#         elapsed_time = 0.5 + 5* i # test time in minutes

        water_vol += (sample_dilution_volume + aliquot_volume)*8

        if water_vol >= max_stock_vol:
            ww += 1
            water_vol = 0
        else:
            pass

        log_file = open(log_filename+ '.txt', 'a')
        water_message= 'The H-cells were replenished with water at {}'.format(
            time.ctime())
        print(water_message)

        log_file.write(water_message)
        log_file.write('\n')

        log_file.close()

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
    
    # create time stamp dataframe and save it to a csv file with the same name
    # as the log file with '_time_stamps' in the name 
    time_stamp_df = pd.DataFrame( time_stamp_schedule, columns= h_cell_col)
    time_stamp_df.to_csv(log_filename+'_time_stamps.csv')