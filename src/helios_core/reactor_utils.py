from collections import Counter

from .reactor_data import GRID_LETTERS, ROD_TYPES


def flatten_grid():
    return [cell for row in GRID_LETTERS for cell in row]


def rod_counts():
    return Counter(flatten_grid())


def render_ascii_map(show_placeholder=False):
    rows = []
    for row in GRID_LETTERS:
        if show_placeholder:
            rows.append(" ".join(row))
        else:
            rows.append(" ".join("." if cell == "P" else cell for cell in row))
    return "\n".join(rows)


def reactor_stats():
    counts = rod_counts()
    active_positions = sum(v for k, v in counts.items() if k != "P")
    total_positions = sum(counts.values())
    return {
        "counts": counts,
        "active_positions": active_positions,
        "total_positions": total_positions,
        "utilization_percent": (active_positions / total_positions) * 100 if total_positions else 0.0,
    }


def estimate_output(power_percent):
    thermal_mw = (power_percent / 100.0) * 3200.0
    electric_mw = thermal_mw * 0.31
    return thermal_mw, electric_mw


def rod_type_table():
    ordered = sorted(ROD_TYPES.items())
    return "\n".join(f"{code}: {name}" for code, name in ordered)
