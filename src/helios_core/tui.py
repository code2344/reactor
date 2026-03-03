from textual.app import App, ComposeResult
from textual.containers import Vertical
from textual.widgets import Footer, Header, Input, Static

from .net import HeliosServerClient
from .reactor_data import GRID_LETTERS
from .state import ReactorCoreState


class ReactorTUI(App):
    CSS = """
    Screen {
        layout: vertical;
    }
    #grid {
        height: 1fr;
        border: solid #666666;
        padding: 1;
    }
    #status {
        height: 3;
        border: solid #666666;
        padding: 0 1;
    }
    #command {
        height: 3;
    }
    """

    BINDINGS = [
        ("left", "move_left", "Left"),
        ("right", "move_right", "Right"),
        ("up", "move_up", "Up"),
        ("down", "move_down", "Down"),
        ("r", "mark_red", "Red"),
        ("y", "mark_yellow", "Yellow"),
        ("o", "mark_off", "Off"),
        ("a", "ack", "Acknowledge"),
        ("q", "quit", "Quit"),
    ]

    def __init__(self, server_url: str | None = None):
        super().__init__()
        self.state = ReactorCoreState()
        self.server_client = HeliosServerClient(server_url) if server_url else None
        self.selected_row = 0
        self.selected_col = 0
        self.rod_lookup = {}
        for rod_number, (row_index, col_index) in self.state.rod_to_pos.items():
            self.rod_lookup[(row_index, col_index)] = rod_number

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical():
            yield Static(id="grid")
            yield Static("Arrows move, r/y/o set alarm, a acknowledge, command supports: red/yellow/off/alloff/ack/text/cleartext/set", id="status")
            yield Input(placeholder="Enter command and press Enter", id="command")
        yield Footer()

    def on_mount(self):
        self.set_interval(0.4, self._tick_flash)
        self._move_to_first_active_cell()
        self._render_grid()

    def _move_to_first_active_cell(self):
        for row_index in range(len(GRID_LETTERS)):
            for col_index in range(len(GRID_LETTERS[row_index])):
                if GRID_LETTERS[row_index][col_index] != "P":
                    self.selected_row = row_index
                    self.selected_col = col_index
                    return

    def _tick_flash(self):
        for info in self.state.alarm_state.values():
            if info["flash"]:
                info["phase"] = not info["phase"]
        self._render_grid()

    def _cell_markup(self, row_index: int, col_index: int):
        letter = GRID_LETTERS[row_index][col_index]
        if letter == "P":
            token = " . "
            if row_index == self.selected_row and col_index == self.selected_col:
                return f"[reverse]{token}[/reverse]"
            return f"[dim]{token}[/dim]"

        rod_number = self.rod_lookup[(row_index, col_index)]
        info = self.state.alarm_state[rod_number]
        mode = info["mode"]
        flashing_on = info["flash"] and info["phase"]

        token = f"{letter:>1}{rod_number:02d}" if rod_number < 100 else f"{letter}{rod_number}"
        token = token[:3]

        style = "on #2b2b2b"
        if mode == "red":
            style = "on #ff3b30" if flashing_on or not info["flash"] else "on #1a1a1a"
        elif mode == "yellow":
            style = "on #ffd60a" if flashing_on or not info["flash"] else "on #1a1a1a"

        if row_index == self.selected_row and col_index == self.selected_col:
            return f"[reverse {style}] {token} [/reverse {style}]"
        return f"[{style}] {token} [/{style}]"

    def _render_grid(self):
        lines = []
        for row_index in range(len(GRID_LETTERS)):
            row_tokens = []
            for col_index in range(len(GRID_LETTERS[row_index])):
                row_tokens.append(self._cell_markup(row_index, col_index))
            lines.append(" ".join(row_tokens))
        grid_widget = self.query_one("#grid", Static)
        grid_widget.update("\n".join(lines))

    def _selected_rod(self):
        return self.rod_lookup.get((self.selected_row, self.selected_col))

    def _move_cursor(self, row_delta: int, col_delta: int):
        new_row = self.selected_row
        new_col = self.selected_col
        for _ in range(169):
            new_row = (new_row + row_delta) % len(GRID_LETTERS)
            new_col = (new_col + col_delta) % len(GRID_LETTERS[0])
            if GRID_LETTERS[new_row][new_col] != "P":
                self.selected_row = new_row
                self.selected_col = new_col
                break
        self._render_grid()

    def action_move_left(self):
        self._move_cursor(0, -1)

    def action_move_right(self):
        self._move_cursor(0, 1)

    def action_move_up(self):
        self._move_cursor(-1, 0)

    def action_move_down(self):
        self._move_cursor(1, 0)

    def _set_selected_alarm(self, colour: str):
        rod_number = self._selected_rod()
        if not rod_number:
            return
        self.state.trigger(rod_number, colour)
        self._render_grid()

    def action_mark_red(self):
        self._set_selected_alarm("red")

    def action_mark_yellow(self):
        self._set_selected_alarm("yellow")

    def action_mark_off(self):
        rod_number = self._selected_rod()
        if not rod_number:
            return
        self.state.turn_off(rod_number)
        self._render_grid()

    def action_ack(self):
        self.state.acknowledge()
        self._render_grid()

    async def on_input_submitted(self, event: Input.Submitted):
        cmd = event.value.strip()
        event.input.value = ""
        if not cmd:
            return

        result = self.state.apply_command(cmd)
        if result.get("ok") and self.server_client:
            for update in result.get("rod_updates", []):
                try:
                    self.server_client.send_rod_update(update["rod"], update["insertion"])
                except Exception:
                    pass
        self._render_grid()


def run_tui(server_url: str | None = None):
    app = ReactorTUI(server_url=server_url)
    app.run()
