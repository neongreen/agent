"""
Main entry point for the agent application.

This module handles command-line argument parsing, configuration loading,
and orchestration of the agent's task processing.
"""

import argparse
import os
import signal
import tempfile
from pathlib import Path
from typing import assert_never

import eliot
import rich
import trio

from ok import git_utils
from ok.cli_settings import CLISettings
from ok.config import OK_SETTINGS as config
from ok.constants import OK_TEMP_DIR
from ok.llm import get_llm
from ok.logging import LLMOutputType
from ok.state_manager import write_state
from ok.task_orchestrator import process_task
from ok.task_result import TaskResult, display_task_summary
from ok.ui import get_ui_manager, set_phase
from ok.utils import log


_llm_instance = None


async def work() -> None:
    """
    This is almost the entry point for the agent.
    The actual entry point is `main()`, which calls `_main()`, which calls `work()`.

    This function handles command-line argument parsing, configuration loading,
    and orchestration of the agent's task processing.

    Parses command-line arguments, sets up the environment, and initiates
    the agentic loop for task processing.
    """
    global _llm_instance

    parser = argparse.ArgumentParser(description="Agentic loop")
    parser.add_argument("--quiet", action="store_true", help="Suppress informational output")
    parser.add_argument("--cwd", type=str, default=None, help="Working directory for task execution")
    parser.add_argument("--base", type=str, default=None, help="Base branch, commit, or git specifier")
    parser.add_argument("--claude", action="store_true", help="Use Claude Code CLI for LLM calls")
    parser.add_argument("--codex", action="store_true", help="Use Codex CLI for LLM calls")
    parser.add_argument("--openrouter", action="store_true", help="Use OpenRouter (via Codex CLI) for LLM calls")
    parser.add_argument("--opencode", action="store_true", help="Use Opencode CLI for LLM calls")
    parser.add_argument("--mock", action="store_true", help="Use MockLLM for LLM calls")
    parser.add_argument("--mock-delay", type=int, default=5, help="Set a 'sleep' inside each mock llm invocation")
    parser.add_argument(
        "--model", type=str, default=None, help="Specify the model name for gemini, claude, codex, or opencode"
    )
    parser.add_argument("--show-config", action="store_true", help="Show the current configuration and exit")
    parser.add_argument(
        "--no-worktree",
        action="store_true",
        help="Work directly in the target directory rather than in a temporary Git worktree.",
    )
    parser.add_argument("prompt", nargs="*", default=None, help="Task(s) to do")
    args = parser.parse_args()

    # Populate CLISettings from parsed args, following pydantic-settings docs
    cli_settings = CLISettings.model_validate(vars(args))

    # Create the agent dir before even doing any logging
    if not OK_TEMP_DIR.exists():
        OK_TEMP_DIR.mkdir(parents=True, exist_ok=True)

    if cli_settings.show_config:
        rich.print(f"```json\n{config.model_dump_json(indent=2)}\n```")
        exit(0)

    if [
        cli_settings.claude,
        cli_settings.codex,
        cli_settings.openrouter,
        cli_settings.opencode,
        cli_settings.mock,
    ].count(True) > 1:
        raise ValueError(
            "Cannot specify multiple LLM engines at once. Choose one of --claude, --codex, --openrouter, --opencode, or --mock."
        )

    with get_ui_manager():
        log(
            f"Configuration loaded:\n```json\n{config.model_dump_json(indent=2)}\n```",
            LLMOutputType.STATUS,
        )

        # This is the only place where get_llm() should be called.
        if cli_settings.mock:
            from ok.llms.mock import MockLLM

            _llm_instance = MockLLM(model=cli_settings.model, mock_delay=cli_settings.mock_delay)
        elif cli_settings.claude:
            _llm_instance = get_llm(engine="claude", model=cli_settings.model)
        elif cli_settings.codex:
            _llm_instance = get_llm(engine="codex", model=cli_settings.model)
        elif cli_settings.openrouter:
            _llm_instance = get_llm(engine="openrouter", model=cli_settings.model)
        elif cli_settings.opencode:
            _llm_instance = get_llm(engine="opencode", model=cli_settings.model)
        else:
            _llm_instance = get_llm(engine="gemini", model=cli_settings.model)

        effective_cwd = Path(os.path.abspath(str(cli_settings.cwd) if cli_settings.cwd else os.getcwd()))

        # Ensure the .ok directory exists
        if not OK_TEMP_DIR.exists():
            log(f"Creating agent directory at {OK_TEMP_DIR}", message_type=LLMOutputType.STATUS)
            OK_TEMP_DIR.mkdir(parents=True, exist_ok=True)

        # XXX: Initialize state file if it doesn't exist.
        # But actually, always erase the state. We don't have proper resumability yet since we don't save evaluations, etc.
        # if not STATE_FILE.exists():
        write_state({})

        base = cli_settings.base if cli_settings.base is not None else config.default_base or "main"

        log(f"Repo directory: {effective_cwd}", LLMOutputType.STATUS)

        log("Starting agentic loop", LLMOutputType.STATUS)

        set_phase("Agent initialized")

        selected_tasks = cli_settings.prompt or []
        task_results: list[TaskResult] = []

        for i, task_prompt in enumerate(selected_tasks, 1):
            with eliot.start_action(
                action_type="task",
                task_number=i,
                task=task_prompt,
            ):
                log(f"Processing task {i}/{len(selected_tasks)}: '{task_prompt}'", LLMOutputType.STATUS)
                work_dir: Path | None = None
                using_worktree: bool = False
                task_status = "Failed"
                last_commit_hash = "N/A"
                task_error = None

                try:
                    if cli_settings.no_worktree:
                        # If no worktree is specified, use the effective_cwd directly
                        work_dir = effective_cwd
                        log(
                            f"Worktrees disabled, using working directory for the task: {work_dir}",
                            LLMOutputType.STATUS,
                        )
                    else:
                        # Create a new worktree for each task
                        work_dir = Path(tempfile.mkdtemp(prefix=f"ok_task_{i}_"))
                        await git_utils.add_worktree(work_dir, rev=base, cwd=effective_cwd)
                        using_worktree = True

                    os.chdir(work_dir)
                    await process_task(task_prompt, i, base_rev=base, cwd=work_dir, llm=_llm_instance)
                    task_status = "Success"
                    last_commit_hash = await git_utils.get_current_commit_hash(cwd=work_dir)
                except Exception as e:
                    task_error = str(e)
                    log(f"Error processing task {i}: {e}", LLMOutputType.TOOL_ERROR)
                finally:
                    task_results.append(
                        TaskResult(
                            task=task_prompt,
                            status=task_status,
                            last_commit_hash=last_commit_hash,
                            error=task_error,
                        )
                    )
                    # Clean up worktree and return to original directory
                    if using_worktree and work_dir and work_dir.exists():
                        try:
                            # Change back to the original directory before removing worktree
                            os.chdir(effective_cwd)
                            await git_utils.remove_worktree(work_dir, cwd=effective_cwd)
                        except Exception as e:
                            log(
                                f"Error cleaning up temporary worktree {work_dir}: {e}",
                                LLMOutputType.TOOL_ERROR,
                            )

        log("Agentic loop completed", LLMOutputType.STATUS)
        set_phase("Agentic loop completed")
        display_task_summary(task_results)

    # Ensure we are back in the original effective_cwd
    os.chdir(effective_cwd)


async def _signal_handler(nursery: trio.Nursery) -> None:
    """Handles SIGINT signals to gracefully shut down the agent."""
    with trio.open_signal_receiver(signal.SIGINT) as signal_chan:
        async for _ in signal_chan:
            if _llm_instance:
                pid = _llm_instance.terminate_llm_process()
                if pid:
                    print(f"LLM process with PID {pid} killed.")
            nursery.cancel_scope.cancel()
            return


async def _main() -> None | SystemExit:
    """
    Initializes the nursery, starts the signal handler and the main work function,
    and ensures graceful shutdown.
    """
    with eliot.start_action(
        action_type="main",
    ):
        async with trio.open_nursery() as nursery:
            try:
                nursery.start_soon(_signal_handler, nursery)
                await work()
            except SystemExit as e:
                return e
            finally:
                nursery.cancel_scope.cancel()


def main() -> None:
    """
    Entry point for the agent application.
    """

    result = trio.run(_main)
    match result:
        case None:
            exit(0)
        case SystemExit():
            raise result
        case _:
            assert_never(result)
