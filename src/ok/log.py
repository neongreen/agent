import os
from datetime import datetime
from enum import StrEnum, auto

import eliot
import eliot.json
from eliot import FileDestination
from rich.console import Console
from rich.errors import MarkupError
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text

from ok.constants import OK_STATE_BASE_DIR
from ok.ui import print_to_main


class LLMOutputType(StrEnum):
    """Represents the different types of LLM outputs."""

    PLAN = auto()
    """Proposed plan by the LLM."""
    EVALUATION = auto()
    """Evaluation by the judge."""
    STATUS = auto()
    """Some kind of status message."""
    DEBUG = auto()
    """Debug message."""
    ERROR = auto()
    """Error message."""
    PROMPT = auto()
    """The prompt sent to the LLM."""
    LLM_RESPONSE = auto()
    """Any generic response from the LLM."""
    TOOL_EXECUTION = auto()
    """Calling any command (shell, etc)."""
    TOOL_OUTPUT = auto()
    """Output from a tool execution."""
    TOOL_ERROR = auto()
    """Error from a tool execution."""


console = Console()


def log_json_encoder(obj):
    """
    Custom JSON encoder that builds on Eliot's JSON encoder but doesn't fail on non-serializable objects.
    """

    try:
        return eliot.json.json_default(obj)
    except TypeError:
        return repr(obj)


_logging_initialized = False


def init_logging() -> None:
    global _logging_initialized
    if _logging_initialized:
        return
    _logging_initialized = True

    # Initialize Eliot logging
    timestamp = datetime.now().strftime("%Y-%m-%dT%H%M%S")
    log_file = OK_STATE_BASE_DIR / "logs" / f"log-{timestamp}_{os.getpid()}.json"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    eliot.add_destinations(FileDestination(file=open(log_file, "ab"), json_default=log_json_encoder))


def __print_formatted_message(message: str, message_type: LLMOutputType):
    """
    Prints a formatted message to the console based on its type.
    """
    try:
        if message_type == LLMOutputType.STATUS:
            print_to_main(Panel(Markdown(message), title="Status", title_align="left", border_style="magenta"))
        elif message_type == LLMOutputType.DEBUG:
            print_to_main(Panel(Markdown(message), title="Debug", title_align="left", border_style="slate_blue3"))
        elif message_type == LLMOutputType.PLAN:
            print_to_main(Panel(Markdown(message), title="Proposed plan", title_align="left", border_style="green"))
        elif message_type == LLMOutputType.EVALUATION:
            print_to_main(
                Panel(Markdown(message), title="Reviewer evaluation", title_align="left", border_style="yellow")
            )
        elif message_type == LLMOutputType.TOOL_EXECUTION:
            print_to_main(Panel(Markdown(message), title="Tool execution", title_align="left", border_style="cyan"))
        elif message_type == LLMOutputType.TOOL_OUTPUT:
            print_to_main(Panel(Markdown(message), title="Tool output", title_align="left", border_style="white"))
        elif message_type == LLMOutputType.TOOL_ERROR:
            print_to_main(Panel(Markdown(message), title="Tool error", title_align="left", border_style="red"))
        elif message_type == LLMOutputType.ERROR:
            print_to_main(Panel(Markdown(message), title="Error", title_align="left", border_style="red"))
        elif message_type == LLMOutputType.PROMPT:
            print_to_main(Panel(Markdown(message), title="Prompt", title_align="left", border_style="bright_blue"))
        elif message_type == LLMOutputType.LLM_RESPONSE:
            print_to_main(
                Panel(Markdown(message), title="LLM response", title_align="left", border_style="bright_magenta")
            )
        else:
            print_to_main(message)
    except MarkupError:
        print_to_main(Panel(Text.from_markup(message)))


def log(
    message: str,
    message_type: LLMOutputType,
    message_human: str | None = None,
    quiet=None,
) -> None:
    """
    Simple logging function that respects quiet mode.

    Arguments:
        message: The message to log to the log file.
        message_type: The type of the message, used for formatting.
        message_human: Optional human-readable message to display in the console. Should be formatted as Markdown.
          If not provided, `message` will be used.
        quiet: If provided, overrides the global quiet mode setting.
    """

    init_logging()

    if not quiet:
        __print_formatted_message(message_human or message, message_type)

    eliot.log_message(f"log.{message_type}", str=message, **({"human": message_human} if message_human else {}))


def format_as_markdown_blockquote(text: str) -> str:
    """
    Formats the given text as a Markdown blockquote.
    """
    lines = text.splitlines()
    blockquote_lines = [f"> {line}" for line in lines]
    return "\n".join(blockquote_lines)
