GRID_LETTERS = [
    ["P", "P", "P", "P", "P", "R", "R", "R", "P", "P", "P", "P", "P"],
    ["P", "P", "P", "P", "R", "G", "G", "G", "R", "P", "P", "P", "P"],
    ["P", "P", "P", "R", "G", "G", "T", "G", "G", "R", "P", "P", "P"],
    ["P", "P", "R", "G", "G", "F", "A", "F", "G", "G", "R", "P", "P"],
    ["P", "R", "G", "G", "F", "C", "F", "C", "F", "G", "G", "R", "P"],
    ["R", "G", "G", "F", "C", "F", "C", "F", "C", "F", "G", "G", "R"],
    ["R", "G", "T", "A", "F", "C", "T", "C", "F", "A", "T", "G", "R"],
    ["R", "G", "G", "F", "C", "F", "C", "F", "C", "F", "G", "G", "R"],
    ["P", "R", "G", "G", "F", "C", "F", "C", "F", "G", "G", "R", "P"],
    ["P", "P", "R", "G", "G", "F", "A", "F", "G", "G", "R", "P", "P"],
    ["P", "P", "P", "R", "G", "G", "T", "G", "G", "R", "P", "P", "P"],
    ["P", "P", "P", "P", "R", "G", "G", "G", "R", "P", "P", "P", "P"],
    ["P", "P", "P", "P", "P", "R", "R", "R", "P", "P", "P", "P", "P"],
]

ROD_TYPES = {
    "R": "Reflector",
    "G": "Graphite",
    "T": "Temperature Sensor",
    "A": "Auto Control Rod",
    "F": "Fuel",
    "C": "Control Rod",
    "P": "Placeholder",
}

CONTROL_RODS = {"C", "A"}
