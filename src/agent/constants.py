"""Defines constants and enumerations used throughout the agent's codebase."""

import uuid
from datetime import datetime
from enum import Enum
from pathlib import Path


class TaskState(Enum):
    """Represents the different states a task can be in."""

    PLAN = "PLAN"
    IMPLEMENT = "IMPLEMENT"
    DONE = "DONE"
    ABORT = "ABORT"


class LLMOutputType(Enum):
    """Represents the different types of LLM outputs."""

    PLAN = "plan"
    FEEDBACK = "feedback"
    THOUGHT = "thought"
    TOOL_CODE = "tool_code"
    TOOL_OUTPUT = "tool_output"
    TOOL_OUTPUT_ERROR = "tool_output_error"


# Constants
AGENT_STATE_BASE_DIR = Path.home() / ".agent"
"""Base directory for agent-related persistent files."""

# Generate a unique session directory
SESSION_ID = datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + "_" + str(uuid.uuid4())
AGENT_TEMP_DIR = AGENT_STATE_BASE_DIR / "sessions" / SESSION_ID
"""Base directory for agent-related temporary files for the current session."""

STATE_FILE = AGENT_TEMP_DIR / ".agent_state.json"
"""Path to the file storing the agent's current state."""
PLAN_FILE = AGENT_TEMP_DIR / "plan.md"
"""Path to the file storing the current task plan."""
TASK_META_DIR = AGENT_TEMP_DIR / "task_meta"
"""Directory for storing task-specific metadata."""
