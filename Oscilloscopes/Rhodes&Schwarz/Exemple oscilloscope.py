import RTMB200 as RTM
import matplotlib.pyplot as plt


# Ce programme est sert d'exemplaire pour une utilisation 
# du programme de pilotage de l'oscilloscope.
# 

# Initialisation de l'oscilloscope
oscillo = RTM.RsInstrument('TCPIP::169.254.158.94::INSTR')

# Regle certains parametres de l'oscilloscope
oscillo.Calibers(channel=1, time_scale=5e-6)
# 'channel' defini quel voies de l'oscilloscope est à modifier
# 'time_scale' change la durée temporelle par division en sec/div
# 'amplitude_scale' change la tension par division en V/

# Adapte la fenetre de l'écran au signal
oscillo.Vertical_Adjust(channel=1)

# Efectue une mesure sur l'écran de l'oscilloscope
t0, dt, data = oscillo.Measure(1)
# t0 : temps du premier echantillon
# dt : pas temporel entre chaques mesures
# data : jeu de données

vector_time = oscillo.Time_Vector(t0, dt, len(data))
plt.plot(vector_time, data)
plt.title("Diagramme de démonstration")
plt.xlabel("Time (en s)")
plt.ylabel("Amplitude (en V)")
plt.show()
