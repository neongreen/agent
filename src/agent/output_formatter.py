from rich.console import Console
from rich.errors import MarkupError
from rich.markdown import Markdown
from rich.panel import Panel
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
