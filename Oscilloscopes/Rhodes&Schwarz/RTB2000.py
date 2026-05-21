import matplotlib.pyplot as plt
import csv
import time
import os
import math

import RsInstrument as rs
# import h5py


# ──────────── Constantes ────────────

IP_address3k = 'TCPIP::169.254.211.73::INSTR'
IP_address2k = 'TCPIP::169.254.158.94::INSTR'
IP_addressLaser = 'TCPIP::169.254.114.3::INSTR'
CSV_NAME_FILE= "test"


# noinspection PyUnboundLocalVariable
class RsInstrument:

    def __init__(self, IP_ADRESS=IP_address3k, time_out=1000, baudrate=9600, limit_time=None):
        self.rtm = rs.RsInstrument(IP_ADRESS)
        self.rtm.visa_timeout = time_out
        self.rtm.write("BUS1:UART:BAUDrate 19200")
        

        print("Waiting for the acquisition to finish...", end=" ")
        self.rtm.query('*OPC?')

        modele = self.rtm.query("*IDN?")
        if "RTM3" in modele :
            self.modele = 3
            self.amplimit =  [1e-3, 10]
            self.timelimit = [1e-9, 500]
        else:
            self.modele = 2
            self.amplimit =  [1e-3, 5]
            self.timelimit = [1e-9, 50]

        if limit_time is not None:
            self.limit_time = limit_time

        for channel in range(1,5):
            state = self.rtm.query_int(f"CHAN{channel}:STATe?")
            if state == 1 :
                self.Save_Oscillo_Settings(channel)

        print("Done")

    def Errors_Reset(self):
        self.rtm.clear_status()
        self.rtm.write('*CLS')
        time.sleep(0.1)

    def close(self):
        self.rtm.close()

    def LimitTime(self, limit_time):
        self.limit_time = limit_time

    def TimeOut(self, time_out):
        self.rtm.visa_timeout = time_out

    def Calibers(self, channel=None, time_scale=None, amplitude_scale=None, horizontal_pos=None, vertical_pos=None, trigger=None):

        if channel is not None:
            if amplitude_scale is not None:
                if amplitude_scale < self.amplimit[0] :
                    amplitude_scale = self.amplimit[0]
                elif amplitude_scale > self.amplimit[1]:
                    amplitude_scale = self.amplimit[1]
                self.rtm.write(f'CHANnel{channel}:SCALe {amplitude_scale}')

            if vertical_pos is not None:
                if vertical_pos < -5 :
                    vertical_pos = -5
                elif vertical_pos > 5 :
                    vertical_pos = 5
                self.rtm.write(f'CHANnel{channel}:POSition {vertical_pos}')

            if trigger is not None:
                self.rtm.write(f'TRIGger:A:LEVel{channel} {trigger}')

        if time_scale is not None:
            if time_scale < self.timelimit[0] :
                time_scale = self.timelimit[0]
            elif time_scale > self.timelimit[1] :
                time_scale = self.timelimit[1]
            self.rtm.write(f'TIMebase:SCALe {time_scale}')

        if horizontal_pos is not None:
            self.rtm.write(f'TIMebase:POSition {horizontal_pos}')


    def Get_Time(self, t0, dt, nb_points):
        liste = []
        for i in range(nb_points):
            liste.append(t0+dt*i)
        return liste


    def Average(self, samples_nb):
        if samples_nb < 2:
            samples_nb = 2
        self.rtm.write('CHANnel:ARIThmetics AVERage')
        time.sleep(0.01)
        self.rtm.write(f'ACQ:AVER:COUN {samples_nb}')


    def Actualise(self, affichage=None):
        
        self.rtm.write('STOP\nRUN')
        done = 0
        
        if affichage:
            print("\nWaiting ... ", end="")

        while done != 1 :
            done = self.rtm.query_int('ACQuire:AVERage:COMPlete?')
        
        if affichage:
            print("Done")


    def Vertical_Adjust(self, channel, Hlimit=4, Llimit=3, quick = False):
        has_adjust = False
        
        if quick :
            self.rtm.write('STOP\nRUN') # Actualise juste l'affichage
            steps_amounts = 1
            mean_number = self.rtm.query('ACQ:AVER:COUN?')   
            self.rtm.write('ACQ:AVER:COUN 2')
        else :
            steps_amounts = 2
        
        t0, dt, data = self.Measure(channel)

        data=Redressement(data)

        maximum = max(data)
        # print(maximum)
        
        scale = self.rtm.query_float(f'CHANnel{channel}:SCALe?')
        # print("S",scale)

        if maximum >= Hlimit*scale or maximum <= Llimit*scale:
            
            while maximum > 4*scale :
                if scale*5 < self.amplimit[1]:
                    self.rtm.write(f'CHANnel{channel}:SCALe {scale*5}')
                    scale *= 5
    
                self.rtm.write('STOP\nRUN')
                
                t0, dt, data = self.Measure(1)
                maximum = max(Redressement(data))


            for step in range(steps_amounts):
                if quick :
                    time.sleep(1)
                else :
                    self.Actualise()
                
                t0, dt, data = self.Measure(1)
                maximum = max(Redressement(data))
                # print(maximum)

                mean = (3*Hlimit+Llimit)/4
                scale = maximum/mean
                # print("S",scale)

                if scale > self.amplimit[1]:
                    scale = self.amplimit[1]
                elif scale < self.amplimit[0]:
                    scale = self.amplimit[0]

                # print("S",scale)
                self.rtm.write(f'CHANnel{channel}:SCALe {scale}')
            
            has_adjust = True

        if quick:
            self.rtm.write(f'ACQ:AVER:COUN {mean_number}')
        
        return has_adjust


    # ────── Measurements ──────

    def Total_Waveform(self, channel):
        data = self.rtm.query_bin_or_ascii_float_list(f'FORM ASC;:CHAN{channel}:DATA?')
        return data
        

    def Measure(self, channel):
        """
        Make the measure on the oscilloscope on one of the channels

        Parameters
        ----------
        rtm : RsInstrument
            return of the initialization of the connection PC/oscillo
        channel : list of str or int
            Channel of the measurement

        Retruns
        -------
        Give back :
        The set of Data
        Time of the first measurement
        Step time between measurements

        """
        self.channel = channel
        time.sleep(0.05)
        try :
            data = self.rtm.query_bin_or_ascii_float_list(f'FORM ASC;:CHAN{channel}:DATA?')
            time.sleep(0.01)
            t0 = self.rtm.query_float(f'CHAN{channel}:DATA:XOR?')
            time.sleep(0.01)
            dt = self.rtm.query_float(f'CHAN{channel}:DATA:XINC?')
            time.sleep(0.01)
        except :
            print("Erreure detéctée")
            self.Errors_Reset()
            time.sleep(0.5)
            
            data = self.rtm.query_bin_or_ascii_float_list(f'FORM ASC;:CHAN{channel}:DATA?')
            time.sleep(0.01)
            t0 = self.rtm.query_float(f'CHAN{channel}:DATA:XOR?')
            time.sleep(0.01)
            dt = self.rtm.query_float(f'CHAN{channel}:DATA:XINC?')
            time.sleep(0.01)
            
        

        if t0 > self.limit_time:
            pass
        else :
            nb = (self.limit_time - t0)/dt
            data = data[int(nb):]
            t0 = int(nb)*dt +t0

        return t0, dt, data
    
    def Save_and_Plot(self, channel):
        t0, dt, data = self.Measure(channel)
        Plot(data, self.Get_Time(t0, dt, len(data)))

    def Seuil_Value(self, seuil, t0, dt, data):
        """
        Renvoi la valeur temporelle de la première valeur qui dépasse un seuil.

        Parameters
        ----------
        t0 : float
        dt : float
        data : list

        Returns
        -------
        float
            Time.
        """
        for value in range(len(data)):
            if abs(data[value]) >= abs(seuil):
                time = value * dt + t0
                return time

    def Peak_Analisis(self, t0, dt, data, get_time = True):
        
        derive, maximum = [], 0
        for nb in range(1, len(data)):
            integration = (data[nb]-data[nb-1])/dt
            if integration > maximum :
                maximum = integration
            # Reduction du bruit
            derive.append(integration)
        
        # Ordre de grandeur des données
        exp = math.floor(math.log10(maximum))
        derive = [ int(number/(5*10**(exp-1))) for number in derive]
        plt.plot(derive)
        plt.show()


        seuil_value = 1000
        nb0 = 0
        peaks = []
        one_peak = []
        in_peak = False

        for indice in range(len(derive)):

            if derive[indice] in [0,1]:
                nb0 += 1

            elif nb0 > seuil_value:

                indice -= 100
                if get_time:
                    time = indice*dt + t0
                    one_peak.append(time)
                else:
                    one_peak.append(indice)
                in_peak = True
                nb0 = 0

            if in_peak and nb0 > seuil_value:

                end_peak = indice
                # for i in range(indice, indice - seuil_value, -1):
                #     if derive[indice] == 0 :
                #         pass
                #     else:
                #         end_peak = i
                #         nb0 = indice - end_peak
                #         break

                # if end_peak is None:
                #     end_peak = indice - seuil_value

                if get_time:
                    time = end_peak*dt + t0
                    one_peak.append(time)
                else:
                    one_peak.append(end_peak)

                in_peak = False

                peaks.append(one_peak)
                one_peak = []
        
        if len(peaks) == 0 :
            t0, dt, data = self.Measure(self.channel)
            return self.Peak_Analisis(t0, dt, data)
        else: 
            return peaks



    # ────── Sauvegarde données ──────

    def Save_Oscillo_Settings(self, channel):

        self.time_scale = self.rtm.query_float('TIMebase:SCALe?')
        self.amplitude_scale = self.rtm.query_float(f'CHANnel{channel}:SCALe?')
        self.horizontal_positon = self.rtm.query_float('TIMebase:POSition?')
        self.vertical_positon = self.rtm.query_float(f'CHANnel{channel}:POSition?')
        self.average = self.rtm.query_int('ACQ:AVER:COUN?')

        return {"time_scale":self.time_scale,
                "amplitude_scale":self.amplitude_scale,
                "horizontal_positon":self.horizontal_positon,
                "vertical_positon":self.vertical_positon,
                "average":self.average}

    def Set_Oscillo_Settings(self, channel, settings=None, save=True):

        if settings is not None:
            if isinstance(settings, list):
                time_scale = settings[0]
                amplitude_scale = settings[1]
                horizontal_positon = settings[2]
                vertical_positon = settings[3]
                average = settings[4]

            elif isinstance(settings, dict):
                time_scale = settings["time_scale"]
                amplitude_scale = settings["amplitude_scale"]
                horizontal_positon = settings["horizontal_positon"]
                vertical_positon = settings["vertical_positon"]
                average = settings["average"]

            self.rtm.write(f'TIMebase:SCALe {time_scale}')
            self.rtm.write(f'CHANnel{channel}:SCALe {amplitude_scale}')
            self.rtm.write(f'TIMebase:POSition {horizontal_positon}')
            self.rtm.write(f'CHANnel{channel}:POSition {vertical_positon}')
            self.rtm.write(f'ACQ:AVER:COUN {average}')

            if save :
                self.time_scale = time_scale
                self.amplitude_scale = amplitude_scale
                self.horizontal_positon = horizontal_positon
                self.vertical_positon = vertical_positon
                self.average = average
        else :
            self.rtm.write(f'TIMebase:SCALe {self.time_scale}')
            self.rtm.write(f'CHANnel{channel}:SCALe {self.amplitude_scale}')
            self.rtm.write(f'TIMebase:POSition {self.horizontal_positon}')
            self.rtm.write(f'CHANnel{channel}:POSition {self.vertical_positon}')
            self.rtm.write(f'ACQ:AVER:COUN {self.average}')



    def Save_Caliber(self, user_name, file_name="meta-data.txt"):

        file = open(file_name, 'a')



        line = f'{user_name};{1};{trigger};{time_scale};{amplitude_scale};{horizontal_pos};{vertical_pos}'
        file.write(line)

        file.close()

    def Import_Calibers(self, file_name="meta_data.txt"):
        file = open(file_name, 'w')



        file.close()


