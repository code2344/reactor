import tkinter as tk
from tkinter import ttk
import socket
import json
import threading
import time

NUM_RODS = 12
SERVER_HOST = "127.0.0.1"
SERVER_PORT = 5050

class PlantModel:
    def __init__(self):
        self.rods = [100.0] * NUM_RODS
        self.power = 0.0
        self.pressure = 0.0
        self.temperature = 20.0
        self.scrammed = False

    def step(self):
        rod_effect = sum(self.rods) / (NUM_RODS * 100)
        target_power = max(0.0, 1.2 - rod_effect)

        if self.scrammed:
            target_power = 0.0

        self.power += (target_power - self.power) * 0.05
        self.pressure += (self.power - self.pressure) * 0.02
        self.temperature += (self.power * 600 - self.temperature) * 0.01

class ReactorClient:
    def __init__(self, root):
        self.root = root
        self.root.title("Core Control Console")

        self.model = PlantModel()
        self.connected = False
        self.sock = None

        self.build_ui()
        self.try_connect()

        self.update_loop()

    def build_ui(self):
        main = ttk.Frame(self.root, padding=10)
        main.grid()

        self.rod_frames = []
        self.rod_scales = []

        rods_frame = ttk.LabelFrame(main, text="Rod Insertion")
        rods_frame.grid(row=0, column=0, padx=10)

        for i in range(NUM_RODS):
            f = ttk.Frame(rods_frame)
            f.grid(row=0, column=i, padx=3)

            s = tk.Scale(
                f,
                from_=100,
                to=0,
                length=200,
                command=lambda v, r=i: self.set_rod(r, float(v))
            )
            s.set(100)
            s.pack()

            ttk.Label(f, text=f"R{i+1}").pack()

            self.rod_scales.append(s)

        status = ttk.LabelFrame(main, text="Plant Status")
        status.grid(row=0, column=1, padx=10, sticky="n")

        self.power_lbl = ttk.Label(status, text="Power: 0.00")
        self.pressure_lbl = ttk.Label(status, text="Pressure: 0.00")
        self.temp_lbl = ttk.Label(status, text="Temperature: 20")

        self.power_lbl.pack(anchor="w")
        self.pressure_lbl.pack(anchor="w")
        self.temp_lbl.pack(anchor="w")

        self.light = tk.Canvas(status, width=40, height=40)
        self.light.pack(pady=10)
        self.light_id = self.light.create_oval(5, 5, 35, 35, fill="green")

        controls = ttk.Frame(main)
        controls.grid(row=1, column=0, columnspan=2, pady=10)

        ttk.Button(controls, text="SCRAM", command=self.scram).pack()

    def try_connect(self):
        try:
            self.sock = socket.create_connection((SERVER_HOST, SERVER_PORT), timeout=1)
            self.connected = True
            threading.Thread(target=self.listen, daemon=True).start()
        except:
            self.connected = False

    def listen(self):
        while True:
            try:
                data = self.sock.recv(4096)
                if not data:
                    break
                msg = json.loads(data.decode())
                if msg["type"] == "state":
                    self.model.rods = msg["rods"]
                    self.model.power = msg["power"]
                    self.model.pressure = msg["pressure"]
                    self.model.temperature = msg["temperature"]
            except:
                break
        self.connected = False

    def send(self, msg):
        if self.connected:
            try:
                self.sock.sendall(json.dumps(msg).encode())
            except:
                self.connected = False

    def set_rod(self, rod, value):
        self.model.rods[rod] = value
        self.send({
            "type": "set_rod",
            "rod": rod,
            "position": value
        })

    def scram(self):
        self.model.scrammed = True
        for i in range(NUM_RODS):
            self.model.rods[i] = 100
            self.rod_scales[i].set(100)
        self.send({"type": "scram"})

    def update_loop(self):
        if not self.connected:
            self.model.step()

        self.power_lbl.config(text=f"Power: {self.model.power:.2f}")
        self.pressure_lbl.config(text=f"Pressure: {self.model.pressure:.2f}")
        self.temp_lbl.config(text=f"Temperature: {int(self.model.temperature)}")

        deviation = max(abs(r - 100) for r in self.model.rods)
        if self.model.scrammed:
            colour = "red"
        elif deviation > 30:
            colour = "yellow"
        else:
            colour = "green"

        self.light.itemconfig(self.light_id, fill=colour)

        self.root.after(100, self.update_loop)

if __name__ == "__main__":
    root = tk.Tk()
    ReactorClient(root)
    root.mainloop()

