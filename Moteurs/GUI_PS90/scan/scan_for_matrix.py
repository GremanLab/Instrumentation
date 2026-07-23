#!/usr/bin/env python3
"""
When you launch a scan with Matrix mode with the interface, this script is called to perform the scan. It is not meant to be run directly.

Warning : This file could not be used for a PS90 motor where the axes are different from :
- X 1
- Y 2
- Z 3
- R 4

"""

import os
import time
from tkinter import * 
import threading

# imports for a lot of functions used in this script: oscilloscope settings, motor settings, csv writing, break timer, path import, and display time
from scan.utils import osc_scan_settings as set_osc, write_csv as csvw
from scan.utils.break_timer import BreakTimer 
from classes import path_import as path
from classes.HDO4034A.HDO4034A import HDO4034A
from classes import display_time as dtime


# This function is called by the interface to perform a scan. It takes a lot of parameters, including the name of the scan, the output path, the path to the matrix file, the oscilloscope settings, and the motor instance. It also takes some callback functions for stopping and updating the scan.
def scan_for_matrix(name="scan",out_path=path.FILE_LOCATION+"/out/",
                    matrix_path=None,
                    osc_ip='169.254.27.102', hyd_chan='C1', exc_chan='C4', hyd_coup='D50', exc_coup='A1', sweep_nb=1, acq_sample_max=5000,
                    ps=None,stop_event=None,break_event=None,on_close=None,on_update=None, break_callbacks=None):

    ### Create output folder if it does not exist
    try:
        os.chdir(out_path+"/"+name) # Scan output folder
    except FileNotFoundError: # create the folder if it does not exist
        os.makedirs(out_path+"/"+name)
        os.chdir(out_path+"/"+name) # Scan output folder
    except Exception as e:
        print(f"Error while charging directory to {out_path}/{name}: {e}")
        on_close()
        return

    """Connections to instruments"""
    # Like we are already connceted to the engine due to the interface, we don't need to connect to it again. We just need to check if the instance is provided.
    if ps is None:
        print("Error: no motor instance provided")
        on_close()
        return

    # Connect to the oscilloscope
    IP_adress = osc_ip
    osc=HDO4034A()
    osc.open_connection(IP_adress)
    if osc.CONNECTION_STATUS=='closed':
        on_close()
        return

    """User settings"""
   
    # Setup oscilloscope for scan with correct settings
    if set_osc.osc_scan_settings(name,osc,hyd_chan,exc_chan,hyd_coup,exc_coup,sweep_nb,acq_sample_max):
        on_close()
        return

    # Count the number of steps in the matrix file to estimate the total duration of the scan
    file = open(matrix_path)
    count = 0
    for line in file:
        count+=1
    nbStepTot = count
    file.close()

    break_timer = BreakTimer()  # Initialize the break timer
    
    def leave_scan():
        """
        Leave the scan function
        """
        if break_timer.is_active():
            break_timer.stop()
        print("STOP")
        on_close()
        osc.close_connection()
        return

    def do_break():
        """
        Handle the break event
        """
        print("BREAK")
        break_event.set()
    
    def do_take_back():
        """
        Handle the take back event
        """
        print("TAKE BACK")
        break_event.clear()

    # If break_callbacks is provided, we set the on_break and on_take_back callbacks to the do_break and do_take_back functions defined above. This allows the interface to control the break and take back events during the scan.
    if break_callbacks is not None:
        break_callbacks['on_break'] = do_break
        break_callbacks['on_take_back'] = do_take_back

    # heart of the scan
    def run_scan():

        # start the timer to estimate the total duration of the scan
        start_timer=time.time()

        idStep=0 # initialize the step counter
        
        file_matrix=open(matrix_path) # open the matrix file containing the scan points
        for point in file_matrix:
            idStep+=1
            # get the coordinates of the point from the matrix file and move the motors to that position
            coords=point.split(",")
            X_pt=float(coords[0])
            Y_pt=float(coords[1])
            Z_pt=float(coords[2])
            if len(coords)>3: # if the matrix file contains a fourth coordinate for the R axis, we use it. Otherwise, we set R to 0.
                R_pt=float(coords[3])
            else:
                R_pt=0
            # move the motors to the specified coordinates and wait until they have finished moving
            ps.X.move_abs(X_pt)
            ps.Y.move_abs(Y_pt)
            ps.Z.move_abs(Z_pt)
            ps.R.move_abs(R_pt)
            while ps.X.state==1:
                pass
            while ps.Y.state==1:
                pass            
            while ps.Z.state==1:
                pass            
            while ps.R.state==1:
                pass

            # display the current step and the total number of steps, as well as the current coordinates of the motors
            print(f"{idStep} / {nbStepTot} : ({ps.X.pos},{ps.Y.pos},{ps.Z.pos},{ps.R.pos})")

            if stop_event.is_set(): # if the user has requested to stop the scan, we call the leave_scan function and return
                leave_scan()
                return
            if break_event.is_set(): # if the user has requested to pause the scan, we wait until the break_event is cleared. We also start the break timer if it is not already active.
                start_break_time=time.time()
            while break_event.is_set():
                if stop_event.is_set(): 
                    leave_scan()
                    return   # STOP works even if the scan is in break mode
                if not break_timer.is_active():
                    break_timer.start()
                    print("BREAK")
                time.sleep(0.1)

            if break_timer.is_active():
                break_timer.stop()
                print("TAKE BACK")

            # signal acquisition
            (T,Y)=osc.read_wave(osc.active_ch) 
    
            # we give result in a particular format to write it in a csv file
            data=[[round(ps.X.pos,2),round(ps.Y.pos,2),round(ps.Z.pos,2),round(ps.R.pos,2)]]
            data.append(Y)
            data.append(T)
    
            csvw.save_data(name,data) # write the data in a csv file
    
            # Display the estimated time remaining and the percentage of completion
            pourcent=((100*(idStep/nbStepTot))//1) 
            current_time = time.time()
            scan_time = current_time - start_timer - break_timer.elapsed(now=current_time)
            estimated = scan_time * (nbStepTot / idStep) * (100 - pourcent) / 100
            if on_update:
                on_update(pourcent, estimated)
            dtime.display_time(scan_time * (nbStepTot / idStep))
        
        end_timer=time.time() # the scan is finished now
        print("Total duration :" + dtime.display_time_str(end_timer-start_timer))
        print("With a break time of :" + dtime.display_time_str(break_timer.elapsed(now=end_timer)))

        on_close()  # close window and oscilloscope connection when the scan is finished
    
    # We run the scan in a separate thread to avoid blocking the interface. The thread is set as a daemon so
    scan_thread = threading.Thread(target=run_scan, daemon=True)
    scan_thread.start()
