from rich.console import Console
from rich.markdown import Markdown

console = Console()


def print_formatted_message(message: str, message_type: str):
    """
    Prints a formatted message to the console based on its type.
    """
    if message_type == "thought":
        console.print(Markdown(f"# LLM Thought\n\n{message}", style="bold magenta"))
    elif message_type == "plan":
        console.print(Markdown(f"# Proposed Plan\n\n{message}", style="bold green"))
    elif message_type == "reviewer_feedback":
        console.print(Markdown(f"# Reviewer Feedback\n\n{message}", style="bold yellow"))
    else:
        console.print(message)


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
