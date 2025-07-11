"""Manages the display of the agent's current status and phase in the CLI using rich.progress."""

import time
from typing import Optional

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TaskID, TextColumn, TimeElapsedColumn


console = Console()
_progress: Optional[Progress] = None
_task_id: Optional[TaskID] = None
_current_phase: Optional[str] = None
_current_attempt_info: Optional[str] = None
_last_message: Optional[str] = None
_action_start_time: Optional[float] = None


def _get_description() -> str:
    desc = _current_phase or ""
    if _current_attempt_info:
        desc += f" (attempt {_current_attempt_info})"
    if _last_message:
        desc += f": {_last_message}"
    return desc or "Initializing..."


def init_status_bar() -> None:
    global _progress, _task_id, _action_start_time
    if _progress is None:
        _progress = Progress(
            SpinnerColumn(style="green"),
            TextColumn("[bold magenta]{task.description}"),
            TimeElapsedColumn(),
            console=console,
            transient=False,
            refresh_per_second=4,
        )
        _progress.start()
        _task_id = TaskID(_progress.add_task(_get_description(), total=None))
        _action_start_time = time.time()


def update_status(message: str, style: str = "dim") -> None:
    global _last_message, _action_start_time
    _last_message = message
    if _action_start_time is None:
        _action_start_time = time.time()
    if _progress and _task_id is not None:
        _progress.update(_task_id, description=_get_description())  # type: ignore[arg-type]


def set_phase(phase: str, attempt_info: Optional[str] = None) -> None:
    global _current_phase, _current_attempt_info, _last_message, _action_start_time
    _current_phase = phase
    _current_attempt_info = attempt_info
    _last_message = None
    _action_start_time = time.time()
    if _progress and _task_id is not None:
        _progress.update(_task_id, description=_get_description())  # type: ignore[arg-type]


def cleanup_status_bar() -> None:
    global _progress, _task_id, _current_phase, _last_message, _action_start_time
    if _progress is not None:
        _progress.stop()
        _progress = None
        _task_id = None
    _current_phase = None
    _last_message = None
    _action_start_time = None
