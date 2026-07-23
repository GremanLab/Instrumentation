"""
Interface graphique pour piloter le moteur OWIS PS90.

Structure :
- ConnectionBar    : barre de connexion (port, bouton, statut)
- AxisControl      : panneau de contrôle d'un axe (X, Y, Z ou R)
- OscSettings      : réglages de l'oscilloscope
- ScanPointFrame   : réglages du scan par 3 points
- ScanLengthFrame  : réglages du scan par 3 longueurs
- ScanMatrixFrame  : réglages du scan matriciel (import CSV)
- ScanPanel        : panneau de droite (scan + osc settings)
- TerminalFrame    : terminal de sortie (stdout + stderr)
- App              : fenêtre principale

Layout de main_frame :
    col=0 row=0  → AxisControl (axes)
    col=0 row=1  → Select BottomFrame
    col=0 row=2  → BottomFrame (terminal or an image)
    col=1 row=0  → ScanPanel (rowspan=3, contient OscSettings en bas)

Note sur les scans :
    scan_by_interf et scan_for_matrix reçoivent un Toplevel() créé ici,
    ce qui évite le conflit entre deux Tk() simultanés.
    Pendant le scan, la fenêtre principale est désactivée (state="disabled")
    et se réactive automatiquement à la fermeture de la fenêtre de scan.
"""

import sys
import threading
import time
from tkinter import *
from tkinter import ttk, filedialog, messagebox, simpledialog
from PIL import Image, ImageTk

from classes.ps90.OWIS_PS90 import OWIS_PS90
from classes.HDO4034A.HDO4034A import HDO4034A
from scan.scan_by_interf import scan_by_interf
from scan.scan_for_matrix import scan_for_matrix
from classes import display_time as dtime
from classes import path_import as path

# ─────────────────────────────────────────────
#  Utilitaire : activer / désactiver récursivement
# ─────────────────────────────────────────────

def set_children_state(widget, state, exclude=()):
    """Active ou désactive récursivement tous les widgets enfants."""
    if widget in exclude:
        return

    try:
        widget.configure(state=state)
    except TclError:
        pass
    for child in widget.winfo_children():
        set_children_state(child, state)


# ─────────────────────────────────────────────
#  Dialogues utilitaires
# ─────────────────────────────────────────────

def ask_output() -> str:
    """Boîte de dialogue pour choisir le répertoire de sortie."""
    dir=filedialog.askdirectory(title="Select output directory")
    if dir !="":
        return dir
    else:
        print("scan cancelled")
        return 

def ask_name() -> str:
    """Boîte de dialogue pour saisir le nom du scan."""
    name=simpledialog.askstring("Scan name", "Enter the scan name:")
    if name !=None:
        return name
    else:
        print("scan  cancelled")
        return 

# ─────────────────────────────────────────────
#  Barre de connexion
# ─────────────────────────────────────────────

class ConnectionBar(ttk.Frame):
    """Barre en haut de la fenêtre : choix du port, connexion, statut."""

    def __init__(self, parent, on_connect, on_disconnect, **kwargs):
        super().__init__(parent, padding=(6, 4), borderwidth=2,
                         relief="groove", **kwargs)
        self.on_connect    = on_connect
        self.on_disconnect = on_disconnect
        self._connected    = False
        self._build()

    def _build(self):
        ttk.Label(self, text="Port :").grid(row=0, column=0, sticky="w")

        self.port_var = IntVar(value=0)
        ttk.Spinbox(self, from_=0, to=9, textvariable=self.port_var,
                    width=4).grid(row=0, column=1, padx=(2, 10))

        self.connect_btn = ttk.Button(self, text="Connect", command=self._toggle)
        self.connect_btn.grid(row=0, column=2, padx=(0, 10))

        self.status_var = StringVar(value="⬤  Disconnected")
        self.status_lbl = ttk.Label(self, textvariable=self.status_var, foreground="red")
        self.status_lbl.grid(row=0, column=3, sticky="w")

    def _toggle(self):
        if self._connected:
            self._connected = False
            self.connect_btn.config(text="Connect")
            self.status_var.set("⬤  Disconnected")
            self.status_lbl.config(foreground="red")
            self.on_disconnect()
        else:
            success = self.on_connect(self.port_var.get())
            if success:
                self._connected = True
                self.connect_btn.config(text="Disconnect")
                self.status_var.set("⬤  Connected")
                self.status_lbl.config(foreground="green")


# ─────────────────────────────────────────────
#  Panneau de contrôle d'un axe
# ─────────────────────────────────────────────

