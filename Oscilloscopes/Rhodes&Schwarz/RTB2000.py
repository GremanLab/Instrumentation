import csv
import math
import os
import time
from time import process_time_ns

import matplotlib.pyplot as plt
import RsInstrument as rs

# ──────────── Classe principale ────────────

class RsInstrument:
    """
    Driver for Rohde & Schwarz RTM2000 / RTM3000 oscilloscopes.

    Wraps RsInstrument to provide waveform acquisition, caliber control,
    averaging, auto-scale and data export helpers.
    """

    def __init__(self, IP_ADRESS: str = IP_address3k,
                 time_out: int = 1000,
                 baudrate: int = 9600,
                 limit_time: float = 0.0):
        """
        Parameters
        ----------
        IP_ADRESS  : str   – VISA address of the oscilloscope.
        time_out   : int   – VISA timeout in ms.
        baudrate   : int   – UART bus baudrate (written at startup).
        limit_time : float – Data before this time (s) is discarded in Measure().
        """
        self.rtm = rs.RsInstrument(IP_ADRESS)
        self.rtm.visa_timeout = time_out
        self.rtm.write(f"BUS1:UART:BAUDrate {baudrate}")
        self.limit_time = limit_time

        print("Waiting for the acquisition to finish…", end=" ", flush=True)
        self.rtm.query('*OPC?')

        model_str = self.rtm.query("*IDN?")
        if "RTM3" in model_str:
            self.modele   = 3
            self.amplimit = [1e-3, 10]
            self.timelimit = [1e-9, 500]
        else:
            self.modele   = 2
            self.amplimit = [1e-3, 5]
            self.timelimit = [1e-9, 50]

        self.channel = None

        # Save settings for all active channels
        for channel in range(1, 5):
            if self.rtm.query_int(f"CHAN{channel}:STATe?") == 1:
                self.Save_Oscillo_Settings(channel)

        print("Done")

    def TimeOut(self, time_out: int):
        """Set the VISA timeout in ms."""
        self.rtm.visa_timeout = time_out

    def close(self):
        """Close the VISA connection."""
        self.rtm.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


    # ──────────── Utilitaires ────────────

    def Errors_Reset(self):
        """Clear the instrument status and error queue."""
        self.rtm.clear_status()
        self.rtm.write('*CLS')
        time.sleep(0.1)

    def Limit_Time(self, limit_time: float):
        """Set the minimum time from which waveform data is kept."""
        self.limit_time = limit_time


    # ──────────── Calibres ────────────

    def Calibers(self, channel: int = None,
                 time_scale: float = None,
                 amplitude_scale: float = None,
                 horizontal_pos: float = None,
                 vertical_pos: float = None,
                 trigger: float = None):
        """
        Set oscilloscope scales and positions.

        Parameters
        ----------
        channel         : int   – Channel number (1–4).
        time_scale      : float – Time/div (s), clamped to instrument limits.
        amplitude_scale : float – V/div, clamped to instrument limits.
        horizontal_pos  : float – Horizontal position (s).
        vertical_pos    : float – Vertical position (divs), clamped to [−5, 5].
        trigger         : float – Trigger level (V).
        """
        if channel is not None:
            if amplitude_scale is not None:
                amplitude_scale = max(self.amplimit[0], min(self.amplimit[1], amplitude_scale))
                self.rtm.write(f'CHANnel{channel}:SCALe {amplitude_scale}')

            if vertical_pos is not None:
                vertical_pos = max(-5.0, min(5.0, vertical_pos))
                self.rtm.write(f'CHANnel{channel}:POSition {vertical_pos}')

            if trigger is not None:
                self.rtm.write(f'TRIGger:A:LEVel{channel} {trigger}')

        if time_scale is not None:
            time_scale = max(self.timelimit[0], min(self.timelimit[1], time_scale))
            self.rtm.write(f'TIMebase:SCALe {time_scale}')

        if horizontal_pos is not None:
            self.rtm.write(f'TIMebase:POSition {horizontal_pos}')

    def Time_Vector(self, t0: float, dt: float, nb_points: int) -> list:
        """Build the time axis list from t0, dt and point count."""
        return [t0 + dt * i for i in range(nb_points)]


    # ──────────── Acquisition ────────────

    def Average(self, samples_nb: int):
        """
        Enable averaging mode with the given number of samples.

        Parameters
        ----------
        samples_nb : int – Number of averages (minimum 2).
        """
        samples_nb = max(2, samples_nb)
        self.rtm.write('CHANnel:ARIThmetics AVERage')
        time.sleep(0.01)
        self.rtm.write(f'ACQ:AVER:COUN {samples_nb}')

    def Actualise(self, affichage: bool = False):
        """
        Restart the acquisition and wait until averaging is complete.

        Parameters
        ----------
        affichage : bool – Print progress messages.
        """
        self.rtm.write('STOP\nRUN')

        if affichage:
            print("\nWaiting for acquisition…", end=" ", flush=True)

        while self.rtm.query_int('ACQuire:AVERage:COMPlete?') != 1:
            time.sleep(0.05)

        if affichage:
            print("Done")

    def Vertical_Adjust(self, channel: int, Hlimit: float = 4.0,
                        Llimit: float = 2.0, quick: bool = False) -> bool:
        """
        Auto-adjust the vertical scale so the signal occupies [Llimit, Hlimit] divisions.

        Parameters
        ----------
        channel : int   – Channel to adjust.
        Hlimit  : float – Upper division limit (default 4).
        Llimit  : float – Lower division limit (default 3).
        quick   : bool  – If True, use a fast 2-average cycle (less accurate).

        Returns
        -------
        bool – True if the scale was changed.
        """
        saved_average = self.rtm.query('ACQ:AVER:COUN?')

        self.rtm.write('STOP\nRUN')

        t0, dt, data = self.Measure(channel)
        data_abs = Redressement(data)
        maximum = max(data_abs)

        scale = self.rtm.query_float(f'CHANnel{channel}:SCALe?')

        if maximum > Llimit * scale and maximum < Hlimit * scale:
            # Signal is already well-framed
            return False

        if quick :
            self.rtm.write('ACQ:AVER:COUN 2')

        # Coarse upward step if clipping
        while maximum > Hlimit * scale :
            scale = (self.amplimit[1]*2+scale)/3
            self.rtm.write(f'CHANnel{channel}:SCALe {scale}')

            self.rtm.write('STOP\nRUN')
            t0, dt, data = self.Measure(channel)
            maximum = max(Redressement(data))

        # Fine adjustment
        target = Hlimit

        scale = max(self.amplimit[0], min(self.amplimit[1], maximum / target))
        self.rtm.write(f'CHANnel{channel}:SCALe {scale}')

        t0, dt, data = self.Measure(channel)
        maximum = max(Redressement(data))

        if quick :
            self.rtm.write(f'ACQ:AVER:COUN {saved_average}')

        return True


    # ──────────── Mesures ────────────

    def Total_Waveform(self, channel: int) -> list:
        """Return the full waveform data from a channel (no time trimming)."""
        return self.rtm.query_bin_or_ascii_float_list(f'FORM ASC;:CHAN{channel}:DATA?')

    def Measure(self, channel: int):
        """
        Acquire the waveform from one channel, trimming data before limit_time.

        Parameters
        ----------
        channel : int – Channel number (1–4).

        Returns
        -------
        t0   : float – Time of the first sample (s).
        dt   : float – Sample interval (s).
        data : list  – Voltage samples (V).
        """
        self.channel = channel
        time.sleep(0.05)

        for attempt in range(2):
            try:
                data = self.rtm.query_bin_or_ascii_float_list(f'FORM ASC;:CHAN{channel}:DATA?')
                time.sleep(0.01)
                t0 = self.rtm.query_float(f'CHAN{channel}:DATA:XOR?')
                time.sleep(0.01)
                dt = self.rtm.query_float(f'CHAN{channel}:DATA:XINC?')
                time.sleep(0.01)
                break
            except Exception as e:
                if attempt == 0:
                    print(f"  Measurement error: {e}. Retrying…")
                    self.Errors_Reset()
                    time.sleep(0.5)
                else:
                    raise

        # Trim data before limit_time
        if t0 < self.limit_time:
            nb = int((self.limit_time - t0) / dt)
            data = data[nb:]
            t0 = nb * dt + t0

        return t0, dt, data

    def Save_and_Plot(self, channel: int):
        """Acquire a channel and plot it immediately."""
        t0, dt, data = self.Measure(channel)
        Plot(data, self.Get_Time(t0, dt, len(data)))

    def Seuil_Value(self, seuil: float, t0: float, dt: float, data: list):
        """
        Return the time of the first sample that exceeds the threshold.

        Parameters
        ----------
        seuil : float – Threshold voltage (V).
        t0    : float – Start time (s).
        dt    : float – Sample interval (s).
        data  : list  – Voltage samples.

        Returns
        -------
        float – Time at which the threshold is first exceeded, or None.
        """
        for i, value in enumerate(data):
            if value > seuil:
                return t0 + i * dt
        return None

    def Peak_Analisis(self, t0: float, dt: float, data: list,
                      peak_duration:float, seuil: float,
                      get_time: bool = True):
        """
        Detect peaks in a waveform based on a seuil and peak duration.

        Parameters
        ----------
        t0       : float – Start time (s).
        dt       : float – Sample interval (s).
        data     : list  – Voltage samples.
        get_time : bool  – Return times (True) or sample indices (False).

        Returns
        -------
        list of [start, end] pairs for the 1st detected peak.
        """
        for idx in range(len(data)):
            if data[idx] >= seuil:
                break
        if idx > 100:
            idx -= 100

        if get_time:
            t = idx*dt+t0
            return [t,t+peak_duration]

        else:
            length = int(((peak_duration-t0)/dt)+1)
            return [idx, idx+length]


    def Math_Peak_Analisis(self, t0: float, dt: float, data: list,
                      get_time: bool = True) -> list:
        """
        Detect peaks in a waveform using a derivative + zero-plateau method.

        Parameters
        ----------
        t0       : float – Start time (s).
        dt       : float – Sample interval (s).
        data     : list  – Voltage samples.
        get_time : bool  – Return times (True) or sample indices (False).

        Returns
        -------
        list of [start, end] pairs for each detected peak.
        """
        derive = [abs(data[i + 1] - data[i]) for i in range(len(data) - 1)]

        maximum = max(derive) if derive else 1
        exp = math.floor(math.log10(maximum)) if maximum > 0 else 0
        derive_norm = [int(v / (5 * 10 ** (exp - 1))) for v in derive]

        plt.plot(derive_norm)
        plt.show()

        seuil_value = 1000
        nb0 = 0
        peaks = []
        one_peak = []
        in_peak = False

        for idx, val in enumerate(derive_norm):
            if val in (0, 1):
                nb0 += 1
            elif nb0 > seuil_value:
                entry = (idx - 100) * dt + t0 if get_time else idx - 100
                one_peak.append(entry)
                in_peak = True
                nb0 = 0

            if in_peak and nb0 > seuil_value:
                exit_val = idx * dt + t0 if get_time else idx
                one_peak.append(exit_val)
                in_peak = False
                peaks.append(one_peak)
                one_peak = []

        if not peaks:
            t0_new, dt_new, data_new = self.Measure(self.channel)
            return self.Peak_Analisis(t0_new, dt_new, data_new, get_time)

        return peaks


    # ──────────── Sauvegarde réglages ────────────

    def Save_Oscillo_Settings(self, channel: int) -> dict:
        """
        Read and store the current oscilloscope settings for one channel.

        Returns
        -------
        dict with keys: time_scale, amplitude_scale, horizontal_position,
                        vertical_position, average.
        """
        self.time_scale          = self.rtm.query_float('TIMebase:SCALe?')
        self.amplitude_scale     = self.rtm.query_float(f'CHANnel{channel}:SCALe?')
        self.horizontal_position = self.rtm.query_float('TIMebase:POSition?')
        self.vertical_position   = self.rtm.query_float(f'CHANnel{channel}:POSition?')
        self.average             = self.rtm.query_int('ACQ:AVER:COUN?')

        return {
            "time_scale"          : self.time_scale,
            "amplitude_scale"     : self.amplitude_scale,
            "horizontal_position" : self.horizontal_position,
            "vertical_position"   : self.vertical_position,
            "average"             : self.average}

    def Set_Oscillo_Settings(self, channel: int,
                             settings=None, save: bool = True):
        """
        Apply oscilloscope settings to one channel.

        Parameters
        ----------
        channel  : int         – Target channel.
        settings : dict or list or None – Settings to apply (None → use saved).
        save     : bool        – Update stored settings after applying.
        """
        if settings is not None:
            if isinstance(settings, (list, tuple)):
                ts, amp, hp, vp, avg = settings[:5]
            elif isinstance(settings, dict):
                ts  = settings["time_scale"]
                amp = settings["amplitude_scale"]
                hp  = settings["horizontal_position"]
                vp  = settings["vertical_position"]
                avg = settings["average"]
            else:
                raise TypeError("settings must be a list, tuple, or dict.")
        else:
            ts, amp, hp, vp, avg = (self.time_scale, self.amplitude_scale,
                                     self.horizontal_position, self.vertical_position,
                                     self.average)

        self.rtm.write(f'TIMebase:SCALe {ts}')
        self.rtm.write(f'CHANnel{channel}:SCALe {amp}')
        self.rtm.write(f'TIMebase:POSition {hp}')
        self.rtm.write(f'CHANnel{channel}:POSition {vp}')
        self.rtm.write(f'ACQ:AVER:COUN {avg}')

        if save:
            self.time_scale          = ts
            self.amplitude_scale     = amp
            self.horizontal_position = hp
            self.vertical_position   = vp
            self.average             = avg

    def Save_Caliber(self, user_name: str, file_name: str = "meta-data.txt"):
        """
        Append the current caliber settings to a text file.

        Parameters
        ----------
        user_name : str – Label or name for this entry.
        file_name : str – Path to the metadata file.
        """
        line = (f"{user_name};"
                f"{self.amplitude_scale};"
                f"{self.time_scale};"
                f"{self.horizontal_position};"
                f"{self.vertical_position};"
                f"{self.average}\n")
        with open(file_name, 'a') as f:
            f.write(line)

    def Import_Calibers(self, file_name: str = "meta-data.txt") -> list:
        """
        Read caliber entries previously saved by Save_Caliber().

        Returns
        -------
        list of dict
        """
        entries = []
        keys = ["name", "amplitude_scale", "time_scale",
                "horizontal_position", "vertical_position", "average"]
        with open(file_name, 'r') as f:
            for line in f:
                parts = line.strip().split(";")
                if len(parts) == len(keys):
                    entries.append(dict(zip(keys, parts)))
        return entries


