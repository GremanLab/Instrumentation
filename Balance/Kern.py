"""
pip install serial si pas déjà fait

Mettre la balance à 9600 baud si 1200 par défaut :
-Maintenir Print/Menu,
-Appui court sur Print/Menu pour aller jusqu’à BAUD
-Entrer
-Sélectionner 9600 puis Entrer

Mettre en connection sur le mode ASK (si on veut des valeurs stabilisées) ou CO_R (pour valeur même si non stabilisée)
-Maintenir Print/Menu,
-Appui court sur Print/Menu pour aller jusqu’à PRINT
-Entrer
-Sélectionner ce que vous voulez
"""

import serial

PORT = "COM7"
BAUDRATE = 9600

_ser = None


def _get_connection():
    global _ser
    if _ser is None or not _ser.is_open:
        _ser = serial.Serial(
            port=PORT,
            baudrate=BAUDRATE,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            xonxoff=False,
            rtscts=False,
            timeout=3,
        )
    return _ser


def lecture_kern():
    """
    Retourne le poids actuel en grammes (float), ou None si la balance
    signale une valeur instable ('S I').

    Comportement selon le mode configuré sur la balance :
      - Mode ASK  : envoie SI sur commande PC ; retourne None si instable.
      - Mode CONT : envoie les valeurs en continu, même instables ; None rare.

    Lève ValueError uniquement si la balance ne répond pas du tout.
    """
    ser = _get_connection()
    ser.reset_input_buffer()
    ser.write(b"SI\r")
    line = ser.readline().decode("ascii", errors="ignore")
    parts = line.strip().split()
    # 'S I' = poids trop dynamique, pas de valeur
    if parts == ["S", "I"]:
        return None
    # Trame normale : ['S', 'S'/'D', '0.0000', 'g']
    if len(parts) != 4:
        raise ValueError(f"Pas de réponse de la balance (trame : {line!r})")
    return float(parts[2])


def fermer():
    """Ferme la connexion série."""
    global _ser
    if _ser and _ser.is_open:
        _ser.close()
        _ser = None


if __name__ == "__main__":
    import time
    try:
        while True:
            poids = lecture_kern()
            if poids is None:
                print("(instable)")
            else:
                print(poids, "g")
            time.sleep(0.5)
    except KeyboardInterrupt:
        fermer()
