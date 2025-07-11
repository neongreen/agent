"""Defines constants and enumerations used throughout the agent's codebase."""

import uuid
from datetime import datetime
from enum import StrEnum, auto
from pathlib import Path


class TaskState(StrEnum):
    """Represents the different states a task can be in."""

    PLAN = auto()
    IMPLEMENT = auto()
    DONE = auto()
    ABORT = auto()

    def __str__(self):
        return self.name

    def to_json(self):
        return self.value

    @classmethod
    def from_json(cls, value):
        return cls(value)


# Constants
OK_STATE_BASE_DIR = Path.home() / ".ok"
"""Base directory for agent-related persistent files."""

# Generate a unique session directory
SESSION_ID = datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + "_" + str(uuid.uuid4())
OK_TEMP_DIR = OK_STATE_BASE_DIR / "sessions" / SESSION_ID
"""Base directory for agent-related temporary files for the current session."""

STATE_FILE = OK_TEMP_DIR / "state.json"
"""Path to the file storing the agent's current state."""
PLAN_FILE = OK_TEMP_DIR / "plan.md"
"""Path to the file storing the current task plan."""
TASK_META_DIR = OK_TEMP_DIR / "task_meta"
"""Directory for storing task-specific metadata."""
