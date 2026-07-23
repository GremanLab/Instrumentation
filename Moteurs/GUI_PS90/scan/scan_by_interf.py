"""
When you launch a scan with Point or Length mode with the interface, this script is called to perform the scan. It is not meant to be run directly.

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

# imports for a lot of functions used in this script: oscilloscope settings, motor settings, axes definitions, csv writing, break timer, path import, and display time
from scan.utils import axe_def, osc_scan_settings as set_osc, write_csv as csvw 
from classes import path_import as path
from classes.HDO4034A.HDO4034A import HDO4034A
from classes import display_time as dtime
from scan.utils.break_timer import BreakTimer

# This function is called by the interface to perform a scan. It takes a lot of parameters, including the name of the scan, the output path, the mode of the scan, the variables for the scan, the deltas for each axis, the oscilloscope settings, and the motor instance. It also takes some callback functions for stopping and updating the scan.
def scan_by_interf(name="scan",out_path=path.FILE_LOCATION+"/out/",mode=None,var1=None,var2=None,var3=None,delta_X:float=0.1,delta_Y:float=0.1,delta_Z:float=0.1,
                    osc_ip='169.254.27.102', hyd_chan='C1', exc_chan='C2', hyd_coup='D50', exc_coup='D50', sweep_nb=1, acq_sample_max=5000,
                    ps=None,stop_event=None,break_event=None,on_close=None,on_update=None, break_callbacks=None):
    
    ### Create output folder if it does not exist
    try:
        os.chdir(out_path+"/"+name) # Dossier de sortie du scan
    except FileNotFoundError: # create the folder if it does not exist
        os.makedirs(out_path+"/"+name)
        os.chdir(out_path+"/"+name) # Dossier de sortie du scan
    except Exception as e:
        print(f"Error while charging directory to {out_path}/{name}: {e}")
        on_close()
        return


    
    """Connections to instruments"""
    
    # Like we are already connceted to the engine due to the interface, we don't need to connect to it again. We just need to check if the instance is provided.
    if ps is None: # Check if the interface gives correctly the motor to this script
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

    #Movement speed of axes X,Y and Z
    for axis in [ps.X,ps.Y,ps.Z]:
        axis.vel = 3 # [mm/s]
        axis.acc = 1 # [mm/s²]

    axe,error=axe_def.axes_init(mode,var1,var2,var3,delta_X,delta_Y,delta_Z) #Creation of axes
    if error: # if there is an error in the axes definition, we close the oscilloscope connection and return
        osc.close_connection()
        on_close()
        return
    
    # Number of steps in each axis
    nbX=len(axe.x)
    nbY=len(axe.y)
    nbZ=len(axe.z)
    nbStepTot = nbX*nbY*nbZ

    
    optPath = True  # if True, the scan will be done in a snake-like pattern, which is faster than going back to the starting point after each line. If False, the scan will be done in a raster pattern.

    # set the oscilloscope settings for the scan. If the user cancels the settings, we close the oscilloscope connection and return.
    if set_osc.osc_scan_settings(name,osc,hyd_chan,exc_chan,hyd_coup,exc_coup,sweep_nb,acq_sample_max):
        osc.close_connection()
        on_close()
        return


    """ Scan """

    # We round the positions to the nearest 0.1mm, 0.01mm, etc. depending on the deltas of the scan
    round_pos=1
    while delta_X*10**round_pos%1 != 0 or delta_Y*10**round_pos%1 != 0 or delta_Z*10**round_pos%1 != 0:
        round_pos+=1

    # We create a BreakTimer instance to keep track of the time spent in break mode. This is used to estimate the remaining time of the scan.
    break_timer = BreakTimer()

    def leave_scan():
        """ 
        This function is called when the user wants to stop the scan. It stops the break timer if it is active, 
        closes the oscilloscope connection, and calls the on_close callback function.
        """
        if break_timer.is_active():
            break_timer.stop()
        print("STOP")
        on_close()
        osc.close_connection()
        return

    def do_break():
        """
        This function is called when the user wants to pause the scan. It sets the break_event, which will cause the scan to wait until the break_event is cleared.
        """
        print("BREAK")
        break_event.set()
    
    def do_take_back():
        """
        This function is called when the user wants to resume the scan. It clears the break_event, which will allow the scan to continue.
        """
        print("TAKE BACK")
        break_event.clear()


    # If the break_callbacks dictionary is provided, we set the on_break and on_take_back callbacks to the do_break and do_take_back functions, respectively. This allows the interface to control the break state of the scan.
    if break_callbacks is not None:
        break_callbacks["on_break"]     = do_break
        break_callbacks["on_take_back"] = do_take_back


    # heart of the scan
    def run_scan():
        # start the timer to estimate the total duration of the scan:
        start_timer=time.time()
        
        idStep=0 # initialize the step counter
        
        for idz in range(nbZ):
            print(f"idz ={idz+1} / {nbZ}") 
            #Moving
            ps.Z.move_abs(axe.z[idz])
            while ps.Z.state == 1: # wait until the Z axis has finished moving
                pass
            for idy in range(nbY):
                print(f"idy = {idy+1} / {nbY}")
                #Moving
                ps.Y.move_abs(axe.y[idy])
                while ps.Y.state==1: # wait until the Y axis has finished moving
                    pass
                for idx in range(nbX):
                    if stop_event.is_set(): # if the user has requested to stop the scan, we call the leave_scan function and return
                        leave_scan()
                        return

                    while break_event.is_set(): # if the user has requested to pause the scan, we wait until the break_event is cleared. We also start the break timer if it is not already active.
                        if stop_event.is_set():
                            leave_scan()  # STOP works even if the scan is in break mode
                            return
                        if not break_timer.is_active():
                            break_timer.start()
                        time.sleep(0.1)

                    if break_timer.is_active():
                        break_timer.stop()
      
                    print(f"idx = {idx+1} / {nbX}")
                    #Moving
                    ps.X.move_abs(axe.x[idx])
                    while ps.X.state==1: # wait until the X axis has finished moving
                        pass
                    # Signal acquisition
                    (T,Y)=osc.read_wave(osc.active_ch) 
    
                    # we give result in a particular format to write it in a csv file
                    data=[[round(ps.X.pos,round_pos),round(ps.Y.pos,round_pos),round(ps.Z.pos,round_pos),round(ps.R.pos,round_pos)]]
                    data.append(T)
                    data.append(Y)
    
                    csvw.save_data(name,data) # write the data in a csv file
    
                    # display the estimated time remaining and the percentage of completion
                    idStep+=1
                    pourcent=((100*(idStep/nbStepTot))//1) 
                    current_time = time.time()
                    scan_time = current_time - start_timer - break_timer.elapsed(now=current_time)
                    estimated = scan_time * (nbStepTot / idStep) * (100 - pourcent) / 100
                    if on_update:
                        on_update(pourcent, estimated)
                    dtime.display_time(scan_time * (nbStepTot / idStep))
                if optPath:
                    axe.x.reverse()
            if optPath:
                axe.y.reverse()

        end_timer=time.time() # the scan is finished now
        print("Total duration :" + dtime.display_time_str(end_timer-start_timer))
        print("With a break time of :" + dtime.display_time_str(break_timer.elapsed(now=end_timer)))

        on_close()  # close window and oscilloscope connection when the scan is finished

    # We run the scan in a separate thread to avoid blocking the interface. The thread is set as a daemon so
    scan_thread = threading.Thread(target=run_scan, daemon=True)
    scan_thread.start()

