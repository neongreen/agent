from typing import Optional

from rich.console import Console
from rich.live import Live
from rich.text import Text

console = Console()
live_display: Optional[Live] = None


def init_status_bar() -> None:
    global live_display
    if live_display is None:
        status_text = Text("Initializing...", style="dim")
        # Use screen=False to allow normal logging above the status
        live_display = Live(status_text, console=console, screen=False, refresh_per_second=4)
        # Manually enter the context
        live_display.__enter__()


def update_status(message: str, style: str = "dim") -> None:
    global live_display
    if live_display is not None:
        live_display.update(Text(message, style=style))


def cleanup_status_bar() -> None:
    global live_display
    if live_display is not None:
        # Manually exit the context
        live_display.__exit__(None, None, None)
        live_display = None
