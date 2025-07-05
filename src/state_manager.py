import json
from .constants import STATE_FILE


def read_state() -> dict:
    """Reads the current state from the state file."""
    if not STATE_FILE.exists():
        return {}
    with open(STATE_FILE, "r") as f:
        return json.load(f)


def write_state(state: dict) -> None:
    """Writes the current state to the state file."""
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=4)
