import os
from datetime import datetime
from enum import StrEnum, auto

import eliot
from eliot import FileDestination
from rich.console import Console
from rich.errors import MarkupError
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from agent.constants import AGENT_STATE_BASE_DIR


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


_logging_initialized = False


def init_logging() -> None:
    global _logging_initialized
    if _logging_initialized:
        return
    _logging_initialized = True

    # Initialize Eliot logging
    timestamp = datetime.now().strftime("%Y-%m-%dT%H%M%S")
    log_file = AGENT_STATE_BASE_DIR / "logs" / f"log-{timestamp}_{os.getpid()}.json"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    eliot.add_destinations(FileDestination(file=open(log_file, "ab")))


def __print_formatted_message(message: str, message_type: LLMOutputType):
    """
    Prints a formatted message to the console based on its type.
    """
    try:
        if message_type == LLMOutputType.STATUS:
            console.print(Panel(Markdown(message), title="Status", title_align="left", border_style="magenta"))
        elif message_type == LLMOutputType.DEBUG:
            console.print(Panel(Markdown(message), title="Debug", title_align="left", border_style="slate_blue3"))
        elif message_type == LLMOutputType.PLAN:
            console.print(Panel(Markdown(message), title="Proposed plan", title_align="left", border_style="green"))
        elif message_type == LLMOutputType.EVALUATION:
            console.print(
                Panel(Markdown(message), title="Reviewer evaluation", title_align="left", border_style="yellow")
            )
        elif message_type == LLMOutputType.TOOL_EXECUTION:
            console.print(Panel(Markdown(message), title="Tool execution", title_align="left", border_style="cyan"))
        elif message_type == LLMOutputType.TOOL_OUTPUT:
            console.print(Panel(Markdown(message), title="Tool output", title_align="left", border_style="white"))
        elif message_type == LLMOutputType.TOOL_ERROR:
            console.print(Panel(Markdown(message), title="Tool error", title_align="left", border_style="red"))
        elif message_type == LLMOutputType.ERROR:
            console.print(Panel(Markdown(message), title="Error", title_align="left", border_style="red"))
        elif message_type == LLMOutputType.PROMPT:
            console.print(Panel(Markdown(message), title="Prompt", title_align="left", border_style="bright_blue"))
        elif message_type == LLMOutputType.LLM_RESPONSE:
            console.print(
                Panel(Markdown(message), title="LLM response", title_align="left", border_style="bright_magenta")
            )
        else:
            console.print(message)
    except MarkupError:
        console.print(Text.from_markup(message).plain)

    console.print("\n", end="")


# print_formatted_message is now internal; use log instead.
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


def display_task_summary(task_results: list):
    """
    Displays a summary of all executed tasks.
    """
    table = Table(title="Task Execution Summary", title_justify="left")
    table.add_column("Task Prompt", style="cyan", no_wrap=False)
    table.add_column("Status", style="magenta")
    table.add_column("Worktree", style="green")
    table.add_column("Commit Hash", style="yellow")
    table.add_column("Error", style="red", no_wrap=False)

    for result in task_results:
        prompt = result.get("prompt", "N/A")
        status = result.get("status", "N/A")
        worktree = result.get("worktree", "N/A")
        commit_hash = result.get("commit_hash", "N/A")
        error = result.get("error", "")

        table.add_row(prompt, status, worktree, commit_hash, error)

    console.print(table)
    console.print("\n\n", end="")
