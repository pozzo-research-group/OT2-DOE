## OT2 folder (OT2_DOE)

This folder contains the code used to run an OT-2 liquid handing robot in the paper "Autonomous retrosynthesis of gold nanoparticles via spectral shape matching".

There are many files in the folder, but only a few are necessary for it to function. The main files are:

- Run OT2.ipynb: This is the jupyter notebook used to simulate and run the protocol. There are additional instructions in the notebook for anyone who wants to use it. 
- New_Testing_Protocol_Generalized.csv: This is a csv file that determines the configurations of the OT-2 such as the labwares on the slot or the pipettes that are attached 

## Folder Contents (OT2_DOE)

### Custom Labware 
This folder contains information on the dimensions of the labware used in the experiment. 

### Volumes 
This folder contains the volumes of each stock that were used to make the samples each iteration 

### Prepare
This folder contains code that is used to program the OT2 robot. The file that contains all this code is OT2Commands.py
