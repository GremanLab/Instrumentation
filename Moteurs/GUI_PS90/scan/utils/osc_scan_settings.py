"""
Setup oscilloscope for scan with correct settings
"""


from classes.HDO4034A.HDO4034A import HDO4034A
from tkinter import *
from tkinter import ttk, messagebox
from scan.utils.write_csv import save_excitation

def osc_scan_settings(name,osc:HDO4034A,
                      hyd_chan:str,exc_chan:str,
                      hyd_coup:str,exc_coup:str,
                      sweep_nb:int, acq_sample_max:int)->bool: # if True : on_close else nothing
    """
    Setup oscilloscope for scan with correct settings
    
    """
    # Channel allocation and configuration
    RF_CH = hyd_chan # HF signal input channel
    RF_CH_coupling = hyd_coup # Coupling DC 50Ohm
    exc_CH = exc_chan # excitation signal input channel
    exc_CH_coupling = exc_coup # Coupling AC 1MOhm
    #     osc.TrigSource = 'C2'

    ## Moyennage
    osc.acq_avg_nb=sweep_nb # Moving average
    # Max number of points
    acq_sample_max_echo = acq_sample_max
    # Decimation
    osc.acq_sparse_nb=2
    # Channel bandwidth
    ch_BW = '20MHz' 


    """Réglage des fenêtres d'acquisition"""

    # Echo
    osc.active_ch=RF_CH
    osc.ch_coupling=RF_CH_coupling
    osc.ch_bw=ch_BW
    osc.acq_mode="average"

    if not(messagebox.askokcancel("echo-acquisition","Manually adjust the echo-acquisition window on the oscilloscope to obtain a clean and centered signal.")):
        print("Scan cancelled")
        return True

    delay_echo = osc.acq_delay   # Saving dalay of trigger-echo
    tbase_echo = osc.time_base   # Saving temporal scale associated with echo acquisition window
    CH_scale_echo = osc.ch_scale # Saving vertical scale associated with echo acquisition window
    osc.time_base=tbase_echo
    osc.ch_scale=CH_scale_echo
    osc.acq_sample_max=acq_sample_max_echo

    osc.re_scale() # rescale window dimensions

    # Excitation
    osc.active_ch=exc_CH
    osc.ch_coupling=exc_CH_coupling
    osc.ch_bw=ch_BW
    osc.acq_delay=0 # The trigger point is deliberately placed in the center of the window to allow recording of the excitation signal, which is synchronized to the rising edge.



    if not(messagebox.askokcancel("excitation-acquisition","Manually adjust the excitation-acquisition window on the oscilloscope to obtain a clean and centered signal.")):
        print("Scan cancelled")
        return True

    delay_excitation = osc.acq_delay   # Saving delay of trigger-excitation
    tbase_excitation = osc.time_base   # Saving temporal scale associated with excitation acquisition window
    CH_scale_excitation = osc.ch_scale # Saving vercal scale associated with excitation acquisition window

    # Saving excitation
    osc.acq_mode="average"
    [T_excitation,Y_excitation] = osc.read_wave(osc.active_ch)
    save_excitation(name, [T_excitation,Y_excitation])

    # Restoring echo parameters
    
    osc.active_ch=RF_CH
    osc.time_base=tbase_echo
    osc.ch_scale=CH_scale_echo
    osc.acq_delay=delay_echo
    osc.acq_sample_max=acq_sample_max_echo

    osc.acq_mode="average"
    
    return False
