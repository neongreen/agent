from rich.live import Live
from rich.text import Text
from rich.console import Console
from typing import Optional

console = Console()
live_display: Optional[Live] = None
_current_phase: Optional[str] = None
_last_message: Optional[str] = None


def _update_display() -> None:
    global live_display, _current_phase, _last_message
    if live_display is not None:
        if _current_phase:
            live_display.update(Text(_current_phase, style="bold green"))
        elif _last_message:
            live_display.update(Text(_last_message, style="dim"))


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
    global _last_message, _current_phase
    _last_message = message
    _current_phase = None  # Clear phase when a new status message comes in
    _update_display()


def set_phase(phase: str) -> None:
    global _current_phase, _last_message
    _current_phase = phase
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
