import datetime
import json
import shlex
import subprocess
from typing import Optional, TypedDict

from rich.console import Console

from .config import AgentConfig
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
    config: Optional[AgentConfig] = None,
) -> None:
    """Simple logging function that respects quiet mode."""
    if quiet is None:
        quiet = config.quiet_mode if config else False

    log_entry = {"timestamp": datetime.datetime.now().isoformat(), "message": message}

    if not quiet:
        _print_formatted(message_human or message, message_type=message_type)

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
    config: Optional[AgentConfig] = None,
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
        log(f"Executing: {description}", message_type="tool_code", config=config)

    if isinstance(command, str):
        command_display = command
    else:
        command_display = shlex.join(command)

    if command_human is None:
        command_human_display = command_display
    else:
        command_human_display = shlex.join(command_human)

    log(
        f"Running command: {command_display}",
        message_human=f"Running command: {command_human_display}",
        message_type="tool_code",
        config=config,
    )

    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False, cwd=directory, shell=shell)

        if result.returncode != 0:
            log(f"Command failed with exit code {result.returncode}", message_type="tool_output_error", config=config)
            log(f"Stderr: {result.stderr}", message_type="tool_output_stderr", config=config)

        log(f"Stdout: {result.stdout}", message_type="tool_output_stdout", config=config)
        log(f"Stderr: {result.stderr}", message_type="tool_output_stderr", config=config)

        return RunResult(
            exit_code=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
            success=result.returncode == 0,
        )

    except Exception as e:
        log(f"Error running command: {e}", message_type="tool_output_error", config=config)
        return RunResult(exit_code=-1, stdout="", stderr=str(e), success=False)
