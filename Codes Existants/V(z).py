import time
import matplotlib.pyplot as plt

import RTMV2 as RTM
import PS90_4 as ps

# ────────── Constantes ──────────

Temp_eau = 26 #°C

v_onde = (1480 + (Temp_eau-20)*2)*10**3  #m/s

nb_moyennage = 8
pas = 0.5 #mm
Zmax = 31 #mm

date = time.strftime("%Y-%m-%d") #€-%S

inpusle_duration = 2e-6 # Duration of the inpulse


# ────────── Initialisation des appareils ──────────

# ───── PS90 ────
ps90 = ps.PS90("COM3")
ps90.Initialisation_Axes([1,2,3], absolu=False)

     
# ─── Oscillo ───
rtm = RTM.RsInstrument(RTM.IP_address3k, limit_time=inpusle_duration)

rtm.Average(nb_moyennage)

# ────────── Mise à zeros ──────────

ps90.Positionnement([1,3])

# ────────── Mesures ──────────

nb_measures = int(Zmax/pas+1)

print("Le nb de mesures est de ", nb_measures)

settings = rtm.Save_Oscillo_Settings(1)
for n in range(nb_measures):
    t1 = time.time()
    
    rtm.Vertical_Adjust(1)

    t0, dt, data = rtm.Measure(1)
    maximum = max(RTM.Redressement(data))
    
    rtm.Calibers(horizontal_pos=settings["horizontal_position"]+(2*pas/v_onde)*n )

    datas = [Temp_eau, nb_moyennage, pas, t0, dt] + data
    RTM.Export_data(f"C:/Users/Utilisateur/PyCharmMiscProject/Nouveau dossier (2)/{n+1}-{nb_measures}-Measure-{date}.csv", datas)

    
    ps90.Move(3, -pas, absolu=False)
    
    t2 = time.time()
    temps_boucle = t2-t1
    temps_estime = (nb_measures-n)*temps_boucle
    print(f"Le temps restant est estimé à {temps_estime//60}min {int(temps_estime%60)}s" )
    
ps90.close()
