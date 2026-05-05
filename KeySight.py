import pyvisa

import time

# ──────────── Class KeySight ────────────

class KeySight:
    
    # ──────────── Constantes ────────────

            # SINusoid, SQUare, RAMP, PULSe, NOISe]
    fonctions = ["SIN", "SQU","RAMP","PULS", "NOIS"]

    freqlimit = [[1e-3, 10e6], [1e-3, 10e6], [1e-3, 100e6], [1e-3, 5e6], [None, None]]
    
    
    # ──────────── Initialisation ────────────

    def __init__(self):
        self.instrument = None
        self.IP_devices = []
        self.output = False
        
        # self.instrument = self.visa.open_resource(adress)
        self.visa = pyvisa.ResourceManager()


    def Initialisation(self, adress):
        try:
            self.instrument = self.visa.open_resource(adress)
            print("Connected")
        except:
            print("\nIP adresse does not work.\nSelect an other one")
            self.List_devices()

    
    # def __exit__(self):
    #     self.instr.close()


    # ──────────── Fct de Base ────────────

    def send_command(self, command):
        self.instrument.write(command)
        if "?" in command :
            message = self.instrument.read()
            try :
                return message.strip()
            except:
                return message
    
    
    def Is_Device_Active(self, IP): 
        try :
            test = self.visa.open_resource(IP)
            test.query("*IDN?")
            test.close()
            return True
        except:
            return False


    def List_devices(self, active=True):
            
        self.visa = pyvisa.ResourceManager()
        self.IP_devices = list(self.visa.list_resources())
        self.IP_devices.sort()
        
        active = False
        if active == True:
            verified = []
            for i in range(len(self.IP_devices)):
                # Vérifie que tt les ports affichés sont utilisables, 
                # Sinon, le retire de la lise
                IP = self.IP_devices[i]
                active_device = self.Is_Device_Active(IP)
                if active_device :
                    verified.append(self.IP_devices[i])
            self.IP_devices = verified
        
        
        if len(self.IP_devices)==0:
            print("Nothing has been detected")
        else :
            i = 1
            print("\nList of devices:\n")
            for option in self.IP_devices:
                print(i,":",option)
                i += 1
    
    # ──────────── Configuration ────────────

    def Config(self, fct = None, amp = None, freq = None, offset = None, phase = None, duty = None, sym = None, ):
        
        if fct is not None:
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
            if self.send_command("FUNCtion?") == "SQU":
                if duty < 20:
                    duty = 20
                elif duty > 80:
                    duty = 80
                self.send_command(f"FUNCtion:SQUare:DCYCle {duty}")
            else:
                print("The fonction 'SQU', related to that parameter, has not been selected")

        if sym is not None:
            if self.send_command("FUNCtion?") == "RAMP":
                if sym < 0:
                    sym = 0
                elif sym > 100:
                    sym = 100
                self.send_command(f"FUNCtion:RAMP:SYMMetry {sym}")
            else:
                print("The fonction 'RAMP', related to that parameter, has not been selected")


    def Output(self, ON=None):
        
        # Si rien n'est indiqué : change automatiquement
        if ON == None:
            if self.output == False:
                self.send_command("OUTPut ON")
                self.output = True
                
            elif self.output:
                self.send_command("OUTPut OFF")
                self.output = False
              
        elif ON :
            self.send_command("OUTPut ON")
            self.output = True
        else:
            self.send_command("OUTPut OFF")
            self.output = False

# ──────────── Fin de class ────────────

gbf = KeySight()

# for i in gbf.visa.list_resources():
#     gbf.Initialisation(i)
#     gbf.Quit()


gbf.List_devices()

gbf.Initialisation('GPIB0::4::INSTR') # Agilent ?Ma salle

gbf.Config(fct = "SQU", amp=2, freq=1e3, offset=0.5, phase=90, duty=50, sym=50)

gbf.Output()

gbf.send_command("*IDN?")

