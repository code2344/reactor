from dataclasses import dataclass, field

from .reactor_data import CONTROL_RODS, GRID_LETTERS


@dataclass
class ReactorCoreState:
    rod_to_pos: dict[int, tuple[int, int]] = field(default_factory=dict)
    rod_to_letter: dict[int, str] = field(default_factory=dict)
    alarm_state: dict[int, dict[str, object]] = field(default_factory=dict)
    custom_text: dict[int, str] = field(default_factory=dict)
    control_rod_levels: dict[int, int] = field(default_factory=dict)

    def __post_init__(self):
        if self.rod_to_pos:
            return

        number = 1
        for row_index in range(len(GRID_LETTERS)):
            for col_index in range(len(GRID_LETTERS[row_index])):
                letter = GRID_LETTERS[row_index][col_index]
                if letter == "P":
                    continue
                self.rod_to_pos[number] = (row_index, col_index)
                self.rod_to_letter[number] = letter
                self.alarm_state[number] = {"mode": "off", "flash": False, "phase": False}
                if letter in CONTROL_RODS:
                    self.control_rod_levels[number] = 100
                number += 1

    def trigger(self, rod_number: int, colour: str):
        if rod_number not in self.alarm_state:
            return False
        self.alarm_state[rod_number]["mode"] = colour
        self.alarm_state[rod_number]["flash"] = True
        return True

    def turn_off(self, rod_number: int):
        if rod_number not in self.alarm_state:
            return False
        self.alarm_state[rod_number] = {"mode": "off", "flash": False, "phase": False}
        return True

    def all_off(self):
        for rod_number in self.alarm_state:
            self.turn_off(rod_number)

    def acknowledge(self):
        for info in self.alarm_state.values():
            if info["mode"] in ("red", "yellow"):
                info["flash"] = False

    def set_text(self, rod_number: int, message: str):
        if rod_number not in self.alarm_state:
            return False
        self.custom_text[rod_number] = message
        return True

    def clear_text(self, rod_number: int):
        self.custom_text.pop(rod_number, None)

    def set_rod_insertion(self, rod_number: int, insertion: int):
        if rod_number not in self.rod_to_letter:
            raise ValueError(f"Rod {rod_number} does not exist")
        if self.rod_to_letter[rod_number] not in CONTROL_RODS:
            raise ValueError(f"Rod {rod_number} is not controllable")
        if insertion < 0 or insertion > 100:
            raise ValueError("Insertion must be 0-100")
        self.control_rod_levels[rod_number] = insertion

    def apply_command(self, command: str):
        parts = command.strip().split()
        if not parts:
            return {"ok": False, "error": "empty command", "rod_updates": []}

        cmd = parts[0].lower()
        rod_updates = []

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
            rod_number = int(parts[1])
            self.set_text(rod_number, " ".join(parts[2:]))
        elif cmd == "cleartext":
            self.clear_text(int(parts[1]))
        elif cmd == "set":
            rod_spec = parts[1]
            insertion = int(parts[2])
            override = len(parts) > 3 and parts[3] == "/override"
            if rod_spec == "*":
                allowed_types = {"C", "A"} if override else {"C"}
                for rod_number, letter in self.rod_to_letter.items():
                    if letter in allowed_types:
                        self.control_rod_levels[rod_number] = insertion
                        rod_updates.append({"rod": rod_number, "insertion": insertion})
            else:
                rod_number = int(rod_spec)
                self.set_rod_insertion(rod_number, insertion)
                rod_updates.append({"rod": rod_number, "insertion": insertion})
        else:
            return {"ok": False, "error": f"unknown command: {cmd}", "rod_updates": []}

        return {"ok": True, "rod_updates": rod_updates}
