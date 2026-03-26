"""
Masutec GPX Converter – GUI  V2.2
Converts GPX waypoint files to Furuno/Masutec NMEA format ($PFEC,GPwpl)
Tab 1: Converter   |   Tab 2: Waypoint Map (OpenStreetMap)

Dependencies:
    pip install pandas lxml tkintermapview
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import math
import re
import os

#Map
try:
    import tkintermapview
    MAP_AVAILABLE = True
except ImportError:
    MAP_AVAILABLE = False

try:
    import pandas as pd
except ImportError:
    messagebox.showerror("Missing dependency",
                         "Please install pandas:\n  pip install pandas lxml")
    raise

# ── Colour palette ────────────────────────────────────────────────────────────
NAVY    = "#0a1628"
STEEL   = "#1c2e4a"
ACCENT  = "#00b4d8"
LIGHT   = "#caf0f8"
WARN    = "#ff9f1c"
GREEN   = "#06d6a0"
RED     = "#ff4d6d"
WHITE   = "#e8f4f8"
GREY    = "#4a6080"

FONT_MONO  = ("Courier New", 10)
FONT_LABEL = ("Georgia", 10)
FONT_TITLE = ("Georgia", 18, "bold")
FONT_SMALL = ("Georgia", 8)
FONT_BTN   = ("Georgia", 10)

# Marker colours per symbol type
SYMBOL_COLOUR = {
    "@q": "#00b4d8",
    "@s": "#ff9f1c",
    "@r": "#ff4d6d",
    "@z": "#06d6a0",
}

# ── Conversion logic (ported from notebook) ───────────────────────────────────

def lat_masu(lat_in):
    if math.isnan(lat_in):
        return -1, -1
    sign = "N"
    if lat_in < 0:
        sign = "S"
        lat_in *= -1
    lat_degree = int(lat_in)
    lat_minute = (lat_in - lat_degree) * 60
    if float(lat_minute) < 10:
        lat_minute = "0" + str(lat_minute)
    lat_out = round(float(str(lat_degree) + str(lat_minute)), 4)
    return lat_out, sign


def long_masu(long_in):
    long_in = float(long_in)
    if math.isnan(long_in):
        return -1, -1
    sign = "E"
    if long_in < 0:
        long_in *= -1
        sign = "W"
    long_degree = int(long_in)
    long_min = (long_in - long_degree) * 60
    if long_min < 10:
        long_min = "0" + str(long_min)
    long_out = float("{:.4f}".format(float(str(long_degree) + str(long_min))))
    if long_out < 1000:
        long_out = "0" + str(long_out)
    if float(long_out) < 100:
        long_out = "0" + str(long_out)
    if float(long_out) < 10:
        long_out = "0" + str(long_out)
    long_out = "0" + str(long_out)
    return long_out, sign


def format_name(name):
    name = str(name).upper()
    if len(name) > 8:
        name = name[:8]
    m = re.compile(r'([^A-Z0-9&()+ \-/=?])').findall(name)
    for ch in m:
        name = name.replace(ch, "?")
    return name


def convert_gpx(input_path, output_path, auto_symbols=True, log_cb=None):
    def log(msg):
        if log_cb:
            log_cb(msg)

    log(f"Reading  {os.path.basename(input_path)} ...")
    raw_xml = pd.read_xml(input_path, encoding='utf-8', parser='lxml')

    df = raw_xml[['lat', 'lon']].copy()
    df.insert(2, "name", raw_xml.iloc[:, 3])

    if math.isnan(df.iloc[0, 0]):
        df.drop(index=df.index[0], inplace=True)
    N = len(df)
    if math.isnan(df.iloc[N - 1, 0]):
        df.drop(index=df.index[N - 1], inplace=True)

    df.insert(1, "N/S", 0)
    df.insert(3, "E/W", 0)
    df.insert(5, "symbol", "@q")
    df.insert(6, "colour", 0)

    log("Converting coordinates ...")
    N = len(df)
    for x in range(N):
        lat = lat_masu(df.iat[x, 0])
        df.iat[x, 1] = lat[1];  df.iat[x, 0] = lat[0]
        lon = long_masu(df.iat[x, 2])
        df.iat[x, 3] = lon[1];  df.iat[x, 2] = lon[0]
        df.iat[x, 4] = format_name(df.iat[x, 4])

    if auto_symbols:
        log("Assigning symbols ...")
        for x in range(N):
            nm = df.iat[x, 4]
            if any(p in nm[0:3] for p in ['CN ', 'CS ', 'CE ', 'CO ', 'CW ']):
                df.iat[x, 5] = '@s'; df.iat[x, 6] = 2
            if 'ZI ' in nm[0:3]:
                df.iat[x, 5] = '@r'; df.iat[x, 6] = 1
            if 'DI ' in nm[0:3]:
                df.iat[x, 5] = '@r'; df.iat[x, 6] = 1
            if 'V ' in nm[0:3]:
                df.iat[x, 5] = '@z'; df.iat[x, 6] = 3
            if 'R ' in nm[0:3]:
                df.iat[x, 5] = '@z'; df.iat[x, 6] = 1

    dupes = df.duplicated(['name'])
    if dupes.any():
        log(f"WARNING: Duplicate names: {', '.join(df[dupes]['name'].tolist())}")
        log("  GPS will only store the last instance of each duplicate.")

    log(f"Writing  {os.path.basename(output_path)} ...")
    with open(output_path, 'w', encoding='utf-8') as f:
        for x in range(N):
            f.write("$PFEC,GPwpl,"
                    + str(df.iat[x, 0]) + ","
                    + str(df.iat[x, 1]) + ","
                    + str(df.iat[x, 2]) + ","
                    + str(df.iat[x, 3]) + ","
                    + df.iat[x, 4] + ","
                    + str(df.iat[x, 6]) + ","
                    + str(df.iat[x, 5]) + ",A,,,," + "\n")
        f.write("$PFEC,GPxfr,CTL,E <CR><LF> \n")

    log(f"Done -- {N} waypoints converted.")
    return N, df


def read_raw_waypoints(input_path):
    """Return list of (lat, lon, name, symbol_code) in original decimal degrees."""
    raw_xml = pd.read_xml(input_path, encoding='utf-8', parser='lxml')
    df = raw_xml[['lat', 'lon']].copy()
    df.insert(2, "name", raw_xml.iloc[:, 3])

    if math.isnan(df.iloc[0, 0]):
        df.drop(index=df.index[0], inplace=True)
    N = len(df)
    if math.isnan(df.iloc[N - 1, 0]):
        df.drop(index=df.index[N - 1], inplace=True)

    waypoints = []
    for _, row in df.iterrows():
        try:
            lat = float(row['lat'])
            lon = float(row['lon'])
        except (ValueError, TypeError):
            continue
        name = format_name(str(row['name']))
        sym = "@q"
        if any(p in name[0:3] for p in ['CN ', 'CS ', 'CE ', 'CO ', 'CW ']):
            sym = "@s"
        if 'ZI ' in name[0:3] or 'DI ' in name[0:3]:
            sym = "@r"
        if 'V ' in name[0:3]:
            sym = "@z"
        if 'R ' in name[0:3]:
            sym = "@z"
        waypoints.append((lat, lon, name, sym))
    return waypoints


# ── Styled ttk notebook ───────────────────────────────────────────────────────

def _style_notebook(root):
    style = ttk.Style(root)
    style.theme_use("default")
    style.configure("Nav.TNotebook",
                    background=NAVY, borderwidth=0, tabmargins=[0, 0, 0, 0])
    style.configure("Nav.TNotebook.Tab",
                    background=STEEL, foreground=GREY,
                    font=("Georgia", 10, "bold"),
                    padding=[20, 8], borderwidth=0)
    style.map("Nav.TNotebook.Tab",
              background=[("selected", NAVY), ("active", STEEL)],
              foreground=[("selected", ACCENT), ("active", LIGHT)])


# ── Main application ──────────────────────────────────────────────────────────

class MasutecApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Masutec GPX Converter  V2.2")
        self.configure(bg=NAVY)
        self.resizable(True, True)
        self.minsize(780, 640)

        self.input_path  = tk.StringVar()
        self.output_path = tk.StringVar()
        self.auto_sym    = tk.BooleanVar(value=True)
        self.status_var  = tk.StringVar(value="Ready.")
        self._df_result  = None
        self._raw_waypoints  = []
        self._map_markers    = []
        self._filtered_indices = None

        _style_notebook(self)
        self._build_header()
        self._build_tabs()
        self._build_statusbar()
        self._center()

    # ── Chrome ───────────────────────────────────────────────────────────────

    def _build_header(self):
        hdr = tk.Frame(self, bg=NAVY, pady=14, padx=24)
        hdr.pack(fill="x")
        tk.Label(hdr, text="Masutec Converter",
                 font=FONT_TITLE, bg=NAVY, fg=WHITE).pack(side="left", padx=8)
        tk.Label(hdr, text="V2.2",
                 font=FONT_SMALL, bg=NAVY, fg=GREY).pack(side="right", anchor="s", pady=6)
        tk.Frame(self, bg=ACCENT, height=2).pack(fill="x")

    def _build_statusbar(self):
        tk.Frame(self, bg=GREY, height=1).pack(fill="x", side="bottom")
        bar = tk.Frame(self, bg=STEEL, padx=12, pady=5)
        bar.pack(fill="x", side="bottom")
        tk.Label(bar, textvariable=self.status_var,
                 font=FONT_SMALL, bg=STEEL, fg=LIGHT).pack(side="left")

    def _build_tabs(self):
        self.nb = ttk.Notebook(self, style="Nav.TNotebook")
        self.nb.pack(fill="both", expand=True, side = "right")

        t1 = tk.Frame(self.nb, bg=NAVY)
        self.nb.add(t1, text="   CONVERT   ")
        self._build_converter_tab(t1)

        t2 = tk.Frame(self.nb, bg=NAVY)
        self.nb.add(t2, text="   MAP   ")
        self._build_map_tab(t2)

    # ── Tab 1: Converter ─────────────────────────────────────────────────────

    def _build_converter_tab(self, parent):
        body = tk.Frame(parent, bg=NAVY, padx=24, pady=20)
        body.pack(fill="both", expand=True)

        self._file_row(body, "Input GPX File",  self.input_path,
                       self._browse_input, row=0)
        self._file_row(body, "Output TXT File", self.output_path,
                       self._browse_output, row=1)

        opt = tk.Frame(body, bg=NAVY, pady=8)
        opt.grid(row=2, column=0, columnspan=3, sticky="w")
        tk.Checkbutton(opt,
                       text="Auto-assign buoy symbols",
                       variable=self.auto_sym,
                       bg=NAVY, fg=LIGHT, selectcolor=STEEL,
                       activebackground=NAVY, activeforeground=ACCENT,
                       font=FONT_LABEL, cursor="hand2").pack(side="left")
        tk.Button(opt, text=" ? ",
                  font=("Georgia", 9, "bold"),
                  bg=STEEL, fg=ACCENT,
                  activebackground=ACCENT, activeforeground=NAVY,
                  relief="flat", padx=4, pady=1,
                  cursor="hand2",
                  command=self._show_symbol_help).pack(side="left", padx=8)

        btn_row = tk.Frame(body, bg=NAVY, pady=4)
        btn_row.grid(row=3, column=0, columnspan=3)

        self.btn_convert = tk.Button(
            btn_row, text="  CONVERT  ",
            font=("Georgia", 12, "bold"),
            bg=ACCENT, fg=NAVY, activebackground=LIGHT,
            activeforeground=NAVY, relief="flat", padx=24, pady=10,
            cursor="hand2", command=self._run_convert)
        self.btn_convert.pack(side="left", padx=8)

        self.btn_preview = tk.Button(
            btn_row, text=" View Preview ",
            font=FONT_BTN, bg=STEEL, fg=LIGHT,
            activebackground=GREY, activeforeground=WHITE,
            relief="flat", padx=16, pady=10,
            cursor="hand2", state="disabled",
            command=self._show_preview)
        self.btn_preview.pack(side="left", padx=4)

        self.btn_goto_map = tk.Button(
            btn_row, text=" View on Map ",
            font=FONT_BTN, bg=STEEL, fg=LIGHT,
            activebackground=GREY, activeforeground=WHITE,
            relief="flat", padx=16, pady=10,
            cursor="hand2", state="disabled",
            command=self._goto_map)
        self.btn_goto_map.pack(side="left", padx=4)

        log_frame = tk.Frame(body, bg=NAVY, pady=8)
        log_frame.grid(row=4, column=0, columnspan=3, sticky="ew")
        tk.Label(log_frame, text="LOG", font=("Courier New", 8, "bold"),
                 bg=NAVY, fg=GREY).pack(anchor="w")

        self.log_text = tk.Text(
            log_frame, height=10, width=74,
            bg=STEEL, fg=LIGHT, insertbackground=ACCENT,
            font=FONT_MONO, relief="flat", wrap="word",
            state="disabled", highlightthickness=1,
            highlightbackground=GREY)
        sb = tk.Scrollbar(log_frame, command=self.log_text.yview,
                          bg=GREY, troughcolor=NAVY)
        self.log_text.configure(yscrollcommand=sb.set)
        self.log_text.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")



    # ── Tab 2: Map ────────────────────────────────────────────────────────────

    def _build_map_tab(self, parent):
        if not MAP_AVAILABLE:
            msg = tk.Frame(parent, bg=NAVY)
            msg.pack(fill="both", expand=True)
            tk.Label(
                msg,
                text=(
                    "tkintermapview is not installed.\n\n"
                    "Run:  pip install tkintermapview\n\n"
                    "then restart the application."
                ),
                font=("Georgia", 13), bg=NAVY, fg=WARN, justify="center"
            ).pack(expand=True)
            return

        # ── toolbar ──
        toolbar = tk.Frame(parent, bg=STEEL, padx=12, pady=8)
        toolbar.pack(fill="x")

        tk.Label(toolbar, text="WAYPOINT MAP  |  OpenStreetMap",
                 font=("Georgia", 11, "bold"), bg=STEEL, fg=ACCENT).pack(side="left")

        tk.Button(toolbar, text="  Load GPX  ",
                  font=FONT_BTN, bg=ACCENT, fg=NAVY,
                  activebackground=LIGHT, activeforeground=NAVY,
                  relief="flat", padx=10, pady=4, cursor="hand2",
                  command=self._map_load_and_plot).pack(side="left", padx=16)

        tk.Button(toolbar, text="Clear",
                  font=FONT_BTN, bg=GREY, fg=WHITE,
                  activebackground=STEEL, relief="flat",
                  padx=8, pady=4, cursor="hand2",
                  command=self._map_clear).pack(side="left", padx=2)

        # zoom
        tk.Button(toolbar, text=" + ", font=("Courier New", 12, "bold"),
                  bg=STEEL, fg=LIGHT, activebackground=GREY,
                  relief="flat", padx=6, pady=2, cursor="hand2",
                  command=lambda: self._map_zoom(+1)).pack(side="right", padx=2)
        tk.Button(toolbar, text=" - ", font=("Courier New", 12, "bold"),
                  bg=STEEL, fg=LIGHT, activebackground=GREY,
                  relief="flat", padx=6, pady=2, cursor="hand2",
                  command=lambda: self._map_zoom(-1)).pack(side="right", padx=2)
        tk.Label(toolbar, text="zoom:", font=FONT_SMALL,
                 bg=STEEL, fg=GREY).pack(side="right", padx=4)

        # ── map + side panel ──
        content = tk.Frame(parent, bg=NAVY)
        content.pack(fill="both", expand=True)

        self.map_widget = tkintermapview.TkinterMapView(
            content, width=640, height=520, corner_radius=0)
        self.map_widget.pack(side="left", fill="both", expand=True)

        # OpenStreetMap tiles
        self.map_widget.set_tile_server(
            "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
            max_zoom=19)
        self.map_widget.set_position(30, -15)
        self.map_widget.set_zoom(3)

        # ── side panel ──
        side = tk.Frame(content, bg=STEEL, width=200)
        side.pack(side="right", fill="y")
        side.pack_propagate(False)

        tk.Label(side, text="WAYPOINTS", font=("Courier New", 8, "bold"),
                 bg=STEEL, fg=GREY).pack(anchor="w", padx=10, pady=(10, 2))

        self.wpt_count_var = tk.StringVar(value="No waypoints loaded")
        tk.Label(side, textvariable=self.wpt_count_var,
                 font=("Georgia", 9), bg=STEEL, fg=ACCENT,
                 wraplength=180).pack(anchor="w", padx=10)

        # filter box
        tk.Label(side, text="Search:", font=FONT_SMALL,
                 bg=STEEL, fg=GREY).pack(anchor="w", padx=10, pady=(10, 0))
        self.filter_var = tk.StringVar()
        self.filter_var.trace_add("write", self._filter_list)
        tk.Entry(side, textvariable=self.filter_var, width=20,
                 bg=NAVY, fg=WHITE, insertbackground=ACCENT,
                 relief="flat", font=FONT_MONO,
                 highlightthickness=1, highlightbackground=GREY
                 ).pack(padx=10, pady=(2, 6), fill="x")

        list_frame = tk.Frame(side, bg=STEEL)
        list_frame.pack(fill="both", expand=True, padx=6, pady=4)

        self.wpt_listbox = tk.Listbox(
            list_frame, bg=NAVY, fg=LIGHT,
            selectbackground=ACCENT, selectforeground=NAVY,
            font=FONT_MONO, relief="flat",
            activestyle="none", highlightthickness=0, borderwidth=0)
        lsb = tk.Scrollbar(list_frame, command=self.wpt_listbox.yview,
                           bg=GREY, troughcolor=NAVY)
        self.wpt_listbox.configure(yscrollcommand=lsb.set)
        self.wpt_listbox.pack(side="left", fill="both", expand=True)
        lsb.pack(side="right", fill="y")
        self.wpt_listbox.bind("<<ListboxSelect>>", self._on_wpt_select)

        # info label (shows coords of selected waypoint)
        self.wpt_info_var = tk.StringVar(value="")
        tk.Label(side, textvariable=self.wpt_info_var,
                 font=("Courier New", 7), bg=STEEL, fg=GREY,
                 wraplength=180, justify="left").pack(anchor="w", padx=10, pady=2)

        # legend
        leg = tk.Frame(side, bg=STEEL, pady=6)
        leg.pack(fill="x", padx=10)
        tk.Label(leg, text="LEGEND", font=("Courier New", 7, "bold"),
                 bg=STEEL, fg=GREY).pack(anchor="w")
        for sym, col, lbl in [("@q", ACCENT, "Default"),
                              ("@s", WARN, "Cardinal"),
                              ("@r", RED, "Danger / Zone"),
                              ("@z", GREEN, "Lateral")]:
            row = tk.Frame(leg, bg=STEEL)
            row.pack(anchor="w", pady=1)
            tk.Label(row, text="●", font=("Georgia", 10),
                     bg=STEEL, fg=col).pack(side="left")
            tk.Label(row, text=f" {lbl}", font=FONT_SMALL,
                     bg=STEEL, fg=LIGHT).pack(side="left")

    # ── Map actions ──────────────────────────────────────────────────────────

    def _map_load_and_plot(self):
        path = filedialog.askopenfilename(
            title="Select GPX file to map",
            filetypes=[("GPX files", "*.gpx"), ("All files", "*.*")])
        if not path:
            return
        try:
            wpts = read_raw_waypoints(path)
        except Exception as e:
            messagebox.showerror("Load error", str(e))
            return
        self._plot_waypoints(wpts)

    def _plot_waypoints(self, waypoints):
        if not MAP_AVAILABLE:
            return
        self._map_clear()
        self._raw_waypoints = waypoints
        self._filtered_indices = None

        self.wpt_listbox.delete(0, "end")
        self.wpt_count_var.set(f"{len(waypoints)} waypoints loaded")

        lats, lons = [], []
        for lat, lon, name, sym in waypoints:
            col = SYMBOL_COLOUR.get(sym, ACCENT)
            marker = self.map_widget.set_marker(
                lat, lon, text=name,
                marker_color_circle=col,
                marker_color_outside=col,
                text_color=WHITE,
                font=("Courier New", 7, "bold"),
            )
            self._map_markers.append(marker)
            lats.append(lat); lons.append(lon)
            self.wpt_listbox.insert("end", name)
            self.wpt_listbox.itemconfig(self.wpt_listbox.size() - 1, fg=col)

        # auto-fit zoom
        if lats:
            clat = (min(lats) + max(lats)) / 2
            clon = (min(lons) + max(lons)) / 2
            self.map_widget.set_position(clat, clon)
            span = max(max(lats) - min(lats), max(lons) - min(lons))
            if   span > 40:  zoom = 3
            elif span > 15:  zoom = 4
            elif span > 6:   zoom = 6
            elif span > 2:   zoom = 8
            elif span > 0.5: zoom = 10
            else:            zoom = 12
            self.map_widget.set_zoom(zoom)

    def _map_clear(self):
        for m in self._map_markers:
            m.delete()
        self._map_markers.clear()
        if hasattr(self, "wpt_listbox"):
            self.wpt_listbox.delete(0, "end")
            self.wpt_count_var.set("No waypoints loaded")
            self.wpt_info_var.set("")

    def _map_zoom(self, delta):
        try:
            z = self.map_widget.zoom + delta
            self.map_widget.set_zoom(max(1, min(19, z)))
        except Exception:
            pass

    def _on_wpt_select(self, _event):
        sel = self.wpt_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        real_idx = (self._filtered_indices[idx]
                    if self._filtered_indices is not None else idx)
        if real_idx < len(self._raw_waypoints):
            lat, lon, name, sym = self._raw_waypoints[real_idx]
            self.map_widget.set_position(lat, lon)
            self.map_widget.set_zoom(12)
            self.wpt_info_var.set(
                f"{name}\nLat: {lat:.5f}\nLon: {lon:.5f}\nSym: {sym}")

    def _filter_list(self, *_):
        query = self.filter_var.get().upper()
        self.wpt_listbox.delete(0, "end")
        self._filtered_indices = [] if query else None
        for i, (lat, lon, name, sym) in enumerate(self._raw_waypoints):
            if not query or query in name:
                col = SYMBOL_COLOUR.get(sym, ACCENT)
                self.wpt_listbox.insert("end", name)
                self.wpt_listbox.itemconfig(
                    self.wpt_listbox.size() - 1, fg=col)
                if query:
                    self._filtered_indices.append(i)

    def _goto_map(self):
        self.nb.select(1)
        if self._raw_waypoints:
            self._plot_waypoints(self._raw_waypoints)

    # ── Symbol help dialog ────────────────────────────────────────────────────

    def _show_symbol_help(self):
        win = tk.Toplevel(self)
        win.title("Auto-assign Symbol Help")
        win.configure(bg=NAVY)
        win.resizable(False, False)
        win.grab_set()

        tk.Label(win, text="Auto-Assign Buoy Symbols",
                 font=("Georgia", 13, "bold"), bg=NAVY, fg=WHITE
                 ).pack(anchor="w", padx=20, pady=(18, 4))
        tk.Label(win,
                 text="When enabled, waypoint names are inspected and a Masutec " 
                      "symbol + colour code is assigned automatically based on \n"
                      "the first characters of the name followed by a space. "
                    "Eg. 'CN Stags' will create a yellow symbol on the chart \n"
                    "Note: Names longer than 8 characters are shortened before conversion. "
                    "Prefixes are checked against the first 3 characters (upper-cased)",
                 font=("Georgia", 9), bg=NAVY, fg=GREY, justify="left"
                 ).pack(anchor="w", padx=20, pady=(0, 12))

        tk.Frame(win, bg=ACCENT, height=1).pack(fill="x", padx=20, pady=(0, 12))

        rules = [
            ("",WARN,     "Cardinal Mark",        "'CN ','CS ','CE ','CO '",
             "Yellow diamond"),
            ("",RED,      "Isolated Danger",      "'DI '",
             "Red circle"),
            ("",RED,      "Restricted Zone",      "'ZI '",
             "Red skull "),
            ("",GREEN,    "Starboard Lateral",    "'V '",
             "Green flag  -  Keep to starboard"),
            ("","#ff6b6b", "Port Lateral",       "'R '",
             "Red flag"),
            ("","#000000",   "Default Waypoint",     "(anything else)",
             "Black Cicle"),
        ]

        for sym, col, label, prefix, desc in rules:
            row_frame = tk.Frame(win, bg=STEEL, pady=8, padx=14)
            row_frame.pack(fill="x", padx=20, pady=3)
            tk.Frame(row_frame, bg=col, width=10).pack(side="left", fill="y", padx=(0, 10))
            info = tk.Frame(row_frame, bg=STEEL)
            info.pack(side="left", fill="both", expand=True)
            top_line = tk.Frame(info, bg=STEEL)
            top_line.pack(anchor="w")
            tk.Label(top_line, text=label,
                     font=("Georgia", 10, "bold"), bg=STEEL, fg=WHITE).pack(side="left")
            tk.Label(top_line, text=f"  {sym}",
                     font=FONT_MONO, bg=STEEL, fg=col).pack(side="left")
            tk.Label(info, text=f"Name prefix:  {prefix}",
                     font=("Courier New", 8), bg=STEEL, fg=LIGHT).pack(anchor="w")
            tk.Label(info, text=desc,
                     font=("Georgia", 8), bg=STEEL, fg=GREY).pack(anchor="w")

        tk.Frame(win, bg=ACCENT, height=1).pack(fill="x", padx=20, pady=(12, 0))
        note = tk.Frame(win, bg=NAVY, padx=20, pady=10)
        note.pack(fill="x")
        tk.Label(note,
                 text="",
                 font=("Georgia", 8), bg=NAVY, fg=GREY, justify="left"
                 ).pack(anchor="w")

        tk.Button(win, text="  Close  ",
                  font=FONT_BTN, bg=ACCENT, fg=NAVY,
                  activebackground=LIGHT, activeforeground=NAVY,
                  relief="flat", padx=16, pady=6, cursor="hand2",
                  command=win.destroy).pack(pady=(4, 16))

    # ── Converter helpers ─────────────────────────────────────────────────────

    def _file_row(self, parent, label, var, cmd, row):
        tk.Label(parent, text=label, font=FONT_LABEL,
                 bg=NAVY, fg=LIGHT, width=16, anchor="w"
                 ).grid(row=row, column=0, sticky="w", pady=6)
        tk.Entry(parent, textvariable=var, width=44,
                 bg=STEEL, fg=WHITE, insertbackground=ACCENT,
                 relief="flat", font=FONT_MONO,
                 highlightthickness=1, highlightbackground=GREY,
                 highlightcolor=ACCENT
                 ).grid(row=row, column=1, padx=8, pady=6)
        tk.Button(parent, text="Browse", command=cmd,
                  bg=GREY, fg=WHITE, relief="flat", font=FONT_SMALL,
                  activebackground=ACCENT, activeforeground=NAVY,
                  cursor="hand2", padx=8).grid(row=row, column=2)

    def _browse_input(self):
        path = filedialog.askopenfilename(
            title="Select GPX file",
            filetypes=[("GPX files", "*.gpx"), ("All files", "*.*")])
        if path:
            self.input_path.set(path)
            self.output_path.set(os.path.splitext(path)[0] + ".txt")
            try:
                self._raw_waypoints = read_raw_waypoints(path)
                self.btn_goto_map.configure(state="normal")
            except Exception:
                pass

    def _browse_output(self):
        path = filedialog.asksaveasfilename(
            title="Save output as",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if path:
            self.output_path.set(path)

    def _log(self, msg):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", msg + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")
        self.update_idletasks()

    def _clear_log(self):
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    def _run_convert(self):
        inp = self.input_path.get().strip()
        out = self.output_path.get().strip()
        if not inp:
            messagebox.showwarning("Missing input", "Please select a GPX file.")
            return
        if not out:
            messagebox.showwarning("Missing output",
                                   "Please specify an output file path.")
            return
        if not os.path.isfile(inp):
            messagebox.showerror("File not found", f"Cannot find:\n{inp}")
            return

        self.btn_convert.configure(state="disabled", text="  Converting...  ")
        self.btn_preview.configure(state="disabled")
        self.btn_goto_map.configure(state="disabled")
        self.status_var.set("Converting...")
        self._clear_log()

        def worker():
            try:
                n, df = convert_gpx(inp, out,
                                    auto_symbols=self.auto_sym.get(),
                                    log_cb=self._log)
                self._df_result = df
                self._raw_waypoints = read_raw_waypoints(inp)
                self.after(0, lambda: self._on_done(n))
            except Exception as e:
                self.after(0, lambda: self._on_error(str(e)))

        threading.Thread(target=worker, daemon=True).start()

    def _on_done(self, n):
        self.btn_convert.configure(state="normal", text="  CONVERT  ")
        self.btn_preview.configure(state="normal")
        self.btn_goto_map.configure(state="normal")
        self.status_var.set(
            f"Done  --  {n} waypoints written to "
            f"{os.path.basename(self.output_path.get())}")

    def _on_error(self, msg):
        self.btn_convert.configure(state="normal", text="  CONVERT  ")
        self.status_var.set("Error during conversion.")
        self._log(f"\nERROR: {msg}")
        messagebox.showerror("Conversion error", msg)

    def _show_preview(self):
        if self._df_result is None:
            return
        win = tk.Toplevel(self)
        win.title("Output Preview")
        win.configure(bg=NAVY)
        try:
            with open(self.output_path.get(), 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except Exception as e:
            messagebox.showerror("Preview error", str(e), parent=win)
            return
        tk.Label(win, text="OUTPUT PREVIEW  (first 40 lines)",
                 font=("Courier New", 9, "bold"),
                 bg=NAVY, fg=GREY).pack(anchor="w", padx=12, pady=(10, 2))
        txt = tk.Text(win, bg=STEEL, fg=LIGHT, font=FONT_MONO,
                      relief="flat", width=78, height=28,
                      highlightthickness=1, highlightbackground=GREY)
        txt.pack(padx=12, pady=(0, 12))
        for line in lines[:40]:
            txt.insert("end", line)
        if len(lines) > 40:
            txt.insert("end", f"\n... and {len(lines) - 40} more lines.")
        txt.configure(state="disabled")

    # ── Window helpers ────────────────────────────────────────────────────────

    def _center(self):
        self.update_idletasks()
        w = self.winfo_width()
        h = self.winfo_height()
        x = (self.winfo_screenwidth()  - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"+{x}+{y}")


if __name__ == "__main__":
    app = MasutecApp()
    app.mainloop()
