# OT2-DOE
A group of python modules and notebooks made for high throughput measurement and analysis of samples made through a liquid handling robot (Opentrons or OT2). 

    Note: As of 02/01/22 this repo is still being developed with new functions, bugs and documentation updated constantly. 
    Feel free to address issues in the issues tab or edit them yourself so long as you document and justify the change. 
    Currently the framework is still not entirely up and running as testing allows for adaptation for the groups use. 

Here is an example where this framework could be implemented for increased discovery. 

![image](https://user-images.githubusercontent.com/52507997/112563961-91c33680-8d97-11eb-890d-1a637d8c0f24.png)


## Introduction
Automatic handling robots (ALH) are one of many high throughput tools that allow for increases discovery of solution based chemistry. If it can be moved by a human using a pipette a ALH can do the same function faster and more reproducible. Our ALH being used is the Opentrons 2, a low cost ALH which has interchangable pipette modules, custom labware, and is controlled through Python. High throuhgput synthesis and charecterization of these solution based systems requires an organized framework consisting of planning, processing and presentation modules. Under all of this is the whole premise for a framework for a design of experiments. The packages and adjacent notebook start this frame work with the main three packages consisting of **Prepare**, **Process**, and **Present**. Each package can contain multiple modules which are relvant to that specfic process such as a module for a processing plate reader data, or a module revovling around prapring sample volumes. In theory these packages should get you from the point of planning an experiment all the way to modeling and presenting the information. 

## To get started
You can install this package using the GitHub repository in following steps: 
* In your terminal, run git clone https://github.com/pozzo-research-group/OT2-DOE.git
* Change the directory to `OT2_DOE` root directory, by running `cd OT2_DOE`
* (Recommended)- Create an environmetn using the provided `environment.yaml` file. To do so, run the following lines:

	`conda install --name OT2_DOE --file environment.yml`
	
	`conda activate OT2_DOE`
* Install the package by running `python setup.py install` in your terminal


## DOE Package Framework:

### Plan: This package contains is to modules which are related to planning the experimental space such as samples compositions, volumes, stocks info and other information prior to OT2 commands. 

Currently the workflow of experimental planning in a notebook is generally as follows (note: all handling is done through pandas DataFrames): 

1. A csv or excel file is loaded as a dictionary. This file will contain all the instructions for both the planning of the experimental space along with the information regarding OT2 specfication. Sample and stock information often include: compositional space (i.e. numpy linspaces), density, molecular weight, among others. 
2. Using loaded information a sample area is created, most easily this is done by creating a grid from a group of compositonal linspaces. 
3. Using the created sample area along with component and stock information (i.e. density, MW...) calculate the volumes required from each stock.	
	* This step is the most tricky as it can be quite specfic to your system (i.e. one stock has 3 components, common solvent among stocks....). It is still being tested which way to go with this, either a series of wrapper to determine the required information for a conversion from composition to volume or seperate specfic functions. For now feel free to make your own functions and add them as new or into an existing module.  
4. The sample area need to filtered depending on two types of constraints: unity and volume
	* Unity: This applies to when a the compositions of a unit must add to one, if above then remove sample.
	* Volume: This is instrument and protocol dependent, where you need to filter out any sample based your specific constraints
	* "Catchers" should be implemented here to identify why samples are being filtered out and make the appropiate changes to an item like stock concentration or total sample volume. We should not be constraining the compostional space if unnecessary. 
5. Once you have your Dataframe of compositions and volumes for each sample you are ready to move onto the **Preparing** stage where you will use OT2 commands.
	* Note: It is advised you plot and vertify your compositional space in some meaningful way to ensure you are comfortable with the selected space


### Prepare: This package contains is to modules which are related to preparing the samples created in the planning phase. 

Mainly this package will contain modules of protocol specfic OT2 commands. There are countless things one can specify in OT2 such as the aspiration/dispensing speed, blow out after dispensing, mixing sample, touching edge of well, among other. 

The OT2 has its own package which main use is for calling a protcol object which is the master behind all OT2 controls. This protocol allows you to assign and create labware and insturment object. The protocol is a global varaible that essentially remembers everything you did, say you assign a plate to slot 1 on the OT2 deck one would call protocol.load_labware(labware_name, labware_slot), if you tried calling this again using this same protocol you would get an error letting you know slot 1 was taken. We can use this memory of the protocol object to create it once and feed it into a countless number of function, use it to create other objects and execute commands, and use it again having confidence we will not overlap or wrongly label something. 

The proposed framework of OT2 commands is as follows:
1. Create a protocol object (simulate or execute)
2. Using a common function load all labware as specified from the initially loaded csv/excel dictionary plan. 
	* Currently `OT2Commands.loading_labware` will load all the necessary instrumentation and labware into a dictionary for which then we can feed into counltess customized functions in Step 3. Mainly loading pipettes and destination/stock wells. 
	* It should be noted that wells from multiple plates are grouped together into one single list/array and are placed in row order (read more here: https://docs.opentrons.com/v2/new_labware.html) as to align with other lab equipment. For example two labware objects L1 and L2 when wells are called are two seperate list of [L1A1, L1A2,...L1F8] and [L2A1, L2A2,...L2F8], instead we combine this into one [L1A1, L1A2,..L2F8] to make it easier and not need to switch. 
	* For the most part you will only need a stock and destionation list of wells, as most of the time the labware between either stock or destination will be the same.
3. Using the loaded dictionary along with the original protocol object, we can now run a customized pipette command function. Typically this consist of:
	* First assigning the pipettes "coverage range". This is to verify the pipettes are appropiate for the volumes and to assign then as either the smaller or larger pipette. The logic of small vs large pipette allows for the use of the smaller higher resolution pipette whenever possible and to reserve the larger pipette only when truly needed. 
	* Determining the range of wells of that will cover a specfic stock position, this is can be outside of the function to verify. `OT2Commands.stock_ranges()` does this by looking at the max volume (or user input if not utilziing max volume) volume of the stock labware and the volumes to pipette and returns the stock arrangement (i.e. 2 stocks A, one stock B, in row order). 
	* Select whether a transfer or dispense option is appropiate. 
4. IMPORTANT: Using the information of the dispensed well, record this information and add it to the dataframe in someway. Currently a function exist that will take information of a well that is formatted `A1 of Falcon 48 Well Plate 1500 ÂµL on 2` and is spliced for the well, slot and plate information, given the time and a user-specified keyword a UID is made as well. 
5. Once you have added the pipetting/final sample information to the original complete dataframe (which contained the compoisitons and volumes), the DataFrame is now complete for the experimental portion and can now be exported and saved. 
6. Broken: Google Drive implementation, the issue around credentials is tricky since each person would need their own...module currently exist with working function but more documentation and testing is needed. 
	
### Process: This package contains is to modules which are related to preparing the samples created in the planning phase. 

This package with primarily hold instrumentation and modeling modules with functions relating directly to the extracting, organizing and processing the information from these instruments. 

Example of this include modules for: 
* Microplate Reader (PlateReader): Works with data from the microplate reader, extracting from excel file formatting as dataframe and adding it to the appropiate DataFrame from the **Preparing** step. Would also contain functions to handle these dataframe structures such as extracting a spectra dataframe from the overall dataframe based on a unit keyword or plotting these crudely. 
* Dynamic Light Scatter Zetasizer (DynamicLightScatter): 
* Gaussian Process Regression Modeling (GPModeling): 
