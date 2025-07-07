"""Utility functions for the agent."""

import datetime
import json
import shlex
import subprocess
from pathlib import Path
from posixpath import abspath
from typing import Optional, TypedDict

from rich.console import Console

from .config import AGENT_SETTINGS as config
from .constants import AGENT_TEMP_DIR
from .ui import status_manager

console = Console()

_session_log_file_path: Optional[Path] = None


def get_session_log_file_path() -> Path:
    global _session_log_file_path
    if _session_log_file_path is None:
        log_dir = AGENT_TEMP_DIR / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        _session_log_file_path = log_dir / f"agent_log_{timestamp}.log"
    return _session_log_file_path


def _print_formatted(message, message_type="default") -> None:
    """
    Prints a formatted message to the console based on message type.

    Args:
        message: The message string to print.
        message_type: The type of message, which determines the formatting style.
    """
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

    session_log_file = get_session_log_file_path()
    if not session_log_file.exists():
        with open(session_log_file, "w", encoding="utf-8") as f:
            f.write("")
    with open(session_log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry) + "\n")


class RunResult(TypedDict):
    """Represents the result of a shell command execution."""

    exit_code: int
    stdout: str
    stderr: str
    success: bool


def run(
    command: str | list[str],
    description=None,
    command_human: Optional[list[str]] = None,
    status_message: Optional[str] = None,
    *,
    directory: str,
    shell: bool = False,
    log_stdout: bool = True,
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

    if status_message:
        status_manager.update_status(status_message)

    if isinstance(command, str):
        command_display = command
    else:
        command_display = shlex.join(command)

    if command_human is None:
        command_human_display = command_display
    else:
        command_human_display = shlex.join(command_human)

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

        if log_stdout:
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
