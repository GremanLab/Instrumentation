import serial
import time


# ──────────── Constants ────────────

class PS90:
    
    #   
    axis_state = {"I" : "Axis is initialized",
           "O" : "Axis is disabled",
           "R" : "Axis initialised and ready",
           "T" : "Axis is positioning in trapezoidal profile",
           "S" : "Axis is positioning in S-curve profile",
           "V" : "Axis is operating in velocity mode",
           "P" : "Reference motion is in progress",
           "F" : "Axis is releasing a limit switch",
           "J" : "Axis is operating in joystick mode",
           "L" : "Axis has been disabled after approaching a hardware limit switch (MINSTOP, MAXSTOP)",
           "B" : "Axis has been stopped after approaching a brake switch (MINDEC, MAXDEC)",
           "A" : "Axis has been disabled after limit switch error",
           "M" : "Axis has been disabled after motion controller error",
           "Z" : "Axis has been disabled after timeout error",
           "H" : "Phase initialization activ (step motor axis)",
           "U" : "Axis is not released",
           "E" : "Axis has been disabled after motion error",
           "?" : "Error, unknown state of axis"}
    

    def __init__(self, COM, baudrate = 9600, timeout = 1):
        self.serial = serial.Serial(port=COM, baudrate=baudrate, timeout=timeout)
        self.unit()
        
    def unit(self, unit="milli"):
        if unit != "milli" and unit != "micro" : 
            print("Unité non comprise, voulez vous dire 'milli' ou 'micro' ?")
            self.unit = "milli"
        else :
            self.unit = unit
        self.ratio = 0.5 # micro metre/pas
        
    def close(self):
        self.serial.close()
    
    def __exit__(self):
        self.close()
    
    


# ──────────── Functions ────────────

# ────── Settings ──────

    
    def send_command(self, cmd):
        time.sleep(0.05)
        self.serial.write((cmd + '\r').encode('ascii'))
        time.sleep(0.05)    # laisser 20-40ms d'interprétation
        if cmd[0]=="?":
            response = self.serial.read_until("\r").decode('ascii').strip()
            return response
        return None

    
    def Initialisation_Axe(self, axe):
        self.send_command(f"EFREE{axe}")
        self.send_command(f"AXIS{axe}=0")
        time.sleep(0.5)
        self.send_command(f"AXIS{axe}=1")
        
        self.send_command(f"INIT{axe}") # Initialise l'axe
        self.send_command(f"MON{axe}")

 
    def Initialisation_Axes(self, axes, absolu = None, affichage = True):
        
        message = self.send_command("?ASTAT")
        
        for axe in axes:
            
            if absolu is not None :
                self.Referenciel(axe, absolu)
            
            if affichage:
                print(message[axe-1], ":", self.axis_state[message[axe-1]])
        
            if message[axe-1] == "R":
                if affichage:
                    print("Already initialised\n")
                continue
            else:
                self.Initialisation_Axe(axe)
        
                message = self.send_command("?ASTAT")
                if affichage:
                    print(message[0],":", self.axis_state[message[0]], end="\n\n")
        
        if affichage:
            print("Axes :", message, "\n\n")
            
    
    def Referenciel(self, axe, absolu):
        if absolu:
            self.send_command(f"ABSOL{axe}")
            print("Mode Absolu Activé")
        else :
            self.send_command(f"RELAT{axe}")
            print("Mode Relatif activé")

    
    def Positionnement(self, axes):
        
        print("Pour se déplacer, entrez une nombre entier.\nPour valider appuyer sur entrée\n")
        
        ok = False
        
        positions =[[],[]]
        
        print("Initialisation du point de départ :")
        for j in range(2):
            for axe in axes:
                print(f" - Pour l'axe {axe} :\n")
                mode = self.send_command(f"?MODE{axe}")
                self.Referenciel( axe, absolu=False)
                
                while ok is False:
                    d = input("Déplacement : ")
                    try :
                        d = float(d)
                        self.Move(axe, d)
                    except:
                        print("Position enregistrée\n\n")
                        pos = self.Get_Position()[axe-1]
                        ok = True
                        positions[j].append(pos)
                ok = False
                
                self.send_command(f"{mode}{axe}")  
                
            if j == 0:
                print("Initialisation du point de d'arrivée :")
            
            
        return positions[0], positions[1]

    
    def Conversion_pas_mm(self, pas):
        distance = pas * self.ratio
        if self.unit == "milli" :
            return distance / 1000
        elif self.unit == "micro":
            return distance
        
    
    def Conversion_mm_pas(self, mm):
        if self.unit == "milli" :
            mm *= 1000
        elif self.unit == "micro":
            pass
        distance = mm / self.ratio
        return distance
    
    # ────── Deplacement ──────
    
    def Move(self, axe, deplacement, absolu=None, high_limit=None, low_limit=None):
        
        if absolu is not None:
            self.Referenciel(axe, absolu)
        
        deplacement = self.Conversion_mm_pas(deplacement)
        
        if high_limit and low_limit is not None :
            if deplacement >= high_limit or deplacement <= low_limit:
                print("Outside of limit range")
                return None
        
        message = self.send_command("?ASTAT")
        print("Check if movable => ", message[axe-1], ":", self.axis_state[message[axe-1]])
        if message[axe-1] == "A":
            print("Re-initialising the axis")
            self.Initialisation_Axe(axe)
        
        message = self.send_command("?ASTAT")
        if message[axe-1] == "R":
            self.send_command(f"PSET{axe}={deplacement}")
            self.send_command(f"PGO{axe}")
            
            time.sleep(0.5)
            message = self.send_command("?ASTAT")
            print(message[axe-1], ":", self.axis_state[message[axe-1]])
            
            while message[axe-1] != "R" :   
                message = self.send_command("?ASTAT")
                print(message[axe-1], ":", self.axis_state[message[axe-1]])
            
                if message[axe-1] == "A" :
                    print("Mouvement stoped due to switch button")
                    break
            
            position = self.Get_Position(axe)
            print(f"Moved to {position} {self.unit} on the axis {axe}", end='\n\n')
    
        else :
            print("Axis is not movable")
            return None
    
    def Get_Position(self, axes=[1,2,3]):
        positions = []
        if type(axes)==int:
            raw_value = int(self.send_command(f"?CNT{axes}"))
            value = self.Conversion_pas_mm(raw_value)
            return value
            
        for axe in axes:
            raw_value = int(self.send_command(f"?CNT{axe}"))
            value = self.Conversion_pas_mm(raw_value)
            positions.append(value)
        return positions



ps = PS90("COM3")
