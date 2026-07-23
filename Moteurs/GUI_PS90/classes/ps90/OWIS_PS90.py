"""
OWIS_PS90 - class definition

Description :
    Driver class of the OWIS PS90 positioning system. A PS90 object
    allows you to open a communication port of the PS90 system and 
    communicate with the motorized axes via the ps90.dll library

Version :
    Author : Timothée Chemla  
    Date : Jun. 2026
    Ver : 1.0 

Notes :
    Place ps90.dll in the same folder as this file.

    Documentation : ps90 > info > ps90func.chm
"""

from ctypes import windll, c_double, create_string_buffer
import time

from classes.ps90.RotaryStageDMT65 import RotaryStageDMT65
from classes.ps90.LinearStageL84N import LinearStageL84N


class OWIS_PS90:

    # ──────────── Constants ────────────
    MODEL_NAME     = "PS90" # Model name
    DEVICE_INDEX   = 1      # Control unit index 1–10 (default=1, range=1...20) (11..20 - debug mode; 1..10 - standard mode)
    # Properties related to serial interfacing (not used if connected via USB)
    BAUD_RATE      = 9600   # Communication speed. Default : 9600 - standard read (byte to byte). Other options : 115200 - fast read (all bytes, fast check); 19200 - fast read (all bytes, slow check)
    SERIAL_DELAY   = 0      # [ms] delay value (=20+x) for serial communication (default=20 ms)
    SERIAL_CHECK   = 0      # Valid inputs : 0 - with check (firmware, terminal mode, clear error); 10 - without check
    SERIAL_FLUSH   = 0      # Valid inputs : 0 - without port flush; 10 - with port flush
    SERIAL_RECONNECT = 0    # Valid inputs : 0 - without reconnect; 5 - reconnect for every message

    # ──────────── Builder ────────────

    def __init__(self, dll_path: str = "ps90.dll"):
        """
        Settings (function called at the creation of the class)
        ----------
        dll_path : str
            Path to ps90.dll (default : same folder as the script).
        """
        self.dll = windll.LoadLibrary(dll_path) #Loading of the library
        self._configure_return_types() # This avoids interpreting double as int in C

        # Motorized axes
        self.X = None
        self.Y = None
        self.Z = None
        self.R = None

    def _configure_return_types(self):
        """
        Declares the non-int return types of the DLL (essential for c_double).        
        """
        self.dll.PS90_GetPositionEx.restype  = c_double
        self.dll.PS90_GetPosFEx.restype      = c_double
        self.dll.PS90_GetFEx.restype         = c_double
        self.dll.PS90_GetAccelEx.restype     = c_double

    # ──────────── Connection ────────────

    def open_connection(self, port=None) -> dict:
        """
        Open the connection with the control unit PS90

        Settings
        ----------
        port : int | str | None
            - None ou 0  → USB, first device found
            - "net"      → TCP/IP socket (localhost:1200)
            - int 1-4    → Port COM serie (i.e. 3 for COM3)

        Return
        --------
        dict {"num": int, "msg": str}
        
        if "num"==0 : Connection established
        else : error -> dict["msg"]

        Usage example
        -------
        error = ps.open_connection(port=0)

        """

        if port is None or port == 0:
            result = self.dll.PS90_SimpleConnect(self.DEVICE_INDEX, b"")
        elif port == "net":
            result = self.dll.PS90_SimpleConnect(self.DEVICE_INDEX, b"net")
        else:
            result = self.dll.PS90_Connect(
                self.DEVICE_INDEX, 0, int(port),
                self.BAUD_RATE, self.SERIAL_DELAY,
                self.SERIAL_CHECK, self.SERIAL_FLUSH, self.SERIAL_RECONNECT
            )
            

        err = self._parse_connect_error(result) # State of the connection
        print(f"[PS90] {err['msg']}")

        if err["num"] == 0:
            time.sleep(0.5)
            # Initialization of motorized axes
            self.X = LinearStageL84N(self, axis_id=1)  # Translation X → channel 1
            self.Y = LinearStageL84N(self, axis_id=2)  # Translation Y → channel 2
            self.Z = LinearStageL84N(self, axis_id=3)  # Translation Z → channel 3
            self.R = RotaryStageDMT65(self, axis_id=4) # Rotation R    → channel 4
            # Reset all positions
            self.set_all_home()
        return err

    def _parse_connect_error(self, num: int) -> dict:
        """ State of the connection """
        messages = {
            0: "Connection successfully established to the PS90 control unit",
            1: "Error : invalid settings (PS90_Connect)",
            3: "Error : invalid serial port / not found",
            4: "Error : access denied (port busy)",
            5: "Error : no response from the control unit (check cables/reset)",
            8: "Error : no Modbus/TCP connection",
            9: "Error : no TCP/IP socket connection"
        }
        return {"num": num, "msg": messages.get(num, f"Uknown error (code {num})")}

    # ──────────── Déconnexion ────────────

    def close_connection(self):
        """Close the connexion with the control unit."""
        result = self.dll.PS90_Disconnect(self.DEVICE_INDEX)
        if result == 0:
            print(f"[PS90] Disconnection of {self.MODEL_NAME} successfully completed")
        else:
            print(f"[PS90] Error during disconnection (code {result})")

    def __del__(self):
        """ Close connection """
        try:
            self.close_connection()
        except Exception:
            pass

    # ──────────── Firmware version ────────────

    def get_firmware_version(self) -> str:
        """Return the controller firmware version."""
        buf = create_string_buffer(20)
        self.dll.PS90_GetBoardVersion(self.DEVICE_INDEX, buf, 20)
        return buf.value.decode("utf-8")

    # ──────────── Axes ────────────

    def set_all_home(self):
        """Resets the origin position of all axes."""
        print("[PS90] Redefining the origin positions for all axes")
        for name, axis in [("X", self.X), ("Y", self.Y), ("Z", self.Z), ("R", self.R)]:
            if axis is not None:
                axis.set_home()
            else:
                print(f"[WARNING] Axe {name} uninitialized.")
    
    def go_all_home(self):
        """Go to the origin position of all axes"""
        for name, axis in [("X", self.X), ("Y", self.Y), ("Z", self.Z), ("R", self.R)]:
            if axis is not None:
                axis.go_home()
            else:
                print(f"[WARNING] Axe {name} uninitialized.")

    def stop_all(self):
        """Emergency stop : stoppe all axes."""
        for name, axis in [("X", self.X), ("Y", self.Y), ("Z", self.Z), ("R", self.R)]:
            if axis is not None:
                axis.stop()
            else:
                print(f"[WARNING] Axe {name} uninitialized.")
    
