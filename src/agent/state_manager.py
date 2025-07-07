"""Manages the reading and writing of the agent's operational state to a file."""

import json

from .constants import STATE_FILE


def read_state() -> dict:
    """
    Reads the current state from the state file.

    Returns:
        A dictionary representing the agent's state.
    """
    if not STATE_FILE.exists():
        return {}
    with open(STATE_FILE, "r") as f:
        return json.load(f)


def write_state(state: dict) -> None:
    """
    Writes the current state to the state file.

    Args:
        state: The dictionary representing the agent's state to write.
    """
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=4)
