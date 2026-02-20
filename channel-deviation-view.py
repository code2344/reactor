import tkinter as tk
import threading
import queue
import sys
from tkinter import simpledialog
import time
import random

# ---------------- GRID LAYOUT ----------------
grid_letters = [
    ["P","P","P","P","P","R","R","R","P","P","P","P","P"],
    ["P","P","P","P","R","G","G","G","R","P","P","P","P"],
    ["P","P","P","R","G","G","T","G","G","R","P","P","P"],
    ["P","P","R","G","G","F","A","F","G","G","R","P","P"],
    ["P","R","G","G","F","C","F","C","F","G","G","R","P"],
    ["R","G","G","F","C","F","C","F","C","F","G","G","R"],
    ["R","G","T","A","F","C","T","C","F","A","T","G","R"],
    ["R","G","G","F","C","F","C","F","C","F","G","G","R"],
    ["P","R","G","G","F","C","F","C","F","G","G","R","P"],
    ["P","P","R","G","G","F","A","F","G","G","R","P","P"],
    ["P","P","P","R","G","G","T","G","G","R","P","P","P"],
    ["P","P","P","P","R","G","G","G","R","P","P","P","P"],
    ["P","P","P","P","P","R","R","R","P","P","P","P","P"],
]

CELL_SIZE = 52  # Increased for better visibility
OFF = "#2b2b2b"
RED = "#ff3b30"
YELLOW = "#ffd60a"
FLASH_DARK = "#1a1a1a"

# Rod type descriptions
ROD_TYPES = {
    "R": "Reflector",
    "G": "Graphite",
    "T": "Temperature Sensor",
    "A": "Auto Control Rod",
    "F": "Fuel",
    "C": "Control Rod",
    "P": "Placeholder"
}

# Control rod allowed operations
CONTROL_RODS = {"C", "A"}  # C and A can be controlled

cmd_queue = queue.Queue()


# -------- READ COMMANDS FROM TERMINAL --------
def command_reader():
    while True:
        line = sys.stdin.readline()
        if not line:
            break
        cmd_queue.put(line.strip())

threading.Thread(target=command_reader, daemon=True).start()


