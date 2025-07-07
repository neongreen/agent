"""Defines constants and enumerations used throughout the agent's codebase."""

from enum import Enum
from pathlib import Path


class TaskState(Enum):
    """Represents the different states a task can be in."""

    PLAN = "PLAN"
    IMPLEMENT = "IMPLEMENT"
    DONE = "DONE"
    ABORT = "ABORT"


# Constants
AGENT_TEMP_DIR = Path(".agent")
"""Base directory for agent-related temporary files."""

STATE_FILE = AGENT_TEMP_DIR / ".agent_state.json"
"""Path to the file storing the agent's current state."""
PLAN_FILE = AGENT_TEMP_DIR / "plan.md"
"""Path to the file storing the current task plan."""
TASK_META_DIR = AGENT_TEMP_DIR / "task_meta"
"""Directory for storing task-specific metadata."""
