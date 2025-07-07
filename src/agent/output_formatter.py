from enum import Enum, auto

from rich.console import Console
from rich.errors import MarkupError
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


class LLMOutputType(Enum):
    """Represents the different types of LLM outputs."""

    PLAN = auto()
    """Proposed plan by the LLM."""
    EVALUATION = auto()
    """Evaluation by the judge."""
    STATUS = auto()
    """Some kind of status message."""
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


def print_formatted_message(message: str, message_type: LLMOutputType):
    """
    Prints a formatted message to the console based on its type.
    """
    try:
        if message_type == LLMOutputType.STATUS:
            console.print(Panel(Markdown(message), title="Status", title_align="left", border_style="magenta"))
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
            console.print(
                Panel(Markdown(message), title="Tool execution failure", title_align="left", border_style="red")
            )
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


def display_task_summary(task_results: list):
    """
    Displays a summary of all executed tasks.
    """
    table = Table(title="Task Execution Summary")
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