# ──────────── Fonctions utilitaires ────────────

def Export_data(path: str, data: list):
    """
    Export a list of values to a CSV file (one value per line, appending).

    Parameters
    ----------
    path : str  – File path. '.csv' extension is added if missing.
    data : list – Values to write.
    """
    if not (path.endswith(".csv") or path.endswith(".txt")):
        path += ".csv"

    with open(path, "w", newline="") as f:
        for value in data:
            f.write(str(value) + "\n")


def Import(path: str):
    """
    Import waveform data from a CSV file.

    Expected format: line 0 = t0, line 1 = dt, remaining lines = samples.

    Parameters
    ----------
    path : str – File path (.csv or .txt).

    Returns
    -------
    t0        : float
    dt        : float
    data_float: list of float
    """
    if not (path.endswith(".txt") or path.endswith(".csv")):
        path += ".csv"

    with open(path, mode='r') as f:
        reader = csv.reader(f)
        rows = list(reader)

    t0 = float(rows[0][0])
    dt = float(rows[1][0])
    data_float = [float(row[0]) for row in rows[2:]]

    return t0, dt, data_float


def Add_data(path: str, data: list):
    """
    Append a new column (semicolon-separated) to each line of an existing file.

    Parameters
    ----------
    path : str  – Path to the existing file.
    data : list – New values, one per line.
    """
    tmp_path = path + ".tmp"

    with open(path, mode='r') as src, open(tmp_path, mode='w') as dst:
        for i, line in enumerate(src):
            suffix = str(data[i]) if i < len(data) else ""
            dst.write(line.rstrip("\n") + ";" + suffix + "\n")

    os.replace(tmp_path, path)


def Plot(value: list, time_axis: list,
         xlabel: str = "Time (s)", ylabel: str = "Amplitude (V)"):
    """
    Plot a waveform.

    Parameters
    ----------
    value     : list – Y values.
    time_axis : list – X values (time).
    xlabel    : str  – X-axis label.
    ylabel    : str  – Y-axis label.
    """
    fig, ax = plt.subplots()
    ax.plot(time_axis, value)
    ax.set(xlabel=xlabel, ylabel=ylabel)
    plt.tight_layout()
    plt.show()


def Redressement(data: list) -> list:
    """Return the element-wise absolute value of a list."""
    return [abs(v) for v in data]


# ──────────── Exemple d'utilisation ────────────

if __name__ == "__main__":
    with RsInstrument(IP_address3k, limit_time=0.0) as oscillo:
        oscillo.Calibers(channel=1, time_scale=1e-3, amplitude_scale=0.2)
        oscillo.Average(32)
        oscillo.Actualise(affichage=True)

        t0, dt, data = oscillo.Measure(channel=1)
        time_axis = oscillo.Get_Time(t0, dt, len(data))

        Plot(data, time_axis)
        Export_data("acquisition.csv", data)
