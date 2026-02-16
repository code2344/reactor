import tkinter as tk
import threading
import queue
import sys

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

CELL_SIZE = 42
OFF = "#2b2b2b"
RED = "#ff3b30"
YELLOW = "#ffd60a"
FLASH_DARK = "#1a1a1a"

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

        self.num_to_cell = {}   # number -> (canvas, letter)
        self.state = {}         # alarm state
        self.custom_text = {}   # number -> message override

        frame = tk.Frame(root, bg="black")
        frame.pack(padx=10, pady=10)

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

                    self.num_to_cell[number] = (canvas, letter)
                    self.state[number] = {"mode": "off", "flash": False, "phase": False}

                    canvas.bind("<Button-1>",
                                lambda e, n=number: self.open_zoom(n))

                    number += 1

        # Buttons
        btn_frame = tk.Frame(root, bg="black")
        btn_frame.pack(fill="x", padx=10, pady=(0,10))

        tk.Button(btn_frame, text="ACKNOWLEDGE",
                  command=self.acknowledge,
                  font=("Helvetica", 12, "bold"),
                  bg="#222", fg="white").pack(side="left", expand=True, fill="x", padx=(0,5))

        tk.Button(btn_frame, text="OFF",
                  command=self.all_off,
                  font=("Helvetica", 12, "bold"),
                  bg="#550000", fg="white").pack(side="left", expand=True, fill="x", padx=(5,0))

        self.root.after(200, self.flash_loop)
        self.root.after(50, self.process_commands)

    # -------- FLASH ENGINE --------
    def flash_loop(self):
        for n, info in self.state.items():
            if not info["flash"]:
                continue

            canvas, _ = self.num_to_cell[n]
            info["phase"] = not info["phase"]

            colour = RED if info["mode"] == "red" else YELLOW
            canvas.configure(bg=colour if info["phase"] else FLASH_DARK)

        self.root.after(400, self.flash_loop)

    # -------- CONTROL --------
    def trigger(self, n, colour):
        if n not in self.state:
            return
        self.state[n]["mode"] = colour
        self.state[n]["flash"] = True

    def turn_off(self, n):
        if n not in self.state:
            return
        canvas, _ = self.num_to_cell[n]
        self.state[n] = {"mode": "off", "flash": False, "phase": False}
        canvas.configure(bg=OFF)

    def all_off(self):
        for n in list(self.state.keys()):
            self.turn_off(n)

    def acknowledge(self):
        for n, info in self.state.items():
            if info["mode"] in ("red", "yellow"):
                info["flash"] = False
                canvas, _ = self.num_to_cell[n]
                canvas.configure(bg=RED if info["mode"] == "red" else YELLOW)

    # -------- ZOOM VIEW --------
    def open_zoom(self, n):
        _, letter = self.num_to_cell[n]

        message = self.custom_text.get(n, letter)

        top = tk.Toplevel(self.root)
        top.title(f"Cell {n}")

        canvas = tk.Canvas(top, width=260, height=200, bg="#111")
        canvas.pack()

        canvas.create_text(130, 70, text=letter,
                           fill="white", font=("Helvetica", 42, "bold"))

        canvas.create_text(130, 150, text=message,
                           fill="#cccccc", font=("Helvetica", 14))

    # -------- COMMAND PARSER --------
    def process_commands(self):
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
                print("Invalid command")

        self.root.after(50, self.process_commands)


# ---------------- RUN ----------------
root = tk.Tk()
root.title("Alarm Grid")
root.configure(bg="black")

GridUI(root)

root.mainloop()