# ---------------- MAIN UI ----------------
class GridUI:
    def __init__(self, root):
        self.root = root

        self.num_to_cell = {}   # number -> (canvas, letter, temp_box, pressure_box, fuel_box, flux_box, temp_text, pressure_text, fuel_text, flux_text)
        self.num_to_pos = {}    # number -> (row, col) for proximity calculations
        self.state = {}         # alarm state
        self.custom_text = {}   # number -> message override
        self.control_rod_levels = {}  # rod number -> insertion percentage
        self.temperatures = {}  # rod number (T only) -> temperature in Kelvin
        self.fuel_levels = {}   # rod number (F only) -> fuel percentage
        self.pump_flow = {}     # pump number -> flow rate
        self.pump_status = {}   # pump number -> on/off
        self.coolant_temp_avg = 293.0  # average coolant temperature (room temp)
        self.core_power = 0.0   # core power percentage
        self.power_output_mw = 0.0  # actual power in MW
        self.pressure = 100.0   # pressure bar (atmospheric)
        self.integrity = 100.0  # structural integrity percentage
        self.turbine_rpm = 0.0  # turbine speed
        self.turbine_power_mw = 0.0  # electrical power output
        self.radiation_level = 0.15  # control room radiation in mSv/h (baseline background)
        self.neutron_flux = {}  # rod number -> neutron flux level
        self.running = False    # reactor running state
        self.startup_in_progress = False  # prevent multiple startups
        self.alerts = {}  # alert status dictionary
        self.staged_commands = []  # commands staged for batch execution
        self.rod_temp_offsets = {}  # individual temperature offsets for each rod
        self.arccs_last_message_time = 0  # rate limiting for ARCCS messages
        self.arccs_recommendation = "System nominal - no action required"  # Current ARCCS recommendation
        self.arccs_commands = []  # Commands that ARCCS wants to execute

        # Main container
        main_frame = tk.Frame(root, bg="black")
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Detail overlay (initially hidden)
        self.detail_overlay = tk.Frame(root, bg="#000000", bd=3, relief="raised")
        self.detail_overlay.place_forget()  # Hidden initially

        # Left side: Grid
        left_frame = tk.Frame(main_frame, bg="black")
        left_frame.pack(side="left", padx=(0, 10), fill="both")

        frame = tk.Frame(left_frame, bg="black")
        frame.pack()

        number = 1

        for r in range(13):
            for c in range(13):
                letter = grid_letters[r][c]

                if letter == "P":
                    canvas = tk.Canvas(frame, width=CELL_SIZE, height=CELL_SIZE,
                                       bg="black", highlightthickness=0, bd=0)
                else:
                    canvas = tk.Canvas(frame, width=CELL_SIZE, height=CELL_SIZE,
                                       bg=OFF, highlightthickness=1,
                                       highlightbackground="#444")

                canvas.grid(row=r, column=c)

                if letter != "P":
                    canvas.create_text(5, 5, text=letter, anchor="nw",
                                       fill="white", font=("Helvetica", 9, "bold"))

                    canvas.create_text(CELL_SIZE-5, 5, text=str(number), anchor="ne",
                                       fill="#aaaaaa", font=("Helvetica", 8))

                    # Create 2x2 grid of boxes at bottom 2/5 of cell
                    # Bottom 1/5: temp (left), pressure (right)
                    # Second 1/5: fuel (left), flux (right)
                    box_height = CELL_SIZE // 5  # Each row is 1/5 of cell
                    box_width = (CELL_SIZE - 4) // 2  # 2 boxes across
                    
                    # Bottom row (temp and pressure)
                    bottom_y = CELL_SIZE - box_height - 2
                    
                    # Temperature box (bottom left)
                    temp_box = canvas.create_rectangle(2, bottom_y, 2 + box_width, CELL_SIZE - 2, 
                                                        fill="#1a1a1a", outline="#444", width=1)
                    temp_text = canvas.create_text(2 + box_width // 2, bottom_y + box_height // 2, 
                                                    text="", fill="white", font=("Courier", 6, "bold"))
                    
                    # Pressure box (bottom right)
                    pressure_box = canvas.create_rectangle(2 + box_width + 2, bottom_y, CELL_SIZE - 2, CELL_SIZE - 2,
                                                           fill="#1a1a1a", outline="#444", width=1)
                    pressure_text = canvas.create_text(2 + box_width + 2 + box_width // 2, bottom_y + box_height // 2,
                                                        text="", fill="white", font=("Courier", 6, "bold"))
                    
                    # Top row (fuel and flux) - second 1/5 from bottom
                    top_y = bottom_y - box_height - 1
                    
                    # Fuel box (top left)
                    fuel_box = canvas.create_rectangle(2, top_y, 2 + box_width, bottom_y - 1,
                                                        fill="#1a1a1a", outline="#444", width=1)
                    fuel_text = canvas.create_text(2 + box_width // 2, top_y + box_height // 2,
                                                    text="", fill="white", font=("Courier", 6, "bold"))
                    
                    # Neutron flux box (top right)
                    flux_box = canvas.create_rectangle(2 + box_width + 2, top_y, CELL_SIZE - 2, bottom_y - 1,
                                                        fill="#1a1a1a", outline="#444", width=1)
                    flux_text = canvas.create_text(2 + box_width + 2 + box_width // 2, top_y + box_height // 2,
                                                    text="", fill="white", font=("Courier", 6, "bold"))
                    
                    # Initialize individual temperature offset for this rod
                    self.rod_temp_offsets[number] = random.uniform(-5, 5)

                    # Initialize control rods to fully inserted (safe state)
                    if letter in CONTROL_RODS:
                        self.control_rod_levels[number] = 100  # 100% = fully inserted

                    self.num_to_cell[number] = (canvas, letter, temp_box, pressure_box, fuel_box, flux_box, 
                                                temp_text, pressure_text, fuel_text, flux_text)
                    self.num_to_pos[number] = (r, c)
                    self.state[number] = {"mode": "off", "flash": False, "phase": False}
                    
                    # Initialize fuel levels for fuel rods
                    if letter == "F":
                        self.fuel_levels[number] = 100.0

                    canvas.bind("<Button-1>",
                                lambda e, n=number: self.open_zoom(n))

                    number += 1

        # ARCCS log below grid
        arccs_label = tk.Label(left_frame, text="ARCCS (Automated Reactor Computer Control System)", 
                               bg="black", fg="#00aaff", font=("Helvetica", 10, "bold"))
        arccs_label.pack(anchor="w", pady=(10, 3))
        
        # ARCCS current recommendation (wrapping label)
        recommendation_frame = tk.Frame(left_frame, bg="#001a2a", relief="sunken", bd=1)
        recommendation_frame.pack(fill="x", pady=(0, 3))
        
        self.arccs_recommendation_box = tk.Label(recommendation_frame, text="System nominal - no action required",
                                                  bg="#001a2a", fg="#ffaa00", font=("Courier", 9, "bold"),
                                                  anchor="w", padx=5, justify="left", wraplength=600)
        self.arccs_recommendation_box.pack(fill="both", expand=True)

        self.arccs_text = tk.Text(left_frame, height=8, width=70, bg="#0a0a15", fg="#88ccff", 
                                  font=("Courier", 9), wrap="word")
        self.arccs_text.pack(fill="both", expand=False, pady=(0, 5))
        self.arccs_text.config(state="disabled")

        # Right side: Control panels
        right_frame = tk.Frame(main_frame, bg="black")
        right_frame.pack(side="right", fill="both", expand=True)

        # SCRAM button (prominent)
        scram_btn = tk.Button(right_frame, text="⚠ SCRAM ⚠",
                               command=self.scram,
                               font=("Helvetica", 15, "bold"),
                               bg="#ff0000", fg="#111",
                               activebackground="#cc0000", activeforeground="#ffffff",
                               highlightthickness=0)
        scram_btn.pack(fill="x", pady=(0, 10))

        # General buttons
        btn_frame = tk.Frame(right_frame, bg="#111")
        btn_frame.pack(fill="x", pady=(0, 10), padx=5)

        tk.Button(btn_frame, text="ACKNOWLEDGE",
                  command=self.acknowledge,
                  font=("Helvetica", 11, "bold"),
                  bg="#004400", fg="#00ff00",
                  activebackground="#006600", activeforeground="#ffffff",
                  highlightthickness=0).pack(fill="x", pady=(0, 3))

        # Status panels
        self.status_labels = {}
        panels_frame = tk.Frame(right_frame, bg="black")
        panels_frame.pack(fill="both", expand=True, pady=(0, 10))

        # Core status
        self.add_status_panel(panels_frame, "CORE", [
            ("Power:", "core_power", "%"),
            ("Output:", "power_mw", "MW"),
            ("Avg Temp:", "avg_temp", "K"),
        ])

        # System status
        self.add_status_panel(panels_frame, "SYSTEM", [
            ("Pressure:", "pressure", "bar"),
            ("Integrity:", "integrity", "%"),
        ])

        # Turbines
        self.add_status_panel(panels_frame, "TURBINES", [
            ("Speed:", "turbine_rpm", "RPM"),
            ("Power:", "turbine_mw", "MW"),
        ])

        # Radiation
        self.add_status_panel(panels_frame, "RADIATION", [
            ("Control Rm:", "radiation", "mSv/h"),
        ])

        # Pumps
        self.add_status_panel(panels_frame, "PUMPS", [
            ("Flow:", "pump_flow", "m³/h"),
            ("Status:", "pump_status", ""),
        ])

        # Alert Grid
        alert_label = tk.Label(right_frame, text="ALERTS", bg="black", fg="white", font=("Helvetica", 11, "bold"))
        alert_label.pack(anchor="w", padx=5, pady=(5, 3))
        
        self.alert_frame = tk.Frame(right_frame, bg="#111")
        self.alert_frame.pack(fill="x", padx=5, pady=(0, 10))
        
        alert_names = [
            ["Power Excursion", "Temp High", "Rod Drive Fault", "Overspeed Turbine"],
            ["Flux Tilt", "Temp Low", "Rod Rate Limit", "Underspeed Turbine"],
            ["Local Overpower", "ΔT High", "Refuel Interlock", "Load Mismatch"],
            ["Reactivity Drift", "Flow Low", "Position Fault", "Heat Sink Limit"]
        ]
        
        self.alert_lights = {}
        for r in range(4):
            for c in range(4):
                alert_name = alert_names[r][c]
                cell_frame = tk.Frame(self.alert_frame, bg="#222", highlightbackground="#333", highlightthickness=1)
                cell_frame.grid(row=r, column=c, padx=2, pady=2, sticky="nsew")
                
                light = tk.Canvas(cell_frame, width=8, height=8, bg="#1a1a1a", highlightthickness=0)
                light.pack(side="left", padx=2)
                
                label = tk.Label(cell_frame, text=alert_name, bg="#222", fg="#888", font=("Courier", 8), anchor="w")
                label.pack(side="left", fill="x", expand=True)
                
                self.alert_lights[alert_name] = light
                self.alerts[alert_name] = False
                
                # Make columns expand evenly
                self.alert_frame.grid_columnconfigure(c, weight=1)

        # Console
        console_label = tk.Label(right_frame, text="Console", bg="black", fg="white", font=("Helvetica", 11, "bold"))
        console_label.pack(anchor="w", pady=(5, 3))

        self.console_text = tk.Text(right_frame, height=12, width=50, bg="#1a1a1a", fg="#00ff00", font=("Courier", 9))
        self.console_text.pack(fill="both", expand=True, pady=(0, 10))
        self.console_text.config(state="disabled")

        # Command input
        input_label = tk.Label(right_frame, text="Command", bg="black", fg="white", font=("Helvetica", 11, "bold"))
        input_label.pack(anchor="w", padx=5)

        self.cmd_input = tk.Entry(right_frame, bg="#222", fg="white", font=("Courier", 10), insertbackground="white")
        self.cmd_input.pack(fill="x", padx=5, pady=(0, 5))
        self.cmd_input.bind("<Return>", self.submit_command)

        self.root.after(200, self.flash_loop)
        self.root.after(50, self.process_commands)
        self.root.after(1000, self.fluctuation_loop)  # Add fluctuation

        # Initial startup message
        self.log_console("╔════════════════════════════════════════════╗")
        self.log_console("║   RBMK REACTOR CONTROL STATION v1.0        ║")
        self.log_console("║   STATUS: OFFLINE                          ║")
        self.log_console("╚════════════════════════════════════════════╝")
        self.log_console("Type 'start' to begin startup sequence")
        self.log_console("Type 'help' for command list")
        
        # ARCCS initial message
        self.log_arccs("ARCCS v2.3 initialized - automatic control STANDBY")
        self.log_arccs("Background radiation: 0.15 mSv/h")
        self.log_arccs("System status: All parameters nominal")

    # -------- PHYSICS ENGINE --------
    def fluctuation_loop(self):
        """Realistic reactor physics simulation"""
        if self.running or self.startup_in_progress:
            # Calculate neutron flux for each fuel rod based on control rod positions
            self.calculate_neutron_flux()
            
            # Calculate reactor power from neutron flux (emergent property)
            self.calculate_reactor_power()
            
            # Calculate temperature from power generation vs cooling
            self.calculate_core_temperature()
            
            # Pressure fluctuations (±0.1-0.5 bar)
            self.pressure += random.uniform(-0.5, 0.5)
            
            # Pump flow fluctuations
            for pump_num in list(self.pump_flow.keys()):
                if self.pump_status.get(pump_num, False):
                    self.pump_flow[pump_num] += random.uniform(-2, 2)
            
            # Individual rod temperature offset fluctuations
            for rod_num in self.rod_temp_offsets:
                # Small drift in individual rod temperatures
                self.rod_temp_offsets[rod_num] += random.uniform(-0.5, 0.5)
                # Keep offsets in reasonable range (-10K to +10K)
                self.rod_temp_offsets[rod_num] = max(-10, min(10, self.rod_temp_offsets[rod_num]))
            
            # Differential fuel consumption based on neutron flux
            if self.core_power > 1:
                for fuel_num in self.fuel_levels:
                    # Get local neutron flux
                    flux = self.neutron_flux.get(fuel_num, 0.0)
                    # Consumption rate proportional to local flux
                    consumption = flux * 0.00008  # Slow realistic fuel depletion
                    self.fuel_levels[fuel_num] = max(0, self.fuel_levels[fuel_num] - consumption)
            
            # Update power output in MW (RBMK-1000 nominal is 3200 MW thermal)
            self.power_output_mw = (self.core_power / 100.0) * 3200
            
            # Turbine speed correlates with power
            target_rpm = 3000 * (self.core_power / 100.0)  # Nominal 3000 RPM
            self.turbine_rpm += (target_rpm - self.turbine_rpm) * 0.05
            self.turbine_rpm += random.uniform(-20, 20)
            
            # Electrical power output (about 1/3 of thermal for RBMK)
            self.turbine_power_mw = self.power_output_mw * 0.31
            
            # Radiation level increases with power and fuel consumption
            avg_fuel = sum(self.fuel_levels.values()) / max(len(self.fuel_levels), 1) if self.fuel_levels else 100
            base_radiation = 0.1  # Background
            power_radiation = (self.core_power / 100.0) * 0.5
            fuel_radiation = (100 - avg_fuel) * 0.01  # More radiation from depleted fuel
            self.radiation_level = base_radiation + power_radiation + fuel_radiation + random.uniform(-0.05, 0.05)
            
            # Slight integrity degradation when running hot
            if self.coolant_temp_avg > 550:
                self.integrity -= 0.0001
            
            # Update alerts based on conditions
            self.update_alerts()
            
            # ARCCS automated control logic (only when running)
            if self.running:
                self.arccs_control()
            
            # Check for rod problems and trigger flashing
            self.check_rod_problems()
            
            self.update_status_displays()
            self.update_grid_bars()
        
        self.root.after(1000, self.fluctuation_loop)

    def calculate_neutron_flux(self):
        """Calculate neutron flux at each fuel rod based on control rod positions"""
        # Clear previous flux
        self.neutron_flux.clear()
        
        for rod_num in self.fuel_levels.keys():
            if rod_num not in self.num_to_pos:
                continue
            
            # Fuel level affects maximum possible flux
            fuel_level = self.fuel_levels.get(rod_num, 100.0)
            if fuel_level < 1:
                self.neutron_flux[rod_num] = 0.0
                continue
                
            r, c = self.num_to_pos[rod_num]
            
            # Start with base flux proportional to remaining fuel
            base_flux = 1.0 * (fuel_level / 100.0)
            
            # Control rods absorb neutrons - calculate reduction
            flux_multiplier = 1.0
            
            # Check nearby control rods - they REDUCE flux when inserted
            for check_num, (check_r, check_c) in self.num_to_pos.items():
                if check_num in self.num_to_cell:
                    letter = self.num_to_cell[check_num][1]
                    if letter in CONTROL_RODS:
                        dist = ((r - check_r) ** 2 + (c - check_c) ** 2) ** 0.5
                        if dist < 4:  # Extended range for more realistic physics
                            # Get insertion level (0 = withdrawn, 100 = fully inserted)
                            insertion = self.control_rod_levels.get(check_num, 100)
                            # Calculate absorption effect
                            # More insertion = more neutron absorption = less flux
                            proximity_factor = 1.0 / (dist + 0.2)
                            absorption = (insertion / 100.0) * proximity_factor * 0.45
                            flux_multiplier *= (1.0 - absorption)
            
            # Final flux is base flux modified by control rod absorption
            flux = base_flux * flux_multiplier
            
            # Add small randomness for realistic variation
            flux *= random.uniform(0.97, 1.03)
            
            # Clamp to reasonable range
            self.neutron_flux[rod_num] = max(0.0, min(3.5, flux))
    
    def calculate_reactor_power(self):
        """Calculate reactor power from total neutron flux (emergent property)"""
        if not self.neutron_flux:
            self.core_power = 0.0
            return
        
        # Total power is sum of all fuel rod neutron flux
        total_flux = sum(self.neutron_flux.values())
        num_fuel_rods = len(self.fuel_levels)
        
        # Average flux across all fuel rods
        avg_flux = total_flux / max(num_fuel_rods, 1)
        
        # Power percentage is based on average flux
        # At criticality (avg_flux ~1.0), reactor is at ~100% power
        # Below criticality (avg_flux <1.0), power drops
        # Above criticality (avg_flux >1.0), power rises (dangerous!)
        self.core_power = avg_flux * 100.0
        
        # Clamp to safe operating range
        self.core_power = max(0.0, min(150.0, self.core_power))
    
    def calculate_core_temperature(self):
        """Calculate core temperature from power generation vs cooling"""
        # Heat generation from fission (proportional to power)
        # At 100% power, generates significant heat
        heat_generation = self.core_power * 2.5  # Base heat generation
        
        # Cooling from pumps (proportional to flow rate)
        # Normal operation: ~240 m³/h should maintain ~500K at 100% power
        total_flow = sum(self.pump_flow.values())
        
        # Cooling effectiveness depends on both flow and temperature
        # Higher temp = easier to cool (larger gradient), but needs more cooling
        temp_above_ambient = max(0, self.coolant_temp_avg - 293.0)
        
        # Base cooling from flow (reduced significantly)
        flow_cooling = total_flow * 0.3
        
        # Temperature-dependent natural cooling (increases with temp)
        natural_cooling = temp_above_ambient * 0.15
        
        total_cooling = flow_cooling + natural_cooling
        
        # Net temperature change per second
        net_change = (heat_generation - total_cooling) * 0.15
        
        # Apply temperature change
        self.coolant_temp_avg += net_change
        
        # Small fluctuations
        self.coolant_temp_avg += random.uniform(-0.5, 0.5)
        
        # Physical limits
        self.coolant_temp_avg = max(293.0, min(800.0, self.coolant_temp_avg))
        
        # Physical limits
        self.coolant_temp_avg = max(293.0, min(800.0, self.coolant_temp_avg))

    def update_alerts(self):
        """Update alert statuses based on reactor conditions"""
        # Temperature alerts
        self.alerts["Temp High"] = self.coolant_temp_avg > 550
        self.alerts["Temp Low"] = self.coolant_temp_avg < 350 and self.running
        
        # Power alerts
        self.alerts["Power Excursion"] = self.core_power > 105
        self.alerts["Local Overpower"] = self.core_power > 100
        
        # Flow alerts
        avg_flow = sum(self.pump_flow.values()) / max(len(self.pump_flow), 1) if self.pump_flow else 0
        self.alerts["Flow Low"] = avg_flow < 80 and self.running
        
        # Pressure alert
        self.alerts["ΔT High"] = abs(self.pressure - 155) > 20 and self.running
        
        # Integrity alert
        self.alerts["Heat Sink Limit"] = self.integrity < 95
        
        # Turbine alerts
        self.alerts["Overspeed Turbine"] = self.turbine_rpm > 3200
        self.alerts["Underspeed Turbine"] = self.turbine_rpm < 2800 and self.running
        
        # Reactivity drift (flux variation)
        if self.neutron_flux:
            flux_values = list(self.neutron_flux.values())
            flux_std = (max(flux_values) - min(flux_values)) if flux_values else 0
            self.alerts["Reactivity Drift"] = flux_std > 0.5
            self.alerts["Flux Tilt"] = flux_std > 0.7

    # -------- FLASH ENGINE --------
    def flash_loop(self):
        for n, info in self.state.items():
            if not info["flash"]:
                continue

            canvas = self.num_to_cell[n][0]
            info["phase"] = not info["phase"]

            colour = RED if info["mode"] == "red" else YELLOW
            canvas.configure(bg=colour if info["phase"] else FLASH_DARK)

        self.root.after(400, self.flash_loop)

    def check_rod_problems(self):
        """Check each rod for problems and trigger yellow (problem) or red (critical) flashing"""
        if not self.running:
            # Turn off all flashing when not running
            for rod_num in self.num_to_cell.keys():
                if self.state[rod_num]["flash"]:
                    self.turn_off(rod_num)
            return
        
        for rod_num in self.num_to_cell.keys():
            # Calculate rod parameters
            temp = self.calculate_rod_temperature(rod_num)
            pressure = self.calculate_rod_pressure(rod_num)
            flux = self.neutron_flux.get(rod_num, 0.0)
            fuel_level = self.fuel_levels.get(rod_num, 100.0)
            letter = self.num_to_cell[rod_num][1]
            
            # Determine problem level
            is_critical = False
            is_problem = False
            
            # Critical conditions (RED)
            if temp > 600:  # Very high temperature
                is_critical = True
            elif pressure > 165:  # Very high pressure
                is_critical = True
            elif flux > 2.5:  # Very high neutron flux
                is_critical = True
            elif letter == "F" and fuel_level < 15:  # Critical fuel low
                is_critical = True
            
            # Problem conditions (YELLOW) - only if not already critical
            if not is_critical:
                if temp > 550:  # High temperature
                    is_problem = True
                elif pressure > 160:  # High pressure
                    is_problem = True
                elif flux > 2.0:  # High neutron flux
                    is_problem = True
                elif letter == "F" and fuel_level < 30:  # Low fuel
                    is_problem = True
            
            # Update flashing state
            if is_critical:
                if self.state[rod_num]["mode"] != "red" or not self.state[rod_num]["flash"]:
                    self.trigger(rod_num, "red")
            elif is_problem:
                if self.state[rod_num]["mode"] != "yellow" or not self.state[rod_num]["flash"]:
                    self.trigger(rod_num, "yellow")
            else:
                # No problem - turn off flashing
                if self.state[rod_num]["flash"]:
                    self.turn_off(rod_num)

    # -------- CONTROL --------
    def trigger(self, n, colour):
        if n not in self.state:
            return
        self.state[n]["mode"] = colour
        self.state[n]["flash"] = True

    def turn_off(self, n):
        if n not in self.state:
            return
        canvas = self.num_to_cell[n][0]
        self.state[n] = {"mode": "off", "flash": False, "phase": False}
        canvas.configure(bg=OFF)

    def all_off(self):
        for n in list(self.state.keys()):
            self.turn_off(n)

    def acknowledge(self):
        for n, info in self.state.items():
            if info["mode"] in ("red", "yellow"):
                info["flash"] = False
                canvas = self.num_to_cell[n][0]
                canvas.configure(bg=RED if info["mode"] == "red" else YELLOW)

    def scram(self):
        """SCRAM button - emergency shutdown"""
        if not self.running:
            self.log_console("Reactor is already offline")
            return
            
        self.log_console("="*50)
        self.log_console("!!! SCRAM ACTIVATED !!!")
        self.log_console("="*50)
        
        # Immediately insert all control rods
        self.log_console("Inserting ALL control rods to 100%...")
        for pos in self.control_rod_levels.keys():
            self.control_rod_levels[pos] = 100.0
        
        # Set cooling to maximum emergency flow (125 m³/h per pump = 250 total)
        self.log_console("Setting emergency cooling to 250 m³/h...")
        self.pump_flow[1] = 125.0
        self.pump_flow[2] = 125.0
        self.pump_status[1] = True
        self.pump_status[2] = True
        
        self.log_console("✓ All control rods: 100% INSERTED")
        self.log_console("✓ Emergency cooling: 250 m³/h")
        self.log_console("Fission chain reaction terminated")
        self.log_console("Physics will naturally bring reactor to safe state...")
        self.log_console("="*50)
        
        self.running = False
        self.log_arccs("SCRAM executed - all control rods inserted, emergency cooling active")
        self.log_arccs("Reactor entering automatic decay heat removal mode")
        
        self.root.after(0, self.update_core_display)
        self.root.after(0, self.update_status_displays)

    def request_startup_pin(self):
        """Request PIN for reactor startup"""
        pin_window = tk.Toplevel(self.root)
        pin_window.title("Reactor Startup - Authentication")
        pin_window.configure(bg="#111")
        pin_window.geometry("300x150")
        pin_window.resizable(False, False)

        tk.Label(pin_window, text="REACTOR STARTUP", bg="#111", fg="#ffff00", font=("Helvetica", 15, "bold")).pack(pady=10)
        tk.Label(pin_window, text="Enter startup code:", bg="#111", fg="#ffffff", font=("Helvetica", 11)).pack()

        pin_entry = tk.Entry(pin_window, show="*", font=("Courier", 18), width=10)
        pin_entry.pack(pady=10)
        pin_entry.focus()

        result = {"authenticated": False}

        def check_pin():
            if pin_entry.get() == "1234":
                result["authenticated"] = True
                pin_window.destroy()
            else:
                pin_entry.delete(0, tk.END)
                tk.Label(pin_window, text="INVALID CODE", bg="#111", fg="#ff0000", font=("Helvetica", 11, "bold")).pack()

        tk.Button(pin_window, text="OK", command=check_pin, bg="#004400", fg="#00ff00", font=("Helvetica", 11, "bold")).pack(pady=5)
        pin_entry.bind("<Return>", lambda e: check_pin())

        self.root.wait_window(pin_window)
        return result["authenticated"]

    def startup_sequence(self):
        """Realistic startup sequence - only manipulates physical controls"""
        if self.startup_in_progress:
            self.log_console("ERROR: Startup already in progress")
            return

        self.startup_in_progress = True
        self.log_console("\n" + "="*50)
        self.log_console("REACTOR STARTUP SEQUENCE INITIATED")
        self.log_console("="*50)

        # Phase 1: Pre-startup checks
        self.log_console("Phase 1: Pre-startup safety checks")
        time.sleep(0.8)
        self.log_console("  Checking safety systems...")
        time.sleep(1.2)
        self.log_console("  ✓ Emergency cooling: READY")
        time.sleep(0.5)
        self.log_console("  ✓ Radiation monitoring: NOMINAL")
        time.sleep(0.5)
        self.log_console("  ✓ Containment integrity: VERIFIED")
        time.sleep(0.8)
        
        # Ensure all control rods are fully inserted
        self.log_console("\n  Verifying control rod positions...")
        for rod_num, cell_data in self.num_to_cell.items():
            letter = cell_data[1]
            if letter in CONTROL_RODS:
                self.control_rod_levels[rod_num] = 100  # Full insertion
        time.sleep(1.0)
        self.log_console("  ✓ All 16 control rods at full insertion")
        time.sleep(0.5)
        self.log_console("  ✓ Rod drive mechanisms: OPERATIONAL")
        time.sleep(0.8)
        
        # Phase 2: Cooling system startup
        self.log_console("\nPhase 2: Cooling system initialization")
        time.sleep(0.8)
        self.log_console("  Starting primary circulation pump #1...")
        self._gradual_pump_startup(1, 120.0)
        
        self.log_console("  Starting primary circulation pump #2...")
        self._gradual_pump_startup(2, 120.0)
        
        self.log_console("  ✓ Primary coolant circulation: 240 m³/h total")
        time.sleep(0.8)
        
        # Phase 3: Pressurization
        self.log_console("\nPhase 3: System pressurization")
        time.sleep(0.6)
        self.log_console("  Pressurizing primary circuit to 140 bar...")
        self._gradual_pressure_startup(100, 140)
        self.log_console("  ✓ System pressure: 140 bar")
        time.sleep(0.8)
        
        # Phase 4: Approach to criticality
        self.log_console("\nPhase 4: Nuclear startup - approaching criticality")
        time.sleep(1.0)
        
        # Withdraw manual control rods gradually
        self.log_console("  Withdrawing control rods (Group 1: 100% → 70%)...")
        self._withdraw_control_rods_gradual(100, 70, rod_group=1)
        time.sleep(0.5)
        self.log_console(f"  Neutron flux: {sum(self.neutron_flux.values())/max(len(self.neutron_flux),1):.3f}x")
        self.log_console(f"  Power: {self.core_power:.1f}% (subcritical)")
        time.sleep(1.0)
        
        self.log_console("  Withdrawing control rods (Group 1: 70% → 40%)...")
        self._withdraw_control_rods_gradual(70, 40, rod_group=1)
        time.sleep(0.5)
        self.log_console(f"  Neutron flux: {sum(self.neutron_flux.values())/max(len(self.neutron_flux),1):.3f}x")
        self.log_console(f"  Power: {self.core_power:.1f}%")
        time.sleep(1.0)
        
        self.log_console("  ✓ CRITICALITY ACHIEVED - Self-sustaining chain reaction")
        time.sleep(0.8)
        
        # Phase 5: Power escalation
        self.log_console("\nPhase 5: Power escalation to nominal operating level")
        time.sleep(0.8)
        
        self.log_console("  Withdrawing control rods (Group 1: 40% → 20%)...")
        self.log_console("  Monitoring: Power ramping to 25%...")
        self._withdraw_control_rods_gradual(40, 20, rod_group=1)
        time.sleep(1.0)
        self.log_console(f"  ✓ Power: {self.core_power:.1f}%, Temp: {self.coolant_temp_avg:.0f}K")
        
        self.log_console("\n  Withdrawing control rods (Group 2: 100% → 50%)...")
        self.log_console("  Monitoring: Power ramping to 50%...")
        self._withdraw_control_rods_gradual(100, 50, rod_group=2)
        time.sleep(1.0)
        self.log_console(f"  ✓ Power: {self.core_power:.1f}%, Temp: {self.coolant_temp_avg:.0f}K")
        
        self.log_console("\n  Final pressurization to operating pressure...")
        self._gradual_pressure_startup(140, 155)
        self.log_console("  ✓ System pressure: 155 bar")
        time.sleep(0.8)
        
        self.log_console("\n  Withdrawing control rods (Group 2: 50% → 15%)...")
        self.log_console("  Monitoring: Power ramping to 100%...")
        self._withdraw_control_rods_gradual(50, 15, rod_group=2)
        time.sleep(2.0)
        
        # Withdraw auto rods to operational position for ARCCS control
        self.log_console("\n  Positioning AUTO control rods for ARCCS operation...")
        auto_rods = [num for num, cell_data in self.num_to_cell.items() if cell_data[1] == "A"]
        for rod_num in auto_rods:
            self.control_rod_levels[rod_num] = 50  # 50% insertion - middle position for ARCCS
        self.log_console(f"  ✓ {len(auto_rods)} AUTO rods set to 50% insertion")
        self.log_console("  ✓ ARCCS automatic control ready")
        self.log_arccs(f"AUTO: {len(auto_rods)} auto rods initialized at 50% insertion for reactivity control")
        time.sleep(1.0)
        
        # Mark reactor as running
        self.running = True
        
        # Final status
        self.log_console("\n" + "="*50)
        self.log_console("REACTOR STARTUP COMPLETE")
        self.log_console("  Status: ONLINE")
        self.log_console(f"  Power: {self.core_power:.1f}% ({self.power_output_mw:.0f} MW thermal)")
        self.log_console(f"  Temperature: {self.coolant_temp_avg:.0f}K")
        self.log_console(f"  Pressure: {self.pressure:.1f} bar")
        self.log_console(f"  Coolant flow: {sum(self.pump_flow.values()):.0f} m³/h")
        self.log_console("  All systems: NOMINAL")
        self.log_console("="*50)
        
        self.log_arccs("Reactor startup complete - automatic control ACTIVE")
        self.log_arccs("All systems nominal - monitoring core parameters")
        
        self.startup_in_progress = False

    def _gradual_pump_startup(self, pump_num, target):
        """Helper for gradual pump changes during startup"""
        step = 3.0
        while self.pump_flow.get(pump_num, 0) < target:
            new_flow = min(self.pump_flow.get(pump_num, 0) + step, target)
            self.pump_flow[pump_num] = new_flow
            self.pump_status[pump_num] = True
            self.root.after(0, self.update_status_displays)
            time.sleep(0.08)

    def _gradual_pressure_startup(self, current, target):
        """Helper for gradual pressure changes during startup"""
        self.pressure = current
        step = 0.8 if target > current else -0.8
        while abs(self.pressure - target) > 0.5:
            self.pressure += step
            self.root.after(0, self.update_status_displays)
            time.sleep(0.08)
        self.pressure = target
        self.root.after(0, self.update_status_displays)
    
    def _withdraw_control_rods_gradual(self, start_insertion, target_insertion, rod_group=1):
        """Withdraw control rods gradually (realistic startup procedure)"""
        # Get control rods for this group
        control_rods = [num for num, cell_data in self.num_to_cell.items() 
                       if cell_data[1] == 'C']  # Manual control rods only
        
        # Divide into groups for sequential withdrawal
        group_size = len(control_rods) // 2
        if rod_group == 1:
            selected_rods = control_rods[:group_size]
        else:
            selected_rods = control_rods[group_size:]
        
        # Gradually withdraw from start to target insertion
        current = start_insertion
        step = -2.0  # Withdraw 2% at a time
        
        while current > target_insertion:
            current = max(target_insertion, current + step)
            for rod_num in selected_rods:
                self.control_rod_levels[rod_num] = current
            
            self.root.after(0, self.update_status_displays)
            time.sleep(0.15)  # Realistic rod movement speed

    # -------- STATUS PANELS --------
    def add_status_panel(self, parent, title, fields):
        """Add a status display panel"""
        panel = tk.Frame(parent, bg="#111", highlightbackground="#333", highlightthickness=1)
        panel.pack(fill="x", pady=3, padx=5)

        title_label = tk.Label(panel, text=title, bg="#222", fg="#ffff00", font=("Helvetica", 10, "bold"))
        title_label.pack(fill="x", padx=3, pady=2)

        for label_text, key, unit in fields:
            row = tk.Frame(panel, bg="#111")
            row.pack(fill="x", padx=5, pady=1)

            tk.Label(row, text=label_text, bg="#111", fg="#aaaaaa", font=("Courier", 9), width=10, anchor="w").pack(side="left")
            value_label = tk.Label(row, text="--", bg="#111", fg="#00ff00", font=("Courier", 9, "bold"), anchor="w")
            value_label.pack(side="left", expand=True, fill="x")
            tk.Label(row, text=unit, bg="#111", fg="#888888", font=("Courier", 9), width=6, anchor="e").pack(side="left")

            self.status_labels[key] = value_label

    def arccs_control(self):
        """ARCCS automated control logic - adjusts auto rods and provides recommendations"""
        if not self.running:
            self.arccs_recommendation = "System nominal - no action required"
            self.arccs_recommendation_box.config(text=self.arccs_recommendation)
            self.arccs_commands = []
            return
        
        current_time = time.time()
        recommendation_parts = []
        self.arccs_commands = []  # Clear previous commands
        
        # Check power deviation and actively control auto rods
        if self.core_power > 103:
            # Power excursion - insert auto rods aggressively
            auto_rods = [num for num, cell_data in self.num_to_cell.items() if cell_data[1] == "A"]
            adjusted = False
            avg_insertion = 0
            for rod_num in auto_rods:
                current_insertion = self.control_rod_levels.get(rod_num, 100)  # Default to fully inserted
                if current_insertion < 95:
                    # More aggressive insertion for high power
                    new_insertion = min(95, current_insertion + 5)
                    self.control_rod_levels[rod_num] = new_insertion
                    adjusted = True
                avg_insertion += self.control_rod_levels.get(rod_num, 100)
            
            if auto_rods:
                avg_insertion /= len(auto_rods)
            
            if adjusted and (current_time - self.arccs_last_message_time) > 10:
                self.log_arccs(f"AUTO: Power {self.core_power:.1f}% - auto rods inserting (avg {avg_insertion:.1f}%)")
                self.arccs_last_message_time = current_time
            
            # Recommend manual control rod insertion
            self.arccs_commands.append("set * 75")
            recommendation_parts.append("CRITICAL: Run 'arccs accept' - Insert all control rods to 75%")
            
        elif self.core_power < 97 and self.core_power > 50:
            # Power deficit - withdraw auto rods
            auto_rods = [num for num, cell_data in self.num_to_cell.items() if cell_data[1] == "A"]
            adjusted = False
            avg_insertion = 0
            for rod_num in auto_rods:
                current_insertion = self.control_rod_levels.get(rod_num, 100)  # Default to fully inserted
                if current_insertion > 5:
                    new_insertion = max(5, current_insertion - 5)
                    self.control_rod_levels[rod_num] = new_insertion
                    adjusted = True
                avg_insertion += self.control_rod_levels.get(rod_num, 100)
            
            if auto_rods:
                avg_insertion /= len(auto_rods)
            
            if adjusted and (current_time - self.arccs_last_message_time) > 10:
                self.log_arccs(f"AUTO: Power {self.core_power:.1f}% - auto rods withdrawing (avg {avg_insertion:.1f}%)")
                self.arccs_last_message_time = current_time
        
        # Check temperature and generate recommendation
        if self.coolant_temp_avg > 530:
            self.arccs_commands.append("set * 70")
            self.arccs_commands.append("pump * 140")
            recommendation_parts.append(f"URGENT: Temp {self.coolant_temp_avg:.0f}K - Run 'arccs accept'")
            if (current_time - self.arccs_last_message_time) > 15:
                self.log_arccs(f"WARN: Coolant temp {self.coolant_temp_avg:.0f}K critical")
                self.arccs_last_message_time = current_time
        elif self.coolant_temp_avg > 515:
            recommendation_parts.append(f"CAUTION: Temp {self.coolant_temp_avg:.0f}K - Consider reducing power")
        
        # Check neutron flux imbalance
        if self.neutron_flux and len(self.neutron_flux) > 10:
            max_flux = max(self.neutron_flux.values())
            min_flux = min(self.neutron_flux.values())
            if max_flux > min_flux * 2.0:
                # Find high-flux rods
                high_flux_rods = [num for num, flux in self.neutron_flux.items() if flux > 1.5]
                if high_flux_rods:
                    rod_list = ", ".join(str(r) for r in high_flux_rods[:5])
                    # Create set commands for high flux rods
                    for rod_num in high_flux_rods[:5]:
                        self.arccs_commands.append(f"set {rod_num} 60")
                    recommendation_parts.append(f"Flux tilt {max_flux/min_flux:.1f}x - Run 'arccs accept'")
                    if (current_time - self.arccs_last_message_time) > 20:
                        self.log_arccs(f"WARN: Neutron flux imbalance detected - ratio {max_flux/min_flux:.2f}")
                        self.arccs_last_message_time = current_time
        
        # Check fuel status (only log occasionally)
        if self.fuel_levels:
            avg_fuel = sum(self.fuel_levels.values()) / len(self.fuel_levels)
            critical_fuel_rods = [num for num, level in self.fuel_levels.items() if level < 15]
            
            if critical_fuel_rods:
                recommendation_parts.append(f"CRITICAL: {len(critical_fuel_rods)} rods <15% fuel - SCRAM and refuel required")
                if (current_time - self.arccs_last_message_time) > 30:
                    self.log_arccs(f"CRITICAL: {len(critical_fuel_rods)} fuel rods critically depleted")
                    self.arccs_last_message_time = current_time
            elif avg_fuel < 30 and (current_time - self.arccs_last_message_time) > 60:
                self.log_arccs(f"INFO: Average fuel at {avg_fuel:.1f}% - schedule refueling within 24h")
                self.arccs_last_message_time = current_time
        
        # Check pump status
        pump1_flow = self.pump_flow.get(1, 0)
        pump2_flow = self.pump_flow.get(2, 0)
        if self.core_power > 80:
            if pump1_flow < 100 or pump2_flow < 100:
                self.arccs_commands.append("pump * 120")
                recommendation_parts.append(f"Coolant flow low - Run 'arccs accept'")
                if (current_time - self.arccs_last_message_time) > 12:
                    self.log_arccs(f"WARN: Insufficient coolant flow at {self.core_power:.0f}% power")
                    self.arccs_last_message_time = current_time
        
        # Update recommendation display
        if recommendation_parts:
            self.arccs_recommendation = " | ".join(recommendation_parts)
        else:
            self.arccs_recommendation = "System nominal - all parameters within limits"
        
        self.arccs_recommendation_box.config(text=self.arccs_recommendation)

    def update_status_displays(self):
        """Update all status display labels"""
        if "core_power" in self.status_labels:
            self.status_labels["core_power"].config(text=f"{self.core_power:.1f}")

        if "power_mw" in self.status_labels:
            self.status_labels["power_mw"].config(text=f"{self.power_output_mw:.0f}")

        if "pressure" in self.status_labels:
            self.status_labels["pressure"].config(text=f"{self.pressure:.1f}")

        if "integrity" in self.status_labels:
            color = "#00ff00" if self.integrity > 90 else "#ffff00" if self.integrity > 70 else "#ff6666"
            self.status_labels["integrity"].config(text=f"{self.integrity:.1f}", fg=color)

        if "avg_temp" in self.status_labels:
            avg = self.coolant_temp_avg
            self.status_labels["avg_temp"].config(text=f"{avg:.0f}")

        if "pump_flow" in self.status_labels:
            flow = self.pump_flow.get(1, 0)
            self.status_labels["pump_flow"].config(text=f"{flow:.0f}")

        if "pump_status" in self.status_labels:
            status = "ON" if self.pump_status.get(1, False) else "OFF"
            color = "#00ff00" if self.pump_status.get(1, False) else "#ff6666"
            self.status_labels["pump_status"].config(text=status, fg=color)
        
        if "turbine_rpm" in self.status_labels:
            self.status_labels["turbine_rpm"].config(text=f"{self.turbine_rpm:.0f}")
        
        if "turbine_mw" in self.status_labels:
            self.status_labels["turbine_mw"].config(text=f"{self.turbine_power_mw:.0f}")
        
        if "radiation" in self.status_labels:
            color = "#00ff00" if self.radiation_level < 1.0 else "#ffff00" if self.radiation_level < 5.0 else "#ff6666"
            self.status_labels["radiation"].config(text=f"{self.radiation_level:.2f}", fg=color)
        
        # Update alert lights
        for alert_name, is_active in self.alerts.items():
            if alert_name in self.alert_lights:
                color = "#ff0000" if is_active else "#1a1a1a"
                self.alert_lights[alert_name].config(bg=color)
        
        # Update temperature and pressure bars on grid
        self.update_grid_bars()

    def update_grid_bars(self):
        """Update the 4 indicator boxes on each rod: temp, pressure, fuel, neutron flux"""
        for rod_num, cell_data in self.num_to_cell.items():
            canvas = cell_data[0]
            letter = cell_data[1]
            temp_box = cell_data[2]
            pressure_box = cell_data[3]
            fuel_box = cell_data[4]
            flux_box = cell_data[5]
            temp_text = cell_data[6]
            pressure_text = cell_data[7]
            fuel_text = cell_data[8]
            flux_text = cell_data[9]
            
            # Calculate temperature and pressure for this rod
            temp = self.calculate_rod_temperature(rod_num)
            pressure = self.calculate_rod_pressure(rod_num)
            fuel_level = self.fuel_levels.get(rod_num, 100.0) if letter == "F" else 0.0
            flux = self.neutron_flux.get(rod_num, 0.0)
            
            # Temperature box: map 250K-700K to color gradient
            temp_norm = max(0, min(1, (temp - 250) / 450))
            if temp_norm < 0.5:
                # Blue to yellow
                temp_color = self._lerp_color("#0055cc", "#ffcc00", temp_norm * 2)
                temp_text_color = "black" if temp_norm > 0.3 else "white"
            else:
                # Yellow to red
                temp_color = self._lerp_color("#ffcc00", "#ff0000", (temp_norm - 0.5) * 2)
                temp_text_color = "black" if temp_norm < 0.7 else "white"
            
            # Pressure box: map 90-170 bar to color gradient
            pressure_norm = max(0, min(1, (pressure - 90) / 80))
            if pressure_norm < 0.5:
                # Green to yellow
                pressure_color = self._lerp_color("#00aa00", "#ffcc00", pressure_norm * 2)
                pressure_text_color = "black" if pressure_norm > 0.3 else "white"
            else:
                # Yellow to red
                pressure_color = self._lerp_color("#ffcc00", "#ff0000", (pressure_norm - 0.5) * 2)
                pressure_text_color = "black" if pressure_norm < 0.7 else "white"
            
            # Fuel box: green to yellow to red based on fuel level
            if fuel_level > 50:
                fuel_norm = (fuel_level - 50) / 50
                fuel_color = self._lerp_color("#ffcc00", "#00aa00", fuel_norm)
                fuel_text_color = "black"
            elif fuel_level > 0:
                fuel_norm = fuel_level / 50
                fuel_color = self._lerp_color("#ff0000", "#ffcc00", fuel_norm)
                fuel_text_color = "white" if fuel_level < 25 else "black"
            else:
                fuel_color = "#1a1a1a"
                fuel_text_color = "#666"
            
            # Neutron flux box: low (blue) to high (red)
            flux_norm = max(0, min(1, flux / 3.0))  # 0-3x range
            if flux_norm < 0.5:
                flux_color = self._lerp_color("#0055cc", "#ffcc00", flux_norm * 2)
                flux_text_color = "black" if flux_norm > 0.3 else "white"
            else:
                flux_color = self._lerp_color("#ffcc00", "#ff0000", (flux_norm - 0.5) * 2)
                flux_text_color = "black" if flux_norm < 0.7 else "white"
            
            # Update box colors
            canvas.itemconfig(temp_box, fill=temp_color)
            canvas.itemconfig(pressure_box, fill=pressure_color)
            canvas.itemconfig(fuel_box, fill=fuel_color)
            canvas.itemconfig(flux_box, fill=flux_color)
            
            # Update text values with contrast
            canvas.itemconfig(temp_text, text=f"{int(temp)}", fill=temp_text_color)
            canvas.itemconfig(pressure_text, text=f"{int(pressure)}", fill=pressure_text_color)
            
            if fuel_level > 0:
                canvas.itemconfig(fuel_text, text=f"{int(fuel_level)}", fill=fuel_text_color)
            else:
                canvas.itemconfig(fuel_text, text="-", fill=fuel_text_color)
            
            if flux > 0.01:
                canvas.itemconfig(flux_text, text=f"{flux:.1f}", fill=flux_text_color)
            else:
                canvas.itemconfig(flux_text, text="-", fill=flux_text_color)
    
    def _lerp_color(self, color1, color2, t):
        """Linearly interpolate between two hex colors"""
        r1, g1, b1 = int(color1[1:3], 16), int(color1[3:5], 16), int(color1[5:7], 16)
        r2, g2, b2 = int(color2[1:3], 16), int(color2[3:5], 16), int(color2[5:7], 16)
        
        r = int(r1 + (r2 - r1) * t)
        g = int(g1 + (g2 - g1) * t)
        b = int(b1 + (b2 - b1) * t)
        
        return f"#{r:02x}{g:02x}{b:02x}"

    # -------- GRADUAL PARAMETER CHANGES --------
    def gradual_power_change(self, target):
        """Gradually change reactor power"""
        current = self.core_power
        diff = abs(target - current)
        step = 0.2 if target > current else -0.2
        delay = 0.2  # Slower, more realistic
        
        self.log_console(f"Power adjustment: {current:.1f}% → {target:.1f}%")
        
        while abs(self.core_power - target) > 0.1:
            self.core_power += step
            if (step > 0 and self.core_power > target) or (step < 0 and self.core_power < target):
                self.core_power = target
            self.root.after(0, self.update_status_displays)
            time.sleep(delay)
        
        self.core_power = target
        self.root.after(0, self.update_status_displays)
        self.log_console(f"✓ Power stabilized at {target:.1f}%")

    def gradual_pressure_change(self, target):
        """Gradually change system pressure"""
        current = self.pressure
        step = 0.3 if target > current else -0.3
        delay = 0.15
        
        self.log_console(f"Pressure adjustment: {current:.1f} bar → {target:.1f} bar")
        
        while abs(self.pressure - target) > 0.1:
            self.pressure += step
            if (step > 0 and self.pressure > target) or (step < 0 and self.pressure < target):
                self.pressure = target
            self.root.after(0, self.update_status_displays)
            time.sleep(delay)
        
        self.pressure = target
        self.root.after(0, self.update_status_displays)
        self.log_console(f"✓ Pressure stabilized at {target:.1f} bar")

    def gradual_pump_change(self, pump_num, target_flow):
        """Gradually change pump flow rate"""
        current_flow = self.pump_flow.get(pump_num, 0)
        step = 1.5 if target_flow > current_flow else -1.5
        delay = 0.1
        
        self.log_console(f"Pump {pump_num} adjustment: {current_flow:.0f} m³/h → {target_flow:.0f} m³/h")
        
        while abs(self.pump_flow.get(pump_num, 0) - target_flow) > 1.0:
            new_flow = self.pump_flow.get(pump_num, 0) + step
            if (step > 0 and new_flow > target_flow) or (step < 0 and new_flow < target_flow):
                new_flow = target_flow
            self.pump_flow[pump_num] = new_flow
            self.pump_status[pump_num] = new_flow > 0
            self.root.after(0, self.update_status_displays)
            time.sleep(delay)
        
        self.pump_flow[pump_num] = target_flow
        self.pump_status[pump_num] = target_flow > 0
        self.root.after(0, self.update_status_displays)
        self.log_console(f"✓ Pump {pump_num} stabilized at {target_flow:.0f} m³/h")

    def gradual_temp_change(self, target):
        """Gradually change average temperature"""
        current = self.coolant_temp_avg
        step = 2.0 if target > current else -2.0
        delay = 0.2
        
        self.log_console(f"Temperature adjustment: {current:.0f}K → {target:.0f}K")
        
        while abs(self.coolant_temp_avg - target) > 1.0:
            self.coolant_temp_avg += step
            if (step > 0 and self.coolant_temp_avg > target) or (step < 0 and self.coolant_temp_avg < target):
                self.coolant_temp_avg = target
            self.root.after(0, self.update_status_displays)
            time.sleep(delay)
        
        self.coolant_temp_avg = target
        self.root.after(0, self.update_status_displays)
        self.log_console(f"✓ Temperature stabilized at {target:.0f}K")

    # -------- TEMPERATURE CALCULATIONS --------
    def calculate_temperature(self, rod_num):
        """Calculate temperature for a T rod based on nearby T sensors"""
        if rod_num not in self.num_to_pos:
            return 293.0

        # If this rod has an explicit temperature set, use it
        if rod_num in self.temperatures:
            return self.temperatures[rod_num]

        # Find all T sensors and calculate weighted average
        r, c = self.num_to_pos[rod_num]
        temps = []
        distances = []

        for check_num, (check_r, check_c) in self.num_to_pos.items():
            if check_num in self.num_to_cell:
                letter = self.num_to_cell[check_num][1]
                if letter == "T" and check_num in self.temperatures:
                    dist = ((r - check_r) ** 2 + (c - check_c) ** 2) ** 0.5
                    if dist > 0:
                        temps.append(self.temperatures[check_num])
                        distances.append(dist)

        if temps:
            # Weighted average by inverse distance
            weights = [1.0 / (d + 0.1) for d in distances]
            total_weight = sum(weights)
            weighted_avg = sum(t * w for t, w in zip(temps, weights)) / total_weight
            return weighted_avg

        return 293.0  # Default room temperature if no nearby sensors

    def calculate_rod_temperature(self, rod_num):
        """Calculate temperature for any rod based on nearest 3 T sensors"""
        if rod_num not in self.num_to_pos:
            return 293.0

        # If this is a T rod with explicit temperature, use it
        cell_data = self.num_to_cell.get(rod_num, (None, None, None, None))
        letter = cell_data[1] if cell_data[0] else None
        if letter == "T" and rod_num in self.temperatures:
            return self.temperatures[rod_num]

        # Find all T sensors with set temperatures
        r, c = self.num_to_pos[rod_num]
        sensor_data = []

        for check_num, (check_r, check_c) in self.num_to_pos.items():
            if check_num in self.num_to_cell:
                check_letter = self.num_to_cell[check_num][1]
                if check_letter == "T" and check_num in self.temperatures:
                    dist = ((r - check_r) ** 2 + (c - check_c) ** 2) ** 0.5
                    sensor_data.append((dist, self.temperatures[check_num]))

        if not sensor_data:
            return self.coolant_temp_avg  # Use average if no sensors

        # Sort by distance and take nearest 3
        sensor_data.sort(key=lambda x: x[0])
        nearest_3 = sensor_data[:3]

        # Weighted average by inverse distance
        weights = [1.0 / (d + 0.1) for d, _ in nearest_3]
        total_weight = sum(weights)
        weighted_avg = sum(temp * w for (_, temp), w in zip(nearest_3, weights)) / total_weight

        # Add individual rod temperature offset (persists across calls, varies per rod)
        rod_offset = self.rod_temp_offsets.get(rod_num, 0.0)
        return weighted_avg + rod_offset

    def calculate_rod_pressure(self, rod_num):
        """Calculate pressure at rod location (varies slightly by position)"""
        if rod_num not in self.num_to_pos:
            return self.pressure

        r, c = self.num_to_pos[rod_num]
        # Pressure slightly higher at bottom (higher row number)
        # and center of reactor
        center_dist = ((r - 6) ** 2 + (c - 6) ** 2) ** 0.5
        position_variation = (r - 6) * 0.5 - center_dist * 0.3
        
        return self.pressure + position_variation + random.uniform(-0.5, 0.5)

    # -------- CONSOLE OUTPUT --------
    def log_console(self, message):
        self.console_text.config(state="normal")
        self.console_text.insert("end", message + "\n")
        self.console_text.see("end")
        self.console_text.config(state="disabled")

    def log_arccs(self, message):
        """Log messages to ARCCS system log"""
        timestamp = time.strftime("%H:%M:%S")
        self.arccs_text.config(state="normal")
        self.arccs_text.insert("end", f"[{timestamp}] {message}\n")
        self.arccs_text.see("end")
        self.arccs_text.config(state="disabled")

    def submit_command(self, event=None):
        cmd = self.cmd_input.get().strip()
        if cmd:
            self.log_console(f"> {cmd}")
            self.process_gui_command(cmd)
            self.cmd_input.delete(0, tk.END)

    # -------- DETAIL VIEW OVERLAY --------
    def open_zoom(self, n):
        """Show rod detail in overlay panel"""
        letter = self.num_to_cell[n][1]
        rod_type = ROD_TYPES.get(letter, "Unknown")
        
        # Clear previous content
        for widget in self.detail_overlay.winfo_children():
            widget.destroy()
        
        # Create detail content
        frame = tk.Frame(self.detail_overlay, bg="#111")
        frame.pack(padx=15, pady=15)
        
        # Close button
        close_btn = tk.Button(frame, text="✕", command=self.close_detail_overlay,
                             bg="#ff0000", fg="white", font=("Helvetica", 11, "bold"),
                             width=3, relief="flat")
        close_btn.pack(anchor="ne", padx=5, pady=5)
        
        # Rod letter
        title = tk.Label(frame, text=letter, bg="#111", fg="white", font=("Helvetica", 40, "bold"))
        title.pack()
        
        # Rod number and type
        info = tk.Label(frame, text=f"Rod {n} - {rod_type}", bg="#111", fg="#cccccc", font=("Helvetica", 13))
        info.pack(pady=(5, 0))
        
        # Position
        if n in self.num_to_pos:
            r, c = self.num_to_pos[n]
            pos = tk.Label(frame, text=f"Position: Row {r}, Col {c}", bg="#111", fg="#888888", font=("Helvetica", 10))
            pos.pack(pady=(3, 0))
        
        # Separator
        tk.Frame(frame, height=2, bg="#333").pack(fill="x", pady=8)
        
        # Temperature
        temp = self.calculate_rod_temperature(n)
        temp_label = tk.Label(frame, text=f"Temperature: {temp:.1f}K", bg="#111", fg="#ff6666", font=("Helvetica", 11, "bold"))
        temp_label.pack(pady=(0, 4))
        
        # Pressure
        pressure = self.calculate_rod_pressure(n)
        pressure_label = tk.Label(frame, text=f"Pressure: {pressure:.1f} bar", bg="#111", fg="#6699ff", font=("Helvetica", 11, "bold"))
        pressure_label.pack(pady=(0, 4))
        
        # Temperature sensor specific
        if letter == "T":
            if n in self.temperatures:
                sensor_temp = tk.Label(frame, text=f"Sensor Reading: {self.temperatures[n]:.1f}K", bg="#111", fg="#ffaa00", font=("Helvetica", 10))
                sensor_temp.pack(pady=(0, 4))
        
        # Fuel rod specific
        if letter == "F":
            fuel_pct = self.fuel_levels.get(n, 100.0)
            fuel_color = "#00ff00" if fuel_pct > 75 else "#ffff00" if fuel_pct > 50 else "#ff6666"
            fuel_label = tk.Label(frame, text=f"Fuel Level: {fuel_pct:.1f}%", bg="#111", fg=fuel_color, font=("Helvetica", 11, "bold"))
            fuel_label.pack(pady=(0, 4))
            
            # Show neutron flux
            flux = self.neutron_flux.get(n, 0.0)
            flux_color = "#00ff00" if flux < 1.2 else "#ffff00" if flux < 1.5 else "#ff6666"
            flux_label = tk.Label(frame, text=f"Neutron Flux: {flux:.2f}x", bg="#111", fg=flux_color, font=("Helvetica", 10))
            flux_label.pack(pady=(0, 4))
        
        # Control rod insertion level
        if letter in CONTROL_RODS:
            insertion = self.control_rod_levels.get(n, 100)  # Default to fully inserted
            level = tk.Label(frame, text=f"Insertion: {insertion}%", bg="#111", fg="#ffff00", font=("Helvetica", 11, "bold"))
            level.pack(pady=(0, 4))
        
        # Show overlay centered in window
        self.detail_overlay.place(relx=0.5, rely=0.5, anchor="center")
        self.detail_overlay.lift()
    
    def close_detail_overlay(self):
        """Hide the detail overlay"""
        self.detail_overlay.place_forget()

    # -------- COMMAND PARSER --------
    def process_gui_command(self, cmd_str):
        """Process commands from GUI console"""
        parts = cmd_str.split()
        if not parts:
            return

        try:
            cmd = parts[0]

            if cmd == "set":
                if len(parts) < 3:
                    self.log_console("ERROR: set requires rod number (or *) and insertion percentage")
                    self.log_console("Usage: set <rod|*> <pct> [/override]")
                    return
                
                rod_spec = parts[1]
                insertion = int(parts[2])
                override = len(parts) > 3 and parts[3] == "/override"
                
                if not 0 <= insertion <= 100:
                    self.log_console(f"ERROR: Insertion must be 0-100%")
                    return
                
                # Wildcard - all control rods
                if rod_spec == "*":
                    # Determine which rod types to control
                    if override:
                        allowed_types = {"C", "A"}  # Control and Auto
                        self.log_console(f"Setting ALL control and auto rods to {insertion}% insertion")
                    else:
                        allowed_types = {"C"}  # Only manual control rods
                        self.log_console(f"Setting all control rods to {insertion}% insertion (use /override for auto rods)")
                    
                    count = 0
                    for num, cell_data in self.num_to_cell.items():
                        letter = cell_data[1]
                        if letter in allowed_types:
                            self.control_rod_levels[num] = insertion
                            count += 1
                    
                    self.log_console(f"✓ {count} rods set to {insertion}%")
                    return
                
                # Single rod
                rod_num = int(rod_spec)
                if rod_num not in self.num_to_cell:
                    self.log_console(f"ERROR: Rod {rod_num} does not exist")
                    return

                letter = self.num_to_cell[rod_num][1]
                if letter not in CONTROL_RODS:
                    self.log_console(f"ERROR: Rod {rod_num} ({letter}) is not controllable")
                    return

                self.control_rod_levels[rod_num] = insertion
                self.log_console(f"Rod {rod_num} set to {insertion}% insertion")

            elif cmd == "temp":
                if len(parts) < 3:
                    self.log_console("ERROR: temp requires sensor rod number and temperature in K")
                    return
                rod_num = int(parts[1])
                temperature = float(parts[2])

                if rod_num not in self.num_to_cell:
                    self.log_console(f"ERROR: Rod {rod_num} does not exist")
                    return

                letter = self.num_to_cell[rod_num][1]
                if letter != "T":
                    self.log_console(f"ERROR: Rod {rod_num} ({letter}) is not a temperature sensor")
                    return

                if temperature < 0 or temperature > 3500:
                    self.log_console(f"ERROR: Temperature must be 0-3500K")
                    return

                self.temperatures[rod_num] = temperature
                # Update average gradually
                if self.temperatures:
                    new_avg = sum(self.temperatures.values()) / len(self.temperatures)
                    if abs(new_avg - self.coolant_temp_avg) > 5:
                        threading.Thread(target=self.gradual_temp_change, args=(new_avg,), daemon=True).start()
                    else:
                        self.coolant_temp_avg = new_avg
                        self.update_status_displays()
                self.log_console(f"Temp sensor {rod_num} set to {temperature:.1f}K")

            elif cmd == "pressure":
                if len(parts) < 2:
                    self.log_console("ERROR: pressure requires bar value")
                    return
                target_pressure = float(parts[1])
                if target_pressure < 0 or target_pressure > 200:
                    self.log_console(f"ERROR: Pressure must be 0-200 bar")
                    return
                
                current = self.pressure
                self.log_console(f"Adjusting pressure from {current:.1f} to {target_pressure:.1f} bar")
                threading.Thread(target=self.gradual_pressure_change, args=(target_pressure,), daemon=True).start()

            elif cmd == "pump":
                if len(parts) < 3:
                    self.log_console("ERROR: pump requires pump number (or *) and flow or on/off")
                    self.log_console("Usage: pump <num|*> <flow|on|off>")
                    return
                
                pump_spec = parts[1]
                
                # Determine target flow
                try:
                    target_flow = float(parts[2])
                except ValueError:
                    status = parts[2].lower() in ("on", "true", "1")
                    target_flow = 120.0 if status else 0.0
                
                # Wildcard - all pumps
                if pump_spec == "*":
                    self.log_console(f"Setting all pumps to {target_flow:.0f} m³/h")
                    for pump_num in [1, 2]:  # RBMK has 2 main circulation pumps
                        current_flow = self.pump_flow.get(pump_num, 0)
                        threading.Thread(target=self.gradual_pump_change, args=(pump_num, target_flow), daemon=True).start()
                    self.log_console(f"✓ All pumps adjusting to {target_flow:.0f} m³/h")
                    return
                
                # Single pump
                pump_num = int(pump_spec)
                current_flow = self.pump_flow.get(pump_num, 0)
                
                try:
                    float(parts[2])  # Verify it's a flow value
                    self.log_console(f"Adjusting pump {pump_num} flow from {current_flow:.0f} to {target_flow:.0f} m³/h")
                except ValueError:
                    status = parts[2].lower() in ("on", "true", "1")
                    self.log_console(f"Setting pump {pump_num} to {'ON' if status else 'OFF'}")
                
                threading.Thread(target=self.gradual_pump_change, args=(pump_num, target_flow), daemon=True).start()

            elif cmd == "reset":
                """Reset all session values to defaults"""
                self.control_rod_levels.clear()
                self.temperatures.clear()
                self.pump_flow.clear()
                self.pump_status.clear()
                self.core_power = 0.0
                self.power_output_mw = 0.0
                self.pressure = 100.0
                self.coolant_temp_avg = 293.0  # Room temperature
                self.radiation_level = 0.15  # Background radiation
                self.turbine_rpm = 0.0
                self.turbine_power_mw = 0.0
                self.integrity = 100.0
                self.running = False
                # Reset fuel levels
                for fuel_num in self.fuel_levels:
                    self.fuel_levels[fuel_num] = 100.0
                # Clear all alerts
                for alert_name in self.alerts:
                    self.alerts[alert_name] = False
                for n in self.state.keys():
                    self.state[n] = {"mode": "off", "flash": False, "phase": False}
                    canvas = self.num_to_cell[n][0]
                    canvas.configure(bg=OFF)
                self.update_status_displays()
                self.log_console("System reset to defaults")

            elif cmd == "start":
                if self.running:
                    self.log_console("ERROR: Reactor is already running")
                    return
                if self.startup_in_progress:
                    self.log_console("ERROR: Startup sequence already in progress")
                    return
                self.log_console("Requesting startup authorization...")
                if self.request_startup_pin():
                    self.log_console("✓ Startup code accepted")
                    threading.Thread(target=self.startup_sequence, daemon=True).start()
                else:
                    self.log_console("✗ Startup code rejected - STARTUP ABORTED")

            elif cmd == "stage":
                if len(parts) < 2:
                    self.log_console("ERROR: stage requires 'run', 'clear', or a command to stage")
                    return
                
                if parts[1] == "run":
                    if not self.staged_commands:
                        self.log_console("No commands staged")
                        return
                    self.log_console(f"\n>>> Executing {len(self.staged_commands)} staged commands:")
                    for staged_cmd in self.staged_commands:
                        self.log_console(f"  > {staged_cmd}")
                        self.process_gui_command(staged_cmd)
                    self.staged_commands.clear()
                    self.log_console(">>> All staged commands executed\n")
                    
                elif parts[1] == "clear":
                    count = len(self.staged_commands)
                    self.staged_commands.clear()
                    self.log_console(f"Cleared {count} staged commands")
                    
                else:
                    # Stage the rest of the command
                    staged_cmd = " ".join(parts[1:])
                    self.staged_commands.append(staged_cmd)
                    self.log_console(f"Staged: {staged_cmd} (total: {len(self.staged_commands)})")

            elif cmd == "help":
                self.log_console("\n" + "="*40)
                self.log_console("AVAILABLE COMMANDS:")
                self.log_console("  start                 - Begin reactor startup")
                self.log_console("  scram                 - Emergency shutdown")
                self.log_console("  set <rod|*> <pct>     - Set control rod % (C only)")
                self.log_console("  set * <pct> /override - Set all C+A rods")
                self.log_console("  temp <sensor> <K>     - Set temperature sensor")
                self.log_console("  pressure <bar>        - Set system pressure")
                self.log_console("  pump <num|*> <flow>   - Set pump(s) flow m³/h")
                self.log_console("  arccs accept          - Execute ARCCS commands")
                self.log_console("  stage <cmd>           - Stage a command for later")
                self.log_console("  stage run             - Execute all staged commands")
                self.log_console("  stage clear           - Clear staged commands")
                self.log_console("  reset                 - Reset to defaults")
                self.log_console("  status                - Show reactor status")
                self.log_console("Click rods for detailed view")
                self.log_console("NOTE: Power is controlled via control rods,")
                self.log_console("      not directly set (realistic operation)")
                self.log_console("="*40 + "\n")

            elif cmd == "status":
                self.log_console("\n--- REACTOR STATUS ---")
                self.log_console(f"Running: {'YES' if self.running else 'NO'}")
                self.log_console(f"Power: {self.core_power:.1f}% ({self.power_output_mw:.0f} MW thermal)")
                self.log_console(f"Electrical: {self.turbine_power_mw:.0f} MW")
                self.log_console(f"Avg Temp: {self.coolant_temp_avg:.0f}K")
                self.log_console(f"Pressure: {self.pressure:.1f} bar")
                self.log_console(f"Integrity: {self.integrity:.1f}%")
                self.log_console(f"Turbine: {self.turbine_rpm:.0f} RPM")
                self.log_console(f"Radiation: {self.radiation_level:.2f} mSv/h")
                self.log_console(f"Pump 1: {self.pump_flow.get(1, 0):.0f} m³/h {'ON' if self.pump_status.get(1, False) else 'OFF'}")
                self.log_console(f"Pump 2: {self.pump_flow.get(2, 0):.0f} m³/h {'ON' if self.pump_status.get(2, False) else 'OFF'}")
                
                # Show control rod status
                if self.control_rod_levels:
                    manual_rods = [ins for num, ins in self.control_rod_levels.items() 
                                  if self.num_to_cell.get(num, (None, None))[1] == 'C']
                    auto_rods = [ins for num, ins in self.control_rod_levels.items() 
                                if self.num_to_cell.get(num, (None, None))[1] == 'A']
                    
                    if manual_rods:
                        avg_manual = sum(manual_rods) / len(manual_rods)
                        self.log_console(f"Manual Control Rods: {avg_manual:.1f}% avg insertion ({len(manual_rods)} rods)")
                    if auto_rods:
                        avg_auto = sum(auto_rods) / len(auto_rods)
                        self.log_console(f"Auto Control Rods: {avg_auto:.1f}% avg insertion ({len(auto_rods)} rods)")
                
                if self.fuel_levels:
                    avg_fuel = sum(self.fuel_levels.values()) / len(self.fuel_levels)
                    self.log_console(f"Avg Fuel: {avg_fuel:.1f}%")
                
                if self.neutron_flux:
                    avg_flux = sum(self.neutron_flux.values()) / len(self.neutron_flux)
                    self.log_console(f"Avg Neutron Flux: {avg_flux:.3f}x")
                    
                active_alerts = [name for name, active in self.alerts.items() if active]
                if active_alerts:
                    self.log_console(f"Active Alerts: {', '.join(active_alerts)}")
                else:
                    self.log_console("Active Alerts: None")
                self.log_console("---\n")

            elif cmd == "arccs" and len(parts) > 1 and parts[1] == "accept":
                # Execute ARCCS recommended commands
                if not self.arccs_commands:
                    self.log_console("ARCCS: No pending commands to execute")
                else:
                    self.log_console(f"ARCCS: Executing {len(self.arccs_commands)} recommended commands:")
                    for arccs_cmd in self.arccs_commands:
                        self.log_console(f"  > {arccs_cmd}")
                        self.process_gui_command(arccs_cmd)
                    self.log_console("✓ ARCCS commands executed")
                    self.arccs_commands = []

            else:
                self.log_console(f"Unknown command: {cmd}")

        except ValueError as e:
            self.log_console("ERROR: Invalid command format")
        except Exception as e:
            self.log_console(f"ERROR: {str(e)}")

    def process_commands(self):
        """Process external commands from stdin"""
        while not cmd_queue.empty():
            parts = cmd_queue.get().split()

            try:
                cmd = parts[0]

                if cmd == "red":
                    self.trigger(int(parts[1]), "red")

                elif cmd == "yellow":
                    self.trigger(int(parts[1]), "yellow")

                elif cmd == "off":
                    self.turn_off(int(parts[1]))

                elif cmd == "alloff":
                    self.all_off()

                elif cmd == "ack":
                    self.acknowledge()

                elif cmd == "text":
                    n = int(parts[1])
                    self.custom_text[n] = " ".join(parts[2:])

                elif cmd == "cleartext":
                    self.custom_text.pop(int(parts[1]), None)

            except Exception:
                pass

        self.root.after(50, self.process_commands)


# ---------------- RUN ----------------
root = tk.Tk()
root.title("RBMK-1000 Reactor Control Station Software v1.0.2")
root.configure(bg="black")
root.geometry("1200x700")  # Set initial size
root.minsize(1000, 600)  # Set minimum size
root.tk.call("tk", "appname", "RBMK-1000 Reactor Control Station Software v1.0.2")

GridUI(root)

root.mainloop()