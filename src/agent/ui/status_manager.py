"""Manages the display of the agent's current status and phase in the CLI."""

from typing import Optional

from rich.columns import Columns
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.spinner import Spinner
from rich.text import Text


console = Console()
live_display: Optional[Live] = None
_current_phase: Optional[str] = None
_current_attempt_info: Optional[str] = None
_last_message: Optional[str] = None
_is_active: bool = False


def _update_display() -> None:
    """Updates the live display with the current phase, attempt info, and last message."""
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
            spinner = Spinner("dots", style="green")
            phase_text = Text(_current_phase, style="bold magenta") if _current_phase else Text("")
            attempt_text = (
                Text(f" (attempt {_current_attempt_info})", style="cyan") if _current_attempt_info else Text("")
            )
            message_text = Text(f": {_last_message}", style="green") if _last_message else Text("")

            # Combine into columns for better layout
            content_elements = []
            if _is_active:
                content_elements.append(spinner)
            content_elements.extend([phase_text, attempt_text, message_text])
            content = Columns(content_elements)
            live_display.update(Panel(content, border_style="dim"))


def init_status_bar() -> None:
    global live_display
    if live_display is None:
        # FIXME: this wrecks the panel output, e.g
        #
        # ```
        # Starting agentic loop
        # Initializing...╭─ LLM Thought ─────────────────────────────────────────────────────────────────╮
        # │ Processing task 1: text etc etc etc
        # ```
        #
        status_text = Text("Initializing...", style="dim")
        # Use screen=False to allow normal logging above the status
        live_display = Live(status_text, console=console, screen=False, refresh_per_second=4)
        # Manually enter the context
        live_display.__enter__()
        _update_display()


def update_status(message: str, style: str = "dim") -> None:
    global _last_message, _is_active
    _last_message = message
    _is_active = True
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
