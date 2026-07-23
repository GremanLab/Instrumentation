"""
HDO4034A — Python driver for LeCroy HDO4034A oscilloscope
Translation of the MATLAB file HDO4034A.m (MCD, Jun. 2021)

Version :
    Author : Timothée Chemla
    Date : June 2024
    Ver : 1.0

Notes :
    Uses ActiveDSO (win32com) for communication with the oscilloscope.
    Prerequisite : pip install pywin32 numpy matplotlib
    Commands (methods) are implemented according to the syntax described in the 'MAUI Oscilloscope Remote Control Manual'
    of LeCroy WaveRunner instruments. Not all functionalities of the instrument are integrated here and can be added.
    Note that most commands are common to different instruments in the WaveRunner range, but some specific features 
    explicitly written here (for example, the number of channels, time limits, etc.) are specific to the HDO4034A.

"""

import win32com.client
import numpy as np
import time
import warnings
import matplotlib.pyplot as plt
import re
import pythoncom



def find_closest(vec, val):
    """Return  the value of vec closest to val."""
    closest = vec[0]
    for elt in vec:
        if abs(elt - val) < abs(closest - val):
            closest = elt
    return closest


class HDO4034A:

    # ──────────── Constants ────────────
    MODEL_NAME = 'HDO 4034A' # Model name
    HSCALE_VEC = [
        100e-12, 200e-12, 500e-12,
        1e-9,  2e-9,  5e-9,  10e-9, 20e-9, 50e-9,
        100e-9, 200e-9, 500e-9,
        1e-6,  2e-6,  5e-6,  10e-6, 20e-6, 50e-6,
        100e-6, 200e-6, 500e-6,
        1e-3,  2e-3,  5e-3,  10e-3, 20e-3, 50e-3,
        100e-3, 200e-3, 500e-3,
        1, 2, 5, 10, 20, 50, 100, 200, 500,
        1e3, 2e3, 2.5e3,
    ] # [s/div] Vector of horizontal (temporal) resolutions accepted by the instrument
    VSCALE_LIM = [1e-3, 1]   # [V/div] updating according to the coupling (D50, D1M, A1M)
    TRIG_LIM   = [-8.20, 8.20]  # [V/div] Trigger level limits (for C1–C4)

    _MEAS_MAP = {
        'frequency': 'FREQ', 'mean':  'MEAN', 'period':   'PER',
        'peak2peak': 'PKPK', 'crms':  'CRMS', 'amplitude':'AMPL',
        'area':      'AREA', 'base':  'BASE',
    }

    # ──────────── Builder ────────────

    def __init__(self):
        self.dso               = None
        self.CONNECTION_STATUS = 'closed' # Connection status ('open' or 'closed')

        # Internal attributes (property storage)
        self._active_ch        = 'C1' # Active channel number as a string of the type 'Cx' with x = 1, 2, 3 or 4
        self.active_ch_id      = 1 # Active channel index
        self._trig_source      = 'C1' # Trigger source ('C1', 'C2', 'C3', 'C4', 'EX') (possibilities to implement others : manual)
        self._trig_type        = 'edge pos' # Trigger type ('edge pos' or 'edge neg') (possibilities to implement others : manual)
        self._meas_source      = 'C1' # 'CX' with X = 1, 2, 3 or 4
        self._meas_type        = 'peak2peak' # Measure type : 'frequency', 'mean', 'period', 'peak2peak', 'crms', 'amplitude', 'area', 'base'
        self.acq_avg_nb_stored = 1 # Number of stored averaging points, bypassing set and get functions, so that they can be read and assigned even when the oscilloscope is not in 'average' mode.
        self._acq_mode_cache   = 'sample' #Acquisition mode : 'sample', 'average', 'envelope'

    # ──────────── Connexion ────────────

    def open_connection(self, ip_adress='169.254.27.102'):
        try:
            # Creation of dso object
            self.dso = win32com.client.Dispatch("LeCroy.ActiveDSOCtrl.1",pythoncom.CoInitialize())
            # Connection
            success  = self.dso.MakeConnection(f"IP:{ip_adress}")
            if not success: # error handling
                raise Exception(f"[HDO4034A] Connection failed : {self.dso.ErrorString}")
            # Communication format definition
            self.dso.WriteString("COMM_HEADER OFF", True)

            self.CONNECTION_STATUS = 'open'

            # Default settings
            self.active_ch     = 'C1'
            self.ch_coupling   = 'D50'
            self.ch_state      = 'on'
            self.trig_type     = 'edge pos'
            self.trig_mode     = 'norm'
            self.acq_sparse_nb = 0

            print(f"[HDO4034A] Connection established with {self.MODEL_NAME} ({ip_adress}).")
        except Exception as e: # error handling
            warnings.warn(f"[HDO4034A] Connection failed : {e}")
            self.CONNECTION_STATUS = 'closed'
            return e

    def close_connection(self):
        if self.dso:
            try:
                self.dso.Disconnect()
                self.CONNECTION_STATUS = 'closed'
                print(f"[HDO4034A] Disconnection of {self.MODEL_NAME}.")
            except Exception as e: # error handling
                warnings.warn(f"[HDO4034A] Error during closing : {e}")

    # ──────────── Active channel ────────────

    @property
    def active_ch(self):
        return self._active_ch

    @active_ch.setter
    def active_ch(self, channel):
        valid = ['C1', 'C2', 'C3', 'C4', 'F1', 'F2', 'F3', 'F4'] # Possibilities to implement other function F1, F2, ..., Fn
        if channel.upper() not in valid: # .upper() to accept all formats : c1 or C1
            raise ValueError(f"Invalid channel. Valids : {valid}")
        self._active_ch    = channel.upper() # type : 'Cx'
        self.active_ch_id  = int(channel[1]) # Channel index
        if self.CONNECTION_STATUS == 'open':
            self.ch_state = 'on' # Trace display

    # ──────────── Channel settings ────────────

    @property
    def ch_scale(self):
        """[V/div] Vertical scale of active channel."""
        self.dso.WriteString(f"{self._active_ch}:VOLT_DIV?", True)
        return float(self.dso.ReadString(80))

    @ch_scale.setter
    def ch_scale(self, ch_scale):
        if not isinstance(ch_scale, (int, float)):
            warnings.warn("Vertical scale must be a number.")
            return
        min_scale = self.VSCALE_LIM[0] * self.ch_probe_att
        max_scale = self.VSCALE_LIM[1] * self.ch_probe_att
        if ch_scale < min_scale:
            warnings.warn(f"Scale too small. Adjusted to {min_scale} V/div.")
            ch_scale = min_scale
        elif ch_scale > max_scale:
            warnings.warn(f"Scale too large. Adjusted to {max_scale} V/div.")
            ch_scale = max_scale
        self.dso.WriteString(f"{self._active_ch}:VOLT_DIV {ch_scale:.6E}", True)

    @property
    def ch_state(self):
        """Active channel display status ('ON' or 'OFF')."""
        self.dso.WriteString(f"{self._active_ch}:TRACE?", True)
        return self.dso.ReadString(80).strip()

    @ch_state.setter
    def ch_state(self, state):
        if state.lower() not in ['on', 'off']:
            warnings.warn('ch_state must be "on" or "off".')
            return
        self.dso.WriteString(f"{self._active_ch}:TRACE {state.upper()}", True)

    @property
    def ch_coupling(self):
        """Active channel coupling ('A1M', 'D1M', 'D50', 'GND')."""
        self.dso.WriteString(f"{self._active_ch}:COUPLING?", True)
        return self.dso.ReadString(80).strip()

    @ch_coupling.setter
    def ch_coupling(self, coupling):
        valid = ['A1M', 'D1M', 'D50', 'GND']
        if coupling.upper() not in valid:
            raise ValueError(f"Invalid coupling. Valids : {valid}")
        self.dso.WriteString(f"{self._active_ch}:COUPLING {coupling.upper()}", True)
        # Updating vertical scale limits based on coupling 
        if coupling.upper() in ['A1M', 'D1M']:
            self.VSCALE_LIM = [1e-3, 10]
        elif coupling.upper() == 'D50':
            self.VSCALE_LIM = [1e-3, 1]

    @property
    def ch_probe_att(self):
        """Attenuation of active channel probe."""
        self.dso.WriteString(f"{self._active_ch}:ATTENUATION?", True)
        return float(self.dso.ReadString(80))

    @ch_probe_att.setter
    def ch_probe_att(self, probe_att):
        valid = [1, 2, 5, 10, 20, 25, 50, 100, 200, 500, 1000, 10000]
        if probe_att not in valid:
            warnings.warn(f"Invalid attenuation. Valids : {valid}")
            return
        self.dso.WriteString(f"{self._active_ch}:ATTENUATION {probe_att}", True)

    @property
    def ch_bw(self):
        """Low pass filter of active channel ('FULL', '20MHZ', '200MHZ')."""
        self.dso.WriteString(f"{self._active_ch}:BANDWIDTH_LIMIT?", True)
        resp  = self.dso.ReadString(256) # Returns a string of the type 'C1,OFF,C2,OFF,C3,OFF,C4,OFF' (after each channel, the value of interest is entered)
        parts = resp.split(',')
        try:
            idx = parts.index(self._active_ch) + 1
            bw  = parts[idx].strip()
        except (ValueError, IndexError):
            return resp.strip()
        return '20MHZ' if bw.upper() == 'ON' else bw.upper()

    @ch_bw.setter
    def ch_bw(self, bw):
        valid = ['full', '20mhz', '200mhz']
        if bw.lower() not in valid:
            warnings.warn(f"Invalid filter. Valids : {[v.upper() for v in valid]}")
            return
        self.dso.WriteString(f"BANDWIDTH_LIMIT {self._active_ch},{bw.upper()}", True)

    # ──────────── Time base ────────────

    @property
    def time_base(self):
        """[s/div] Horizontal resolution (temporal)."""
        self.dso.WriteString("TIME_DIV?", True)
        return float(self.dso.ReadString(80))

    @time_base.setter
    def time_base(self, t_base):
        if not isinstance(t_base, (int, float)):
            warnings.warn("The time base must be a number.")
            return
        val_closest = find_closest(self.HSCALE_VEC, t_base)
        self.dso.WriteString(f"TIME_DIV {val_closest:.6E}", True)
        if val_closest != t_base:
            warnings.warn(
                f"Time base adjusted to closest valid value : {val_closest:.3E} s/div."
            )

    # ──────────── Trigger Settings ────────────

    @property
    def trig_source(self):
        """Trigger source ('C1'-'C4', 'LINE', 'EX', 'EX10')."""
        return self._trig_source

    @trig_source.setter
    def trig_source(self, source):
        valid = ['C1', 'C2', 'C3', 'C4', 'LINE', 'EX', 'EX10']
        if source.upper() not in valid:
            warnings.warn(f"Invalid trigger source. Valids : {valid}")
            return
        self._trig_source = source.upper()
        self.dso.WriteString(f"TRIG_SELECT EDGE,SR,{self._trig_source}", True)

    @property
    def trig_type(self):
        """Trigger type ('edge pos' ou 'edge neg')."""
        return self._trig_type

    @trig_type.setter
    def trig_type(self, trig_type):
        if trig_type.lower() not in ['edge pos', 'edge neg']:
            warnings.warn("Invalid trigger type. Valids : 'edge pos', 'edge neg'")
            return
        self._trig_type = trig_type.lower()
        slope = 'POS' if trig_type.lower() == 'edge pos' else 'NEG'
        self.dso.WriteString(f"TRIG_SELECT EDGE,SR,{self._trig_source}", True)
        self.dso.WriteString(f"{self._trig_source}:TRIG_SLOPE {slope}", True)

    @property
    def trig_mode(self):
        """Trigger mode ('AUTO', 'NORM', 'SINGLE', 'STOP')."""
        self.dso.WriteString("TRIG_MODE?", True)
        return self.dso.ReadString(80).strip()

    @trig_mode.setter
    def trig_mode(self, mode):
        valid = ['AUTO', 'NORM', 'SINGLE', 'STOP']
        if mode.upper() not in valid:
            raise ValueError(f"Invalid trigger mode. Valids : {valid}")
        self.dso.WriteString(f"TRIG_MODE {mode.upper()}", True)

    @property
    def trig_level(self):
        """[V] Trigger level."""
        self.dso.WriteString(f"{self._trig_source}:TRIG_LEVEL?", True)
        return float(self.dso.ReadString(80).replace('V', '').strip())

    @trig_level.setter
    def trig_level(self, level):
        if not isinstance(level, (int, float)):
            warnings.warn("Trigger level must be a number.")
            return
        # Checking if the wanted trigger level respects the allowed limits of the oscilloscope model :
        if level < self.TRIG_LIM[0]:
            warnings.warn(f"Level too low. Adjusted to {self.TRIG_LIM[0]} V.")
            level = self.TRIG_LIM[0]
        elif level > self.TRIG_LIM[1]:
            warnings.warn(f"Level too high. Adjusted to {self.TRIG_LIM[1]} V.")
            level = self.TRIG_LIM[1]
        self.dso.WriteString(f"{self._trig_source}:TRIG_LEVEL {level:.6E}V", True)

    @property
    def trig_coupling(self):
        """Trigger coupling ('AC', 'DC', 'HFREJ', 'LFREJ')."""
        self.dso.WriteString(f"{self._trig_source}:TRIG_COUPLING?", True)
        return self.dso.ReadString(80).strip()

    @trig_coupling.setter
    def trig_coupling(self, coupling):
        valid = ['AC', 'DC', 'HFREJ', 'LFREJ']
        if coupling.upper() not in valid:
            warnings.warn(f"Invalid trigger coupling. Valids : {valid}")
            return
        self.dso.WriteString(
            f"{self._trig_source}:TRIG_COUPLING {coupling.upper()}", True
        )

    # ──────────── Acquisition Settings ────────────

    @property
    def acq_sparse_nb(self):
        """Decimation (0 = all points)."""
        self.dso.WriteString("WAVEFORM_SETUP?", True)
        resp = self.dso.ReadString(256) # Returns a string of the type 'SP,x1,NP,x1,FP,x3,SN,x4'. The sparse number we are looking for corresponds to x1
        m = re.search(r'SP,(\d+)', resp)
        return int(m.group(1)) if m else 0

    @acq_sparse_nb.setter
    def acq_sparse_nb(self, nb):
        if not isinstance(nb, int):
            warnings.warn("acq_sparse_nb must be an integer.")
            return
        self.dso.WriteString(f"WAVEFORM_SETUP SP,{nb},NP,0,FP,0,SN,0", True) # By default, we send all the segment

    @property
    def acq_mode(self):
        """Acquisition mode : 'sample', 'average' ou 'envelope'."""
        self.dso.WriteString("PERSIST?", True)
        if self.dso.ReadString(80).strip().upper() == 'ON':
            return 'envelope'
        self.dso.WriteString(
            f' vbs? "return=app.Acquisition.{self._active_ch}.AverageSweeps"', True
        )
        try:
            if int(self.dso.ReadString(80)) != 1:
                return 'average'
        except ValueError:
            pass
        return 'sample'

    @acq_mode.setter
    def acq_mode(self, mode):
        m = mode.lower()
        if m == 'sample':
            self.dso.WriteString("PERSIST OFF", True)
            self.dso.WriteString(
                f' vbs "app.Acquisition.{self._active_ch}.AverageSweeps = 1"', True
            )
        elif m == 'average':
            self.dso.WriteString(
                f' vbs "app.Acquisition.{self._active_ch}.AverageSweeps = {self.acq_avg_nb_stored}"',
                True,
            )
            self.dso.WriteString("PERSIST OFF", True)
        elif m == 'envelope':
            self.dso.WriteString(
                f' vbs "app.Acquisition.{self._active_ch}.AverageSweeps = 1"', True
            )
            self.dso.WriteString("PERSIST ON", True)
            self.dso.WriteString("PERSIST_SETUP infinite,PERTRACE", True)
        else:
            raise ValueError("Invalid mode. Valids : 'sample', 'average', 'envelope'")
        self._acq_mode_cache = m

    @property
    def acq_avg_nb(self):
        """Number of averages."""
        return self.acq_avg_nb_stored

    @acq_avg_nb.setter
    def acq_avg_nb(self, nb):
        if not isinstance(nb, int):
            warnings.warn("acq_avg_nb must be an integer.")
            return
        self.acq_avg_nb_stored = nb

    @property
    def acq_sample_max(self):
        """Maximum number of sample (MSIZ)."""
        self.dso.WriteString("MSIZ?", True)
        return int(float(self.dso.ReadString(80)))

    @acq_sample_max.setter
    def acq_sample_max(self, max_samples):
        valid = [500, 10_000, 100_000, 1_000_000,
                 2_500_000, 5_000_000, 10_000_000, 12_500_000, 25_000_000] # vector of values ​​accepted by the instrument
        if max_samples not in valid:
            warnings.warn(f"Invalid value. Valids : {valid}")
            return
        self.dso.WriteString(f"MEMORY_SIZE {int(max_samples)}", True)

    @property
    def acq_delay(self):
        """[s] Acquisition delay (time between trigger and the center of the window)."""
        self.dso.WriteString("TRIG_DELAY?", True)
        return -float(self.dso.ReadString(80))

    @acq_delay.setter
    def acq_delay(self, delay):
            # Range negative delay:( 0 to -10,000) x Time/div
            # Range postive delay:(0 to +10) x Time/div
        if not isinstance(delay, (int, float)):
            warnings.warn("acq_delay must be a number.")
            return
        self.dso.WriteString(f"TRIG_DELAY {-delay:.6E}", True)
    
    # Negative sign explenation :
    # The internal function 'TRIG_DELAY?' returns the time at which the trigger occurs, relative to the nominal 0, which is the center of the acquisition window. That is to say, it returns a negative value when the clock pulse
    # corresponding to the trigger is before the center of the window, and conversely, a positive value when it is after. For convenience, we prefer to speak in terms of acquisition delay, that is, to return the
    # time elapsed between the trigger and the center of the window; this is why we multiply by -1 in the definition of AcqDelay


    # ──────────── Sweeps ────────────

    @property
    def sweeps_per_acq(self):
        """Average number of sweeps since the last CLSW."""
        self.dso.WriteString(f'{self._active_ch}:INSPECT? "SWEEPS_PER_ACQ"', True)
        resp = self.dso.ReadString(256)
        m = re.search(r':\s*([\d.eE+\-]+)', resp)
        if m:
            return int(float(m.group(1)))
        raise ValueError(f"Cannot parse SWEEPS_PER_ACQ : {resp!r}")

    # ──────────── Measurement Settings ────────────

    @property
    def meas_source(self):
        """measure source channel ('C1'–'C4')."""
        return self._meas_source

    @meas_source.setter
    def meas_source(self, source):
        valid = ['C1', 'C2', 'C3', 'C4']
        if source.upper() not in valid:
            raise ValueError(f"Invalid source. Valids : {valid}")
        self._meas_source = source.upper()

    @property
    def meas_type(self):
        """Measure type ('frequency', 'mean', 'peak2peak', …)."""
        return self._meas_type

    @meas_type.setter
    def meas_type(self, meas_type):
        if meas_type.lower() not in self._MEAS_MAP:
            raise ValueError(
                f"Invalid type. Valids : {list(self._MEAS_MAP.keys())}"
            )
        self._meas_type = meas_type.lower()

    @property
    def meas_value(self):
        """(read only) Numerical value of the current measurement."""
        scpi_param = self._MEAS_MAP[self._meas_type]
        # Activate the measurement of the oscilloscope and then wait for the calculation
        self.dso.WriteString(
            f"{self._meas_source}:PARAMETER_CUSTOM {scpi_param}", True
        )
        time.sleep(0.5)
        self.dso.WriteString(
            f"{self._meas_source}:PARAMETER_VALUE? {scpi_param}", True
        )
        resp  = self.dso.ReadString(256)
        parts = resp.split(',')
        try:
            return float(parts[-1])
        except ValueError:
            raise ValueError(f"Cannot read meas_value : {resp!r}")

    # ──────────── Read of waveform ────────────
    def read_wave(self, source='C1'):
        """
        Acquisition of a waveform.

        Settings
        ----------
        source : str  — Voie : 'C1'–'C4' ou 'F1'–'F4'.

        Return
        --------
        T : np.ndarray  — time vector [s]
        Y : np.ndarray  — amplitude vector [V]
        """
        
        # Reset the average number of signals
        self.dso.WriteString('CLSW', True)

        if self._acq_mode_cache == 'average':
            avg_nb = self.acq_avg_nb_stored
            self.dso.WriteString('TRIG_MODE NORM', True)
            print(f"Waiting for {avg_nb} sweeps …")

            last_count = 0
            no_progress_time = 0

            while self.sweeps_per_acq < avg_nb:
                current = self.sweeps_per_acq
                print(f"{current} / {avg_nb}")

                # Détecte si le compteur est bloqué
                if current == last_count:
                    no_progress_time += 0.5
                    if no_progress_time >= 3.0:
                        print(f"⚠ Trigger bloqué à {current} sweeps — vérifiez le signal et le seuil de trigger.")
                        print(f"  trig_mode  : {self.trig_mode}")
                        print(f"  trig_level : {self.trig_level} V")
                        break  # sort de la boucle plutôt que boucler à l'infini
                else:
                    no_progress_time = 0
                    last_count = current

                time.sleep(0.5)

        time.sleep(1)
        
        waveform = self.dso.GetScaledWaveformWithTimes(source, 0, 0) # waveform recovery with active DSO
        if self.dso.ErrorFlag:
            raise Exception(f"Error : {self.dso.ErrorString}")

        data = np.array(waveform)
        T = data[0].astype(np.float64)
        Y = data[1].astype(np.float64)
        return T, Y

    # ──────────── Specific methods ────────────

    def re_scale(self):
        """Automatically adjusts the vertical scale of the active channel."""
        _, Y     = self.read_wave(self._active_ch) # Acquiring the signal within the window in order to calculate its vertical limits
        offset   = np.mean(Y)
        envelope = np.abs(Y - offset) # Not sure, normally : abs(hilber(Y-offset)) but we don't have the hilbert function for the moment
        epsilon  = 0.25e-3   # margin [V]
        self.ch_scale = float(np.max(envelope) / 4) + epsilon # new scale factor [V/div]

    def mean_wave(self, chan, mean_factor):
        """
        Configure the channel averaging on F1.

        Settings
        ----------
        chan : str        — Channel source ('C1'–'C4').
        mean_factor : int — Average number of sweeps.
        """
        # Channel recovery
        if chan.upper() not in ['C1', 'C2', 'C3', 'C4']:
            raise ValueError(
                "Invalid channel. mean_wave only works on C1–C4."
            )
        if not isinstance(mean_factor, int):
            warnings.warn("mean_factor must be an integer.")
            return

        old_ch = self._active_ch # keep old active channel
        self.active_ch = chan
        if self.ch_state.lower() == 'off':
            warnings.warn(f"Channel {chan} is not active — activating.")
            self.ch_state = 'on'
        self.active_ch = old_ch

        # Definition of averaging
        self.dso.WriteString(
            f'F1:DEFINE EQN,"AVG({chan.upper()})",AVERAGETYPE,CONTINUOUS,'
            f'SWEEPS,{mean_factor} SWEEP,INVALIDINPUTPOLICY,SKIP',
            True,
        )

        # Display of F1
        old_ch = self._active_ch
        self.active_ch = 'F1'
        self.ch_state  = 'on'
        self.active_ch = old_ch


