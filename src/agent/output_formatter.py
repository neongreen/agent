from rich.console import Console
from rich.markdown import Markdown
from rich.text import Text

console = Console()


def format_llm_thought(thought_text: str) -> Markdown:
    """Formats LLM thoughts as a Markdown block."""
    return Markdown(
        f"""# LLM Thought
{thought_text}
""",
        style="dim",
    )


def format_reviewer_feedback(feedback_text: str) -> Markdown:
    """Formats reviewer feedback as a Markdown block."""
    return Markdown(
        f"""# Reviewer Feedback
{feedback_text}
""",
        style="red",
    )


def format_plan(plan_text: str) -> Markdown:
    """Formats a plan as a Markdown block."""
    return Markdown(
        f"""# Proposed Plan
{plan_text}
""",
        style="cyan",
    )


def print_formatted_message(message, message_type="default"):
    """Prints a formatted message to the console based on message type."""
    if message_type == "thought":
        console.print(format_llm_thought(message))
    elif message_type == "reviewer_feedback":
        console.print(format_reviewer_feedback(message))
    elif message_type == "plan":
        console.print(format_plan(message))
    elif message_type == "tool_code":
        console.print(Text(message, style="cyan"))
    elif message_type == "tool_output_stdout":
        console.print(Text(message, style="green"))
    elif message_type == "tool_output_stderr" or message_type == "tool_output_error":
        console.print(Text(message, style="red"))
    elif message_type == "file_path":
        console.print(Text(message, style="yellow"))
    else:
        console.print(Text(message))