class AxisControl(ttk.Frame):
    """Panneau réutilisable pour un axe (X, Y, Z ou R)."""

    def __init__(self, parent, axis, label, unit="mm", **kwargs):
        super().__init__(parent, padding=(3, 3, 12), **kwargs)
        self.axis  = axis
        self.label = label
        self.unit  = unit
        self._build()

    def _build(self):
        # Position
        self.pos_var = DoubleVar()
        ttk.Label(self,text=f"Position {self.label}:").grid(row=0, column=0, sticky="w")
        self.pos_entry=ttk.Entry(self, textvariable=self.pos_var)
        self.pos_entry.grid(row=0, column=1, pady=(0, 4))
        #self.pos_var.trace_add("write", self._on_pos_change) # if we change manually the position: go to the position
        self.pos_entry.bind("<Return>",lambda e: self._on_pos_change())
        self.pos_entry.bind("<FocusOut>",lambda e: self._on_pos_change())
        
        ttk.Label(self, text="mm" if self.unit=="mm" else "°").grid(row=0, column=2, sticky="w")

        # Déplacement
        up_btn = ttk.Button(self, text="▲")
        up_btn.bind("<ButtonPress-1>",   lambda e: self.axis.go_vel(1))
        up_btn.bind("<ButtonRelease-1>", lambda e: self.axis.stop_vel())
        up_btn.grid(row=1, column=0, columnspan=3, sticky="ew")

        down_btn = ttk.Button(self, text="▼")
        down_btn.bind("<ButtonPress-1>",   lambda e: self.axis.go_vel(-1))
        down_btn.bind("<ButtonRelease-1>", lambda e: self.axis.stop_vel())
        down_btn.grid(row=2, column=0, columnspan=3, sticky="ew")

        # Vitesse
        self.vel_var = DoubleVar(value=5)
        ttk.Label(self, text=f"V{self.label.lower()} :").grid(row=3, column=0, sticky="w")
        vel_spin = ttk.Spinbox(self, from_=0, to=self.axis.MAX_VEL,
                               textvariable=self.vel_var, width=6)
        vel_spin.delete(0, END)
        vel_spin.insert(0, 5)
        vel_spin.grid(row=3, column=1, sticky="ew",columnspan=3)
        self.vel_var.trace_add("write", self._on_vel_change)

        # Home
        ttk.Button(self, text=f"Set home {self.label}",
                   command=self.axis.set_home
                   ).grid(row=4, column=0, columnspan=3, sticky="ew", pady=(6, 0))
        ttk.Button(self, text=f"Go home {self.label}",
                   command=self.axis.go_home
                   ).grid(row=5, column=0, columnspan=3, sticky="ew")

    def _on_pos_change(self, *_):
        try:
            self.axis.move_abs(self.pos_var.get())
        except Exception:
            pass

    def _on_vel_change(self, *_):
        try:
            self.axis.vel = self.vel_var.get()
        except Exception:
            pass

    def refresh(self):
        """Met à jour l'affichage de la position."""
        if self.pos_entry == self.pos_entry.focus_get():
            return
        if self.unit == "°":
            self.pos_var.set(
                round(self.axis.pos / 1000,3))
        else:
            self.pos_var.set(
                round(self.axis.pos,3))


# ─────────────────────────────────────────────
#  Réglages oscilloscope
# ─────────────────────────────────────────────

class OscSettings(ttk.LabelFrame):
    """Panneau de réglages de l'oscilloscope."""

    def __init__(self, parent, osc, **kwargs):
        super().__init__(parent, text="Oscilloscope settings", **kwargs)
        self.osc = osc
        self._build()

    def _build(self):

        # oscilloscope IP address
        self.osc_ip = StringVar(value='169.254.27.102')
        ttk.Label(self, text="Oscilloscope IP address :").grid(row=0, column=0, sticky="e", padx=(0,4))
        osc_ip_entry = ttk.Entry(self, textvariable=self.osc_ip, width=15)
        osc_ip_entry.grid(row=0, column=1, sticky="w")

        # Hydrophone channel
        self.hyd_chan = StringVar(value="C1")
        ttk.Label(self, text="Hydrophone channel :").grid(row=1, column=0, sticky="e", padx=(0,4))
        hyd_comb = ttk.Combobox(self, textvariable=self.hyd_chan, width=6,
                                values=["C1", "C2", "C3", "C4"], state="readonly")
        hyd_comb.grid(row=1, column=1, sticky="w")

        # Hydrophone coupling
        self.hyd_coup = StringVar(value="D50")
        ttk.Label(self, text="Hydrophone coupling :").grid(row=2, column=0, sticky="e", padx=(0,4))
        hyd_coup_comb = ttk.Combobox(self, textvariable=self.hyd_coup, width=6,
                                     values=["A1M", "D1M", "D50", "GND"], state="readonly")
        hyd_coup_comb.grid(row=2, column=1, sticky="w")

        # Excitation channel
        self.exc_chan = StringVar(value="C2")
        ttk.Label(self, text="Excitation channel :").grid(row=3, column=0, sticky="e", padx=(0,4))
        exc_comb = ttk.Combobox(self, textvariable=self.exc_chan, width=6,
                                values=["C1", "C2", "C3", "C4"], state="readonly")
        exc_comb.grid(row=3, column=1, sticky="w")

        # Excitation coupling
        self.exc_coup = StringVar(value="D50")
        ttk.Label(self, text="Excitation coupling :").grid(row=4, column=0, sticky="e", padx=(0,4))
        exc_coup_comb = ttk.Combobox(self, textvariable=self.exc_coup, width=6,
                                     values=["A1M", "D1M", "D50", "GND"], state="readonly")
        exc_coup_comb.grid(row=4, column=1, sticky="w")

        # Sweeps per acquisition
        self.sweep_nb = IntVar(value=1)
        ttk.Label(self, text="Sweep per acquisition :").grid(row=5, column=0, sticky="e", padx=(0,4))
        ttk.Entry(self, textvariable=self.sweep_nb, width=8).grid(row=5, column=1, sticky="w")

        # maximum sample per acquisition
        self.acq_sample_max = IntVar(value=500)
        ttk.Label(self, text="Maximum sample per acquisition :").grid(row=6, column=0, sticky="e", padx=(0,4))
        ttk.Entry(self, textvariable=self.acq_sample_max, width=8).grid(row=6, column=1, sticky="w")

