"""Manages the display of the agent's current status and phase in the CLI using rich.progress and rich.layout."""

import time
from contextlib import contextmanager
from typing import Generator, Optional

from rich.console import Console
from rich.live import Live
from rich.progress import Progress, SpinnerColumn, TaskID, TextColumn, TimeElapsedColumn


console = Console()
live: Optional[Live] = None
_progress: Optional[Progress] = None
_task_id: Optional[TaskID] = None
_current_phase: Optional[str] = None
_current_attempt_info: Optional[str] = None
_last_message: Optional[str] = None
_action_start_time: Optional[float] = None


def _get_description() -> str:
    """Returns the description for the progress bar."""
    desc = _current_phase or ""
    if _current_attempt_info:
        desc += f" (attempt {_current_attempt_info})"
    if _last_message:
        desc += f": {_last_message}"
    return desc or "Initializing..."


def _init_status_bar() -> None:
    """Initializes the status bar."""
    global _progress, _task_id, _action_start_time, live
    if _progress is None:
        _progress = Progress(
            SpinnerColumn(style="green"),
            TextColumn("[bold magenta]{task.description}"),
            TimeElapsedColumn(),
            console=console,
            transient=True,
        )
        _task_id = _progress.add_task(_get_description(), total=None)
        _action_start_time = time.time()

        live = Live(_progress, console=console, refresh_per_second=10)
        live.start()


def update_status(message: str, style: str = "dim") -> None:
    """
    Updates the status message in the progress bar.

    Args:
        message: The message to display.
        style: The style of the message (not currently used).
    """
    global _last_message, _action_start_time
    _last_message = message
    if _action_start_time is None:
        _action_start_time = time.time()
    if _progress and _task_id is not None:
        _progress.update(_task_id, description=_get_description())


def set_phase(phase: str, attempt_info: Optional[str] = None) -> None:
    """
    Sets the current phase of the agent.

    Args:
        phase: The name of the phase.
        attempt_info: Optional information about the attempt.
    """
    global _current_phase, _current_attempt_info, _last_message, _action_start_time
    _current_phase = phase
    _current_attempt_info = attempt_info
    _last_message = None
    _action_start_time = time.time()
    if _progress and _task_id is not None:
        _progress.update(_task_id, description=_get_description())


def _cleanup_status_bar() -> None:
    """Cleans up the status bar, stopping the live display."""
    global live, _progress, _task_id, _current_phase, _last_message, _action_start_time
    if live:
        live.stop()
        live = None
    if _progress is not None:
        _progress = None
        _task_id = None
    _current_phase = None
    _last_message = None
    _action_start_time = None


@contextmanager
def get_status_manager() -> Generator[None, None, None]:
    """A context manager for the status bar."""
    _init_status_bar()
    try:
        yield
    finally:
        _cleanup_status_bar()
