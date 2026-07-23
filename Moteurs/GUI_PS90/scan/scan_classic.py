#!/usr/bin/env python3
"""
If you want to create a particular scan. You can edit some settings here to create yours


Warning : This file could not be used for a PS90 motor where the axes are different from :
- X 1
- Y 2
- Z 3
- R 4

"""

import os
import sys
import time
from tkinter import * # pour l'interface graphique (progress bar)
from tkinter import ttk, messagebox
import threading

from scan.utils import axe_def, write_csv as csvw # pour que l'interface graphique puisse s'ouvrir en second plan
from classes import path_import as path

from classes.ps90.OWIS_PS90 import OWIS_PS90
from classes.HDO4034A.HDO4034A import HDO4034A
from classes import display_time as dtime

"""##Gestion des chemins d'accès""" #/!\ à modifier si autre session
os.chdir(path.FILE_LOCATION+"/out/") # Dossier de sortie du scan


def scan_classic(name):



    """##Connexion aux instruments"""

    ps=OWIS_PS90(dll_path=path.FILE_LOCATION+'/classes/ps90/ps90.dll') ##Creation de l'interface objet
    error=ps.open_connection(port=0)

    if error["num"] !=0:
        return

    IP_adress = '169.254.27.102'
    osc=HDO4034A()
    osc.open_connection(IP_adress)

    """User settings"""
    #Scan settings

    #Movement speed of axes X,Y and Z
    ps.X.vel = 3 # [mm/s]
    ps.Y.vel = 3 # [mm/s]
    ps.Z.vel = 3 # [mm/s]
    ps.X.acc = 1 # [mm/s²]
    ps.Y.acc = 1 # [mm/s²]
    ps.Z.acc = 1 # [mm/s²]

    ##on initialise les axes ?? 
    axe=axe_def.init_axes() 

    ## Positional scan vectors on X
    dx = 1 ## [mm] Pas spatial
    xMin = -5 ## [mm] Position minimale du scan (relativement � la position origine ('home') = 0)
    xMax = 0 ## [mm] Position maximale du scan (relativement � la position origine ('home') = 0)
    axe.x = axe.creer_axe(xMin,xMax,dx) ## [m] Vecteur de positionnement
    nbX = len(axe.x) ## Nombre de points du vecteur positionnement
        
    ## Vecteur des positions de scan selon y
    dy = 1 ## [mm] Pas spatial
    yMin = -5 ## [mm] Position minimale du scan (relativement � la position origine ('home') = 0)
    yMax = 0 ## [mm] Position maximale du scan (relativement � la position origine ('home') = 0)
    axe.y = axe.creer_axe(yMin,yMax,dy) ## [m] Vecteur de positionnement
    nbY = len(axe.y) ## Nombre de points du vecteur positionnement    
        
    ## Vecteur des positions de scan selon z
    dz = 1 ## [mm] Pas spatial
    zMin = -5 ## [mm] Position minimale du scan (relativement � la position origine ('home') = 0)
    zMax = 0 ## [mm] Position maximale du scan (relativement � la position origine ('home') = 0)
    axe.z = axe.creer_axe(zMin,zMax,dz) ## [m] Vecteur de positionnement
    nbZ = len(axe.z) ## Nombre de points du vecteur positionnement

    ## Type de balayage
    optPath = True ## 1 : maillage serpentin (tant�t axe.y croissant, tant�t axe.y d�croissant), 0 : maillage r�gulier (axe.y toujours croissant)




    ## Param�trage de l'oscilloscope
    ## Affectation et param�trage des voies
    RF_CH = 'C1' ## Voie d'entr�e signal HF
    RF_CH_coupling = 'D50' ## Couplage DC 50Ohm
    exc_CH = 'C1' ## Voie de recueil de l'excitation
    exc_CH_coupling = 'A1M' ## Couplage AC 1MOhm
    #     osc.TrigSource = 'C2'

    ## Moyennage
    osc.acq_avg_nb=200 ## Moyenne glissante
    ## Nombre max de points
    acq_sample_max_echo = 10e3
    ## D�cimation
    osc.acq_sparse_nb=2
    ## Channel bandwidth
    ch_BW = '200MHz' ## On n'applique de filtre pour aucune voie


    """Réglage des fenêtres d'acquisition"""

    # Echo
    osc.active_ch=RF_CH
    osc.ch_coupling=RF_CH_coupling
    osc.ch_bw=ch_BW
    osc.acq_mode="average"

    if not(messagebox.askokcancel("echo-acquisition","Waiting for you to calibrate echo-acquisition window, enter 'ok' when you are done")):
        print("Scan cancelled")
        return
    
    delay_echo = osc.acq_delay
    tbase_echo = osc.time_base
    CH_scale_echo = osc.ch_scale
    osc.acq_sample_max=acq_sample_max_echo

    osc.re_scale()

    # Excitation
    osc.active_ch=exc_CH
    osc.ch_coupling=exc_CH_coupling
    osc.ch_bw=ch_BW
    osc.acq_delay=0


    if not(messagebox.askokcancel("excitation-acquisition","Waiting for you to calibrate excitation-acquisition window, enter 'ok' when you are done")):
        print("Scan cancelled")
        return

    delay_excitation = osc.acq_delay
    CH_scale_excitation = osc.ch_scale
    tbase_excitation = osc.time_base

    # Enregistrement de l'excitation
    osc.acq_mode="average"
    [T_excitation,Y_excitation] = osc.read_wave(osc.active_ch)

    """ Scan interface """

    root =Tk()

    estimated_time_frame=ttk.Frame(root)
    time_pourcent = IntVar()
    estimated_time_progressbar = ttk.Progressbar(estimated_time_frame,orient=HORIZONTAL,length=200,mode="determinate",variable=time_pourcent)
    estimated_time_var = StringVar(value=f"Estimated time :\n...(wait some calculs)")
    estimated_time_label = ttk.Label(estimated_time_frame,textvariable=estimated_time_var)

    scan_buttons_frame=ttk.Frame(root)
    scan_break_button=ttk.Button(scan_buttons_frame,text="BREAK")
    scan_take_back_button=ttk.Button(scan_buttons_frame,text="Take Back")
    scan_stop_button=ttk.Button(scan_buttons_frame,text="STOP")

    def update_time(val):
        """Update the estimated time"""
        estimated_time_var.set(f"Estimated time :\n"+dtime.display_time_str(val))

    estimated_time_frame.grid(column=0,row=0)
    estimated_time_label.grid(column=0,row=0)
    estimated_time_progressbar.grid(column=1,row=0)

    scan_buttons_frame.grid(column=0,row=1)
    scan_break_button.grid(column=0,row=0)
    scan_stop_button.grid(column=1,row=0)


    stop_event = threading.Event()
    break_event = threading.Event()
    

    def stop_scan(event=None):          # event=None pour le bind
        stop_event.set()
        ps.stop_all()
        ps.close_connection()
        osc.close_connection()
        print("Emergency STOP")
        root.destroy()

    scan_stop_button.bind("<ButtonPress-1>", stop_scan)

    #variables pour recalculer estimation si l'on fait une pause
    global break_timer
    break_timer=0
    global start_break_time
    start_break_time=0
    global stop_break_time
    stop_break_time=0


    def break_scan(event=None):
        global start_break_time 
        start_break_time=time.time()                          
        print("BREAK")
        break_event.set()
        scan_break_button.grid_remove()
        scan_take_back_button.grid(column=0, row=0)


    def take_back_scan(event=None):
        global stop_break_time
        global break_timer
        print("TAKE BACK")
        break_event.clear()
        scan_take_back_button.grid_remove()
        scan_break_button.grid(column=0, row=0)
        stop_break_time=time.time()                          
        break_timer += stop_break_time-start_break_time

    scan_break_button.bind("<ButtonPress-1>", break_scan)
    scan_take_back_button.bind("<ButtonPress-1>", take_back_scan)

    """ Scan """
    osc.active_ch=RF_CH
    osc.time_base=tbase_echo
    osc.ch_scale=CH_scale_echo
    osc.acq_delay=delay_echo
    osc.acq_sample_max=acq_sample_max_echo

    osc.acq_mode="average"

    nbStepTot = nbX*nbY*nbZ


    def run_scan():
        # Time estimation :
        start_timer=time.time()
        T_exp,Y_exp=osc.read_wave('C1')
        time_for_estimating=time.time()
        estimated_time=(time_for_estimating-start_timer)*nbStepTot
        dtime.display_time(estimated_time)
    
        idStep=0
        
        
        for idz in range(nbZ):
            print(f"idz ={idz+1} / {nbZ}")
            #Moving
            ps.Z.move_abs(axe.z[idz])
            while ps.Z.state == 1: # on attend que le mouvement finisse
                pass
            for idy in range(nbY):
                print(f"idy = {idy+1} / {nbY}")
                #Moving
                ps.Y.move_abs(axe.y[idy])
                while ps.Y.state==1:
                    pass
                for idx in range(nbX):
                    if stop_event.is_set(): return
                    while break_event.is_set():
                        if stop_event.is_set(): return   # STOP fonctionne même en pause
                        time.sleep(0.1)
                    print(f"idx = {idx+1} / {nbX}")
                    #Moving
                    ps.X.move_abs(axe.x[idx])
                    while ps.X.state==1:
                        pass
                    # Acquisition du signal
                    (T,Y)=osc.read_wave(osc.active_ch) 
    
                    data=[[ps.X.pos,ps.Y.pos,ps.Z.pos]]
                    data.append(Y)
                    data.append(T)

                    csvw.save_data(name,data)

                    # Affichage état avancement
                    idStep+=1
                    if (idStep)*100//nbStepTot != (idStep+1)*100//nbStepTot: 
                        pourcent=((100*(idStep/nbStepTot))//1) #update green bar
                        scan_time=(time.time()-start_timer-break_timer) 
                        estimated=scan_time * (nbStepTot / idStep)*(100-pourcent)/100
                        root.after(0, lambda _pourcent=pourcent: time_pourcent.set(_pourcent))
                        root.after(0, lambda _t=estimated: update_time(_t))
                        dtime.display_time(scan_time * (nbStepTot / idStep))

                if optPath:
                    axe.x.reverse()
            if optPath:
                axe.y.reverse()

        end_timer=time.time()
        print("Total duration :" + dtime.display_time_str(end_timer-start_timer))
        print("With a break time of :"+ dtime.display_time_str(break_timer))

        root.after(0, root.destroy)  # Ferme la fenêtre quand le scan est fini



    scan_thread = threading.Thread(target=run_scan, daemon=True)
    scan_thread.start()

    root.mainloop()

scan_classic("scan1.py")