# ──────────── Main ────────────

def main(): # tests of some functions defined here
    osc = HDO4034A()
    osc.open_connection()
    try:
        osc.active_ch   = 'C1'
        osc.ch_coupling = 'D50'
        osc.ch_scale    = 0.2
        osc.time_base   = 1e-6
        osc.trig_source = 'C1'
        osc.trig_type   = 'edge pos'
        osc.trig_level  = 0.1
        osc.trig_mode   = 'auto'   # AUTO pour déclencher même sans signal

        T, Y = osc.read_wave('C1')
        print(f"{len(T)} points — "
              f"T=[{T[0]:.3e}, {T[-1]:.3e}] s — "
              f"Y=[{Y.min():.3f}, {Y.max():.3f}] V")

        osc.meas_source = 'C1'
        osc.meas_type   = 'frequency'
        #print(f"Measured frequency : {osc.meas_value:.3f} Hz")

        plt.figure()
        plt.plot(T * 1e6, Y)
        plt.xlabel("Time (µs)")
        plt.ylabel("Amplitude (V)")
        plt.title(f"Waveform — {osc.MODEL_NAME} C1")
        plt.grid(True)
        plt.tight_layout()
        plt.show()

    finally:
        osc.dso.WriteString("BUZZ",True)
        time.sleep(0.5)
        osc.dso.WriteString("BUZZ",True)
        time.sleep(0.5)
        osc.dso.WriteString("BUZZ",True)
        time.sleep(0.5)
        osc.close_connection()


if __name__ == '__main__': 
    main()