def Export_data(path, data):
    """
    Import a raw set of data and export it into a csv format
    Parameters
    ----------
    name : string
        List of characters that will be the name of the name of the csv file
    data : list of floats
        Set of raws data
    t0 : float
        Initial time of the measure, used tu make the timescale
    dt : float
        Interval time between measures, used to ùake the timescale

    Returns
    -------
    None

    File
    ----
    Write a file with the format in 1 column : t0, dt, all datas
    """

    if path[-4:] !=".csv" or path[-4:] !=".txt":
        path += '.csv'

    with open(path, "a" , newline="") as file:
        for row in data:
            file.write(str(row)+'\n')



# ────── Post Traitement ──────

def Plot(value, time, xlabel="Temps (s)", ylabel = "Amplitude (V)"):
    """"
    Draw a plot of the data using the X and Y coordinates

    Parameters
    ----------
    X : list of floats
        List of x values
    Y : list of floats
        List of y values

    Returns
    -------
    None
    """
    fig, ax = plt.subplots()
    ax.plot(time, value)
    ax.set(xlabel=xlabel , ylabel=ylabel)
    plt.show()


def Redressement(data):
    new_data = []
    for value in data:
        new_data.append(abs(value))
    return new_data


def Add_data(path, data):

    # if path[-4:] !=".txt" or path[-4:] !=".csv": path += '.csv'

    file = open(path, mode='r')
    tempo = open("Temprary file.txt", mode="w")

    # reader = csv.reader(file, delimiter=';')

    for nb in range(len(data)):

        line = file.readline()
        new_line = line[:-1] + ";" + str(data[nb]) + "\n"

        tempo.write(new_line)

    tempo.close()
    file.close()

    os.remove(path)
    os.rename("Temprary file.txt", path)


