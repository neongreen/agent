from enum import Enum
from pathlib import Path


class TaskState(Enum):
    PLAN = "PLAN"
    IMPLEMENT = "IMPLEMENT"
    DONE = "DONE"
    ABORT = "ABORT"


# Constants
AGENT_TEMP_DIR = Path(".agent")
LOG_FILE = AGENT_TEMP_DIR / ".agentic-log"
STATE_FILE = AGENT_TEMP_DIR / ".agent_state.json"
PLAN_FILE = AGENT_TEMP_DIR / "plan.md"
TASK_META_DIR = AGENT_TEMP_DIR / "task_meta"
