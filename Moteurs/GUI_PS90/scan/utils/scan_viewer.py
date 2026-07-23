"""
This file contains the code for viewing scan results.
"""


import os
import matplotlib.pyplot as plt
import numpy as np
from classes import path_import as path

os.chdir(path.FILE_LOCATION+"/out/") # Scan output folder

from classes.HDO4034A.HDO4034A import HDO4034A

T=[]
Y=[]

with open('move_y/move_y_(0.0,3.3,0.0,0.0).csv', 'r') as f: # open the csv file
    lines = f.readlines()[1:] # skip the first line which contains the coordinates
    for line in lines:
        elt=line.split(",")
        # collect the data in the T and Y lists
        T.append(float(elt[0]))
        Y.append(float(elt[1]))


# Display the waveform using matplotlib
plt.figure()
plt.plot(T,Y)
plt.xlabel("Time (µs)")
plt.ylabel("Amplitude (V)")
plt.title(f"Waveform - {HDO4034A.MODEL_NAME} C1")
plt.grid(True)
plt.tight_layout()
plt.show()