def Import(path):

    # Verify if the path given end by .csv if not, add it
    if path[-4:] !=".txt" and path[-4:] != ".csv": path += '.csv'

    with open(path, mode='r') as file:  # Open and read the file
        reader = csv.reader(file)

        data = [row for row in reader]  # Extract the data of the file
        t0 = float(data[0][0])                    # Get t0 and dt
        dt = float(data[1][0])

        data_float=[]
        for i in data[2:] :
            data_float.append(float(i[0]))                 # Delet t0 and dt from the global data

    return t0, dt, data_float


# def Export_h5(data, t0, dt):
#
#     # Création du fichier
#     with h5py.File("donnees.h5", "w") as file:
#         # Créer un groupe
#         grp = file.create_group("experience_1")
#
#         # Créer un dataset dans le groupe
#         grp.create_dataset("Donnees", data=data)
#
#         # Ajouter des attributs (métadonnées)
#         grp["Donnees"].attrs["temps initial"] = t0
#         grp["Donnees"].attrs["Pas temporel"] =  dt
#
# def Add_h5(data, t0, dt):
#     with h5py.File("donnees.h5", "a") as f:  # "a" = append
#
#         anciens_data = f["experience_1/temperatures"][:]
#
#         # Supprimer l'ancien dataset
#         del f["experience_1/temperatures"]
#
#         # Créer le nouveau avec une colonne supplémentaire
#         nouvelle_colonne = np.ones((1000, 1)) * 42
#         nouveaux_data = np.hstack([anciens_data, nouvelle_colonne])
#
#         f["experience_1"].create_dataset("temperatures", data=nouveaux_data)