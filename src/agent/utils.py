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
from .output_formatter import LLMOutputType, print_formatted_message
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


# TODO: should we forbid using `print_formatted_message` directly and require `log` instead?
# Probably yes.
def log(
    message: str,
    message_type: LLMOutputType,
    message_human: Optional[str] = None,
    quiet=None,
) -> None:
    """Simple logging function that respects quiet mode."""
    if quiet is None:
        quiet = config.quiet_mode

    log_entry = {"timestamp": datetime.datetime.now().isoformat(), "message": message}

    if not quiet:
        print_formatted_message(message_human or message, message_type)

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
    error: Optional[str]
    signal: Optional[int]
    background_pids: Optional[list[int]]
    process_group_pgid: Optional[int]


def run(
    command: str | list[str],
    description=None,
    command_human: Optional[list[str]] = None,
    status_message: Optional[str] = None,
    *,
    directory: Path,
    shell: bool = False,
    log_stdout: bool = True,
) -> RunResult:
    """
    Run command and log it.

    Args:
        command: Command to run as a list of arguments.
        description: Optional description of the command for logging.
        directory: Optional working directory to run the command in as a Path.
        command_human: If present, will be used in console output instead of the full command.
        config: Agent configuration for logging settings.
    """

    if description:
        log(f"Executing: {description}", message_type=LLMOutputType.TOOL_EXECUTION)

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

    abs_directory = abspath(str(directory))

    log(
        f"Running command: {command_display} in {abs_directory}",
        message_human=f"Running command: {command_human_display} in {abs_directory}",
        message_type=LLMOutputType.TOOL_EXECUTION,
    )

    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False, cwd=abs_directory, shell=shell)

        if result.returncode != 0:
            log(
                f"Command failed with exit code {result.returncode}\nStdout: {result.stdout}\nStderr: {result.stderr}",
                message_type=LLMOutputType.TOOL_ERROR,
            )

        # TODO: do we want to log success? or do we always log it later somewhere?

        return RunResult(
            exit_code=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
            success=result.returncode == 0,
            error=None,
            signal=None,
            background_pids=None,
            process_group_pgid=None,
        )

    except Exception as e:
        log(f"Error running command: {e}", message_type=LLMOutputType.TOOL_ERROR)
        return RunResult(
            exit_code=-1,
            stdout="",
            stderr=str(e),
            success=False,
            error=str(e),
            signal=None,
            background_pids=None,
            process_group_pgid=None,
        )


# TODO: this seems weird
def format_tool_code_output(tool_output: RunResult) -> str:
    """
    Formats the output of a tool code execution.
    """
    formatted_output = ""
    if tool_output["stdout"] and tool_output["stdout"] != "(empty)":
        formatted_output += f"stdout: {tool_output['stdout']}\n"
    if tool_output["stderr"] and tool_output["stderr"] != "(empty)":
        formatted_output += f"stderr: {tool_output['stderr']}\n"
    if tool_output["error"]:
        formatted_output += f"error: {tool_output['error']}\n"
    if tool_output["exit_code"] is not None:
        formatted_output += f"exit_code: {tool_output['exit_code']}\n"
    if tool_output["signal"] is not None:
        formatted_output += f"signal: {tool_output['signal']}\n"
    if tool_output["background_pids"]:
        formatted_output += f"background_pids: {tool_output['background_pids']}\n"
    if tool_output["process_group_pgid"] is not None:
        formatted_output += f"process_group_pgid: {tool_output['process_group_pgid']}\n"
    return formatted_output
