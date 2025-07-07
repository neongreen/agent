from enum import Enum
from pathlib import Path


class TaskState(Enum):
    PLAN = "PLAN"
    IMPLEMENT = "IMPLEMENT"
    DONE = "DONE"
    ABORT = "ABORT"


# Constants
LOG_FILE = ".agentic-log"
STATE_FILE = Path(".agent_state.json")
