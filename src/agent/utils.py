import datetime
import json
import shlex
import subprocess
from posixpath import abspath
from typing import Optional, TypedDict

from rich.console import Console

from .config import AGENT_SETTINGS as config
from .constants import LOG_FILE

console = Console()


def _print_formatted(message, message_type="default") -> None:
    style = ""
    if message_type == "thought":
        style = "dim"
    elif message_type == "tool_code":
        style = "cyan"
    elif message_type == "tool_output_stdout":
        style = "green"
    elif message_type == "tool_output_stderr" or message_type == "tool_output_error":
        style = "red"
    elif message_type == "file_path":
        style = "yellow"

    console.print(message, style=style)


def log(
    message: str,
    message_human: Optional[str] = None,
    quiet=None,
    message_type="default",
) -> None:
    """Simple logging function that respects quiet mode."""
    if quiet is None:
        quiet = config.quiet_mode

    log_entry = {"timestamp": datetime.datetime.now().isoformat(), "message": message}

    if not quiet:
        _print_formatted(message_human or message, message_type=message_type)

    if not LOG_FILE.exists():
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            f.write("")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry) + "\n")


class RunResult(TypedDict):
    exit_code: int
    stdout: str
    stderr: str
    success: bool


def run(
    command: str | list[str],
    description=None,
    command_human: Optional[list[str]] = None,
    directory=None,
    shell: bool = False,
) -> RunResult:
    """
    Run command and log it.

    Args:
        command: Command to run as a list of arguments.
        description: Optional description of the command for logging.
        directory: Optional working directory to run the command in.
        command_human: If present, will be used in console output instead of the full command.
        config: Agent configuration for logging settings.
    """

    if description:
        log(f"Executing: {description}", message_type="tool_code")

    if isinstance(command, str):
        command_display = command
    else:
        command_display = shlex.join(command)

    if command_human is None:
        command_human_display = command_display
    else:
        command_human_display = shlex.join(command_human)

    if directory is None:
        directory = "."
    directory = abspath(directory)

    log(
        f"Running command: {command_display} in {directory}",
        message_human=f"Running command: {command_human_display} in {directory}",
        message_type="tool_code",
    )

    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False, cwd=directory, shell=shell)

        if result.returncode != 0:
            log(f"Command failed with exit code {result.returncode}", message_type="tool_output_error")
            log(f"Stderr: {result.stderr}", message_type="tool_output_stderr")

        log(f"Stdout: {result.stdout or '<empty>'}", message_type="tool_output_stdout")
        log(f"Stderr: {result.stderr or '<empty>'}", message_type="tool_output_stderr")

        return RunResult(
            exit_code=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
            success=result.returncode == 0,
        )

    except Exception as e:
        log(f"Error running command: {e}", message_type="tool_output_error")
        return RunResult(exit_code=-1, stdout="", stderr=str(e), success=False)
