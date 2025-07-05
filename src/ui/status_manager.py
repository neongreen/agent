from rich.live import Live
from rich.text import Text
from rich.console import Console
from typing import Optional

console = Console()
live_display: Optional[Live] = None
_current_phase: Optional[str] = None
_current_attempt_info: Optional[str] = None
_last_message: Optional[str] = None


def _update_display() -> None:
    global live_display, _current_phase, _current_attempt_info, _last_message
    if live_display is not None:
        display_text = ""
        if _current_phase:
            display_text += f"{_current_phase}"
        if _current_attempt_info:
            if display_text:
                display_text += f": attempt {_current_attempt_info}"
            else:
                display_text += f"attempt {_current_attempt_info}"
        if _last_message:
            if display_text:
                display_text += f": {_last_message}"
            else:
                display_text += f"{_last_message}"

        if display_text:
            live_display.update(Text(f">>> {display_text} <<<", style="bold black on grey23"))


def init_status_bar() -> None:
    global live_display
    if live_display is None:
        status_text = Text("Initializing...", style="dim")
        # Use screen=False to allow normal logging above the status
        live_display = Live(status_text, console=console, screen=False, refresh_per_second=4)
        # Manually enter the context
        live_display.__enter__()
        _update_display()


def update_status(message: str, style: str = "dim") -> None:
    global _last_message
    _last_message = message
    _update_display()


def set_phase(phase: str, attempt_info: Optional[str] = None) -> None:
    global _current_phase, _current_attempt_info, _last_message
    _current_phase = phase
    _current_attempt_info = attempt_info
    _last_message = None  # Clear last message when a new phase comes in
    _update_display()


def cleanup_status_bar() -> None:
    global live_display, _current_phase, _last_message
    if live_display is not None:
        # Manually exit the context
        live_display.__exit__(None, None, None)
        live_display = None
    _current_phase = None
    _last_message = None
