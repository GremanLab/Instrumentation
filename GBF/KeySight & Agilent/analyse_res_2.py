"""
analyse_res_2.py
====================
Analyse de résistance par sweep I(V) avec un SMU Keysight B2901A
via GPIB-USB-HS.

Prérequis :
    pip install pyvisa pandas matplotlib
    Installez NI-VISA depuis https://www.ni.com/fr-fr/support/downloads/drivers/download.ni-visa.html
        (recommandé pour GPIB-USB-HS)
    Installer le pilote NI-488.2 

Branchement 4 fils (Kelvin) :
    Force HI  → borne + de la résistance
    Force LO  → borne - de la résistance
    Sense HI  → borne + de la résistance (proche de R)
    Sense LO  → borne - de la résistance (proche de R)
"""

import time
import datetime
import csv
import os
import pyvisa
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


# ────────────────────────────────────────────────────────────────────────────
#  CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────

GPIB_ADDRESS  = "GPIB0::23::INSTR"          # Adresse GPIB du B2901A


# Sweep de tension

V_START       = 0.5         # Tension de départ (V)
V_STOP        = 10.0        # Tension finale (V)
V_STEPS       = 20          # Nombre de points
V_COMPLIANCE  = 1e-3        # Courant max autorisé (A) — protection instrument/DUT
                            # Pour 10 MΩ : I = V/R = 10/10e6 = 1µA → 1mA est largement suffisant

NPLC          = 1           # Intégration (1 = 20ms, 10 = 200ms plus précis)
OUTPUT_CSV    = "iv_curve_B2901A.csv"

# ─────────────────────────────────────────────────────────────────────────────


def connect(gpib_address: int):
    rm = pyvisa.ResourceManager()
    print("Ressources VISA détectées :")
    for r in rm.list_resources():
        print(f"  {r}")

    instr = rm.open_resource(gpib_address)
    instr.timeout = 15000
    instr.write_termination = "\n"
    instr.read_termination  = "\n"

    idn = instr.query("*IDN?").strip()
    print(f"\nInstrument : {idn}")
    return instr


def configure_B2901A(instr, v_compliance: float):
    """Configure le B2901A en source de tension / mesure de courant."""
    instr.write("*RST")
    instr.write("*CLS")
    time.sleep(1)

    instr.write(":SOUR:FUNC:MODE VOLT")           # Source tension
    instr.write(":SOUR:VOLT:MODE FIX")
    instr.write(f":SENS:CURR:PROT {v_compliance}") # Compliance courant
    instr.write(":SENS:FUNC 'CURR'")               # Mesure courant
    instr.write(f":SENS:CURR:NPLC {NPLC}")
    instr.write(":SENS:CURR:RANG:AUTO ON")
    instr.write(":FORM:ELEM:SENS CURR,VOLT")       # Retourne I et V
    instr.write(":OUTP:SENS ON")                   # Active la mesure 4 fils (Remote Sense)

    print("B2901A configuré : source tension, mesure courant 4 fils.")


def sweep_iv(instr, v_start, v_stop, v_steps):
    """Effectue le sweep I(V) et retourne les données."""
    voltages   = np.linspace(v_start, v_stop, v_steps)
    results    = []

    print(f"\n{'Point':>6}  {'Tension (V)':>12}  {'Courant (A)':>14}  {'Résistance (Ω)':>16}")
    print("─" * 58)

    instr.write(":OUTP ON")   # Sortie ON

    try:
        for i, v in enumerate(voltages):
            instr.write(f":SOUR:VOLT {v:.6f}")
            time.sleep(0.05)  # stabilisation

            raw = instr.query(":MEAS:CURR?").strip()
            # Le B2901A retourne parfois "I,V" — on prend le premier champ
            current = float(raw.split(",")[0])

            resistance = abs(v / current) if current != 0 else float("inf")
            ts = datetime.datetime.now().isoformat()

            results.append({
                "index":      i,
                "timestamp":  ts,
                "voltage_V":  v,
                "current_A":  current,
                "resistance_Ohm": resistance,
            })

            print(f"{i:6d}  {v:12.4f}  {current:14.4e}  {resistance:16.4e}")

    finally:
        instr.write(":SOUR:VOLT 0")   # Remise à 0 avant de couper
        time.sleep(0.1)
        instr.write(":OUTP OFF")      # Sortie OFF
        print("\nSortie désactivée.")

    return results


def save_csv(filepath, results):
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=results[0].keys())
        writer.writeheader()
        writer.writerows(results)
    print(f"Données enregistrées : {os.path.abspath(filepath)}")


def plot_iv(results):
    df = pd.DataFrame(results)

    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    fig.suptitle("Analyse I(V) — Keysight B2901A", fontsize=13)

    # Courbe I(V)
    axes[0].plot(df["voltage_V"], df["current_A"] * 1e6,
                 "o-", color="steelblue", linewidth=1.5, markersize=4)
    axes[0].set_xlabel("Tension (V)")
    axes[0].set_ylabel("Courant (µA)")
    axes[0].set_title("Courbe I(V)")
    axes[0].grid(True, linestyle="--", alpha=0.5)

    # Résistance calculée R = V/I
    df_valid = df[df["resistance_Ohm"] < 1e15]   # exclut les infinis
    axes[1].plot(df_valid["voltage_V"], df_valid["resistance_Ohm"] / 1e6,
                 "o-", color="coral", linewidth=1.5, markersize=4)
    axes[1].set_xlabel("Tension (V)")
    axes[1].set_ylabel("Résistance (MΩ)")
    axes[1].set_title("Résistance calculée R = V/I")
    axes[1].grid(True, linestyle="--", alpha=0.5)

    plt.tight_layout()
    plt.savefig("iv_curve_B2901A.png", dpi=150)
    plt.show()
    print("Graphe sauvegardé : iv_curve_B2901A.png")

    # Statistiques
    r_vals = df_valid["resistance_Ohm"].values
    print("\n─── Résistance (R = V/I) ───────────────────")
    print(f"  Moyenne  : {r_vals.mean()/1e6:.4f} MΩ")
    print(f"  Std dev  : {r_vals.std()/1e6:.4f} MΩ")
    print(f"  Min      : {r_vals.min()/1e6:.4f} MΩ")
    print(f"  Max      : {r_vals.max()/1e6:.4f} MΩ")
    print("────────────────────────────────────────────")


def main():
    instr = connect(GPIB_ADDRESS)
    try:
        configure_B2901A(instr, V_COMPLIANCE)
        results = sweep_iv(instr, V_START, V_STOP, V_STEPS)
        save_csv(OUTPUT_CSV, results)
        plot_iv(results)
    finally:
        instr.write(":OUTP OFF")
        instr.close()
        print("Connexion fermée.")


if __name__ == "__main__":
    main()