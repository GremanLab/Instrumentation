"""
This file has been created in case of HDO4034A.py doesn't work :
If HDO4034A.py uses Active DSO to give instruction to the scop, this file uses pyvisa

PS : this file has not been tested and could be incomplete.

"""




import pyvisa
import numpy as np
import time
import warnings

class HDO4034A:
    def __init__(self):
        # Constantes du modèle
        self.MODEL_NAME = 'HDO 4034A'
        self.DRIVER_NAME = 'lecroy_basic_driver.mdd'  # Non utilisé en Python
        self.VSCALE_LIM = [1e-3, 1]  # [V/div] en 50Ω
        self.HSCALE_LIM = [200e-9, 1.25e3]  # [s/div]
        self.HSCALE_VEC = [
            100e-12, 200e-12, 500e-12, 1e-9, 2e-9, 5e-9, 10e-9, 20e-9, 50e-9, 100e-9,
            200e-9, 500e-9, 1e-6, 2e-6, 5e-6, 10e-6, 20e-6, 50e-6, 100e-6, 200e-6,
            500e-6, 1e-3, 2e-3, 5e-3, 10e-3, 20e-3, 50e-3, 100e-3, 200e-3, 500e-3,
            1, 2, 5, 10, 20, 50, 100, 200, 500, 1e3, 2e3, 2.5e3
        ]
        self.TRIG_LIM = [-8.20, 8.20]  # [V]
        self.CONNECTION_STATUS = 'closed'

        # Propriétés dynamiques
        self.IpAdress = '169.254.27.102'
        self.visaObj = None
        self.TimeBase = None
        self.SweepsPerAcq = None
        self.ActiveCh = 'C1'
        self.ActiveChId = 1
        self.ChScale = None
        self.ChState = 'on'
        self.ChCoupling = 'D50'
        self.ChProbeAtt = 1
        self.ChBW = 'full'
        self.TrigSource = 'C1'
        self.TrigType = 'edge pos'
        self.TrigMode = 'norm'
        self.TrigLevel = 0.0
        self.TrigSlope = 'rising'
        self.TrigCoupling = 'DC'
        self.AcqSparseNb = 0
        self.AcqMode = 'sample'
        self.AcqAvgNb = 1
        self.AcqAvgNbStored = 1
        self.AcqState = 'stop'
        self.AcqFormat = 'int16'
        self.AcqSampleMax = 10e6
        self.AcqDelay = 0.0
        self.MeasSource = 'C1'
        self.MeasType = 'peak2peak'
        self.MeasValue = None

    # --- Méthodes de connexion ---
    def open_connection(self):
        """Ouvre la connexion VISA avec l'oscilloscope."""
        try:
            rm = pyvisa.ResourceManager()
            self.visaObj = rm.open_resource(f'TCPIP0::{self.IpAdress}::inst0::INSTR')
            print(f"Connection to {self.MODEL_NAME}, IP : {self.IpAdress}")
            self.visaObj.timeout = 1000  # ms
            self.visaObj.read_termination = '\n'
            self.visaObj.write_termination = '\n'
            self.visaObj.read_buffer_size = 10_000_000  # 10 Mo

            # Désactive les en-têtes de réponse
            self.visaObj.write('COMM_HEADER OFF')

            # Réglages par défaut
            self.ActiveCh = 'C1'
            self.ChCoupling = 'D50'
            self.ChState = 'on'
            self.TrigType = 'edge pos'
            self.TrigMode = 'norm'
            self.AcqSparseNb = 0

            self.CONNECTION_STATUS = 'open'
            print(f"Connexion établie avec {self.MODEL_NAME} ({self.IpAdress}).")

        except Exception as e:
            warnings.warn(f"Échec de la connexion : {e}")
            self.CONNECTION_STATUS = 'closed'

    def close_connection(self):
        """Ferme la connexion VISA."""
        if self.visaObj:
            try:
                self.visaObj.close()
                self.CONNECTION_STATUS = 'closed'
                print(f"Déconnexion de {self.MODEL_NAME}.")
            except Exception as e:
                warnings.warn(f"Erreur lors de la fermeture : {e}")

    # --- Méthodes de base (get/set) ---
    @property
    def TimeBase(self):
        """Récupère la base de temps (TIME_DIV)."""
        if self.CONNECTION_STATUS != 'open':
            raise Exception("Connexion non ouverte.")
        return float(self.visaObj.query('TIME_DIV?'))

    @TimeBase.setter
    def TimeBase(self, tBase):
        """Définit la base de temps (TIME_DIV)."""
        if self.CONNECTION_STATUS != 'open':
            raise Exception("Connexion non ouverte.")
        if not isinstance(tBase, (int, float)):
            warnings.warn("La base de temps doit être un nombre.")
            return

        # Trouve la valeur la plus proche dans HSCALE_VEC
        closest = min(self.HSCALE_VEC, key=lambda x: abs(x - tBase))
        self.visaObj.write(f'TIME_DIV {closest}')
        if abs(closest - tBase) > 1e-12:
            warnings.warn(f"Base de temps ajustée à {closest}s (valeur demandée : {tBase}s).")

    @property
    def SweepsPerAcq(self):
        """Récupère le nombre de sweeps par acquisition."""
        if self.CONNECTION_STATUS != 'open':
            raise Exception("Connexion non ouverte.")
        resp = self.visaObj.query(f'{self.ActiveCh}:INSPECT? "SWEEPS_PER_ACQ"')
        # Parse la réponse (ex: 'SWEEPS_PER_ACQ: 100')
        start = resp.find(':') + 1
        end = resp.find('"', start) - 1
        return int(resp[start:end].strip())

    @property
    def ChScale(self):
        """Récupère l'échelle verticale de la voie active."""
        if self.CONNECTION_STATUS != 'open':
            raise Exception("Connexion non ouverte.")
        return float(self.visaObj.query(f'{self.ActiveCh}:VOLT_DIV?'))

    @ChScale.setter
    def ChScale(self, chScale):
        """Définit l'échelle verticale de la voie active."""
        if self.CONNECTION_STATUS != 'open':
            raise Exception("Connexion non ouverte.")
        if not isinstance(chScale, (int, float)):
            warnings.warn("L'échelle verticale doit être un nombre.")
            return

        # Ajuste en fonction des limites et de l'atténuation de la sonde
        min_scale = self.VSCALE_LIM[0] * self.ChProbeAtt
        max_scale = self.VSCALE_LIM[1] * self.ChProbeAtt
        if chScale < min_scale:
            warnings.warn(f"Échelle trop petite. Ajustée à {min_scale}V.")
            chScale = min_scale
        elif chScale > max_scale:
            warnings.warn(f"Échelle trop grande. Ajustée à {max_scale}V.")
            chScale = max_scale

        self.visaObj.write(f'{self.ActiveCh}:VOLT_DIV {chScale}')

    @property
    def ChState(self):
        """Récupère l'état de la voie active (on/off)."""
        if self.CONNECTION_STATUS != 'open':
            raise Exception("Connexion non ouverte.")
        return self.visaObj.query(f'{self.ActiveCh}:TRACE?').strip().lower()

    @ChState.setter
    def ChState(self, state):
        """Définit l'état de la voie active (on/off)."""
        if self.CONNECTION_STATUS != 'open':
            raise Exception("Connexion non ouverte.")
        if state.lower() not in ['on', 'off']:
            raise ValueError("L'état doit être 'on' ou 'off'.")
        self.visaObj.write(f'{self.ActiveCh}:TRACE {state.upper()}')

    @property
    def ChCoupling(self):
        """Récupère le couplage de la voie active."""
        if self.CONNECTION_STATUS != 'open':
            raise Exception("Connexion non ouverte.")
        return self.visaObj.query(f'{self.ActiveCh}:COUPLING?').strip()

    @ChCoupling.setter
    def ChCoupling(self, coupling):
        """Définit le couplage de la voie active."""
        if self.CONNECTION_STATUS != 'open':
            raise Exception("Connexion non ouverte.")
        valid_couplings = ['A1M', 'D1M', 'D50', 'GND']
        if coupling.upper() not in valid_couplings:
            raise ValueError(f"Couplage invalide. Valides : {valid_couplings}")
        self.visaObj.write(f'{self.ActiveCh}:COUPLING {coupling.upper()}')
        # Met à jour les limites d'échelle verticale
        if coupling.upper() in ['A1M', 'D1M']:
            self.VSCALE_LIM = [1e-3, 10]  # 1MΩ
        elif coupling.upper() == 'D50':
            self.VSCALE_LIM = [1e-3, 1]  # 50Ω

    @property
    def ChProbeAtt(self):
        """Récupère l'atténuation de la sonde."""
        if self.CONNECTION_STATUS != 'open':
            raise Exception("Connexion non ouverte.")
        return float(self.visaObj.query(f'{self.ActiveCh}:ATTENUATION?'))

    @ChProbeAtt.setter
    def ChProbeAtt(self, att):
        """Définit l'atténuation de la sonde."""
        if self.CONNECTION_STATUS != 'open':
            raise Exception("Connexion non ouverte.")
        valid_atts = [1, 2, 5, 10, 20, 25, 50, 100, 200, 500, 1000, 10000]
        if att not in valid_atts:
            raise ValueError(f"Atténuation invalide. Valides : {valid_atts}")
        self.visaObj.write(f'{self.ActiveCh}:ATTENUATION {att}')

    @property
    def ChBW(self):
        """Récupère le filtre passe-bas de la voie active."""
        if self.CONNECTION_STATUS != 'open':
            raise Exception("Connexion non ouverte.")
        resp = self.visaObj.query(f'{self.ActiveCh}:BANDWIDTH_LIMIT?')
        # Parse la réponse (ex: 'C1,OFF,C2,OFF,...')
        parts = resp.split(',')
        index = parts.index(self.ActiveCh) + 1
        bw = parts[index]
        if bw == 'ON':
            return '20MHz'  # Cas particulier (cf. code MATLAB)
        return bw

    @ChBW.setter
    def ChBW(self, bw):
        """Définit le filtre passe-bas de la voie active."""
        if self.CONNECTION_STATUS != 'open':
            raise Exception("Connexion non ouverte.")
        valid_bws = ['full', '20mhz', '200mhz']
        if bw.lower() not in valid_bws:
            warnings.warn(f"Filtre invalide. Valides : {valid_bws}")
            return
        self.visaObj.write(f'BANDWIDTH_LIMIT {self.ActiveCh},{bw.upper()}')

    @property
    def ActiveCh(self):
        """Récupère la voie active."""
        return self._ActiveCh

    @ActiveCh.setter
    def ActiveCh(self, channel):
        """Définit la voie active."""
        valid_channels = ['C1', 'C2', 'C3', 'C4', 'F1', 'F2', 'F3', 'F4']
        if channel.upper() not in valid_channels:
            raise ValueError(f"Voie invalide. Valides : {valid_channels}")
        self._ActiveCh = channel.upper()
        self.ActiveChId = int(channel[1])  # Extrait le numéro (ex: 'C1' -> 1)
        self.ChState = 'on'  # Active la voie par défaut

    # --- Méthodes de trigger ---
    @property
    def TrigSource(self):
        """Récupère la source de déclenchement."""
        if self.CONNECTION_STATUS != 'open':
            raise Exception("Connexion non ouverte.")
        return self._TrigSource

    @TrigSource.setter
    def TrigSource(self, source):
        """Définit la source de déclenchement."""
        valid_sources = ['C1', 'C2', 'C3', 'C4', 'LINE', 'EX', 'EX10']
        if source.upper() not in valid_sources:
            warnings.warn(f"Source de déclenchement invalide. Valides : {valid_sources}")
            return
        self._TrigSource = source.upper()
        self.visaObj.write(f'TRIG_SELECT EDGE,SR,{self._TrigSource}')

    @property
    def TrigType(self):
        """Récupère le type de déclenchement."""
        return self._TrigType

    @TrigType.setter
    def TrigType(self, trig_type):
        """Définit le type de déclenchement (edge pos/neg)."""
        if trig_type.lower() not in ['edge pos', 'edge neg']:
            warnings.warn("Type de déclenchement invalide. Valides : 'edge pos', 'edge neg'")
            return
        self._TrigType = trig_type.lower()
        self.visaObj.write(f'TRIG_SELECT EDGE,SR,{self.TrigSource}')
        slope = 'POS' if trig_type.lower() == 'edge pos' else 'NEG'
        self.visaObj.write(f'{self.TrigSource}:TRIG_SLOPE {slope}')

    @property
    def TrigMode(self):
        """Récupère le mode de déclenchement."""
        if self.CONNECTION_STATUS != 'open':
            raise Exception("Connexion non ouverte.")
        return self.visaObj.query('TRIG_MODE?').strip()

    @TrigMode.setter
    def TrigMode(self, mode):
        """Définit le mode de déclenchement (AUTO, NORM, SINGLE, STOP)."""
        if self.CONNECTION_STATUS != 'open':
            raise Exception("Connexion non ouverte.")
        valid_modes = ['AUTO', 'NORM', 'SINGLE', 'STOP']
        if mode.upper() not in valid_modes:
            raise ValueError(f"Mode invalide. Valides : {valid_modes}")
        self.visaObj.write(f'TRIG_MODE {mode.upper()}')

    @property
    def TrigLevel(self):
        """Récupère le seuil de déclenchement."""
        if self.CONNECTION_STATUS != 'open':
            raise Exception("Connexion non ouverte.")
        return float(self.visaObj.query(f'{self.TrigSource}:TRIG_LEVEL?').replace('V', ''))

    @TrigLevel.setter
    def TrigLevel(self, level):
        """Définit le seuil de déclenchement."""
        if self.CONNECTION_STATUS != 'open':
            raise Exception("Connexion non ouverte.")
        if not isinstance(level, (int, float)):
            warnings.warn("Le seuil doit être un nombre.")
            return
        if level < self.TRIG_LIM[0]:
            warnings.warn(f"Seuil trop bas. Ajusté à {self.TRIG_LIM[0]}V.")
            level = self.TRIG_LIM[0]
        elif level > self.TRIG_LIM[1]:
            warnings.warn(f"Seuil trop haut. Ajusté à {self.TRIG_LIM[1]}V.")
            level = self.TRIG_LIM[1]
        self.visaObj.write(f'{self.TrigSource}:TRIG_LEVEL {level}V')

    @property
    def TrigCoupling(self):
        """Récupère le couplage du déclenchement."""
        if self.CONNECTION_STATUS != 'open':
            raise Exception("Connexion non ouverte.")
        return self.visaObj.query(f'{self.TrigSource}:TRIG_COUPLING?').strip()

    @TrigCoupling.setter
    def TrigCoupling(self, coupling):
        """Définit le couplage du déclenchement."""
        if self.CONNECTION_STATUS != 'open':
            raise Exception("Connexion non ouverte.")
        valid_couplings = ['AC', 'DC', 'HFREJ', 'LFREJ']
        if coupling.upper() not in valid_couplings:
            warnings.warn(f"Couplage invalide. Valides : {valid_couplings}")
            return
        self.visaObj.write(f'{self.TrigSource}:TRIG_COUPLING {coupling.upper()}')

    # --- Méthodes d'acquisition ---
    @property
    def AcqSparseNb(self):
        """Récupère le facteur de décimation."""
        if self.CONNECTION_STATUS != 'open':
            raise Exception("Connexion non ouverte.")
        resp = self.visaObj.query('WAVEFORM_SETUP?')
        # Parse la réponse (ex: 'SP,1,NP,0,FP,0,SN,0')
        start = resp.find('SP,') + 3
        end = resp.find(',NP', start)
        return int(resp[start:end])

    @AcqSparseNb.setter
    def AcqSparseNb(self, nb):
        """Définit le facteur de décimation."""
        if self.CONNECTION_STATUS != 'open':
            raise Exception("Connexion non ouverte.")
        if not isinstance(nb, int):
            warnings.warn("Le facteur de décimation doit être un entier.")
            return
        self.visaObj.write(f'WAVEFORM_SETUP SP,{nb},NP,0,FP,0,SN,0')

    @property
    def AcqMode(self):
        """Récupère le mode d'acquisition."""
        if self.CONNECTION_STATUS != 'open':
            raise Exception("Connexion non ouverte.")
        persist = self.visaObj.query('PERSIST?').strip()
        if persist == 'ON':
            return 'envelope'
        # Vérifie si on est en mode average
        avg_sweeps = int(self.visaObj.query(f' vbs? "return=app.Acquisition.{self.ActiveCh}.AverageSweeps"'))
        if avg_sweeps != 1:
            return 'average'
        return 'sample'

    @AcqMode.setter
    def AcqMode(self, mode):
        """Définit le mode d'acquisition (sample, average, envelope)."""
        if self.CONNECTION_STATUS != 'open':
            raise Exception("Connexion non ouverte.")
        if mode.lower() == 'sample':
            self.visaObj.write('PERSIST OFF')
            self.visaObj.write(f' vbs "app.Acquisition.{self.ActiveCh}.AverageSweeps = 1"')
        elif mode.lower() == 'average':
            self.visaObj.write(f' vbs "app.Acquisition.{self.ActiveCh}.AverageSweeps = {self.AcqAvgNbStored}"')
            self.visaObj.write('PERSIST OFF')
        elif mode.lower() == 'envelope':
            self.visaObj.write(f' vbs "app.Acquisition.{self.ActiveCh}.AverageSweeps = 1"')
            self.visaObj.write('PERSIST ON')
            self.visaObj.write('PERSIST_SETUP infinite,PERTRACE')
        else:
            raise ValueError("Mode invalide. Valides : 'sample', 'average', 'envelope'")

    @property
    def AcqAvgNb(self):
        """Récupère le nombre de moyennages."""
        return self.AcqAvgNbStored

    @AcqAvgNb.setter
    def AcqAvgNb(self, nb):
        """Définit le nombre de moyennages."""
        if not isinstance(nb, int):
            warnings.warn("Le nombre de moyennages doit être un entier.")
            return
        self.AcqAvgNbStored = nb

    @property
    def AcqState(self):
        """Récupère l'état de l'acquisition."""
        if self.CONNECTION_STATUS != 'open':
            raise Exception("Connexion non ouverte.")
        # Utilise le driver MATLAB pour accéder à l'état (non disponible en pyvisa pur)
        # Alternative : envoyer une commande SCPI pour vérifier l'état
        # Exemple : 'ACQ:STATE?' (à vérifier dans la doc LeCroy)
        warnings.warn("AcqState : Méthode non implémentée (nécessite le driver MATLAB ou ActiveDSO).")
        return None

    @AcqState.setter
    def AcqState(self, state):
        """Définit l'état de l'acquisition (stop, run, auto, single)."""
        if self.CONNECTION_STATUS != 'open':
            raise Exception("Connexion non ouverte.")
        valid_states = ['stop', 'run', 'auto', 'single']
        if state.lower() not in valid_states:
            raise ValueError(f"État invalide. Valides : {valid_states}")
        # Alternative SCPI (à vérifier) : 'ACQ:STATE {state}'
        warnings.warn("AcqState : Méthode non implémentée (nécessite le driver MATLAB ou ActiveDSO).")

    @property
    def AcqFormat(self):
        """Récupère le format de l'acquisition."""
        if self.CONNECTION_STATUS != 'open':
            raise Exception("Connexion non ouverte.")
        warnings.warn("AcqFormat : Méthode non implémentée (nécessite le driver MATLAB ou ActiveDSO).")
        return None

    @AcqFormat.setter
    def AcqFormat(self, fmt):
        """Définit le format de l'acquisition (ASCII, int16, int8)."""
        if self.CONNECTION_STATUS != 'open':
            raise Exception("Connexion non ouverte.")
        valid_formats = ['ASCII', 'int16', 'int8']
        if fmt.lower() not in valid_formats:
            raise ValueError(f"Format invalide. Valides : {valid_formats}")
        warnings.warn("AcqFormat : Méthode non implémentée (nécessite le driver MATLAB ou ActiveDSO).")

    @property
    def AcqSampleMax(self):
        """Récupère le nombre maximal d'échantillons."""
        if self.CONNECTION_STATUS != 'open':
            raise Exception("Connexion non ouverte.")
        return int(self.visaObj.query('MSIZ?'))

    @AcqSampleMax.setter
    def AcqSampleMax(self, max_samples):
        """Définit le nombre maximal d'échantillons."""
        if self.CONNECTION_STATUS != 'open':
            raise Exception("Connexion non ouverte.")
        valid_sizes = [500, 10e3, 100e3, 1e6, 2.5e6, 5e6, 10e6, 12.5e6, 25e6]
        if max_samples not in valid_sizes:
            warnings.warn(f"Taille invalide. Valides : {valid_sizes}")
            return
        self.visaObj.write(f'MEMORY_SIZE {int(max_samples)}')

    @property
    def AcqDelay(self):
        """Récupère le délai d'acquisition."""
        if self.CONNECTION_STATUS != 'open':
            raise Exception("Connexion non ouverte.")
        delay = float(self.visaObj.query('TRIG_DELAY?'))
        return -delay  # Inversion pour correspondre à la logique MATLAB

    @AcqDelay.setter
    def AcqDelay(self, delay):
        """Définit le délai d'acquisition."""
        if self.CONNECTION_STATUS != 'open':
            raise Exception("Connexion non ouverte.")
        if not isinstance(delay, (int, float)):
            warnings.warn("Le délai doit être un nombre.")
            return
        self.visaObj.write(f'TRIG_DELAY {-delay}')  # Inversion pour correspondre à la logique MATLAB

    # --- Méthodes de mesure ---
    @property
    def MeasSource(self):
        """Récupère la source de mesure."""
        return self._MeasSource

    @MeasSource.setter
    def MeasSource(self, source):
        """Définit la source de mesure."""
        valid_sources = ['C1', 'C2', 'C3', 'C4']
        if source.upper() not in valid_sources:
            raise ValueError(f"Source invalide. Valides : {valid_sources}")
        self._MeasSource = source.upper()

    @property
    def MeasType(self):
        """Récupère le type de mesure."""
        return self._MeasType

    @MeasType.setter
    def MeasType(self, meas_type):
        """Définit le type de mesure."""
        valid_types = ['frequency', 'mean', 'period', 'peak2peak', 'crms', 'amplitude', 'area', 'base']
        if meas_type.lower() not in valid_types:
            raise ValueError(f"Type invalide. Valides : {valid_types}")
        self._MeasType = meas_type.lower()

    @property
    def MeasValue(self):
        """Récupère la valeur de la mesure."""
        if self.CONNECTION_STATUS != 'open':
            raise Exception("Connexion non ouverte.")
        # Utilise la commande PAVA? pour récupérer la mesure
        # Exemple : 'C1:PAVA? AMPL' pour l'amplitude
        # À adapter selon MeasType
        warnings.warn("MeasValue : Méthode non implémentée (nécessite une commande SCPI spécifique).")
        return None

    # --- Méthodes spécifiques ---
    # def ReScale(self):
    #     """Ajuste automatiquement l'échelle verticale de la voie active."""
    #     if self.CONNECTION_STATUS != 'open':
    #         raise Exception("Connexion non ouverte.")
    #     T, Y = self.ReadWave(self.ActiveCh)
    #     offset = np.mean(Y)
    #     Yh = np.abs(np.imag(hilbert(Y - offset)))  # Enveloppe (nécessite scipy.signal.hilbert)
    #     epsilon = 0.25e-3  # Marge en V
    #     scale2apply = (np.max(Yh) / 4) + epsilon
    #     self.ChScale = scale2apply

    def ReadWave(self, source="C1"):
        """
        Lit la waveform de la source spécifiée.
        Retourne : (T, Y) où T est le vecteur temps et Y le vecteur amplitude.
        """
        if self.CONNECTION_STATUS != 'open':
            raise Exception("Connexion non ouverte.")

        # Nettoie le registre des anciens moyennages
        self.visaObj.write('CLSW')

        # Attend que l'acquisition soit terminée si en mode average
        if self.AcqMode.lower() == 'average':
            avg_nb = self.AcqAvgNb
            while True:
                sweeps = self.SweepsPerAcq
                if sweeps >= avg_nb:
                    break
                time.sleep(0.1)

        time.sleep(3)  # Pause pour laisser le temps à l'instrument de répondre

        # Récupère le délai horizontal (HORIZ_OFFSET)
        resp = self.visaObj.query(f'{source}:INSPECT? "HORIZ_OFFSET"')
        start = resp.find(':') + 1
        end = resp.find('"', start) - 1
        delay = float(resp[start:end].strip())

        # Récupère la fréquence d'échantillonnage
        fs = float(self.visaObj.query('vbs? "return=app.Acquisition.Horizontal.SamplingRate"'))
        tdiv = self.TimeBase  # Durée d'une division
        nbPts = int(fs * tdiv * 10)  # Nombre de points
        ts = 1 / fs  # Période d'échantillonnage

        # Construit le vecteur temps
        tmp_T = np.arange(delay, delay + (nbPts - 1) * ts, ts)

        # Décimation si nécessaire
        if self.AcqSparseNb > 1:
            T = tmp_T[::self.AcqSparseNb]
        else:
            T = tmp_T

        # Récupère les données d'amplitude
        self.visaObj.write(f'{source}:INSPECT? DATA_ARRAY_1,FLOAT')
        self.visaObj.read_bytes(10)  # Lit les 10 premiers octets (en-tête)
        Y = np.fromfile(self.visaObj, dtype=np.float32, count=nbPts)
        Y = Y[1:-1]  # Supprime le premier et dernier point (problème connu)

        # Ajuste la taille de T et Y pour qu'ils aient la même longueur
        if len(T) > len(Y):
            T = T[:len(Y)]
        elif len(Y) > len(T):
            Y = Y[:len(T)]

        return T, Y

    def meanWave(self, chan, meanFactor):
        """
        Effectue un moyennage sur la voie spécifiée.
        Args:
            chan (str): Voie à moyener (ex: 'C1').
            meanFactor (int): Facteur de moyennage.
        """
        if self.CONNECTION_STATUS != 'open':
            raise Exception("Connexion non ouverte.")

        old_active_channel = self.ActiveCh
        self.ActiveCh = chan

        if self.ChState.lower() == 'off':
            warnings.warn(f"La voie {chan} n'est pas active. Activation...")
            self.ChState = 'on'

        self.ActiveCh = old_active_channel

        # Définit le moyennage
        if isinstance(meanFactor, int):
            self.visaObj.write(f'F1:DEFINE EQN,"AVG({chan})",AVERAGETYPE,CONTINUOUS,SWEEPS,{meanFactor} SWEEP,INVALIDINPUTPOLICY,SKIP')
            self.visaObj.write(f'F1:DEFINE SWEEPS,{self.AcqAvgNb}')
        else:
            warnings.warn("meanFactor doit être un entier.")

        # Affiche la voie moyennée (F1)
        self.ActiveCh = 'F1'
        self.ChState = 'on'
        self.ActiveCh = old_active_channel

def main():
    osc=HDO4034A()
    osc.open_connection()
    osc.close_connection()
main()
