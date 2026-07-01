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
        self.overrideredirect(True)
        self.geometry(f"{self.winfo_screenwidth()}x{self.winfo_screenheight()}+0+0")
        self.bind("<Escape>", lambda e: self.destroy())
        
        # Socket creation for networking to desktop
        self.socket = socket.socket(
                socket.AF_INET,
                socket.SOCK_DGRAM
                )
        self.socket.bind(("", 8080))
            
        # WLED variables
        self.wled_ip = ["192.168.4.49", "192.168.4.40"] # WLED Controller name
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
        self.leisure_seconds = 5000 # Leisure mode timer, keeping track of # seconds left in leisure mode
        
        self.last_flash_time = 0
        self.flash_cooldown = 0.1 # Seconds
        
        # Build UI
        self._build_layout()
        
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
            text="WORK",
            font=ctk.CTkFont(size=22, weight="bold"),
            command=self.set_mode_work,
            corner_radius=6
            )
        self._btn_work.grid(row=0, column=0, sticky="nsew", padx=(0, GAP), pady=(0, GAP))
        
        # Entertainment Button
        self._btn_work = ctk.CTkButton(
            mode_frame,
            text="ENTERTAINMENT",
            font=ctk.CTkFont(size=22, weight="bold"),
            command=self.set_mode_leisure,
            corner_radius=6
            )
        self._btn_work.grid(row=0, column=1, sticky="nsew", padx=(GAP, 0), pady=(0, GAP))
        
        # Music Button
        self._btn_work = ctk.CTkButton(
            mode_frame,
            text="MUSIC",
            font=ctk.CTkFont(size=22, weight="bold"),
            command=self.button_callback,
            corner_radius=6
            )
        self._btn_work.grid(row=1, column=0, sticky="nsew", padx=(0, GAP), pady=(GAP, 0))
        
        # Custom Button
        self._btn_work = ctk.CTkButton(
            mode_frame,
            text="CUSTOM",
            font=ctk.CTkFont(size=22, weight="bold"),
            command=self.button_callback,
            corner_radius=6
            )
        self._btn_work.grid(row=1, column=1, sticky="nsew", padx=(GAP, 0), pady=(GAP, 0))
    
        # -- Sidebar ---------------------------------------------------------------------------------------
    
        sidebar = ctk.CTkFrame(self, fg_color="#13132A", corner_radius=0, width=130)
        sidebar.grid(row=0, column=1, sticky="nsew")
        sidebar.grid_propagate(False)
        sidebar.grid_rowconfigure((0, 1, 2, 3), weight=1)
        sidebar.grid_columnconfigure(0, weight=1)
        
        for row, (text, cmd) in enumerate([
            ("TIMERS", self.button_callback),
            ("CUSTOM\nMODE", self.button_callback),
            ("SETTINGS", self.button_callback),
            ("EXIT", self.destroy)
        ]):
            ctk.CTkButton(
                sidebar,
                text=text,
                font=ctk.CTkFont(size=11, weight="bold"),
                command=cmd,
                fg_color="#1E1E40",
                hover_color="#2E2E60",
                text_color="#AAAACC",
                corner_radius=8,
                height=80
            ).grid(row=row, column=0, padx=10, pady=6, sticky="ew")
                
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
                self.my_frame.button_work.configure(text=f"Work\n{time}")
        elif self.current_mode == "Leisure":
            # If there is still leisure time left, tick the leisure clock down by 1s
            if self.leisure_seconds > 0:
                self.leisure_seconds -= 1
                time = self.format_time(self.leisure_seconds)
                self.my_frame.button_leisure.configure(text=f"Leisure\n{time}")
            # If out of leisure time, WLEDs flash Red for 5s, then switch to Idle mode
            else:
                self.end_of_leisure()
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
                if self.current_mode == "Leisure":
                    # Extract the 12 color bytes (Payload)
                    payload = data[1:]
                    self.after(0, lambda: self.update_screen_sync(payload))
                    
    def update_screen_sync(self,payload):
        top = [payload[0], payload[1], payload[2]]
        bottom = [payload[3], payload[4], payload[5]]
        left = [payload[6], payload[7], payload[8]]
        right = [payload[9], payload[10], payload[11]]
        
        self.sync_wleds({
                            "seg": [
                                {"id": 0, "col": [top]},
                                {"id": 1, "col": [bottom]},
                                {"id": 2, "col": [left]},
                                {"id": 3, "col": [right]}
                                ]
                            })
        
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
        self.after(100,  lambda: self.sync_wleds({"bri": 128, "tt": 5, "seg": [{"col": [[0, 255, 0]]}]}))

    # -----------------------------------------------------------------------------------------------------------
    # Modes
    # -----------------------------------------------------------------------------------------------------------
    
    def set_mode_work(self):
        self.current_mode = "Work"
        print("Work Mode Enabled")
        print(self.work_seconds)
        self.sync_wleds({
                            "on": True,
                            "bri": 128,
                            "seg": [{
                                "col": [[0, 255, 0]],
                                "fx": 0,
                                }]
                          })
        
    def set_mode_leisure(self):
        self.current_mode = "Leisure"
        print("Leisure Mode Enabled")
        print(self.leisure_seconds)
        if self.leisure_seconds > 0:
            self.sync_wleds({
                            "on": True,
                            "bri": 128,
                            "seg": [{
                                "col": [[255, 255, 0]],
                                "fx": 0,
                                }]
                          })
        
    def set_mode_idle(self):
        self.current_mode = "Idle"
        print("Idle Mode Enabled")
        self.sync_wleds({
                            "on": True,
                            "bri": 128,
                            "seg": [{
                                "col": [[255, 255, 255]],
                                "fx": 0,
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
        
    def end_of_leisure(self):
        self.sync_wleds({
                            "on": True,
                            "bri": 128,
                            "seg": [{
                                "id": 0,
                                "start": 0,
                                "stop": 300,
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
                
app = Dashboard()
app.mainloop()

        

        
app = Dashboard()
app.mainloop()