"""Utility functions for the agent."""

import shlex
from dataclasses import dataclass
from pathlib import Path
from posixpath import abspath
from typing import Optional

import trio
from eliot import start_action

from ok.env import Env, RunResult
from ok.log import LLMOutputType


async def real_run(
    env: Env,
    command: str | list[str],
    description=None,
    command_human: Optional[list[str]] = None,
    status_message: Optional[str] = None,
    *,
    directory: Path,
    shell: bool = False,
    run_timeout_seconds: int,
) -> RunResult:
    """
    Run command asynchronously using Trio and log it.

    Errors are logged but *not* raised as exceptions.

    Args:
        command: Command to run as a list of arguments.
        description: Optional description of the command for logging.
        directory: Optional working directory to run the command in as a Path.
        command_human: If present, will be used in console output instead of the full command.
        run_timeout_seconds: Timeout for the command execution in seconds. Expected to come from `ConfigModel`.
    """

    if isinstance(command, str):
        command_display = command
    else:
        command_display = shlex.join(command)

    if command_human is None:
        command_human_display = command_display
    else:
        command_human_display = shlex.join(command_human)

    # Trio wants a list of strings if shell=False, or a single string if shell=True
    real_command: str | list[str]
    if shell:
        real_command = command if isinstance(command, str) else shlex.join(command)
    else:
        real_command = [command] if isinstance(command, str) else command

    with start_action(
        action_type="run",
        command=command_display,
        description=description,
        directory=directory,
        shell=shell,
    ) as action:
        if status_message:
            env.update_status(status_message)

        abs_directory = abspath(str(directory))

        env.log(
            f"Running command: {command_display} in {abs_directory}",
            message_human=(description + "\n\n" if description else "")
            + f"Running command: `{command_human_display}` in `{abs_directory}`",
            message_type=LLMOutputType.TOOL_EXECUTION,
        )

        try:
            # Use fail_after for timeout
            with trio.fail_after(run_timeout_seconds):
                # TODO: this still seems to wait a couple of seconds before registering Ctrl+C.. sometimes.
                # Perhaps we need to write a custom `deliver_cancel`.
                # But it's good enough for now.
                #
                # NB: If we ever need to get the result out of `start_soon`, use the `aioresult` lib.
                result = await trio.run_process(
                    real_command,
                    cwd=abs_directory,
                    shell=shell,
                    capture_stdout=True,
                    capture_stderr=True,
                    check=False,
                    # Don't let the children get our Ctrl+C
                    start_new_session=True,
                )

            env.log_debug(
                "Command completed successfully",
                command=command_display,
                directory=abs_directory,
                result=repr(result),
            )

            stdout = result.stdout.decode() if result.stdout else ""
            stderr = result.stderr.decode() if result.stderr else ""
            returncode = result.returncode

            if returncode != 0:
                env.log(
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

            result_obj = RunResult(
                exit_code=returncode,
                stdout=stdout,
                stderr=stderr,
                success=returncode == 0,
            )

            action.add_success_fields(
                **({"exit_code": result_obj.exit_code} if result_obj.exit_code != 0 else {}),
                **({"stdout": result_obj.stdout} if result_obj.stdout.strip() else {}),
                **({"stderr": result_obj.stderr} if result_obj.stderr.strip() else {}),
            )

        except* trio.TooSlowError as group:
            env.log_debug("Caught an exception group", exc=[repr(e) for e in group.exceptions])
            env.log(
                f"Command timed out after {run_timeout_seconds} seconds: {command_display}",
                message_human=f"Command timed out after {run_timeout_seconds} seconds:\n`{command_human_display}`",
                message_type=LLMOutputType.TOOL_ERROR,
            )
            action.add_success_fields(error=f"Command timed out after {run_timeout_seconds} seconds")
            result_obj = RunResult(
                exit_code=-1,
                stdout="",
                stderr="",
                success=False,
                error=f"Command timed out after {run_timeout_seconds} seconds",
            )

        except* KeyboardInterrupt as group:
            env.log_debug("Caught an exception group", exc=[repr(e) for e in group.exceptions])
            env.log(
                f"Command was interrupted: {command_display}",
                message_human=f"Command was interrupted:\n`{command_human_display}`",
                message_type=LLMOutputType.TOOL_ERROR,
            )
            action.add_success_fields(error="Command was interrupted")
            raise

        return result_obj


@dataclass
class TaskResult:
    """Represents the result of processing a task."""

    task: str
    status: str
    last_commit_hash: str | None
    error: str | None = None


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
