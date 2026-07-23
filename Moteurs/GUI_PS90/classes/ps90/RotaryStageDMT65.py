"""
RotaryStageDMT65 class definition

Description :
    Almost the same file as LinearStageL84N.py but this one is for axes in rotation.

Version :
    Author : Timothée Chemla  
    Date : Jun. 2026
    Ver : 1.0 

Notes :
    A RotaryStageDMT65 object could be created only after having create a PS90 object.
    The documentation for the PS90 library functions is available at: ps90 > ps90func.chm  

    Unit : degrees (°) only
"""

from ctypes import windll, c_double


class RotaryStageDMT65:

    # ──────────── Constants ────────────
    MAX_VEL        = 80     # [°/s] Maximum allowable speed
    MAX_ACC        = 200    # [°/s²] Maximum allowable acceleration
    DEFAULT_VEL    = 10     # [°/s] Default speed at initialization
    DEFAULT_ACC    = 200    # [°/s²] Default acceleration at initialization
    COUNTER_RES    = 2000   # Engine resolution (= number of increments per revolution)
    GEAR_RED       = 180    # Reduction ratio 180:1
    COUNTS_PER_DEG = round(2000 / 360)
    PITCH          = 360    # [°] 1 revolution = 360°

    # ──────────── Constructeur ────────────

    def __init__(self, ps, axis_id: int):
        """
        Paramètres
        ----------
        ps      : OWIS_PS90  — control unit already connected
        axis_id : int        — channel number (1 to 4)
        """
        self.ps  = ps # PS90 type object
        self.dll = windll.LoadLibrary("ps90.dll")
        self.idx = ps.DEVICE_INDEX
        self.mode = "position"

        # Material axis attributes
        self.dll.PS90_SetStageAttributes(
            self.idx, axis_id,
            c_double(float(self.PITCH)),
            self.COUNTER_RES,
            c_double(float(self.GEAR_RED))
        )

        self._chan = None
        self.chan  = axis_id    # → calls init_axis()

        self._vel = self.DEFAULT_VEL  # Intern speed


    # ──────────── Errors ────────────
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
        self.read_error()
        self.vel = self.DEFAULT_VEL
        self.acc = self.DEFAULT_ACC

    # ──────────── Déplacement ────────────
    def set_home(self):
        """Resets the counter to zero — redefines the home position."""
        error_msg = self.dll.PS90_ResetCounter(self.idx, self._chan)
        match error_msg:
            case -1:
                raise RuntimeError("Error calling PS90_ResetCounter")
            case -2:
                raise RuntimeError("Communication error during PS90_ResetCounter")
            case -3:
                raise RuntimeError("Syntaxe error during PS90_ResetCounter")


    def go_home(self):
        """Moves the connector board to the origin position (0°)."""
        self.move_abs(0.0)

    def stop(self):
        """Emergency stop with braking ramp (PS90_Stop)."""
        self.dll.PS90_Stop(self.idx, self._chan)
        self.read_error()

    def move_abs(self, angle: float):
        """
        Absolute displacement to distance (in the current unit).
        Reference = home position.
        """
        self.dll.PS90_SetTargetMode(self.idx, self._chan, 1)
        self.dll.PS90_MoveEx(self.idx, self._chan, c_double(angle), 1)
        self.read_error()

    def move_rel(self, angle: float):
        """
        Relative displacement of distance (in the current unit).
        Reference = current position.
        """
        self.dll.PS90_SetTargetMode(self.idx, self._chan, 0)
        self.dll.PS90_MoveEx(self.idx, self._chan, c_double(angle), 1)
        self.read_error()

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
    def state(self) -> int:
        """0 = free axis, 1 = in motion."""
        s = self.dll.PS90_GetMoveState(self.idx, self._chan)
        return 1 if s in (1, 2, 3, 7, 8) else 0

    @property
    def pos(self) -> float:
        """Current angular position in degrees (PS90_GetPositionEx)."""
        return self.dll.PS90_GetPositionEx(self.idx, self._chan)

    @pos.setter
    def pos(self, value: float):
        """Absolute rotation to value (in degrees)."""
        self.move_abs(value) # pas sûr de cette ligne, si ne fonctionne pas : la remplacer par les 2 suivantes 
        
        #self.dll.PS90_SetPositionEx(self.idx,self._chan,value)
        #self.read_error()

    @property
    def vel(self) -> float:
        """Current rotation speed in °/s."""
        if self.mode == "position":
            return self.dll.PS90_GetPosFEx(self.idx, self._chan)
        else:
            return self.dll.PS90_GetFEx(self.idx, self._chan)

    @vel.setter
    def vel(self, value: float):
        """Adjusts the speed validated against MAX_VEL (80 °/s)."""
        if not isinstance(value, (int, float)):
            print("[WARNING] Non-digital speed ignored.")
            return
        if abs(value) > self.MAX_VEL:
            print(f"[WARNING] Speed {value} out of range (max={self.MAX_VEL} °/s).")
            return
        if self.mode == "position":
            self.dll.PS90_SetPosFEx(self.idx, self._chan, c_double(value))
        else:
            self.dll.PS90_SetFEx(self.idx, self._chan, c_double(value))
        self.read_error()

    @property
    def acc(self) -> float:
        """Current acceleration in °/s²."""
        return self.dll.PS90_GetAccelEx(self.idx, self._chan)

    @acc.setter
    def acc(self, value: float):
        """Adjusts acceleration — validate in ]0, MAX_ACC]."""
        if not isinstance(value, (int, float)):
            print("[WARNING] non digital acceleration ignored.")
            return
        if not (0 < value <= self.MAX_ACC):
            print(f"[WARNING] Acceleration {value} out of range (0 < acc <= {self.MAX_ACC} °/s²).")
            return
        self.dll.PS90_SetAccelEx(self.idx, self._chan, c_double(value))
        self.read_error()
