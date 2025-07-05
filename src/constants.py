from enum import Enum
from pathlib import Path


class TaskState(Enum):
    PLAN = "PLAN"
    IMPLEMENT = "IMPLEMENT"
    DONE = "DONE"
    ABORT = "ABORT"


# Global variables
LOG_FILE = ".agentic-log"
QUIET_MODE = False
JUDGE_EXTRA_PROMPT = ""
STATE_FILE = Path(".agent_state.json")
