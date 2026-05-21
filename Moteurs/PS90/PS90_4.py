import time

import serial


# ──────────── Constants ────────────

class PS90:

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


    def __init__(self, COM, baudrate = 9600, timeout = 0.005):
        self.serial = serial.Serial(port=COM, baudrate=baudrate, timeout=timeout)
        self.Unit()
        self.intialized_axis = []
        self.affichage = True


    def Unit(self, unit="milli"):
        self.possibilites = {"centi":0.5e-4, "milli":0.5e-3, "micro":0.5, "pas":1}
        #                                            mm/pas,        µm/pas     pas/pas
        if unit not in self.possibilites :
            print("Unité non comprise, voulez vous dire 'milli' ou 'micro' ?")
            self.unit = "milli"
        else :
            self.unit = unit

        self.ratio = self.possibilites[self.unit]


    def Affichage(self, affiche):
        self.affichage = affiche


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

        if axe not in self.intialized_axis :
            self.intialized_axis.append(axe)


    def Initialisation_Axes(self, axes, absolu = None, affichage = True):

        message = self.send_command("?ASTAT")

        if affichage is not None:
            self.affichage = affichage

        for axe in axes:

            if absolu is not None :
                self.Referenciel(axe, absolu, affichage)

            if self.affichage:
                print(message[axe-1], ":", self.axis_state[message[axe-1]])
            
            if axe not in self.intialized_axis :
                self.intialized_axis.append(axe)

            if message[axe-1] == "R":
                if self.affichage:
                    print("Already initialised\n")
                continue
            else:
                self.Initialisation_Axe(axe)

                if self.affichage:
                    message = self.send_command("?ASTAT")
                    print(message[axe-1],":", self.axis_state[message[axe-1]], end="\n\n")
                    

        if self.affichage:
            print("Axes :", message, "\n\n")


    def Referenciel(self, axe, absolu, affichage = True):
        if absolu:
            self.send_command(f"ABSOL{axe}")
            if affichage :
                print("\nMode Absolu Activé")
        else :
            self.send_command(f"RELAT{axe}")
            if affichage:
                print("\nMode Relatif activé")


    def Positionnement(self, axes, set_zero = True):

        print("Pour se déplacer, entrez une nombre entier.\nPour valider appuyer sur entrée\n")

        ok = False

        positions =[[],[]]

        print("Initialisation du point de départ :")
        for step in range(2):
            for axe in axes:
                print(f" - Pour l'axe {axe} :\n")
                mode = self.send_command(f"?MODE{axe}")
                self.Referenciel(axe, absolu=False, affichage = False)

                while ok is False:
                    d = input("Déplacement : ")
                    try :
                        d = float(d)
                        self.Move(axe, d)
                    except:

                        if step == 0 and set_zero:
                            self.Set_Zero(axe)
                        else :
                            print("Position enregistrée\n\n")
                            pos = self.Get_Position()[axe-1]
                            positions[step].append(pos)
                        ok = True

                ok = False

                self.send_command(f"{mode}{axe}")

            if step == 0:
                print("\nInitialisation du point de d'arrivée :")


        return positions[0], positions[1]


    def Conversion_pas_mm(self, pas):
        """
        Convert the unit used by the PS90 to mm.

        Parameters
        ----------
        pas : float
            Value of deplacement.

        Returns
        -------
        float
            DESCRIPTION.
        """
        mm = pas * self.ratio
        return mm


    def Conversion_mm_pas(self, mm):
        """
        Convert the unit mm to the unit used by the PS90.

        Parameters
        ----------
        mm : float
            Value of deplacement.

        Returns
        -------
        float
            DESCRIPTION.
        """
        pas = mm / self.ratio
        return pas

    # ────── Deplacement ──────

    def Move(self, axe, deplacement, absolu=None):
        """
        SUMMARY.

        Déplace un axe d'une certaine valeure
        ----------
        axe : int
            Numéro de l'axe a déplacer.
        deplacement : float
            Valeur du déplacement à effectuer.
        absolu : bool, optional
            Activate or desactivate the deplacement in a absolu mode. The default is None.

        Returns
        -------
        None
        """

        if absolu is not None:
            self.Referenciel(axe, absolu)
        deplacement = self.Conversion_mm_pas(deplacement)

        message = self.send_command("?ASTAT")
        print("\nCheck if movable => ", message[axe-1], ":", self.axis_state[message[axe-1]])
        if message[axe-1] == "A":
            print("Re-initialising the axis")
            self.Initialisation_Axe(axe)

        if message[axe-1] == "R":
            self.send_command(f"PSET{axe}={deplacement}")
            self.send_command(f"PGO{axe}")

            # time.sleep(0.5)
            message = self.send_command("?ASTAT")
            print(message[axe-1], ":", self.axis_state[message[axe-1]])

            t0 = time.time()
            while message[axe-1] != "R" :
                message = self.send_command("?ASTAT")

                if self.affichage and time.time()-t0 > 1:
                    print(message[axe-1], ":", self.axis_state[message[axe-1]])
                    t0 = time.time()

                if message[axe-1] == "A" :
                    print("Mouvement stoped due to switch button")
                    break

            position = self.Get_Position(axe)
            print(f"Moved to {position} {self.unit} on the axis {axe}")

        else :
            print("Axis is not movable")
            return None


    def Get_Position(self, axes=[1,2,3]):
        """
        Return the position on each axis.

        Parameters
        ----------
        axes : list of float, optional
            List of the axis to get the position. The default is [1,2,3].

        Returns
        -------
        list of float
            Return a list of int refering to the position on each axis depending on the input.
        """

        positions = []
        if type(axes)==int:
            try :
                raw_value = int(self.send_command(f"?CNT{axes}"))
            except:
                print("PLease, wait 1sec")
                time.sleep(1)
                raw_value = int(self.send_command(f"?CNT{axes}").split()[-1])

            value = self.Conversion_pas_mm(raw_value)
            return value

        for axe in axes:
            raw_value = int(self.send_command(f"?CNT{axe}"))
            value = self.Conversion_pas_mm(raw_value)
            positions.append(value)
        return positions


    def Set_Zero(self, axis = None , value = 0):
        if axis is None :
            for axe in self.intialized_axis:
                self.send_command(f"CNT{axe}={value}")
        else :
            if type(axis) == list:
                for axe in axis:
                    self.send_command(f"CNT{axe}={value}")
            elif type(axis) == int:
                self.send_command(f"CNT{axis}={value}")
            else:
                print("Merci de rentrer une liste d'axe ou un seul axe")
                return None
        print("Définition du point actuel comme origine\n")


    def Move_Zero(self, axes = None):
        if axes is not None:
            for axe in axes :
                self.Move(axe, 0, absolu=True)
        else :
            for axe in self.intialized_axis:
                self.Move(axe, 0, absolu=True)