"""
LinearStageL84N class definition

Description :
    Driver class for an OWIS linear motorized stage of type Limes 84N. 
    An object of type linearStageL84N includes the properties of positioning,
    speed, acceleration, and motor resolution. The various methods of the class
    allow reading the positioning information, setting the speed and acceleration
    for stage movement, and moving the stage to a desired position.

Version :
    Author : Timothée Chemla  
    Date : Jun. 2026
    Ver : 1.0 

Notes :
    A linearStageL84N object could be created only after having create a PS90 object.
    The documentation for the PS90 library functions is available at: ps90 > ps90func.chm  
"""

from ctypes import windll, c_double


class LinearStageL84N:

    # ──────────── Constants ────────────
    MAX_VEL       = 25      # [mm/s] Maximum allowable speed
    MAX_ACC       = 200     # [mm/s²] Maximum allowable acceleration
    DEFAULT_VEL   = 1       # [mm/s] Default speed at initialization
    DEFAULT_ACC   = 3       # [mm/s²] Default acceleration at initialization
    COUNTER_RES   = 2000    # Engine resolution (= number of increments per revolution)
    SPINDLE_PITCH = 1       # [mm] Distance per revolution
    GEAR_RED      = 1       # Reduction ratio

    _UNIT_MAP = {"cm": -2, "mm": -3, "µm": -6}

    # ──────────── Builder ────────────

    def __init__(self, ps, axis_id: int):
        """
        Settings
        ----------
        ps      : OWIS_PS90  — control unit already connected
        axis_id : int        — channel number (1 to 4)
        """
        self.ps   = ps # PS90 type object
        self.dll = windll.LoadLibrary("ps90.dll")
        self.idx  = ps.DEVICE_INDEX

        self.ROT_TO_TRANS  = 1 / self.SPINDLE_PITCH
        self.COUNTS_PER_MM = round(self.COUNTER_RES * self.SPINDLE_PITCH)

        # Unit (metric) for calling positioning functions (-2 for 'cm', -3 for 'mm' and -6 for 'µm')
        self._unit_exp = -3     
        self._unit_str = "mm"

        self.mode      = "position" # Mode of movement ('position' to move to a target position, or 'speed' to move continuously without a target position)



        # Material axis attributes
        self.dll.PS90_SetStageAttributes(
            self.idx, axis_id,
            c_double(self.SPINDLE_PITCH),
            self.COUNTER_RES,
            c_double(self.GEAR_RED)
        )

        self._chan = None # Channel (1, 2, 3 or 4)
        # Channel assignment
        self.chan  = axis_id    # → calls init_axis()

        self._vel = self.DEFAULT_VEL  #intern speed

    # ──────────── Erreurs ────────────

    def read_error(self):
        """Read and display the current mistake (PS90_GetReadError)."""
        num = self.dll.PS90_GetReadError(self.idx)
        match num: # the case num==0 corresponds to correct operation
            case -1:
                print(f"[Error axis {self._chan}] Function call error")
            case -2:
                print(f"[Error axis {self._chan}] Communication error")
            case -3:
                print(f"[Error axis {self._chan}] Syntaxe error ")
            case -4:
                print(f"[Error axis {self._chan}] Incorrect axis positioning")

    # ──────────── Initialisation ────────────

    def init_axis(self):
        """Initializes and activates the axis (PS90_MotorInit)."""
        self.dll.PS90_MotorInit(self.idx, self._chan)
        self.read_error() # We make sure everything went well.
        # Assigning default values
        self.vel = self.DEFAULT_VEL
        self.acc = self.DEFAULT_ACC

    # ──────────── Déplacement ────────────

    def set_home(self):
        """Resets the counter to zero — redefines the home position."""
        error_msg = self.dll.PS90_ResetCounter(self.idx, self._chan)
        match error_msg: # case error_msg==0 : Origin position successfully redefined
            case -1:
                raise RuntimeError("Error calling PS90_ResetCounter")
            case -2:
                raise RuntimeError("Communication error during PS90_ResetCounter")
            case -3:
                raise RuntimeError("Syntaxe error during PS90_ResetCounter")
            

    def go_home(self):
        """Moves the connector board to the origin position (0)."""
        self.move_abs(0.0)

    def stop(self):
        """Emergency stop with braking ramp (PS90_Stop)."""
        self.dll.PS90_Stop(self.idx, self._chan)
        self.read_error() # We make sure everything went well.

    def go_ref_min(self):
        """Searches for max and then min stop, resets to 0 in the min position (mode 6)."""
        self.dll.PS90_GoRef(self.idx, self._chan, 6)
        self.read_error() # We make sure everything went well.

    def go_ref_max(self):
        """Searches for min and then max stop, resets to 0 in the max position (mode 7)."""
        self.dll.PS90_GoRef(self.idx, self._chan, 7)
        self.read_error() # We make sure everything went well.

    def move_abs(self, dist: float):
        """
        Absolute displacement to distance (in the current unit).
        Reference = home position.
        """
        self.dll.PS90_SetTargetMode(self.idx, self._chan, 1) # Set target mode to absolute positioning (target value is target position) (mode=1)
        self.dll.PS90_MoveEx(self.idx, self._chan, c_double(dist), 1) # Definition and movement to Target Position
        self.read_error() # We make sure everything went well.

    def move_rel(self, dist: float):
        """
        Relative displacement of distance (in the current unit).
        Reference = current position.
        """
        self.dll.PS90_SetTargetMode(self.idx, self._chan, 0) # Set target mode to absolute positioning (target value is target position) (mode=1)
        self.dll.PS90_MoveEx(self.idx, self._chan, c_double(dist), 1) # Definition and movement to Target Position
        self.read_error() # We make sure everything went well.

    def go_vel(self, direction: int):
        """
        Continuous movement in speed mode.
        Direction: +1 positive direction, -1 negative direction.
        """
        self.mode = "speed"
        new_vel = abs(self._vel) * direction
        self.dll.PS90_SetFEx(self.idx, self._chan, c_double(new_vel))
        self.dll.PS90_GoVel(self.idx, self._chan)


    def stop_vel(self):
        """Stops movement in speed mode."""
        self.dll.PS90_StopVel(self.idx, self._chan)
        self.read_error()
    


    def wait_move(self): 
        """Block until the end of the movement."""
        while self.state == 1:
            pass

    # ──────────── Properties ────────────

    @property
    def chan(self) -> int:
        return self._chan

    @chan.setter
    def chan(self, value: int):
        """Channel assignment"""
        self._chan = value
        self.init_axis()

    @property
    def unit(self) -> str:
        return self._unit_str

    @unit.setter
    def unit(self, value: str):
        """Change the unit ('cm', 'mm' ou 'µm') and recalculate the resolution."""
        if value not in self._UNIT_MAP:
            raise ValueError(f"Invalid unit : '{value}'. Accepted values : {list(self._UNIT_MAP)}")
        old_exp = self._unit_exp
        old_vel = self.vel
        old_acc = self.acc

        self._unit_str = value
        self._unit_exp = self._UNIT_MAP[value]

        new_res = 1e3 * (10 ** self._unit_exp) / self.COUNTER_RES
        self.dll.PS90_SetCalcResol(self.idx, self._chan, c_double(new_res))
        self.read_error()

        factor = 10 ** (old_exp - self._unit_exp)
        self.vel = old_vel * factor
        self.acc = old_acc * factor

    @property
    def state(self) -> int:
        """0 = free axis, 1 = in motion."""
        s = self.dll.PS90_GetMoveState(self.idx, self._chan)
        return 1 if s in (1, 2, 3, 7, 8) else 0

    @property
    def pos(self) -> float:
        """
        Current position in current unit.
        Calculated from raw increments to avoid rounding DLL.
        """
        pos_inc = self.dll.PS90_GetPosition(self.idx, self._chan)
        pos_mm  = pos_inc / self.COUNTS_PER_MM
        if self._unit_exp == -2:
            return pos_mm * 1e-1    # cm
        elif self._unit_exp == -6:
            return pos_mm * 1e3     # µm
        return pos_mm               # mm

    @pos.setter
    def pos(self, value: float):
        """Absolute move to value (in current unit)."""
        self.move_abs(value)

    @property
    def vel(self) -> float:
        """Current speed in current unit per second."""
        if self.mode == "position":
            return self.dll.PS90_GetPosFEx(self.idx, self._chan)
        else:
            return self.dll.PS90_GetFEx(self.idx, self._chan)

    @vel.setter
    def vel(self, value: float):
        """Adjusts the speed validated against MAX_VEL."""
        max_v = 1e3 * (10 ** self._unit_exp) * self.MAX_VEL
        if not isinstance(value, (int, float)):
            print("[WARNING] Non-digital speed ignored.")
            return
        if abs(value) > max_v:
            print(f"[WARNING] Speed {value} out of range (max={max_v} {self._unit_str}/s).")
            return
        if self.mode == "position":
            self._vel=value
            self.dll.PS90_SetPosFEx(self.idx, self._chan, c_double(value))
        else:
            self._vel=value
            self.dll.PS90_SetFEx(self.idx, self._chan, c_double(value))
        self.read_error()

    @property
    def acc(self) -> float:
        """Current acceleration in current unit per seconde²."""
        return self.dll.PS90_GetAccelEx(self.idx, self._chan)

    @acc.setter
    def acc(self, value: float):
        """Adjusts acceleration."""
        self.dll.PS90_SetAccelEx(self.idx, self._chan, c_double(value))
        self.read_error()
