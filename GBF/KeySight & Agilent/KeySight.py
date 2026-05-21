import time
import pyvisa


# ──────────── Class KeySight ────────────

class KeySight:

    # ──────────── Constantes ────────────

    #              SINusoid, SQUare, RAMP, PULSe, NOISe
    fonctions  = ["SIN", "SQU", "RAMP", "PULS", "NOIS"]
    freqlimit  = [[1e-3, 10e6], [1e-3, 10e6], [1e-3, 100e6], [1e-3, 5e6], [None, None]]

    # ──────────── Initialisation ────────────

    def __init__(self, adress: str = None):
        self.instrument = None
        self.IP_devices = []
        self.output = False
        self.visa = pyvisa.ResourceManager()

        if adress is not None:
            self.Initialisation(adress)
        else:
            print("\nList of available addresses:")
            self.List_devices()

    def Initialisation(self, adress: str):
        """Connect to the instrument at the given VISA address."""
        try:
            self.instrument = self.visa.open_resource(adress)
            idn = self.instrument.query("*IDN?").strip()
            print(f"Connected: {idn}")
        except Exception as e:
            print(f"\nCould not connect to '{adress}': {e}")
            print("Select another address:")
            self.List_devices()

    def close(self):
        """Close the VISA connection."""
        if self.instrument is not None:
            self.instrument.close()
            self.instrument = None
            print("Disconnected")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    # ──────────── Fct de Base ────────────

    def send_command(self, command: str):
        """
        Send a SCPI command. If the command contains '?', read and return the response.

        Parameters
        ----------
        command : str
            SCPI command string.

        Returns
        -------
        str or None
            Response string if the command is a query, None otherwise.
        """
        if self.instrument is None:
            raise RuntimeError("Instrument is not connected. Call Initialisation() first.")
        self.instrument.write(command)
        if "?" in command:
            return self.instrument.read().strip()
        return None

    def Is_Device_Active(self, IP: str) -> bool:
        """Return True if the resource at IP responds to *IDN?."""
        try:
            test = self.visa.open_resource(IP)
            test.query("*IDN?")
            test.close()
            return True
        except Exception:
            return False

    def List_devices(self, active: bool = False):
        """
        List available VISA resources.

        Parameters
        ----------
        active : bool
            If True, only show resources that respond to *IDN?. Default is False.
        """
        self.visa = pyvisa.ResourceManager()
        self.IP_devices = sorted(self.visa.list_resources())

        if active:
            self.IP_devices = [ip for ip in self.IP_devices if self.Is_Device_Active(ip)]

        if not self.IP_devices:
            print("No device detected.")
        else:
            print("\nList of devices:\n")
            for i, device in enumerate(self.IP_devices, start=1):
                print(f"  {i} : {device}")

    # ──────────── Configuration ────────────

    def Config(self, fct: str = None, amp: float = None, freq: float = None,
               offset: float = None, phase: float = None,
               duty: float = None, sym: float = None):
        """
        Configure the function generator output.

        Parameters
        ----------
        fct    : str   – Waveform function: SIN, SQU, RAMP, PULS, NOIS
        amp    : float – Peak-to-peak amplitude (V)
        freq   : float – Frequency (Hz)
        offset : float – DC offset (V)
        phase  : float – Phase (°)
        duty   : float – Duty cycle (%) for SQU only, clamped to [20–80]
        sym    : float – Symmetry (%) for RAMP only, clamped to [0–100]
        """
        if fct is not None:
            if fct not in self.fonctions:
                print(f"Unknown function '{fct}'. Choose from: {self.fonctions}")
                return
            self.send_command(f"FUNCtion {fct}")

        if amp is not None:
            self.send_command(f"VOLTage {amp}")

        if freq is not None:
            self.send_command(f"FREQuency {freq}")

        if offset is not None:
            self.send_command(f"VOLTage:OFFSet {offset}")

        if phase is not None:
            self.send_command(f"PHASE {phase}")

        if duty is not None:
            current_fct = self.send_command("FUNCtion?")
            if current_fct == "SQU":
                duty = max(20.0, min(80.0, duty))
                self.send_command(f"FUNCtion:SQUare:DCYCle {duty}")
            else:
                print(f"Duty cycle requires SQU function (current: {current_fct}).")

        if sym is not None:
            current_fct = self.send_command("FUNCtion?")
            if current_fct == "RAMP":
                sym = max(0.0, min(100.0, sym))
                self.send_command(f"FUNCtion:RAMP:SYMMetry {sym}")
            else:
                print(f"Symmetry requires RAMP function (current: {current_fct}).")

    def Output(self, ON: bool = None):
        """
        Control the output state.

        Parameters
        ----------
        ON : bool or None
            True = ON, False = OFF, None = toggle.
        """
        if ON is None:
            ON = not self.output

        if ON:
            self.send_command("OUTPut ON")
            self.output = True
        else:
            self.send_command("OUTPut OFF")
            self.output = False

    def Get_State(self) -> dict:
        """Return a dict with the current instrument settings."""
        if self.instrument is None:
            raise RuntimeError("Instrument is not connected.")
        return {
            "function"  : self.send_command("FUNCtion?"),
            "amplitude" : self.send_command("VOLTage?"),
            "frequency" : self.send_command("FREQuency?"),
            "offset"    : self.send_command("VOLTage:OFFSet?"),
            "phase"     : self.send_command("PHASe?"),
            "output"    : self.output,
        }

# ──────────── Fin de class ────────────


# ──────────── Exemple d'utilisation ────────────

if __name__ == "__main__":
    with KeySight() as gbf:
        gbf.List_devices()
        gbf.Initialisation("GPIB2::9::INSTR")

        gbf.Config(fct="SQU", amp=2.0, freq=1e3)
        gbf.Output(True)

        print(gbf.Get_State())

        time.sleep(2)
        gbf.Output(False)
