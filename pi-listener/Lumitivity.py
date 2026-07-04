import customtkinter as ctk # Import for GUI
import socket # Import for networking to desktop
import threading # Import for background listening for calls from desktop
import time
import json


class Dashboard(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Lumitivity")
        ctk.set_appearance_mode("dark")
        self.configure(fg_color="#0D0D0D")
        self.geometry("1024x600")
        #self.overrideredirect(True)
        #self.geometry(f"{self.winfo_screenwidth()}x{self.winfo_screenheight()}+0+0")
        self.bind("<Escape>", lambda e: self.destroy())

        # Socket creation for networking to desktop
        self.socket = socket.socket(
                socket.AF_INET,
                socket.SOCK_DGRAM
                )
        self.socket.bind(("", 8080))

        # WLED variables
        self.wled_ip = ["192.168.4.74", "192.168.4.40"] # WLED Controller name
        self.is_on = False # Variable that keeps track of WLED power state
        self.set_on = {"on": True} # JSON data, Sets WLED state to 'On'
        self.set_off = {"on": False} # JSON data, Sets WLED state to 'Off'

        # Mode Variables
        self.current_mode = "Idle" # Keeps track of current mode
        self.work_seconds = 0 # Work mode timer, keeping track of # seconds spent in work mode
        self.entertainment_duration = 5 # Time allotment for entertainment mode
        self.entertainment_seconds = self.entertainment_duration # Entertainment mode timer, counting down

        self.last_flash_time = 0
        self.flash_cooldown = 0.1 # Seconds

        self.custom_color = [255, 255, 255]
        self.custom_brightness = 128
        self.custom_fx = 0

        self.mode_colors = {
            "Work":          [0,   255, 0  ],
            "Entertainment": [255, 255, 0  ],
            "Music":         [0,   255, 255],
            "Idle":          [255, 255, 255],
        }
        self._themes = {
            "Default":  {"btn_fg": "#1F6AA5", "btn_hover": "#144870",
                         "sidebar": "#13132A", "backdrop": "#07071A",
                         "overlay": "#16163A", "card": "#1E1E45", "divider": "#2A2A55"},
            "Midnight": {"btn_fg": "#2A2A6A", "btn_hover": "#3A3A8A",
                         "sidebar": "#0A0A1A", "backdrop": "#04040E",
                         "overlay": "#0F0F28", "card": "#161635", "divider": "#202050"},
            "Slate":    {"btn_fg": "#383838", "btn_hover": "#484848",
                         "sidebar": "#111111", "backdrop": "#050505",
                         "overlay": "#1A1A1A", "card": "#222222", "divider": "#333333"},
            "Forest":   {"btn_fg": "#1A4A2A", "btn_hover": "#2A6A3A",
                         "sidebar": "#061208", "backdrop": "#020804",
                         "overlay": "#0A1A0C", "card": "#101E12", "divider": "#1A3020"},
            "Ember":    {"btn_fg": "#6A2A1A", "btn_hover": "#8A3A2A",
                         "sidebar": "#140604", "backdrop": "#080200",
                         "overlay": "#1C0804", "card": "#240C06", "divider": "#361410"},
        }
        self._theme = self._themes["Default"]

        # PERF: CTkFont objects are not free — each one is a Tk font resource.
        # The old code built a new CTkFont for nearly every widget (~30+ objects).
        # Build the handful of styles once and share them.
        self._fonts = {
            "mode":    ctk.CTkFont(size=22, weight="bold"),
            "sidebar": ctk.CTkFont(size=11, weight="bold"),
            "title":   ctk.CTkFont(size=20, weight="bold"),
            "body":    ctk.CTkFont(size=14),
            "body_b":  ctk.CTkFont(size=14, weight="bold"),
            "small":   ctk.CTkFont(size=13),
            "small_b": ctk.CTkFont(size=13, weight="bold"),
            "btn":     ctk.CTkFont(size=15, weight="bold"),
            "close":   ctk.CTkFont(size=15),
            "chip":    ctk.CTkFont(size=12, weight="bold"),
        }

        # PERF: panel cache. Panels are built ONCE on first open, then reused.
        # Creating a CustomTkinter widget is expensive (every widget is a canvas
        # that Python redraws with anti-aliased corners), so destroy-and-rebuild
        # on every open is what made panels slow to appear.
        self._backdrop = None       # shared full-screen dim layer, built once
        self._panels = {}           # name -> cached panel frame
        self._panel_on_show = {}    # name -> callback to refresh dynamic state

        # Build UI
        self._active_btn = None
        self._build_layout()

        # Start background thread and timer loop
        threading.Thread(target=self.receive_data, daemon=True).start()
        self.main_loop()

    # -----------------------------------------------------------------------------------------------------------
    # Layout
    # -----------------------------------------------------------------------------------------------------------

    def _build_layout(self):
        # Root grid: mode area takes all spare space, sidebar is fixed width
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, minsize=130)

        # -- 2x2 mode button grid -------------------------------------------------------------------------------
        mode_frame = ctk.CTkFrame(self, fg_color="#0D0D0D", corner_radius=0)
        mode_frame.grid(row=0, column=0, sticky="nsew")
        mode_frame.grid_rowconfigure((0, 1), weight=1, uniform="col")
        mode_frame.grid_columnconfigure((0, 1), weight=1, uniform="col")

        GAP = 3 # px gap between buttons, creates the grid-line effect

        # Work Button
        self._btn_work = ctk.CTkButton(
            mode_frame,
            text="WORK\n00:00:00",
            font=self._fonts["mode"],
            command=self.set_mode_work,
            corner_radius=6
            )
        self._btn_work.grid(row=0, column=0, sticky="nsew", padx=(0, GAP), pady=(0, GAP))

        # Entertainment Button
        self._btn_entertainment = ctk.CTkButton(
            mode_frame,
            text=f"ENTERTAINMENT\n{self.format_time(self.entertainment_seconds)}",
            font=self._fonts["mode"],
            command=self.set_mode_entertainment,
            corner_radius=6
            )
        self._btn_entertainment.grid(row=0, column=1, sticky="nsew", padx=(GAP, 0), pady=(0, GAP))

        # Music Button
        self._btn_music = ctk.CTkButton(
            mode_frame,
            text="MUSIC",
            font=self._fonts["mode"],
            command=self.set_mode_music,
            corner_radius=6
            )
        self._btn_music.grid(row=1, column=0, sticky="nsew", padx=(0, GAP), pady=(GAP, 0))

        # Custom Button
        self._btn_custom = ctk.CTkButton(
            mode_frame,
            text="CUSTOM",
            font=self._fonts["mode"],
            command=self.set_mode_custom,
            corner_radius=6
            )
        self._btn_custom.grid(row=1, column=1, sticky="nsew", padx=(GAP, 0), pady=(GAP, 0))

        # -- Sidebar --------------------------------------------------------------------------------------------

        self._sidebar = ctk.CTkFrame(self, fg_color=self._theme["sidebar"], corner_radius=0, width=130)
        self._sidebar.grid(row=0, column=1, sticky="nsew")
        self._sidebar.grid_propagate(False)
        self._sidebar.grid_rowconfigure((0, 1, 2, 3), weight=1)
        self._sidebar.grid_columnconfigure(0, weight=1)

        self._sidebar_btns = []
        for row, (text, cmd) in enumerate([
            ("TIMERS", self.show_timers_panel),
            ("CUSTOM\nMODE", self.show_custom_panel),
            ("SETTINGS", self.show_settings_panel),
            ("EXIT", self.destroy)
        ]):
            btn = ctk.CTkButton(
                self._sidebar, text=text,
                font=self._fonts["sidebar"],
                command=cmd,
                fg_color=self._theme["btn_fg"], hover_color=self._theme["btn_hover"],
                text_color="#AAAACC", corner_radius=8, height=80
            )
            btn.grid(row=row, column=0, padx=10, pady=6, sticky="ew")
            self._sidebar_btns.append(btn)

    # -- Overlay System -----------------------------------------------------------------------------------------
    # PERF: the old system destroyed the whole overlay and rebuilt every widget
    # from scratch on each open. Now: one shared backdrop + one cached frame per
    # panel. First open pays the build cost; every open after that is just a
    # place() call, which is effectively instant. Dynamic values (timer text,
    # custom-mode sliders) are refreshed by a per-panel on_show callback.

    def _open_panel(self, name, builder):
        # Shared dim backdrop, created lazily on first use
        if self._backdrop is None:
            self._backdrop = ctk.CTkFrame(self, fg_color=self._theme["backdrop"], corner_radius=0)
            # Clicking the backdrop closes the overlay. Tk bindings do not fire
            # for clicks on child widgets, so clicks inside the panel are safe.
            self._backdrop.bind("<Button-1>", lambda e: self._close_overlay())

        # Build the panel once, then reuse it forever (until a theme change)
        if name not in self._panels:
            panel = ctk.CTkFrame(self._backdrop,
                                 fg_color=self._theme["overlay"],
                                 corner_radius=14,
                                 width=740,
                                 height=530)
            panel.pack_propagate(False)
            builder(panel)
            self._panels[name] = panel

        # Hide any other cached panel, refresh this one's dynamic state, show it
        for other_name, other in self._panels.items():
            if other_name != name:
                other.place_forget()
        on_show = self._panel_on_show.get(name)
        if on_show:
            on_show()
        self._backdrop.place(x=0, y=0, relwidth=1, relheight=1)
        self._panels[name].place(relx=0.5, rely=0.5, anchor="center")

    def _close_overlay(self):
        # place_forget hides without destroying — the widgets stay cached
        if self._backdrop:
            self._backdrop.place_forget()

    def _invalidate_panels(self):
        # Called on theme change: cached panels hold old theme colors, so drop
        # them and let them rebuild on next open. Theme changes are rare;
        # panel opens are frequent — right side of the trade.
        for panel in self._panels.values():
            panel.destroy()
        self._panels.clear()
        self._panel_on_show.clear()
        if self._backdrop:
            self._backdrop.destroy()
            self._backdrop = None

    def _panel_header(self, panel, title, close_fn=None):
        if close_fn is None:
            close_fn = self._close_overlay
        header = ctk.CTkFrame(panel, fg_color="transparent")
        header.pack(fill="x", padx=24, pady=(20, 0))
        ctk.CTkLabel(header, text=title,
                    font=self._fonts["title"],
                    text_color="#FFFFFF").pack(side="left")
        ctk.CTkButton(header, text="x", width=38, height=38,
                    fg_color=self._theme["btn_fg"], hover_color=self._theme["btn_hover"],
                    font=self._fonts["close"],
                    command=close_fn).pack(side="right")
        ctk.CTkFrame(panel, fg_color=self._theme["divider"], height=1).pack(fill="x", padx=24, pady=(12, 0))

    def _section_label(self, parent, text):
        ctk.CTkLabel(parent, text=text,
                    font=self._fonts["body_b"],
        text_color="#7777AA").pack(anchor="w", pady=(12, 4))

    def _card(self, parent):
        f = ctk.CTkFrame(parent, fg_color=self._theme["card"], corner_radius=8)
        f.pack(fill="x", pady=(0, 6))
        return f

    #-- Timers Panel --------------------------------------------------------------------------------------------

    def show_timers_panel(self):
        self._open_panel("timers", self._build_timers)

    def _build_timers(self, panel):
        self._panel_header(panel, "TIMERS")
        # PERF: CTkScrollableFrame is the single slowest CTk widget to build
        # (it nests a canvas + frame + scrollbar and re-layouts constantly).
        # This content fits in the 740x530 panel, so a plain frame does the job.
        content = ctk.CTkFrame(panel, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=24, pady=16)

        # Work Timer
        self._section_label(content, "Work Timer")
        wr = self._card(content)
        # Labels stored on self so main_loop / on_show can refresh them
        self._timers_work_label = ctk.CTkLabel(wr, text="",
                                font=self._fonts["body"], text_color="#CCCCEE")
        self._timers_work_label.pack(side="left", padx=16, pady=14)
        ctk.CTkButton(wr, text="Reset", width=100,
                    command=self._reset_work
                    ).pack(side="right", padx=12, pady=10)

        # Entertainment Timer
        self._section_label(content, "Entertainment Timer")
        er = self._card(content)
        self._timers_ent_label = ctk.CTkLabel(er, text="",
                                font=self._fonts["body"], text_color="#CCCCEE")
        self._timers_ent_label.pack(side="left", padx=16, pady=14)
        ctk.CTkButton(er, text="Reset", width=100,
                    command=self._reset_entertainment
                    ).pack(side="right", padx=12, pady=10)

        # Duration Presets
        self._section_label(content, "Set Entertainment Duration")
        dur = self._card(content)
        for label, secs in [("1 hr", 3600), ("2 hr", 7200), ("4 hr", 14400), ("8 hr", 28800)]:
            ctk.CTkButton(dur, text=label, width=90, height=38,
                        command=lambda s=secs: self._set_entertainment_duration(s)
                        ).pack(side="left", padx=8, pady=10)

        # Event Zones
        self._section_label(content, "Event Zones")
        ez = self._card(content)
        info = ctk.CTkFrame(ez, fg_color="transparent")
        info.pack(fill="x", padx=16, pady=12)
        ctk.CTkLabel(info, text="End of Work -> Flash green for 10s, return to Work",
                    font=self._fonts["small"], text_color="#8888AA").pack(anchor="w")
        ctk.CTkLabel(info, text="End of Entertainment -> Flash red for 5s, switch to Idle",
                    font=self._fonts["small"], text_color="#8888AA").pack(anchor="w", pady=(4, 0))

        # Refresh the two dynamic labels every time the panel is shown
        self._panel_on_show["timers"] = self._refresh_timer_labels

    def _refresh_timer_labels(self):
        self._timers_work_label.configure(text=f"Elapsed: {self.format_time(self.work_seconds)}")
        self._timers_ent_label.configure(text=f"Remaining: {self.format_time(self.entertainment_seconds)}")

    def _timers_panel_visible(self):
        panel = self._panels.get("timers")
        return panel is not None and panel.winfo_ismapped()

    def _reset_work(self):
        self.work_seconds = 0
        self._btn_work.configure(text=f"WORK\n{self.format_time(0)}")
        self._refresh_timer_labels()

    def _reset_entertainment(self):
        self.entertainment_seconds = self.entertainment_duration
        self._btn_entertainment.configure(
            text=f"ENTERTAINMENT\n{self.format_time(self.entertainment_seconds)}")
        self._refresh_timer_labels()

    def _set_entertainment_duration(self, secs):
        self.entertainment_duration = secs
        self.entertainment_seconds = secs
        self._btn_entertainment.configure(
            text=f"ENTERTAINMENT\n{self.format_time(secs)}")
        self._refresh_timer_labels()

    #-- Custom Panel --------------------------------------------------------------------------------------------

    def show_custom_panel(self):
        self._open_panel("custom", self._build_custom)

    def _build_custom(self, panel):
        # Vars live on self; widgets are built once. on_show re-seeds the vars
        # from current state and snapshots the previous values for revert.
        self._cp_r   = ctk.IntVar(value=self.custom_color[0])
        self._cp_g   = ctk.IntVar(value=self.custom_color[1])
        self._cp_b   = ctk.IntVar(value=self.custom_color[2])
        self._cp_bri = ctk.IntVar(value=self.custom_brightness)
        self._cp_effects = {
            "Solid": 0, "Blink": 1, "Breathe": 2,
            "Color Wipe": 3, "Chase": 22, "Rainbow": 9, "Twinkle": 7
        }
        self._cp_fx = ctk.StringVar(value="Solid")
        self._cp_prev = {}  # snapshot taken on show, used by revert

        def preview(*_):
            self.sync_wleds({
                "on": True, "tt": 0,
                "bri": self._cp_bri.get(),
                "seg": [{"col": [[self._cp_r.get(), self._cp_g.get(), self._cp_b.get()]],
                         "fx": self._cp_effects[self._cp_fx.get()]}]
            })

        self._panel_header(panel, "CUSTOM MODE SETTINGS", close_fn=self._cp_revert)
        content = ctk.CTkFrame(panel, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=24, pady=16)
        self._section_label(content, "Color")
        for label, var, accent in [
            ("R", self._cp_r, "#FF5555"),
            ("G", self._cp_g, "#55FF55"),
            ("B", self._cp_b, "#5599FF")
        ]:
            row = ctk.CTkFrame(content, fg_color="transparent")
            row.pack(fill="x", pady=3)
            ctk.CTkLabel(row, text=label, width=22,
                         font=self._fonts["body_b"],
                         text_color=accent).pack(side="left")
            ctk.CTkSlider(row, from_=0, to=255, variable=var,
                          button_color=accent, progress_color=accent,
                          command=preview).pack(side="left", fill="x", expand=True, padx=10)
            ctk.CTkLabel(row, textvariable=var, width=36,
                         font=self._fonts["small"], text_color="#FFFFFF").pack(side="left")
        self._section_label(content, "Brightness")
        bri_row = ctk.CTkFrame(content, fg_color="transparent")
        bri_row.pack(fill="x", pady=3)
        ctk.CTkSlider(bri_row, from_=1, to=255, variable=self._cp_bri,
                      command=preview).pack(side="left", fill="x", expand=True, padx=(0, 10))
        ctk.CTkLabel(bri_row, textvariable=self._cp_bri, width=36,
                     font=self._fonts["small"], text_color="#FFFFFF").pack(side="left")
        self._section_label(content, "Effect")
        ctk.CTkOptionMenu(content, values=list(self._cp_effects.keys()), variable=self._cp_fx,
                          fg_color="#252550", command=preview).pack(anchor="w", pady=3)

        btn_row = ctk.CTkFrame(content, fg_color="transparent")
        btn_row.pack(fill="x", pady=(20, 0))
        ctk.CTkButton(btn_row, text="Cancel", height=46, width=120,
                      fg_color="#2A2A55", hover_color="#3A3A77",
                      font=self._fonts["btn"],
                      command=self._cp_revert).pack(side="left")
        ctk.CTkButton(btn_row, text="Save", height=46,
                      font=self._fonts["btn"],
                      command=self._cp_save).pack(side="left", fill="x", expand=True, padx=(10, 0))

        self._panel_on_show["custom"] = self._cp_on_show

    def _cp_on_show(self):
        # Seed widgets from current state (setting a Var does not fire the
        # slider's command callback, so this won't spam preview packets)
        self._cp_r.set(self.custom_color[0])
        self._cp_g.set(self.custom_color[1])
        self._cp_b.set(self.custom_color[2])
        self._cp_bri.set(self.custom_brightness)
        current = next((k for k, v in self._cp_effects.items() if v == self.custom_fx), "Solid")
        self._cp_fx.set(current)
        # Snapshot for revert
        self._cp_prev = {
            "color": list(self.custom_color),
            "brightness": self.custom_brightness,
            "fx": self.custom_fx,
            "mode": self.current_mode,
        }

    def _cp_revert(self):
        prev = self._cp_prev
        self.custom_color      = prev["color"]
        self.custom_brightness = prev["brightness"]
        self.custom_fx         = prev["fx"]
        # Restore whatever lights were showing before the panel opened.
        # (Old code checked for a "Leisure" mode that doesn't exist — the
        # Entertainment case silently never restored. Fixed.)
        restore = {
            "Work": self.set_mode_work,
            "Entertainment": self.set_mode_entertainment,
            "Music": self.set_mode_music,
            "Idle": self.set_mode_idle,
        }.get(prev["mode"])
        if restore:
            restore()
        elif prev["mode"] == "Custom":
            self.sync_wleds({
                "on": True, "tt": 0,
                "bri": prev["brightness"],
                "seg": [{"col": [prev["color"]], "fx": prev["fx"]}]
            })
        self._close_overlay()

    def _cp_save(self):
        self.custom_color      = [self._cp_r.get(), self._cp_g.get(), self._cp_b.get()]
        self.custom_brightness = self._cp_bri.get()
        self.custom_fx         = self._cp_effects[self._cp_fx.get()]
        if self.current_mode != "Custom":
            self.set_mode_custom()
        self._close_overlay()

    #-- Settings Panel ------------------------------------------------------------------------------------------

    def show_settings_panel(self):
        self._open_panel("settings", self._build_settings)

    def _build_settings(self, panel):
        self._panel_header(panel, "SETTINGS")
        # PERF: was a CTkScrollableFrame wrapping 37+ buttons — the most
        # expensive panel to rebuild, and the content fits without scrolling.
        content = ctk.CTkFrame(panel, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=24, pady=16)
        # UI Theme presets
        self._section_label(content, "UI Theme")
        theme_row = ctk.CTkFrame(content, fg_color="transparent")
        theme_row.pack(fill="x", pady=(0, 6))
        for name in ["Default", "Midnight", "Slate", "Forest", "Ember"]:
            t = self._themes[name]
            ctk.CTkButton(theme_row, text=name, width=110, height=36,
                          fg_color=t["btn_fg"], hover_color=t["btn_hover"],
                          font=self._fonts["chip"],
                          command=lambda n=name: self._apply_ui_preset(n)
            ).pack(side="left", padx=4)
        # Mode LED colors
        self._section_label(content, "Mode Colors")
        swatches = [
            ("White",   [255, 255, 255]),
            ("Red",     [255, 0,   0  ]),
            ("Green",   [0,   255, 0  ]),
            ("Blue",    [0,   0,   255]),
            ("Yellow",  [255, 255, 0  ]),
            ("Cyan",    [0,   255, 255]),
            ("Magenta", [255, 0,   255]),
            ("Orange",  [255, 128, 0  ]),
        ]
        for mode in ["Work", "Entertainment", "Music", "Idle"]:
            row = ctk.CTkFrame(content, fg_color=self._theme["card"], corner_radius=8)
            row.pack(fill="x", pady=(0, 6))
            ctk.CTkLabel(row, text=mode, width=110,
                         font=self._fonts["small_b"],
                         text_color="#CCCCEE").pack(side="left", padx=12, pady=10)
            for _, rgb in swatches:
                hex_col = "#{:02X}{:02X}{:02X}".format(*rgb)
                ctk.CTkButton(row, text="", width=30, height=30,
                              fg_color=hex_col, hover_color=hex_col, corner_radius=4,
                              command=lambda m=mode, c=rgb: self._set_mode_color(m, c)
                ).pack(side="left", padx=3, pady=8)

    def _apply_ui_preset(self, name):
        self._theme = self._themes[name]
        t = self._theme
        self._close_overlay()
        # Cached panels were built with the old theme's colors — rebuild lazily
        self._invalidate_panels()
        self._sidebar.configure(fg_color=t["sidebar"])
        for btn in [self._btn_work, self._btn_entertainment,
                    self._btn_music, self._btn_custom] + self._sidebar_btns:
            btn.configure(fg_color=t["btn_fg"], hover_color=t["btn_hover"])

    def _set_mode_color(self, mode, color):
        self.mode_colors[mode] = color
        if self.current_mode == mode:
            self.sync_wleds({"on": True, "tt": 0, "bri": 128,
                             "seg": [{"col": [color], "fx": 0}]})

    # -----------------------------------------------------------------------------------------------------------
    # Timer Loop
    # -----------------------------------------------------------------------------------------------------------

    def main_loop(self):
        if self.current_mode == "Work":
            # If work timer has reached 8 hours, WLEDs flash Green for 10s
            if self.work_seconds == 28800:
                # Increment clock by 1 so that it doesn't loop forever
                self.work_seconds += 1
                # Enable End of Work celebration for 10 seconds then return to work mode
                self.end_of_work()
                self.after(10000, self.set_mode_work)
            # If work timer is above or below 8 hours, tick the work clock up by 1s
            else:
                self.work_seconds += 1
                self._btn_work.configure(text=f"WORK\n{self.format_time(self.work_seconds)}")
        elif self.current_mode == "Entertainment":
            # If there is still entertainment time left, tick the entertainment clock down by 1s
            if self.entertainment_seconds > 0:
                self.entertainment_seconds -= 1
                self._btn_entertainment.configure(
                    text=f"ENTERTAINMENT\n{self.format_time(self.entertainment_seconds)}")
            # If out of entertainment time, WLEDs flash Red for 5s, then switch to Idle mode
            else:
                self.end_of_entertainment()
                self.after(5000, self.set_mode_idle)

        # Keep the Timers panel live if it's currently on screen
        if self._timers_panel_visible():
            self._refresh_timer_labels()

        self.after(1000, self.main_loop)

    # -----------------------------------------------------------------------------------------------------------
    # Network
    # -----------------------------------------------------------------------------------------------------------

    def receive_data(self):
        while True:
            # Thread sleeps here until Windows 'shouts'
            data, addr = self.socket.recvfrom(1024)
            # Check the first byte (The Header)
            header = data[0]

            if header == 107: # 'k' for keyboard
                if self.current_mode == "Work":
                    # PERF: apply the cooldown HERE, in the receiver thread.
                    # The old code scheduled after(0, ...) for every keystroke
                    # and only then checked the cooldown on the UI thread —
                    # fast typing flooded the Tk event queue with no-op
                    # callbacks and starved widget redraws.
                    now = time.time()
                    if now - self.last_flash_time >= self.flash_cooldown:
                        self.last_flash_time = now
                        # Jump back to the main thread for UI/Light safety
                        self.after(0, self.trigger_keyboard_flash)
            elif header == 115: # 's' for Screen
                if self.current_mode == "Entertainment":
                    # Extract the 12 color bytes (Payload)
                    payload = data[1:]
                    self.after(0, lambda p=payload: self.update_screen_sync(p))

    def update_screen_sync(self, payload):
        # TODO: screen sync mode not implemented yet.
        # NOTE: the old code called this method without defining it — the first
        # screen packet in Entertainment mode would have raised AttributeError.
        pass

    def sync_wleds(self, payload):
        # Convert dictionary to binary-encoded JSON string
        packet = json.dumps(payload).encode()
        for ip in self.wled_ip:
            try:
                # Use the raw IP address to avoid mDNS lag
                self.socket.sendto(packet, (ip, 21324))
            except Exception as e:
                print(f"UDP Error: {e}")

    # -----------------------------------------------------------------------------------------------------------
    # Keyboard Flash
    # -----------------------------------------------------------------------------------------------------------

    def trigger_keyboard_flash(self):
        self.sync_wleds({
                            "on": True,
                            "bri": 255,
                            "tt": 0,
                            "seg": [{"col": [[255, 255, 255]]}]
                            })
        # Return to normal work lights after 100ms
        self.after(100,  lambda: self.sync_wleds({"bri": 128, "tt": 5, "seg": [{"col": [self.mode_colors["Work"]]}]}))

    # -----------------------------------------------------------------------------------------------------------
    # Modes
    # -----------------------------------------------------------------------------------------------------------

    def _apply_mode_lights(self, color, bri=128, fx=0):
        self.sync_wleds({
                            "on": True,
                            "bri": bri,
                            "seg": [{
                                "col": [color],
                                "fx": fx,
                                }]
                          })

    def set_mode_idle(self):
        self.current_mode = "Idle"
        self._set_active(None)
        self._apply_mode_lights(self.mode_colors["Idle"])

    def set_mode_work(self):
        self.current_mode = "Work"
        self._set_active(self._btn_work)
        self._apply_mode_lights(self.mode_colors["Work"])

    def set_mode_entertainment(self):
        self.current_mode = "Entertainment"
        self._set_active(self._btn_entertainment)
        if self.entertainment_seconds > 0:
            self._apply_mode_lights(self.mode_colors["Entertainment"])

    def set_mode_music(self):
        self.current_mode = "Music"
        self._set_active(self._btn_music)
        self._apply_mode_lights(self.mode_colors["Music"])

    def set_mode_custom(self):
        self.current_mode = "Custom"
        self._set_active(self._btn_custom)
        self._apply_mode_lights(self.custom_color, bri=self.custom_brightness, fx=self.custom_fx)

    # -----------------------------------------------------------------------------------------------------------
    # Events
    # -----------------------------------------------------------------------------------------------------------

    def end_of_work(self):
        self.sync_wleds({
                            "on": True,
                            "bri": 128,
                            "seg": [{
                                "col": [[0, 255, 0]],
                                "fx": 1,
                                "sx": 200
                                }]
                            })

    def end_of_entertainment(self):
        self.sync_wleds({
                            "on": True,
                            "bri": 128,
                            "seg": [{
                                "col": [[255, 0, 0], [0, 0, 0]],
                                "fx": 1,
                                "sx": 200
                                }]
                          })

    # -----------------------------------------------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------------------------------------------

    def format_time(self, seconds):
        hours = seconds // 3600
        minutes = (seconds // 60) % 60
        secs = seconds % 60
        return f"{hours:02}:{minutes:02}:{secs:02}"

    def _set_active(self, btn):
        # If there is already an active button, get rid of its border
        if self._active_btn:
            self._active_btn.configure(border_width=0)

        # Add a border to the new active button
        self._active_btn = btn
        if btn:
            btn.configure(border_width=3, border_color="#FFFFFF")


app = Dashboard()
app.mainloop()