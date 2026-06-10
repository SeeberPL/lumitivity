import customtkinter as ctk # Import for GUI
import requests
import socket # Import for networking to desktop
import threading # Import for background listening for calls from desktop
import time
import json

class MyFrame(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        
        # Work Mode Button
        self.button_work = ctk.CTkButton(self.master, width=487, height=200, text="Work\n00:00:00", command=self.master.set_mode_work)
        self.button_work.grid(row=0, column=0, padx=(0,10), pady=(0,10))
        # Idle Mode Button
        self.button_idle = ctk.CTkButton(self.master, width=487, height=200, text="Idle", command=self.master.set_mode_idle)
        self.button_idle.grid(row=0, column=1, pady=(0,10))
        # Music Mode Button
        self.button_music = ctk.CTkButton(self.master, width=487, height=200, text="Music", command=self.master.button_callback)
        self.button_music.grid(row=1, column=0, padx=(0,10))
        # Leisure Mode Button
        self.button_leisure = ctk.CTkButton(self.master, width=487, height=200, text="Leisure\n04:00:00", command=self.master.set_mode_leisure)
        self.button_leisure.grid(row=1, column=1)
                
class Dashboard(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Lumitivity")
        self.geometry("1024x600")
        #self.grid_rowconfigure(0, weight=1)
        #self.grid_columnconfigure(0, weight=1)
        #self.current_time =
        
        # Socket Creation for networking to desktop
        self.socket = socket.socket(
                socket.AF_INET,
                socket.SOCK_DGRAM
                )
        self.socket.bind(("", 8080))
        
        # WLED variables
        self.wled_ip = ["192.168.4.40", "192.168.4.38"] # WLED Controller name
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
        self.leisure_seconds = 5 # Leisure mode timer, keeping track of # seconds left in leisure mode
        
        # Frame for Lumitivity Buttons
        self.my_frame = MyFrame(master=self)
        self.my_frame.grid(row=1, column=1, padx=20, pady=20, sticky="nsew")
        
        desktop_input_thread = threading.Thread(target=self.receive_data, daemon=True).start()
        self.main_loop()        
        
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
    
    def receive_data(self):
        while True:
            # Thread sleeps here until Windows 'shouts'
            data, addr = self.socket.recvfrom(1024)
            if self.current_mode == "Work":
                print(f"Received data from {addr}: {data.decode()}")
                # Jump back to the main thread for UI/Light safety
                self.after(0, self.trigger_keyboard_flash)
                
    def trigger_keyboard_flash(self):
        self.sync_wleds({
                            "on": True,
                            "bri": 128,
                            "seg": [{
                                "col": [[255, 255, 255]],
                                "tt": 0
                                }]
                            })
        # Return to normal work lights after 100ms
        self.after(100,  lambda: self.sync_wleds({"bri": 128, "seg": [{"col": [[0, 255, 0]], "tt": 0}]}))
            
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
    
    def format_time(self, time):
        hours = time // 3600
        minutes = (time // 60) % 60
        seconds = time % 60
        return f"{hours:02}:{minutes:02}:{seconds:02}"
    
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
        
    def sync_wleds(self, payload):
        # Convert dictionary to binary-encoded JSON string
        packet = json.dumps(payload).encode()
        for ip in self.wled_ip:
            try:
                # Use the raw IP address for Station 1 to avoid mDNS lag
                self.socket.sendto(packet, (ip, 21324))
            except Exception as e:
                print(f"UDP Error: {e}")
        
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