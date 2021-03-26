# phasIR
A group of python modules and notebooks made for high throughput measurement and analysis of samples made through a liquid handling robot (Opentrons or OT2). 

    Note: As of 03/25/21 this repo is still being developed with new functions, bugs and documentation updated constantly. Feel free to address issues in the issues tab or edit them yourself so long as you document and justify the change. Current the framework is still not entirely up and running as testing allows for adaptation for the groups use. 

![image](https://user-images.githubusercontent.com/52507997/112563961-91c33680-8d97-11eb-890d-1a637d8c0f24.png)


## Introduction
Automatic handling robots (ALH) are one of many high throughput tools that allow for increases discovery of solution based chemistry. If it can be moved by a human using a pipette a ALH can do the same function faster and more reproducible. Our ALH being used is the Opentrons 2, a low cost ALH which has interchangable pipette modules, custom labware, and is controlled through Python. High throuhgput synthesis and charecterization of these solution based systems requires an organized framework consisting of planning, processing and presentation modules. Under all of this is the whole premise for a framework for a design of experiments. The packages and adjacent notebook start this frame work with the main three packages consisting of **Prepare**, **Process**, and **Present**. Each package can contain multiple modules which are relvant to that specfic process such as a module for a processing plate reader data, or a module revovling around prapring sample volumes. In theory these packages should get you from the point of planning an experiment all the way to modeling and presenting the information. 

## Installation
    Note: These modules are to be placed in a package which should be installed thorugh a simple command -- in progess...

## DOE Package Framework:

### Prepare: This package contains modules which are relate to planning and preparing


#### The python package adopts the following two techniques to obtain the temperature profile of the samples and sample holder to determine the melting point of the samples:

1. Temperature profile through edge detection

* This method can be used for images(video frames) with high contrast and minimal noise which will allow for detection of edges of just the samples.
* The temperature profile of the samples and plate is determined by detecting the edges, filling and labeling them, and monitoring the temperature at their centroids.
* This technique can be adapted by using the functions `input_file` and `centroid_temp` from the `musicalrobot.edge_detection` module to load the recorded video and obtain the temperature profile of the samples and sample holder.

2. Temperature profile through pixel value analysis.

* This is an alternative technique for low contrast images(video frames). In some situations, the contrast between the image and sample maybe too low for edge detection, even with contrast enhancement.
* Alternatively, centroid location for each sample can be found by summing pixel values over individual rows and columns of the sample holder(well plate).
* This technique can be adapted by using the functions `input_file` and `pixel_temp` from the `musicalrobot.pixel_analysis` module to load the recorded video and obtain the temperature profile of the samples and sample holder.

#### Melting point determination

* An inflection is observed at the melting point in the temperature profile of the samples due to the following reasons
1. Change in thermal conductivity of the sample
2. Increase in thermal contact between the sample and the well plate
* The point of inflection in the temperature profile is determined by detecting the peak in the second derivative of the temperature profile. Since an analytical approach is used to determine the melting point, the temperature profile plots have to classified to eliminate plots with noise and without an inflection in them.
* The module `musicalrobot.data_encoding` can be used to classify the temperature profiles.

An example of adapting the above mentioned modules and functions using the `musicalrobot` package can be found in the ipython notebook `Tutorial.ipynb` found in the examples folder.

## For Development
* Install python version 3.6
* Clone the repository on your machine using git clone https://github.com/pozzo-research-group/phasIR.git . This will create a copy of this repository on your machine.
* Go to the repository folder using cd musical-robot.
* Install the python dependencies by using pip install -r requirements.txt
