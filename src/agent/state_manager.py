"""Manages the reading and writing of the agent's operational state to a file."""

import json
from typing import Dict

from agent.constants import STATE_FILE, TaskState


def read_state() -> Dict[str, TaskState]:
    """
    Reads the current state from the state file.

    Returns:
        A dictionary representing the agent's state.
    """
    if not STATE_FILE.exists():
        return {}
    with open(STATE_FILE, "r") as f:
        raw_state = json.load(f)
        return {task_id: TaskState.from_json(state_value) for task_id, state_value in raw_state.items()}


def write_state(state: Dict[str, TaskState]) -> None:
    """
    Writes the current state to the state file.

    Args:
        state: The dictionary representing the agent's state to write.
    """
    serializable_state = {task_id: task_state.to_json() for task_id, task_state in state.items()}
    with open(STATE_FILE, "w") as f:
        json.dump(serializable_state, f, indent=4)
