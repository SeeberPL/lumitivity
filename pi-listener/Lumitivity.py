import customtkinter as ctk # Import for GUI
import requests
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
        self.wled_instr = {
                            "seg": {
                                "on": True,
                                "bri": 50,
                                "col":[255, 255, 255]
                                }
                           }
        self.is_on = False # Variable that keeps track of WLED power state
        self.set_on = {"on": True} # JSON data, Sets WLED state to 'On'
        self.set_off = {"on": False} # JSON data, Sets WLED state to 'Off'
        
        # Mode Variables
        self.current_mode = "Idle" # Keeps track of current mode
        self.work_seconds = 0 # Work mode timer, keeping track of # seconds spent in work mode
        self.entertainment_duration = 5 # Time allotment for entertainment mode
        self.entertainment_seconds = self.entertainment_duration # Entertainment mode timer, keeping track of # seconds left in entertainment mode
        
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
        
        # Build UI
        self._build_layout()
        self._active_btn = None
        self._overlay = None
        
        # Start background thread and timer loop
        desktop_input_thread = threading.Thread(target=self.receive_data, daemon=True).start()
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
            font=ctk.CTkFont(size=22, weight="bold"),
            command=self.set_mode_work,
            corner_radius=6
            )
        self._btn_work.grid(row=0, column=0, sticky="nsew", padx=(0, GAP), pady=(0, GAP))
        
        # Entertainment Button
        self._btn_entertainment = ctk.CTkButton(
            mode_frame,
            text=f"ENTERTAINMENT\n{self.format_time(self.entertainment_seconds)}",
            font=ctk.CTkFont(size=22, weight="bold"),
            command=self.set_mode_entertainment,
            corner_radius=6
            )
        self._btn_entertainment.grid(row=0, column=1, sticky="nsew", padx=(GAP, 0), pady=(0, GAP))
        
        # Music Button
        self._btn_music = ctk.CTkButton(
            mode_frame,
            text="MUSIC",
            font=ctk.CTkFont(size=22, weight="bold"),
            command=self.set_mode_music,
            corner_radius=6
            )
        self._btn_music.grid(row=1, column=0, sticky="nsew", padx=(0, GAP), pady=(GAP, 0))
        
        # Custom Button
        self._btn_custom = ctk.CTkButton(
            mode_frame,
            text="CUSTOM",
            font=ctk.CTkFont(size=22, weight="bold"),
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
                font=ctk.CTkFont(size=11, weight="bold"),
                command=cmd,
                fg_color=self._theme["btn_fg"], hover_color=self._theme["btn_hover"],
                text_color="#AAAACC", corner_radius=8, height=80
            )
            btn.grid(row=row, column=0, padx=10, pady=6, sticky="ew")
            self._sidebar_btns.append(btn)
                
    # -- Overlay System -----------------------------------------------------------------------------------------
        
    def _show_overlay(self, build_fn):
        # If there's already an open overlay, close that one
        if self._overlay:
            self._overlay.destroy()
                
        # Full-screen dark backdrop
        overlay = ctk.CTkFrame(self, fg_color=self._theme["backdrop"], corner_radius=0)
        overlay.place(x=0, y=0, relwidth=1, relheight=1)
        overlay.bind("<Button-1>", lambda e: self._close_overlay())
        self._overlay = overlay
            
        # Centered panel
        panel = ctk.CTkFrame(overlay,
                            fg_color=self._theme["overlay"],
                            corner_radius=14,
                            width=740,
                            height=530)
        panel.place(relx=0.5, rely=0.5, anchor="center")
        panel.pack_propagate(False)
        build_fn(panel)
            
    def _close_overlay(self):
        if self._overlay:
            self._overlay.destroy()
            self._overlay = None
                
    def _panel_header(self, panel, title, close_fn=None):
        if close_fn is None:
            close_fn = self._close_overlay
        header = ctk.CTkFrame(panel, fg_color="transparent")
        header.pack(fill="x", padx=24, pady=(20, 0))
        ctk.CTkLabel(header, text=title,
                    font=ctk.CTkFont(size=20, weight="bold"),
                    text_color="#FFFFFF").pack(side="left")
        ctk.CTkButton(header, text="x", width=38, height=38,
                    fg_color=self._theme["btn_fg"], hover_color=self._theme["btn_hover"],
                    font=ctk.CTkFont(size=15),
                    command=close_fn).pack(side="right")
        ctk.CTkFrame(panel, fg_color=self._theme["divider"], height=1).pack(fill="x", padx=24, pady=(12, 0))
            
    def _section_label(self, parent, text):
        ctk.CTkLabel(parent, text=text,
                    font=ctk.CTkFont(size=14, weight="bold"),
        text_color="#7777AA").pack(anchor="w", pady=(12, 4))
            
    def _card(self, parent):
        f = ctk.CTkFrame(parent, fg_color=self._theme["card"], corner_radius=8)
        f.pack(fill="x", pady=(0, 6))
        return f
        
    #-- Timers Panel --------------------------------------------------------------------------------------------
                
    def show_timers_panel(self):
        self._show_overlay(self._build_timers)
            
    def _build_timers(self, panel):
        self._panel_header(panel, "TIMERS")
        content = ctk.CTkScrollableFrame(panel, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=24, pady=16)
            
        # Work Timer
        self._section_label(content, "Work Timer")
        wr = self._card(content)
        work_label = ctk.CTkLabel(wr, text=f"Elapsed: {self.format_time(self.work_seconds)}",
                                font=ctk.CTkFont(size=14), text_color="#CCCCEE")
        work_label.pack(side="left", padx=16, pady=14)
        ctk.CTkButton(wr, text="Reset", width=100,
                    command=lambda: self._reset_work(work_label)
                    ).pack(side="right", padx=12, pady=10)
            
        # Entertainment Timer
        self._section_label(content, "Entertainment Timer")
        er = self._card(content)
        ent_label = ctk.CTkLabel(er, text=f"Remaining: {self.format_time(self.entertainment_seconds)}",
                                font=ctk.CTkFont(size=14), text_color="#CCCCEE")
        ent_label.pack(side="left", padx=16, pady=14)
        ctk.CTkButton(er, text="Reset", width=100,
                    command=lambda: self._reset_entertainment(ent_label)
                    ).pack(side="right", padx=12, pady=10)
            
        # Duration Presets
        self._section_label(content, "Set Entertainment Duration")
        dur = self._card(content)
        for label, secs in [("1 hr", 3600), ("2 hr", 7200), ("4 hr", 14400), ("8 hr", 28800)]:
            ctk.CTkButton(dur, text=label, width=90, height=38,
                        command=lambda s=secs: self._set_entertainment_duration(s, ent_label)
                        ).pack(side="left", padx=8, pady=10)
                
        # Event Zones
        self._section_label(content, "Event Zones")
        ez = self._card(content)
        info = ctk.CTkFrame(ez, fg_color="transparent")
        info.pack(fill="x", padx=16, pady=12)
        ctk.CTkLabel(info, text="End of Work -> Flash green for 10s, return to Work",
                    font=ctk.CTkFont(size=13), text_color="#8888AA").pack(anchor="w")
        ctk.CTkLabel(info, text="End of Entertainment -> Flash red for 5s, switch to Idle",
                    font=ctk.CTkFont(size=13), text_color="#8888AA").pack(anchor="w", pady=(4, 0))
            
    def _reset_work(self, label):
        self.work_seconds = 0
        self._btn_work.configure(text=f"WORK\n{self.format_time(0)}")
        label.configure(text=f"Elapsed: {self.format_time(0)}")
            
    def _reset_entertainment(self, label):
        self.entertainment_seconds = self.entertainment_duration
        self._btn_entertainment.configure(
            text=f"ENTERTAINMENT\n{self.format_time(self.entertainment_seconds)}")
        label.configure(text=f"Remaining: {self.format_time(self.entertainment_seconds)}")
            
    def _set_entertainment_duration(self, secs, label):
        self.entertainment_duration = secs
        self.entertainment_seconds = secs
        self._btn_entertainment.configure(
            text=f"ENTERTAINMENT\n{self.format_time(secs)}")
        label.configure(text=f"Remaining: {self.format_time(secs)}")
        
    #-- Custom Panel --------------------------------------------------------------------------------------------
        
    def show_custom_panel(self):
        self._show_overlay(self._build_custom)
        
    def _build_custom(self, panel):
        # Snapshot values so ✕ / Cancel can revert
        prev_color      = list(self.custom_color)
        prev_brightness = self.custom_brightness
        prev_fx         = self.custom_fx
        prev_mode       = self.current_mode

        def revert():
            self.custom_color      = prev_color
            self.custom_brightness = prev_brightness
            self.custom_fx         = prev_fx
            # Restore whatever lights were showing before the panel opened
            if prev_mode == "Work":
                self.set_mode_work()
            elif prev_mode == "Leisure":
                self.set_mode_leisure()
            elif prev_mode == "Idle":
                self.set_mode_idle()
            elif prev_mode == "Custom":
                self.sync_wleds({
                    "on": True, "tt": 0,
                    "bri": prev_brightness,
                    "seg": [{"col": [prev_color], "fx": prev_fx}]
                })
            self._close_overlay()

        self._panel_header(panel, "CUSTOM MODE SETTINGS", close_fn=revert)

        content = ctk.CTkFrame(panel, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=24, pady=16)

        self._section_label(content, "Color")
        r_var   = ctk.IntVar(value=self.custom_color[0])
        g_var   = ctk.IntVar(value=self.custom_color[1])
        b_var   = ctk.IntVar(value=self.custom_color[2])
        bri_var = ctk.IntVar(value=self.custom_brightness)

        effects = {
            "Solid": 0, "Blink": 1, "Breathe": 2,
            "Color Wipe": 3, "Chase": 22, "Rainbow": 9, "Twinkle": 7
        }
        current = next((k for k, v in effects.items() if v == self.custom_fx), "Solid")
        fx_var = ctk.StringVar(value=current)

        def preview(*_):
            self.sync_wleds({
                "on": True, "tt": 0,
                "bri": bri_var.get(),
                "seg": [{"col": [[r_var.get(), g_var.get(), b_var.get()]],
                         "fx": effects[fx_var.get()]}]
            })

        for label, var, accent in [
            ("R", r_var, "#FF5555"),
            ("G", g_var, "#55FF55"),
            ("B", b_var, "#5599FF")
        ]:
            row = ctk.CTkFrame(content, fg_color="transparent")
            row.pack(fill="x", pady=3)
            ctk.CTkLabel(row, text=label, width=22,
                         font=ctk.CTkFont(size=14, weight="bold"),
                         text_color=accent).pack(side="left")
            ctk.CTkSlider(row, from_=0, to=255, variable=var,
                          button_color=accent, progress_color=accent,
                          command=preview).pack(side="left", fill="x", expand=True, padx=10)
            ctk.CTkLabel(row, textvariable=var, width=36,
                         font=ctk.CTkFont(size=13), text_color="#FFFFFF").pack(side="left")

        self._section_label(content, "Brightness")
        bri_row = ctk.CTkFrame(content, fg_color="transparent")
        bri_row.pack(fill="x", pady=3)
        ctk.CTkSlider(bri_row, from_=1, to=255, variable=bri_var,
                      command=preview).pack(side="left", fill="x", expand=True, padx=(0, 10))
        ctk.CTkLabel(bri_row, textvariable=bri_var, width=36,
                     font=ctk.CTkFont(size=13), text_color="#FFFFFF").pack(side="left")

        self._section_label(content, "Effect")
        ctk.CTkOptionMenu(content, values=list(effects.keys()), variable=fx_var,
                          fg_color="#252550", command=preview).pack(anchor="w", pady=3)

        def save():
            self.custom_color      = [r_var.get(), g_var.get(), b_var.get()]
            self.custom_brightness = bri_var.get()
            self.custom_fx         = effects[fx_var.get()]
            if self.current_mode != "Custom":
                self.set_mode_custom()
            self._close_overlay()

        btn_row = ctk.CTkFrame(content, fg_color="transparent")
        btn_row.pack(fill="x", pady=(20, 0))
        ctk.CTkButton(btn_row, text="Cancel", height=46, width=120,
                      fg_color="#2A2A55", hover_color="#3A3A77",
                      font=ctk.CTkFont(size=15, weight="bold"),
                      command=revert).pack(side="left")
        ctk.CTkButton(btn_row, text="Save", height=46,
                      font=ctk.CTkFont(size=15, weight="bold"),
                      command=save).pack(side="left", fill="x", expand=True, padx=(10, 0))
        
    #-- Settings Panel ------------------------------------------------------------------------------------------
        
    def show_settings_panel(self):
        self._show_overlay(self._build_settings)

    def _build_settings(self, panel):
        self._panel_header(panel, "SETTINGS")
        content = ctk.CTkScrollableFrame(panel, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=24, pady=16)

        # UI Theme presets
        self._section_label(content, "UI Theme")
        themes = ["Default", "Midnight", "Slate", "Forest", "Ember"]
        theme_row = ctk.CTkFrame(content, fg_color="transparent")
        theme_row.pack(fill="x", pady=(0, 6))
        for name in themes:
            t = self._themes[name]
            ctk.CTkButton(theme_row, text=name, width=110, height=36,
                          fg_color=t["btn_fg"], hover_color=t["btn_hover"],
                          font=ctk.CTkFont(size=12, weight="bold"),
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
            row = ctk.CTkFrame(content, fg_color="#1E1E45", corner_radius=8)
            row.pack(fill="x", pady=(0, 6))
            ctk.CTkLabel(row, text=mode, width=110,
                         font=ctk.CTkFont(size=13, weight="bold"),
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
                time = self.format_time(self.work_seconds)
                self._btn_work.configure(text=f"WORK\n{time}")
        elif self.current_mode == "Entertainment":
            # If there is still entertainment time left, tick the entertainment clock down by 1s
            if self.entertainment_seconds > 0:
                self.entertainment_seconds -= 1
                time = self.format_time(self.entertainment_seconds)
                self._btn_entertainment.configure(text=f"ENTERTAINMENT\n{time}")
            # If out of entertainment time, WLEDs flash Red for 5s, then switch to Idle mode
            else:
                self.end_of_entertainment()
                self.after(5000, self.set_mode_idle)
                
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
                    print(f"Received data from {addr}: {data.decode()}")
                    # Jump back to the main thread for UI/Light safety
                    self.after(0, self.trigger_keyboard_flash)
            elif header == 115: # 's' for Screen
                if self.current_mode == "Entertainment":
                    # Extract the 12 color bytes (Payload)
                    payload = data[1:]
                    self.after(0, lambda: self.update_screen_sync(payload))
        
    def sync_wleds(self, payload):
        # Convert dictionary to binary-encoded JSON string
        packet = json.dumps(payload).encode()
        for ip in self.wled_ip:
            try:
                # Use the raw IP address for Station 1 to avoid mDNS lag
                self.socket.sendto(packet, (ip, 21324))
            except Exception as e:
                print(f"UDP Error: {e}")
                
    # -----------------------------------------------------------------------------------------------------------
    # Keyboard Flash
    # -----------------------------------------------------------------------------------------------------------
                
    def trigger_keyboard_flash(self):
        now = time.time()
        if now - self.last_flash_time < self.flash_cooldown:
            return
        self.last_flash_time = now
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
    
    def set_mode_idle(self):
        self.current_mode = "Idle"
        self._set_active(None)
        print("Idle Mode Enabled")
        self.sync_wleds({
                            "on": True,
                            "bri": 128,
                            "seg": [{
                                "col": [self.mode_colors["Idle"]],
                                "fx": 0,
                                }]
                          })
        
    def set_mode_work(self):
        self.current_mode = "Work"
        self._set_active(self._btn_work)
        print("Work Mode Enabled")
        print(self.work_seconds)
        self.sync_wleds({
                            "on": True,
                            "bri": 128,
                            "seg": [{
                                "col": [self.mode_colors["Work"]],
                                "fx": 0,
                                }]
                          })
        
    def set_mode_entertainment(self):
        self.current_mode = "Entertainment"
        self._set_active(self._btn_entertainment)
        print("Entertainment Mode Enabled")
        print(self.entertainment_seconds)
        if self.entertainment_seconds > 0:
            self.sync_wleds({
                            "on": True,
                            "bri": 128,
                            "seg": [{
                                "col": [self.mode_colors["Entertainment"]],
                                "fx": 0,
                                }]
                          })
        
    def set_mode_music(self):
        self.current_mode = "Music"
        self._set_active(self._btn_music)
        print("Music Mode Enabled")
        self.sync_wleds({
                            "on": True,
                            "bri": 128,
                            "seg": [{
                                "col": [self.mode_colors["Music"]],
                                "fx": 0,
                                }]
                          })
        
    def set_mode_custom(self):
        self.current_mode = "Custom"
        self._set_active(self._btn_custom)
        print("Custom Mode Enabled")
        self.sync_wleds({
                            "on": True,
                            "bri": self.custom_brightness,
                            "seg": [{
                                "col": [self.custom_color],
                                "fx": self.custom_fx,
                                }]
                          })
        
    # Placeholder for button function
    def button_callback(self):
        print("button clicked")
    
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
    
    def format_time(self, time):
        hours = time // 3600
        minutes = (time // 60) % 60
        seconds = time % 60
        return f"{hours:02}:{minutes:02}:{seconds:02}"
    
    # Function that toggles the power state of the LEDs
    def toggle_light(self):
        if self.is_on:
            try:
                requests.post(f"http://{self.wled_right_wall_ip}/json/state", json=self.set_off)
                self.is_on = False
                print("LEDs Off")
            except Exception as e:
                print(f"Error: {e}")
        else:
            try:
                requests.post(f"http://{self.wled_right_wall_ip}/json/state", json=self.set_on)
                self.is_on = True
                print("LEDs On")
            except Exception as e:
                print(f"Error: {e}")
                
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