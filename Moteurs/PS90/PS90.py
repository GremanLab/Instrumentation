import time
import serial


# ──────────── Class PS90 ────────────

class PS90:

    axis_state = {
        "I": "Axis is initialized",
        "O": "Axis is disabled",
        "R": "Axis initialized and ready",
        "T": "Axis is positioning in trapezoidal profile",
        "S": "Axis is positioning in S-curve profile",
        "V": "Axis is operating in velocity mode",
        "P": "Reference motion is in progress",
        "F": "Axis is releasing a limit switch",
        "J": "Axis is operating in joystick mode",
        "L": "Axis has been disabled after approaching a hardware limit switch (MINSTOP, MAXSTOP)",
        "B": "Axis has been stopped after approaching a brake switch (MINDEC, MAXDEC)",
        "A": "Axis has been disabled after limit switch error",
        "M": "Axis has been disabled after motion controller error",
        "Z": "Axis has been disabled after timeout error",
        "H": "Phase initialization active (step motor axis)",
        "U": "Axis is not released",
        "E": "Axis has been disabled after motion error",
        "?": "Error, unknown state of axis",
    }
    
    
    # ──────────── Initialisation ────────────

    def __init__(self, COM: str, baudrate: int = 9600, timeout: float = 0.005):
        self.serial = serial.Serial(port=COM, baudrate=baudrate, timeout=timeout)
        self.initialized_axis = []
        self.affichage = True
        self.Unit()
        self.velocity = 301990
        
        
    def Unit(self, unit: str = "milli"):
        """
        Set the displacement unit.

        Parameters
        ----------
        unit : str
            'milli' (mm, default), 'micro' (µm), 'centi' (cm), 'pas' (raw steps).
        """
        self._unit_ratios = {"centi": 0.5e-4, "milli": 0.5e-3, "micro": 0.5, "pas": 1}
        if unit not in self._unit_ratios:
            print(f"Unknown unit '{unit}'. Defaulting to 'milli'. Options: {list(self._unit_ratios)}")
            unit = "milli"
        self.unit = unit
        self.ratio = self._unit_ratios[self.unit]

    def Affichage(self, affiche: bool):
        """Enable or disable console messages."""
        self.affichage = affiche

    def close(self):
        """Close the serial connection."""
        if self.serial.is_open:
            self.serial.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    # ──────────── Communication ────────────

    def send_command(self, cmd: str):
        """
        Send a command to the PS90 controller.

        Commands starting with '?' are read-queries: the response is returned.
        All other commands are write-only and return None.

        Parameters
        ----------
        cmd : str
            Command string (without trailing CR).

        Returns
        -------
        str or None
        """
        time.sleep(0.05)
        self.serial.write((cmd + '\r').encode('ascii'))
        time.sleep(0.05)

        if cmd.startswith("?"):
            response = b""
            deadline = time.time() + 1.0
            while time.time() < deadline:
                chunk = self.serial.read(128)
                if chunk:
                    response += chunk
                    if b'\r' in response:
                        break
            return response.decode('ascii', errors='replace').strip()
        return None

    def _get_axis_status(self) -> str:
        """Return the raw ASTAT string (one char per axis)."""
        return self.send_command("?ASTAT") or ""

    # ──────────── Settings ────────────

    def Referenciel(self, axe: int, absolu: bool = None, affichage: bool = True):
        """
        Set the reference frame for an axis.

        Parameters
        ----------
        axe     : int  – Axis number.
        absolu  : bool – True for absolute mode, False for relative.
        affichage : bool – Print confirmation message.
        """
        if absolu == None:
            return self.send_command(f"?MODE{axe}")
            
        if absolu:
            self.send_command(f"ABSOL{axe}")
            if affichage:
                print(f"Axis {axe}: absolute mode enabled")
        else:
            self.send_command(f"RELAT{axe}")
            if affichage:
                print(f"Axis {axe}: relative mode enabled")

    # ──────────── Initialisation des axes ────────────

    def Initialisation_Axe(self, axe: int):
        """Perform a full initialization sequence on a single axis."""
        self.send_command(f"EFREE{axe}")
        self.send_command(f"AXIS{axe}=0")
        time.sleep(0.5)
        self.send_command(f"AXIS{axe}=1")
        self.send_command(f"INIT{axe}")
        self.send_command(f"MON{axe}")

        if axe not in self.initialized_axis:
            self.initialized_axis.append(axe)

    def Initialisation_Axes(self, axes: list, absolu: bool = None, affichage: bool = True):
        """
        Initialize one or more axes, skipping those already ready.

        Parameters
        ----------
        axes      : list  – List of axis numbers to initialize.
        absolu    : bool  – If not None, sets the reference frame before init.
        affichage : bool  – Print status messages.
        """
        if affichage is not None:
            self.affichage = affichage

        status = self._get_axis_status()

        for axe in axes:
            if absolu is not None:
                self.Referenciel(axe, absolu, affichage=self.affichage)

            state_char = status[axe - 1] if axe - 1 < len(status) else "?"
            if self.affichage:
                print(f"Axis {axe}: [{state_char}] {self.axis_state.get(state_char, '?')}")

            if axe not in self.initialized_axis:
                self.initialized_axis.append(axe)

            if state_char == "R":
                if self.affichage:
                    print("  → Already initialized\n")
                continue

            self.Initialisation_Axe(axe)

            if self.affichage:
                status = self._get_axis_status()
                state_char = status[axe - 1] if axe - 1 < len(status) else "?"
                print(f"  → After init: [{state_char}] {self.axis_state.get(state_char, '?')}\n")

        if self.affichage:
            print(f"All axes status: {self._get_axis_status()}\n")

    # ──────────── Déplacement ────────────

    def Move(self, axe: int, deplacement: float, absolu: bool = None):
        """
        Move an axis by a given displacement.

        Parameters
        ----------
        axe         : int   – Axis number.
        deplacement : float – Displacement in the current unit (mm by default).
        absolu      : bool  – If not None, sets the reference frame before moving.
        """
        if absolu is not None:
            self.Referenciel(axe, absolu, affichage=False)

        steps = self.Conversion_mm_pas(deplacement)
        status = self._get_axis_status()
        state_char = status[axe - 1] if axe - 1 < len(status) else "?"

        if self.affichage:
            print(f"\nAxis {axe}: [{state_char}] {self.axis_state.get(state_char, '?')}")
            position = self.Get_Position(axe)

            base = self.Referenciel(axe)
            
            if base == 'RELAT':
                position += deplacement
            if base == 'ABSOL':
                position = deplacement
            print(f"Axis {axe} will go to {position:.2f} {self.unit}")
            

        if state_char == "A":
            print(f"  → Axis {axe} in error state, re-initializing…")
            self.Initialisation_Axe(axe)
            status = self._get_axis_status()
            state_char = status[axe - 1] if axe - 1 < len(status) else "?"

        if state_char != "R":
            print(f"  → Axis {axe} is not ready (state: {state_char}). Move aborted.")
            return None

        self.send_command(f"PSET{axe}={int(steps)}")
        self.send_command(f"PGO{axe}")

        # Wait until the axis is ready again
        t0 = time.time()
        while True:
            status = self._get_axis_status()
            state_char = status[axe - 1] if axe - 1 < len(status) else "?"

            if state_char == "R":
                break

            if state_char == "A":
                print(f"  → Movement stopped: limit switch triggered on axis {axe}")
                break
            
            position = self.Get_Position(axe)
            if self.affichage and time.time() - t0 > 1.0:
                print(f"  … Actual position : {position:.2f} {self.unit}")
                # print(f"  … [{state_char}] {self.axis_state.get(state_char, '?')}")
                t0 = time.time()

        position = self.Get_Position(axe)
        if self.affichage:
            print(f"  → Axis {axe} moved to {position:.4f} {self.unit}")
        return position

    
    def Speed(self, axe, speed):
        
        """
        speed in step/sec (I think)
            default = 301990
        """
        if speed > 301990:
            print("Value to high, stoped at 301990")
            speed = 301990

        self.send_command(f"PVEL{axe}={speed}")

    def Joystick(self):
        self.send_command("JOYON")
        input("Press 'ENTER' when finish....")
        self.send_command("JOYOFF")
        print("Done : Joystick disconected")


    def Get_Position(self, axes=None):
        """
        Return the current position of one or more axes.

        Parameters
        ----------
        axes : int or list of int
            Axis number(s). Default: all initialized axes.

        Returns
        -------
        float or list of float
            Position(s) in the current unit.
        """
        if axes is None:
            axes = self.initialized_axis

        if isinstance(axes, int):
            raw = self._read_counter(axes)
            return self.Conversion_pas_mm(raw)

        return [self.Conversion_pas_mm(self._read_counter(axe)) for axe in axes]

    def _read_counter(self, axe: int) -> int:
        """Read the raw step counter for a single axis with retry on failure."""
        for attempt in range(2):
            try:
                raw = self.send_command(f"?CNT{axe}")
                return int(raw.split()[-1])
            except (ValueError, AttributeError):
                if attempt == 0:
                    time.sleep(0.5)
        raise RuntimeError(f"Could not read counter for axis {axe}")
        
    def Set_Zero(self, axis=None, value: int = 0):
        """
        Define the current position as the origin (or a given value).

        Parameters
        ----------
        axis  : None, int, or list of int
            None → all initialized axes.
        value : int
            Counter value to set (default 0).
        """
        if axis is None:
            axes_to_zero = self.initialized_axis
        elif isinstance(axis, int):
            axes_to_zero = [axis]
        elif isinstance(axis, list):
            axes_to_zero = axis
        else:
            print("axis must be None, an int, or a list of ints.")
            return

        for axe in axes_to_zero:
            self.send_command(f"CNT{axe}={value}")

        if self.affichage:
            print("Current position set as origin.\n")

    def Move_Zero(self, axes: list = None):
        """
        Move one or more axes back to the origin (absolute position 0).

        Parameters
        ----------
        axes : list of int or None
            None → all initialized axes.
        """
        target = axes if axes is not None else self.initialized_axis
        for axe in target:
            self.Move(axe, 0, absolu=True)

    # ──────────── Conversions ────────────

    def Conversion_pas_mm(self, pas: float) -> float:
        """Convert raw steps to the current unit."""
        return pas * self.ratio

    def Conversion_mm_pas(self, mm: float) -> float:
        """Convert a value in the current unit to raw steps."""
        return mm / self.ratio

    # ──────────── Positionnement interactif ────────────

    def Positionnement(self, axes: list, set_zero: bool = True):
        """
        Interactive method to define a start and end position by jogging.

        Parameters
        ----------
        axes     : list of int – Axes to position.
        set_zero : bool        – If True, set the start position as origin.

        Returns
        -------
        tuple of lists: (start_positions, end_positions)
        """
        print("Enter integer displacements and press Enter to move.\nPress Enter with no value to confirm.\n")

        positions = [[], []]

        labels = ["Starting point", "End point"]
        for step in range(2):
            print(f"Setting {labels[step]}:")
            for axe in axes:
                print(f"  Axis {axe}:")

                # Temporarily switch to relative mode
                mode = self.send_command(f"?MODE{axe}")
                self.Referenciel(axe, absolu=False, affichage=False)

                while True:
                    d = input("    Displacement: ").strip()
                    if d == "":
                        if step == 0 and set_zero:
                            self.Set_Zero(axe)
                        else:
                            pos = self.Get_Position(axe)
                            positions[step].append(pos)
                            print(f"    Position recorded: {pos:.4f} {self.unit}\n")
                        break
                    try:
                        self.Move(axe, float(d))
                    except ValueError:
                        print("    Please enter a numeric value.")

                # Restore previous mode
                if mode:
                    self.send_command(f"{mode}{axe}")

        return positions[0], positions[1]


# %% ──────────── Exemple d'utilisation ────────────

if __name__ == "__main__":
    ps = PS90(COM="COM3")
    ps.Unit("milli")
    ps.Initialisation_Axes(axes=[1, 2], absolu=True)

    ps.Set_Zero(axis=[1, 2])

    ps.Move(axe=1, deplacement=5.0)
    print("Positions:", ps.Get_Position(axes=[1, 2]))

    ps.Move_Zero(axes=[1, 2])

    ps.close()
