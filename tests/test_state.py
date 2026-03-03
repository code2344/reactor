from helios_core.state import ReactorCoreState


def test_set_single_control_rod_updates_state():
    state = ReactorCoreState()
    control_rod = next(rod for rod, letter in state.rod_to_letter.items() if letter == "C")

    result = state.apply_command(f"set {control_rod} 35")

    assert result["ok"] is True
    assert state.control_rod_levels[control_rod] == 35
    assert result["rod_updates"] == [{"rod": control_rod, "insertion": 35}]


def test_set_wildcard_only_manual_without_override():
    state = ReactorCoreState()

    result = state.apply_command("set * 45")

    assert result["ok"] is True
    for rod, letter in state.rod_to_letter.items():
        if letter == "C":
            assert state.control_rod_levels[rod] == 45
        elif letter == "A":
            assert state.control_rod_levels[rod] == 100


def test_alarm_and_acknowledge_flow():
    state = ReactorCoreState()
    first_rod = min(state.alarm_state)

    red_result = state.apply_command(f"red {first_rod}")
    assert red_result["ok"] is True
    assert state.alarm_state[first_rod]["mode"] == "red"
    assert state.alarm_state[first_rod]["flash"] is True

    ack_result = state.apply_command("ack")
    assert ack_result["ok"] is True
    assert state.alarm_state[first_rod]["flash"] is False
