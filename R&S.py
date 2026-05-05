import matplotlib.pyplot as plt
import csv
import time
import os

import RsInstrument as rs
# import h5py


# ──────────── Constantes ────────────

IP_address3k = 'TCPIP::169.254.211.73::INSTR'
IP_address2k = 'TCPIP::169.254.158.94::INSTR'
IP_addressLaser = 'TCPIP::169.254.114.3::INSTR'
CSV_NAME_FILE= "test"


class RsIntrument:
    
    def __init__(self, IP_ADRESS=IP_address3k, time_out=1000):
        self.rtm = rs.RsInstrument(IP_ADRESS)
        self.rtm.visa_timeout = time_out

        print("Waiting for the acquisition to finish...", end=" ")
        self.rtm.query('*OPC?')
        
        modele = self.rtm.query("*IDN?")
        if "RTM3" in modele :
            self.modele = 3
            self.amplimit =  [1e-3, 10]
            self.timelimit = [1e-9, 500]
        else:
            self.model = 2
            self.amplimit =  [1e-3, 5]
            self.timelimit = [1e-9, 50]
        print("Done")

    def close(self):
        self.rtm.close()

    
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
                self.rtm.write(f'TRIGger:A:LEVel{channel} {trigger} ')
    
        if time_scale is not None:
            if time_scale < self.timelimit[0] :
                time_scale = self.timelimit[0]
            elif time_scale > self.timelimit[1] :
                time_scale = self.timelimit[1]
            self.rtm.write(f'TIMebase:SCALe {time_scale}')
    
        if horizontal_pos is not None:
            self.rtm.write(f'TIMebase:POSition {horizontal_pos}')
    
    
    def Get_Time(t0, dt, nb_points):
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
    
    
    def Actualise(self):
    
        # print("Wait ... ", end="")
        # rtm.query('*OPC?')
        # print("Done")
    
    
        # Attend suffisament longtemps que la moyenne se fasse
        sample_rate = self.rtm.query_float('ACQuire:SRATe?') # Recup la fréquence d'échantillonage
        nb_points = self.rtm.query_float('ACQuire:POINts?') # Recup le nb de pts à faire
        nb_samples = self.rtm.query_float('ACQ:AVER:COUN?') # Nombre de moyenne à faire
    
        self.rtm.write('STOP\nRUN')
    
        t = (nb_points / sample_rate) * (nb_samples + 1)
        
        if t > 60 :
            print("≈", t//60, "min et ", t%60, "sec")
        else :
            print("≈", int(t), "sec")
        
        print(f"Wait {t}sec ... ", end="")
        time.sleep(t)
        # rtm.query('*OPC?')
    
        print("Done")
    
    
    def Vertical_Adjust(self, channel, Hlimit=4, Llimit=2, timelimit=0):
        
        t0, dt, data = self.Measure(channel)
        
        if t0 > timelimit:
            pass
        else :
            nb = (timelimit - t0)/dt
            data = data[int(nb):]
        
        highest, lowest = max(data), min(data)
        
        scale = self.rtm.query_float(f'CHANnel{channel}:SCALe?')
        # print(highest, lowest)
        # print(scale)
        
        if highest >= Hlimit*scale or highest <= Llimit*scale or lowest <= -Hlimit*scale or lowest >= -Llimit*scale :
            self.rtm.write(f'CHANnel{channel}:SCALe 5')
            
            data = self.Donnes_Brutes(channel)
            highest, lowest = max(data), min(data)
            
            scale = max(abs(highest), abs(lowest))
            # print(scale)
            
            division = (Hlimit+Llimit)/2
            scale = round(scale/division, 2)
            
            print(scale)
            self.rtm.write(f'CHANnel{channel}:SCALe {scale}')
            
            return True
        return False
            
    
    # ────── Measurements ──────
    
    def Donnes_Brutes(self, channel):
        self.data = self.rtm.query_bin_or_ascii_float_list(f'FORM ASC;:CHAN{channel}:DATA?')
    
    
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
    
        self.waveform = self.rtm.query_bin_or_ascii_float_list(f'FORM ASC;:CHAN{channel}:DATA?')
        time.sleep(0.01)
        self.t0 = self.rtm.query_float(f'CHAN{channel}:DATA:XOR?')
        time.sleep(0.01)
        self.dt = self.rtm.query_float(f'CHAN{channel}:DATA:XINC?')
    
    
    
    # ────── Sauvegarde données ──────
    
    def Save_Oscillo_Settings(self, channel):
        self.amplitude_scale = self.rtm.query_float(f'CHANnel{channel}:SCALe?')
        self.time_scale = self.rtm.query_float('TIMebase:SCALe?')
        self.horizontal_positon = self.rtm.query_float('TIMebase:POSition?')
        self.vertical_positon = self.rtm.query_float(f'CHANnel{channel}:POSition?')
        self.average = self.rtm.query('ACQ:AVER:COUN?')
    
        return [self.amplitude_scale, self.time_scale, self.horizontal_positon, self.vertical_positon, self.average]
    
    def Import_Oscillo_Settings(self, channel):
        self.rtm.write(f'CHANnel{channel}:SCALe {self.amplitude_scale}')
        self.rtm.write(f'TIMebase:SCALe {self.time_scale}')
        self.rtm.write(f'TIMebase:POSition {self.horizontal_positon}')
        self.rtm.write(f'CHANnel{channel}:POSition {self.vertical_positon}')
        self.rtm.write(f'ACQ:AVER:COUN {self.average}')
    
    
    def Save_Caliber(self, user_name, file_name="meta-data.txt"):
    
        file = open(file_name, 'a')
    
        for i in range(1, 5):
            print(self.rtm.query(f"TRIG:A:SOUR CH{i}?"))
    
        trigger = self.rtm.query('TRIGger:A:LEVel?')
        time_scale = self.rtm.query('TIMebase:SCALe?')
        horizontal_pos = self.rtm.query('TIMebase:POSition?')
    
        amplitude_scale = []
        vertical_pos = []
        for channel in range(1, 5):  # A changer
            amplitude_scale.append(self.rtm.query(f'CHANnelCH{channel}:SCALe?'))
            vertical_pos.append(self.rtm.query(f'CHANnelCH{channel}:POSition?'))
    
        line = f'{user_name};{1};{trigger};{time_scale};{amplitude_scale};{horizontal_pos};{vertical_pos}'
        file.write(line)
    
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