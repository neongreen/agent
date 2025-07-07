from rich.console import Console
from rich.errors import MarkupError
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


console = Console()


def print_formatted_message(message: str, message_type: str):
    """
    Prints a formatted message to the console based on its type.
    """
    try:
        if message_type == "thought":
            console.print(Panel(Markdown(message), title="LLM Thought", title_align="left", border_style="magenta"))
        elif message_type == "plan":
            console.print(Panel(Markdown(message), title="Proposed Plan", title_align="left", border_style="green"))
        elif message_type == "reviewer_feedback":
            console.print(
                Panel(Markdown(message), title="Reviewer Feedback", title_align="left", border_style="yellow")
            )
        else:
            console.print(message)
    except MarkupError:
        console.print(Text.from_markup(message).plain)


def format_llm_thought(thought_text: str) -> str:
    """
    Formats LLM thoughts for aesthetic output.
    """
    return thought_text


def format_reviewer_feedback(feedback_text: str) -> str:
    """
    Formats reviewer feedback for aesthetic output.
    """
    return feedback_text


def format_plan(plan_text: str) -> str:
    """
    Formats a plan for aesthetic output.
    """
    return plan_text


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
