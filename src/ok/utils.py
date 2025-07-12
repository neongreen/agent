"""Utility functions for the agent."""

import shlex
from dataclasses import dataclass
from pathlib import Path
from posixpath import abspath
from typing import Optional

import trio
from eliot import start_action

from ok.logging import LLMOutputType, log
from ok.ui import update_status


@dataclass(frozen=True)
class RunResult:
    """Represents the result of a shell command execution."""

    exit_code: int
    stdout: str
    stderr: str
    success: bool
    error: Optional[str] = None


async def run(
    command: str | list[str],
    description=None,
    command_human: Optional[list[str]] = None,
    status_message: Optional[str] = None,
    *,
    directory: Path,
    shell: bool = False,
    log_stdout: bool = True,
    store_process: bool = False,
) -> RunResult:
    """
    Run command asynchronously using Trio and log it.

    Errors are logged but *not* raised as exceptions.

    Args:
        command: Command to run as a list of arguments.
        description: Optional description of the command for logging.
        directory: Optional working directory to run the command in as a Path.
        command_human: If present, will be used in console output instead of the full command.
        store_process: Ignored (for compatibility).
    """

    if isinstance(command, str):
        command_display = command
    else:
        command_display = shlex.join(command)

    if command_human is None:
        command_human_display = command_display
    else:
        command_human_display = shlex.join(command_human)

    with start_action(
        action_type="run",
        command=command_display,
        description=description,
        directory=directory,
        shell=shell,
    ) as action:
        if status_message:
            update_status(status_message)

        abs_directory = abspath(str(directory))

        log(
            f"Running command: {command_display} in {abs_directory}",
            message_human=(description + "\n\n" if description else "")
            + f"Running command: `{command_human_display}` in `{abs_directory}`",
            message_type=LLMOutputType.TOOL_EXECUTION,
        )

        try:
            result_obj = await trio.run_process(
                command,
                cwd=abs_directory,
                shell=shell,
                capture_stdout=True,
                capture_stderr=True,
                check=False,
            )
            stdout = result_obj.stdout.decode() if result_obj.stdout else ""
            stderr = result_obj.stderr.decode() if result_obj.stderr else ""
            returncode = result_obj.returncode

            if returncode != 0:
                log(
                    f"Command {command_display} failed with exit code {returncode}\nStdout: {stdout}\nStderr: {stderr}",
                    message_human=(
                        "\n\n".join(
                            [
                                f"Command `{command_human_display}` failed with exit code {returncode}",
                                f"Stdout:\n\n```\n{stdout}\n```" if stdout.strip() else "Stdout: empty",
                                f"Stderr:\n\n```\n{stderr}\n```" if stderr.strip() else "Stderr: empty",
                            ]
                        )
                    ),
                    message_type=LLMOutputType.TOOL_ERROR,
                )

            result = RunResult(
                exit_code=returncode,
                stdout=stdout,
                stderr=stderr,
                success=returncode == 0,
            )

            action.add_success_fields(
                **({"exit_code": result.exit_code} if result.exit_code != 0 else {}),
                **({"stdout": result.stdout} if result.stdout.strip() else {}),
                **({"stderr": result.stderr} if result.stderr.strip() else {}),
            )

            return result

        except Exception as e:
            log(f"Error running command: {e}", message_type=LLMOutputType.TOOL_ERROR)
            result = RunResult(
                exit_code=-1,
                stdout="",
                stderr=str(e),
                success=False,
                error=str(e),
            )

            action.add_success_fields(
                exit_code=result.exit_code,
                stdout=result.stdout,
                stderr=result.stderr,
                error=result.error,
            )

            return result


# TODO: this seems weird
def format_tool_code_output(
    tool_output: RunResult,
    code_block_language: str | None = None,
) -> str:
    """
    Formats the output of a tool code execution.

    Args:
        tool_output: The output of the tool code execution as a RunResult.
        markdown_code_block: If present, wraps the output in a Markdown code block with the specified language.
          Used for human-readable output. Only applies to `stdout` and `stderr`.
    """
    formatted_output = []
    if tool_output.stdout:
        if code_block_language:
            formatted_output.append(f"stdout: \n\n```{code_block_language}\n{tool_output.stdout}\n```\n")
        else:
            formatted_output.append(f"stdout: \n\n```\n{tool_output.stdout}\n```\n")
    if tool_output.stderr:
        if code_block_language:
            formatted_output.append(f"stderr: \n\n```{code_block_language}\n{tool_output.stderr}\n```\n")
        else:
            formatted_output.append(f"stderr: \n\n```\n{tool_output.stderr}\n```\n")
    if tool_output.error is not None:
        formatted_output.append(f"error: {tool_output.error}\n")
    if tool_output.exit_code is not None:
        formatted_output.append(f"exit_code: {tool_output.exit_code}\n")
    return "\n".join(formatted_output)


@dataclass(frozen=True)
class TaskResult:
    """Represents the result of processing a task."""

    task: str
    status: str
    last_commit_hash: str | None
    error: str | None = None
