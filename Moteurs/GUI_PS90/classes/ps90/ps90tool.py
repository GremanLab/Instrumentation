# -*- coding: utf-8 -*-
"""
Created on Wed Aug 17 14:06:45 2016

This file = example of manipulation of ps90.dll

@author: as
"""

#ps90tool This is a demo application for the PS 90 controller.
#   retval = ps90tool( COM_port, axis_no, velocity, distance, params_export ) moves the attached axis...
#   function parameters 
#   parameter 1 - COM port
#   parameter 2 - axis number (1-3)
#   parameter 3 - positioning velocity in Hz
#   parameter 4 - distance for positioning in mm, distance=0 - reference run
#   parameter 5 - mode for data export: 0 - nothing to do, 1 - save, 2 - load

import ctypes
#from ctypes import *
from ctypes import windll, c_double
#from ctypes import windll, c_double, create_string_buffer
import sys

nComPort=3
nAxis=1
dPosF=30000.0
dDistance=10.0 
nExport=0

if (len(sys.argv) != 6):
    print("ps90tool.py <COM port> <axis no.> <velocity> <distance> <params_export>")
    print("e.g. ps90tool.py 3 1 30000 10 0")
    sys.exit(0)
else:
    # set parameters *************
    nComPort=int(sys.argv[1])
    nAxis=int(sys.argv[2])
    dPosF=float(sys.argv[3])
    dDistance=float(sys.argv[4])
    nExport=int(sys.argv[5])
    # ****************************

# load library
# give location of dll
mydll = windll.LoadLibrary("C:/Users/tchemla/Documents/gestion_moteur/hydrophone_handling/classes/ps90/ps90.dll")

# open virtual serial interface (or serial interface via tcp/ip socket)
if nComPort==0: # find first connected control unit
    result1=mydll.PS90_SimpleConnect(1, b"") # ANSI/Unicode !!
elif nComPort==-1: # find the first connected control unit via tcp/ip socket (localhost, port=1200)
    result1=mydll.PS90_SimpleConnect(1, b"net") # ANSI/Unicode !!
else: # connect control unit with defined COM port
    result1=mydll.PS90_Connect(1, 0, nComPort, 9600,0,0,0,0)

# define constants for calculation Inc -> mm
#result1=mydll.PS90_SetStageAttributes(1, nAxis, c_double(1.0), 200, c_double(1.0))

"""
# get firmware version (string test)
str_data = create_string_buffer(20) # ANSI/Unicode !!
result1=mydll.PS90_GetBoardVersion(1, str_data, 20)
print( "Version=%s" %(str_data.value.decode("utf-8")) )
"""

# load param file
if nExport==2:
    result1=mydll.PS90_LoadTextFile(1, nAxis, b"ps90_params_export.txt") # ANSI/Unicode !!

# initialize axis
result1=mydll.PS90_MotorInit(1, nAxis)

# save param file
if nExport==1:
    result1=mydll.PS90_SaveTextFile(1, nAxis, b"ps90_params_export.txt") # ANSI/Unicode !!

# set target mode (0 - relative)
result1=mydll.PS90_SetTargetMode(1, nAxis, 0)

# set velocity 
if dPosF > 0.0:
    result1=mydll.PS90_SetPosF(1, nAxis, c_double(dPosF))

# check position
PS90_GetPositionEx=mydll.PS90_GetPositionEx
PS90_GetPositionEx.restype = ctypes.c_double
result2=PS90_GetPositionEx(1, nAxis)
print( "Position=%.3f" %(result2) )

# start positioning
if dDistance==0.0: # go home (to start position)
	result1=mydll.PS90_GoRef(1, nAxis, 4)
else: # move to target position (+ positive direction, - negative direction)
	result1=mydll.PS90_MoveEx(1, nAxis, c_double(dDistance), 1)

# check move state of the axis
print("Axis is moving...")
state = mydll.PS90_GetMoveState(1, nAxis)
while state > 0: 
    state = mydll.PS90_GetMoveState(1, nAxis)
    
print("Axis is in position.")

# check position
result2=PS90_GetPositionEx(1, nAxis)
print( "Position=%.3f" %(result2) )

# close interface
result1=mydll.PS90_Disconnect(1)