# ─────────────────────────────────────────────
#  Terminal (stdout / stderr redirigés)
# ─────────────────────────────────────────────

class TerminalFrame(ttk.LabelFrame):
    """Panneau terminal : redirige stdout et stderr vers un widget Text."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, text="Terminal", **kwargs)
        self._build()

    def _build(self):
        self.text = Text(self, height=15, width=80, state="normal",
                         bg="#1e1e1e", fg="#d4d4d4", font=("Courier", 9))
        scrollbar = ttk.Scrollbar(self, orient=VERTICAL, command=self.text.yview)
        self.text.configure(yscrollcommand=scrollbar.set)

        self.text.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Redirection (save previous streams so we can restore them later)
        self._old_stdout = sys.stdout
        self._old_stderr = sys.stderr
        sys.stdout = self
        sys.stderr = self

    def write(self, text):
        """Appelé par print() et les erreurs."""
        try:
            # Guard against the Text widget being destroyed (TclError)
            self.text.insert(END, text)
            self.text.see(END)
        except TclError:
            # If the widget no longer exists, fallback to original stderr
            try:
                self._old_stderr.write(text)
            except Exception:
                pass

    def flush(self):
        """Requis pour la compatibilité avec sys.stdout."""
        pass

    def close(self):
        """Restore previous stdout/stderr when the terminal is destroyed."""
        try:
            sys.stdout = self._old_stdout
        except Exception:
            pass
        try:
            sys.stderr = self._old_stderr
        except Exception:
            pass


# ─────────────────────────────────────────────
#  Panneau scan — mode "3 points"
# ─────────────────────────────────────────────

class ScanPointFrame(ttk.Frame):
    """Réglages du scan par 3 points + bouton Launch."""

    def __init__(self, parent, on_launch, osc_settings, ps, **kwargs):
        super().__init__(parent, **kwargs)
        self.on_launch    = on_launch
        self.osc_settings = osc_settings
        self.ps           = ps   # pour le bouton "Set Px (current pos)"
        self._build()

    def _build(self):
        # Points P1 / P2 / P3
        self.point_vars = {
            name: {ax: DoubleVar(value=0) for ax in ("X", "Y", "Z")}
            for name in ("P1", "P2", "P3")
        }
        for row, (name, color) in enumerate(
                [("P1", "red"), ("P2", "green"), ("P3", "blue")]):
            ttk.Label(self, text=f"{name} (mm) :", foreground=color).grid(
                row=row, column=0, sticky="w")
            for i, ax in enumerate(("X", "Y", "Z")):
                ttk.Label(self, text=f"{ax}:", foreground=color).grid(
                    row=row, column=2 * i + 1)
                ttk.Entry(self, textvariable=self.point_vars[name][ax],
                          foreground=color, width=7).grid(
                    row=row, column=2 * i + 2, sticky="w")
            ttk.Button(self, text=f"Set {name}",
                       command=lambda n=name: self._set_current_pos(n)
                       ).grid(row=row, column=7, sticky="w", padx=(6, 0))

        # Pas dX / dY / dZ
        self.delta_vars = {}
        for i, ax in enumerate(("X", "Y", "Z")):
            var = DoubleVar(value=0.1)
            self.delta_vars[ax] = var
            ttk.Label(self, text=f"d{ax} (mm) =").grid(row=3 + i, column=0, sticky="w")
            ttk.Entry(self, textvariable=var).grid(
                row=3 + i, column=1, sticky="ew", columnspan=6)

        ttk.Button(self, text="Launch", command=self._on_click_launch).grid(
            row=6, column=0, columnspan=8, sticky="ew", ipady=4, pady=(8, 4))

        # self._load_image()

    def _set_current_pos(self, point_name):
        self.point_vars[point_name]["X"].set(self.ps.X.pos)
        self.point_vars[point_name]["Y"].set(self.ps.Y.pos)
        self.point_vars[point_name]["Z"].set(self.ps.Z.pos)

    def _on_click_launch(self):
        osc = self.osc_settings
        out_path_choosed=ask_output()
        if out_path_choosed==None:
            return
        name_choosed=ask_name()
        if name_choosed==None:
            return
        self.on_launch(
            out_path = out_path_choosed,
            name     = name_choosed,
            mode     = "point",
            p1       = [self.point_vars["P1"][ax].get() for ax in ("X", "Y", "Z")],
            p2       = [self.point_vars["P2"][ax].get() for ax in ("X", "Y", "Z")],
            p3       = [self.point_vars["P3"][ax].get() for ax in ("X", "Y", "Z")],
            dx       = self.delta_vars["X"].get(),
            dy       = self.delta_vars["Y"].get(),
            dz       = self.delta_vars["Z"].get(),
            osc_ip = osc.osc_ip.get(),
            hyd_chan = osc.hyd_chan.get(),
            exc_chan = osc.exc_chan.get(),
            hyd_coup = osc.hyd_coup.get(),
            exc_coup = osc.exc_coup.get(),
            sweep_nb = osc.sweep_nb.get(),
            acq_sample_max = osc.acq_sample_max.get()
        )

    # def _load_image(self):
#         try:
            # img = Image.open(self.IMG_PATH)
            # img.thumbnail((300, 200))
            # self._photo = ImageTk.PhotoImage(img)
            # ttk.Label(self, image=self._photo).grid(row=7, column=0, columnspan=8)
        # except FileNotFoundError:
            # pass


# ─────────────────────────────────────────────
#  Panneau scan — mode "3 longueurs"
# ─────────────────────────────────────────────

class ScanLengthFrame(ttk.Frame):
    """Réglages du scan par 3 longueurs + bouton Launch."""

    def __init__(self, parent, on_launch, osc_settings, **kwargs):
        super().__init__(parent, **kwargs)
        self.on_launch    = on_launch
        self.osc_settings = osc_settings
        self._build()

    def _build(self):

        self.length_vars = {}
        for row, (name, color) in enumerate(
                [("X'", "green"), ("Y'", "red"), ("Z'", "blue")]):
            var = DoubleVar(value=0)
            self.length_vars[name] = var
            ttk.Label(self, text=f"{name} (mm) :", foreground=color).grid(
                row=row + 1, column=0, sticky="w")
            ttk.Entry(self, textvariable=var, foreground=color).grid(
                row=row + 1, column=1, sticky="ew")

        self.delta_vars = {}
        for i, ax in enumerate(("X", "Y", "Z")):
            var = DoubleVar(value=0.1)
            self.delta_vars[ax] = var
            ttk.Label(self, text=f"d{ax} (mm) =").grid(row=4 + i, column=0, sticky="w")
            ttk.Entry(self, textvariable=var).grid(row=4 + i, column=1, sticky="ew")

        ttk.Button(self, text="Launch", command=self._on_click_launch).grid(
            row=7, column=0, columnspan=2, sticky="ew", ipady=4, pady=(8, 4))

        ttk.Label(self, text="Please sethome to the origin point",font=("calibri",11,"bold")).grid(
            row=8, column=0, columnspan=2, sticky="w", pady=(0, 4))

    def _on_click_launch(self):
        osc = self.osc_settings
        out_path_choosed=ask_output()
        if out_path_choosed==None:
            return
        name_choosed=ask_name()
        if name_choosed==None:
            return
        self.on_launch(
            out_path = out_path_choosed,
            name     = name_choosed,
            mode     = "length",
            p1       = self.length_vars["X'"].get(),
            p2       = self.length_vars["Y'"].get(),
            p3       = self.length_vars["Z'"].get(),
            dx       = self.delta_vars["X"].get(),
            dy       = self.delta_vars["Y"].get(),
            dz       = self.delta_vars["Z"].get(),
            osc_ip   = osc.osc_ip.get(),
            hyd_chan = osc.hyd_chan.get(),
            exc_chan = osc.exc_chan.get(),
            hyd_coup = osc.hyd_coup.get(),
            exc_coup = osc.exc_coup.get(),
            sweep_nb = osc.sweep_nb.get(),
            acq_sample_max = osc.acq_sample_max.get()        
        )

    # def _load_image(self):
#         try:
            # img = Image.open(self.IMG_PATH)
            # img.thumbnail((300, 200))
            # self._photo = ImageTk.PhotoImage(img)
            # ttk.Label(self, image=self._photo).grid(row=8, column=0, columnspan=2)
        # except FileNotFoundError:
            # pass


# ─────────────────────────────────────────────
#  Panneau scan — mode "matrice"
# ─────────────────────────────────────────────

class ScanMatrixFrame(ttk.Frame):
    """Réglages du scan matriciel : import CSV + bouton Launch."""

    def __init__(self, parent, on_launch, osc_settings, **kwargs):
        super().__init__(parent, **kwargs)
        self.on_launch    = on_launch
        self.osc_settings = osc_settings
        self.matrix_path  = None
        self._build()

    def _build(self):
        ttk.Button(self, text="Import a CSV file",
                   command=self._import_file
                   ).grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 4))

        self.file_var = StringVar(value="No file selected")
        ttk.Label(self, textvariable=self.file_var, foreground="gray",
                  wraplength=250).grid(row=1, column=0, columnspan=2, sticky="w")

        self.osc_settings.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(8, 4))

        ttk.Button(self, text="Launch", command=self._on_click_launch).grid(
            row=3, column=0, columnspan=2, sticky="ew", ipady=4, pady=(10, 0))

    def _import_file(self):
        path = filedialog.askopenfilename(
            title="Select a matrix file",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if path:
            self.matrix_path = path
            self.file_var.set(path)

    def _on_click_launch(self):
        if not self.matrix_path:
            messagebox.showwarning("Missing file", "Please import a CSV file first.")
            return
        osc = self.osc_settings
        out_path_choosed=ask_output()
        if out_path_choosed==None:
            return
        name_choosed=ask_name()
        if name_choosed==None:
            return
        self.on_launch(
            out_path    = out_path_choosed,
            name        = name_choosed,
            matrix_path = self.matrix_path,
            osc_ip     = osc.osc_ip.get(),
            hyd_chan    = osc.hyd_chan.get(),
            exc_chan    = osc.exc_chan.get(),
            hyd_coup    = osc.hyd_coup.get(),
            exc_coup    = osc.exc_coup.get(),
            sweep_nb    = osc.sweep_nb.get(),
            acq_sample_max = osc.acq_sample_max.get()        
        )


# ─────────────────────────────────────────────
#  Panneau des réglages de scan (droite)
# ─────────────────────────────────────────────

class ScanPanel(ttk.Frame):
    """
    Panneau de droite :
      - boutons home globaux
      - sélecteur de mode + sous-panneau de scan
      - OscSettings en bas
    """

    def __init__(self, parent, ps, osc, on_scan_start, on_scan_end,on_mode_change, **kwargs):
        super().__init__(parent, **kwargs)
        self.ps            = ps
        self.osc = osc
        self.on_scan_start = on_scan_start
        self.on_scan_end   = on_scan_end
        self.on_mode_change=on_mode_change
        self._build()

    def _build(self):
        # ── Boutons home ────────────────────────────────────────────────────
        home_frame = ttk.Frame(self)
        home_frame.grid(row=0, column=0, sticky="ew", pady=(0, 4))
        ttk.Button(home_frame, text="Set home (all axes)",
                   command=self.ps.set_all_home
                   ).grid(row=0, column=0, sticky="ew", ipady=5, padx=(0, 4))
        ttk.Button(home_frame, text="Go home (all axes)",
                   command=self.ps.go_all_home
                   ).grid(row=0, column=1, sticky="ew", ipady=5)

        # ── Sélecteur de mode ────────────────────────────────────────────────
        mode_frame = ttk.Frame(self, borderwidth=3, relief="sunken", padding=4)
        mode_frame.grid(row=1, column=0, sticky="ew", pady=4)

        self.scan_mode = StringVar()
        for i, (text, value) in enumerate([
                ("Scan with 3 points",   "points"),
                ("Scan with 3 lengths",  "lengths"),
                ("Matrix scan",          "matrix"),
        ]):
            ttk.Radiobutton(mode_frame, text=text,
                            variable=self.scan_mode, value=value
                            ).grid(row=i, column=0, sticky="w")

        # ── OscSettings (instance partagée avec les sous-panneaux) ───────────
        self.osc_settings = OscSettings(self, self.osc, padding=(4, 4))

        # ── Sous-panneaux de scan ────────────────────────────────────────────
        self.panel_points  = ScanPointFrame(
            self, on_launch=self._launch_by_interf,
            osc_settings=self.osc_settings, ps=self.ps)
        self.panel_lengths = ScanLengthFrame(
            self, on_launch=self._launch_by_interf,
            osc_settings=self.osc_settings)
        self.panel_matrix  = ScanMatrixFrame(
            self, on_launch=self._launch_matrix,
            osc_settings=self.osc_settings)

        # OscSettings placé en bas (row=3), toujours visible
        self.osc_settings.grid(row=2, column=0, sticky="ew", pady=5)

        self.scan_mode.trace_add("write", self._on_mode_change)

    def _on_mode_change(self, *_):
        """Affiche uniquement le sous-panneau du mode sélectionné."""
        for panel in (self.panel_points, self.panel_lengths, self.panel_matrix):
            panel.grid_remove()
        match self.scan_mode.get():
            case "points":
                self.on_mode_change("img_points")
                self.panel_points.grid( row=3, column=0, sticky="nsew")
            case "lengths":
                self.on_mode_change("img_lengths")
                self.panel_lengths.grid(row=3, column=0, sticky="nsew")
            case "matrix":
                self.on_mode_change("terminal")
                self.panel_matrix.grid( row=3, column=0, sticky="nsew")

    # ── Création du widget de scan ────────────────────────────

    def _make_scan_window(self, break_callbacks=None):
        stop_event  = threading.Event()
        break_event = threading.Event()

        on_close = self.on_scan_start(stop_event, break_event, break_callbacks)
        return stop_event, break_event, on_close

    # ── Lancement des scans dans un thread daemon ────────────────────────────

    def _launch_by_interf(self, out_path, name, mode, p1, p2, p3,
                          dx, dy, dz, osc_ip, hyd_chan, exc_chan, hyd_coup, exc_coup, sweep_nb, acq_sample_max):
        break_callbacks = {}
        stop_event, break_event, on_close = self._make_scan_window(break_callbacks)
        root = self.winfo_toplevel()
        safe_on_close = lambda: root.after(0,on_close)

        threading.Thread(
            target=scan_by_interf,
            args=(name, out_path, mode, p1, p2, p3,
                  float(dx), float(dy), float(dz),
                  osc_ip, hyd_chan, exc_chan, hyd_coup, exc_coup, sweep_nb, acq_sample_max),
            kwargs={
                "ps": self.ps,
                "stop_event": stop_event,
                "break_event": break_event,
                "on_close": safe_on_close,
                "on_update": lambda pct, t: root.after(
                    0, lambda: self.master.master.scan_progress.update_progress(pct, t)
                ),
                "break_callbacks": break_callbacks,
            },
            daemon=True,
        ).start()

    def _launch_matrix(self, out_path, name, matrix_path,
                       osc_ip, hyd_chan, exc_chan, hyd_coup, exc_coup, sweep_nb, acq_sample_max):
        break_callbacks = {}
        stop_event, break_event, on_close = self._make_scan_window()
        root = self.winfo_toplevel()
        safe_on_close = lambda: root.after(0,on_close)

        threading.Thread(
            target=scan_for_matrix,
            args=(name, out_path, matrix_path,
                  osc_ip, hyd_chan, exc_chan, hyd_coup, exc_coup, sweep_nb, acq_sample_max),
            kwargs={
                "ps": self.ps,
                "stop_event": stop_event,
                "break_event": break_event,
                "on_close": safe_on_close,
                "on_update": lambda pct, t: root.after(
                    0, lambda: self.master.master.scan_progress.update_progress(pct,t)
                ),
                "break_callbacks": break_callbacks,

            },
            daemon=True,
        ).start()


class ScanProgressFrame(ttk.Frame):
    def __init__(self, parent, on_stop, on_break_cb, on_take_back_cb, **kwargs):
        super().__init__(parent, **kwargs)
        self.on_stop      = on_stop
        self.on_break_cb     = on_break_cb
        self.on_take_back_cb = on_take_back_cb
        self._build(on_stop)
    
    def _build(self, on_stop):
        self.time_percent = IntVar(value=0)
        self.remaining_time_var = StringVar(value="Remaining time: \n ... calculating ... ")

        ttk.Label(self,textvariable=self.remaining_time_var).grid(row=0,column=0,pady=(0,4))
        ttk.Progressbar(self, orient=HORIZONTAL, length=300, 
                        mode='determinate',
                        variable=self.time_percent
                        ).grid(row=0,column=1,pady=(0,4))

        #self.break_btn = ttk.Button(self, text="BREAK",command = self.on_break)
        #self.take_back_btn = ttk.Button(self, text="TAKE BACK",command = self.on_take_back)
        self.stop_btn = ttk.Button(self, text="STOP",command = on_stop)

        self.break_btn = ttk.Button(self, text="BREAK", command=self.on_break)
        self.take_back_btn = ttk.Button(self, text="TAKE BACK", command=self.on_take_back)

        self.break_btn.grid(row=1,column=0,ipady=4,pady=(4,0))
        self.stop_btn.grid(row=1,column=1,ipady=4,pady=(4,0))

    def update_progress(self, percent:int, remaining_time:str):
        self.time_percent.set(percent)
        self.remaining_time_var.set(f"Remaining time: \n {dtime.display_time_str(remaining_time)} ")

    def on_break(self):
        self.on_break_cb()
        self.break_btn.grid_remove()
        self.take_back_btn.grid(row=1,column=0)

    def on_take_back(self):
        self.on_take_back_cb()
        self.take_back_btn.grid_remove()
        self.break_btn.grid(row=1,column=0)

# ─────────────────────────────────────────────
#  Fenêtre principale
# ─────────────────────────────────────────────

class App(ttk.Frame):
    """
    Fenêtre principale.

    Layout de main_frame (row=1 de App) :
        col=0 row=0  → AxisControl
        col=0 row=1  → (réservé)
        col=0 row=2  → TerminalFrame
        col=1 row=0  → ScanPanel (rowspan=3)
    """

    DLL_PATH   = (path.FILE_LOCATION +'/classes/ps90/ps90.dll')
    REFRESH_MS = 200

    def __init__(self, root):
        super().__init__(root, padding=6)
        self.ps            = None
        self.osc           = None
        self.axis_controls = []
        self._main_frame   = None
        self.grid(sticky="nsew")
        self.rowconfigure(0, weight=0)   # ConnectionBar : taille fixe
        self.rowconfigure(1, weight=1)   # main_frame : s'étire
        self.columnconfigure(0, weight=1)
        root.title("OWIS PS90 user interface")
        self._build_connection_bar()

    # ── Barre de connexion ───────────────────────────────────────────────────

    def _build_connection_bar(self):
        ConnectionBar(
            self,
            on_connect=self._connect,
            on_disconnect=self._disconnect,
        ).grid(row=0, column=0, sticky="ew", pady=(0, 6))

    # ── Connexion / déconnexion ──────────────────────────────────────────────

    def _connect(self, port: int) -> bool:
        """Ouvre la connexion au moteur (et à l'oscilloscope). Retourne True si succès."""
        self.ps = OWIS_PS90(dll_path=self.DLL_PATH)
        error   = self.ps.open_connection(port=port)
        if error["num"] != 0:
            messagebox.showerror(
                "Connection error",
                f"Unable to connect on port {port}.\nError code : {error['num']}"
            )
            self.ps = None
            return False

        self.osc = HDO4034A()
        # self.osc.open_connection(ip_address='169.254.27.102')

        self._build_main_panel()
        self._start_refresh_loop()
        return True

    def _disconnect(self):
        """Ferme la connexion et retire le panneau de contrôle."""
        if self.ps is not None:
            try:
                self.ps.close_connection()
                # self.osc.close_connection()
            except Exception:
                pass
            self.ps  = None
            self.osc = None

        if self._main_frame is not None:
            # Restore stdout/stderr if terminal exists to avoid TclError after widget destruction
            try:
                if hasattr(self, "terminal_frame") and self.terminal_frame is not None:
                    try:
                        self.terminal_frame.close()
                    except Exception:
                        pass
            except Exception:
                pass
            self._main_frame.destroy()
            self._main_frame   = None
            self.axis_controls = []

    # ── Activation / désactivation pendant un scan ───────────────────────────

    def _disable_main(self, stop_event, break_event, break_callbacks=None):
        
        self._setup_scan_interf(stop_event, break_event, break_callbacks)
        return self._unsetup_scan_interf

    def _enable_main(self):
        set_children_state(self, "normal")#,exclude=(self.terminal_frame))

    # ── Panneaux de contrôle ─────────────────────────────────────────────────

    def _build_main_panel(self):
        self._main_frame = ttk.Frame(self)
        self._main_frame.grid(row=1, column=0, sticky="nsew")
        self._main_frame.columnconfigure(0, weight=1)
        self._main_frame.columnconfigure(1, weight=1)
        self._main_frame.rowconfigure(0, weight=1)
        self._main_frame.rowconfigure(1, weight=1)
        self._main_frame.rowconfigure(2, weight=1)   

        # ── col=0 row=0 : Axes ───────────────────────────────────────────────
        self.axes_frame = ttk.Frame(
            self._main_frame, borderwidth=3, relief="sunken", padding=(3, 3, 12))
        self.axes_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        self.axis_controls = []
        for col, (axis, label, unit) in enumerate([
                (self.ps.X, "X", "mm"),
                (self.ps.Y, "Y", "mm"),
                (self.ps.Z, "Z", "mm"),
                (self.ps.R, "R", "°"),
        ]):
            ctrl = AxisControl(self.axes_frame, axis, label, unit)
            ctrl.grid(row=0, column=col, sticky="ns", padx=2)
            self.axis_controls.append(ctrl)
            axis.vel = 5

        # ── col=0 row=1 : Select_info ────────────────────────────────────────────
        self.info_select = ttk.Frame(self._main_frame)
        self.info_select.grid(row=1, column=0, sticky="ew", pady=(4, 0))

        ttk.Button(self.info_select, text="Terminal",
                   command=lambda: self._show_bottom_panel("terminal")
                   ).grid(row=0,column=0,padx=2)

        ttk.Button(self.info_select, text="Image (points)",
                   command=lambda: self._show_bottom_panel("img_points")
                   ).grid(row=0,column=1,padx=2)

        ttk.Button(self.info_select, text="Image (lengths)",
                   command=lambda: self._show_bottom_panel("img_lengths")
                   ).grid(row=0,column=2,padx=2)


        # ── col=0 row=2 : BottomPanel ───────────────────────────────────────────

        self.terminal_frame = TerminalFrame(self._main_frame, padding=(4, 4))

        img_points=Image.open(path.FILE_LOCATION+"/images/img_scan_point.png")
        img_points.thumbnail((600, 400))  # taille maximale, les proportions sont conservées
        self.img_scan_points = ImageTk.PhotoImage(img_points)
        self.img_points_label = Label(self._main_frame,image=self.img_scan_points)

        img_lengths=Image.open(path.FILE_LOCATION+"/images/img_scan_length.png")
        img_lengths.thumbnail((600, 400))  # taille maximale, les proportions sont conservées
        self.img_scan_lengths = ImageTk.PhotoImage(img_lengths)
        self.img_lengths_label = Label(self._main_frame,image=self.img_scan_lengths)

        self._show_bottom_panel("terminal")

        # ── col=1 row=0 rowspan=3 : ScanPanel ───────────────────────────────
        self.scan_settings = ScanPanel(
            self._main_frame,
            ps            = self.ps,
            osc           = self.osc,
            on_scan_start = self._disable_main,
            on_scan_end   = self._enable_main,
            on_mode_change  = self._show_bottom_panel,
            padding       = (3, 3, 12),
        )
        self.scan_settings.grid(row=0, column=1, rowspan=3, sticky="nsew")

    # ── Boucle de rafraîchissement ───────────────────────────────────────────

    def _start_refresh_loop(self):
        if self.ps is None:
            return
        for ctrl in self.axis_controls:
            try:
                ctrl.refresh()
            except Exception as e:
                print(f"Error occurred while refreshing control: {e}")
        self.after(self.REFRESH_MS, self._start_refresh_loop)

    def _show_bottom_panel(self,name:str):
        # On cache tout les widgets du slot (col=0, row=2):
        for widget in (self.terminal_frame, self.img_points_label, self.img_lengths_label):
            widget.grid_remove()
        
        # On affiche uniquement le widget demandé :
        match name:
            case "terminal":
                self.terminal_frame.grid(row=2,column=0,sticky="nswe")
            case "img_points":
                self.img_points_label.grid(row=2,column=0,sticky="nswe")
            case "img_lengths":
                self.img_lengths_label.grid(row=2,column=0,sticky="nswe")

    def _setup_scan_interf(self, stop_event, break_event, break_callbacks=None):
        for widget in (self.axes_frame, self.scan_settings, self.info_select):
            widget.grid_remove()

        def on_break_requested():
            break_event.set()
            callback = break_callbacks.get("on_break") if break_callbacks is not None else None
            if callback is not None:
                callback()

        def on_take_back_requested():
            break_event.clear()
            callback = break_callbacks.get("on_take_back") if break_callbacks is not None else None
            if callback is not None:
                callback()

        # On affiche les widgets nécessaires au scan (temps estimé, break, stop)
        self.scan_progress = ScanProgressFrame(
            self._main_frame,
            on_stop=lambda: stop_event.set(),
            on_break_cb=on_break_requested,
            on_take_back_cb=on_take_back_requested,
        )
        self.scan_progress.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self._show_bottom_panel("terminal")

    def _unsetup_scan_interf(self):
        
        if hasattr(self,"scan_progress"):
            self.scan_progress.destroy()

        # on remet la possibilité de relancer un scan
        self.axes_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self.scan_settings.grid(row=0, column=1, rowspan=3, sticky="nsew")
        self.info_select.grid(row=1, column=0, sticky="ew", pady=(4, 0))


# ─────────────────────────────────────────────
#  Point d'entrée
# ─────────────────────────────────────────────

if __name__ == "__main__":
    root = Tk()
    root.rowconfigure(0, weight=1)
    root.columnconfigure(0, weight=1)
    App(root)
    root.mainloop()
