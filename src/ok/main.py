"""
Main entry point for the agent application.

This module handles command-line argument parsing, configuration loading,
and orchestration of the agent's task processing.
"""

import os
import shutil
import tempfile
from pathlib import Path
from typing import Optional, assert_never

import eliot
import rich
import trio

import ok.log
from ok import git_utils
from ok.config import ConfigModel, get_settings
from ok.constants import OK_TEMP_DIR
from ok.env import Env, RunResult
from ok.llm import get_llm
from ok.llms.mock import MockLLM
from ok.log import LLMOutputType
from ok.state_manager import write_state
from ok.task_orchestrator import process_task
from ok.task_result import TaskResult, display_task_summary
from ok.ui import get_ui_manager, set_phase
from ok.utils import real_run


class RealEnv(Env):
    """
    A real environment class that extends Env for actual task processing.
    """

    def __init__(self, config: ConfigModel) -> None:
        self.config = config
        ok.log.init_logging()

    def log(self, message: str, message_type: ok.log.LLMOutputType, message_human: str | None = None) -> None:
        ok.log.real_log(message, message_type, message_human=message_human)

    def log_debug(self, message: str, **kwargs) -> None:
        eliot.log_message("log", message=message, **kwargs)

    async def run(
        self,
        command: str | list[str],
        description=None,
        command_human: Optional[list[str]] = None,
        status_message: Optional[str] = None,
        *,
        directory: Path,
        shell: bool = False,
        run_timeout_seconds: int,
    ) -> RunResult:
        return await real_run(
            env=self,
            command=command,
            description=description,
            command_human=command_human,
            status_message=status_message,
            directory=directory,
            shell=shell,
            run_timeout_seconds=run_timeout_seconds,
        )


async def work(nursery: trio.Nursery) -> None:
    """
    This is almost the entry point for the agent.
    The actual entry point is `main()`, which calls `_main()`, which calls `work()`.

    This function handles command-line argument parsing, configuration loading,
    and orchestration of the agent's task processing.

    Parses command-line arguments, sets up the environment, and initiates
    the agentic loop for task processing.
    """

    # Populate OkSettings from parsed args and config file
    settings = get_settings()
    config: ConfigModel = settings

    # Create the agent dir before even doing any logging
    if not OK_TEMP_DIR.exists():
        OK_TEMP_DIR.mkdir(parents=True, exist_ok=True)

    if settings.show_config:
        rich.print(f"```json\n{config.model_dump_json(indent=2)}\n```")
        exit(0)

    with get_ui_manager():
        env = RealEnv(config=config)
        del settings

        env.log(
            f"Configuration loaded:\n```json\n{config.model_dump_json(indent=2)}\n```",
            LLMOutputType.STATUS,
        )

        # This is the only place where get_llm() should be called.
        if config.llm.engine == "mock":
            llm_instance = MockLLM(model=config.llm.model, mock_delay=config.mock_cfg.delay)
        else:
            llm_instance = get_llm(engine=config.llm.engine, model=config.llm.model)

        task_results: list[TaskResult] = []

        for i, task in enumerate(config.tasks):
            prompt = task.prompt
            base = task.base or config.base
            cwd = Path(task.cwd or config.cwd or os.getcwd())
            no_worktree = task.no_worktree or config.no_worktree
            del task

            # Ensure the session directory exists.
            # TODO: this will break if we do tasks in parallel.
            env.log_debug("Creating session directory", session_directory=str(OK_TEMP_DIR))
            if OK_TEMP_DIR.exists():
                shutil.rmtree(OK_TEMP_DIR, ignore_errors=True)
            OK_TEMP_DIR.mkdir(parents=True, exist_ok=True)

            # XXX: Initialize state file if it doesn't exist.
            # But actually, always erase the state. We don't have proper resumability yet since we don't save evaluations, etc.
            # if not STATE_FILE.exists():
            write_state({})

            env.log(f"Repo directory: {cwd}", LLMOutputType.STATUS)

            set_phase("Agent initialized")

            with eliot.start_action(
                action_type="task",
                task_number=i,
                task=prompt,
            ):
                env.log(f"Processing task {i}/{len(config.tasks)}: '{prompt}'", LLMOutputType.STATUS)
                work_dir: Path | None = None
                using_worktree: bool = False
                task_status = "Failed"
                last_commit_hash = "N/A"
                task_error = None

                try:
                    if no_worktree:
                        # If no worktree is specified, use the effective_cwd directly
                        work_dir = cwd
                        env.log(
                            f"Worktrees disabled, using working directory for the task: {work_dir}",
                            LLMOutputType.STATUS,
                        )
                    else:
                        # Create a new worktree for each task
                        work_dir = Path(tempfile.mkdtemp(prefix=f"ok_task_{i}_"))
                        await git_utils.add_worktree(env, work_dir, rev=base, cwd=cwd)
                        using_worktree = True

                    os.chdir(work_dir)
                    await process_task(env, task=prompt, task_num=i, base_rev=base, cwd=work_dir, llm=llm_instance)
                    task_status = "Success"
                    last_commit_hash = await git_utils.get_current_commit_hash(env, cwd=work_dir)
                except Exception as e:
                    env.log_debug("Caught an exception", exc=repr(e))
                    task_error = str(e)
                    env.log(f"Error processing task {i}: {e}", LLMOutputType.TOOL_ERROR)
                finally:
                    task_results.append(
                        TaskResult(
                            task=prompt,
                            status=task_status,
                            last_commit_hash=last_commit_hash,
                            error=task_error,
                        )
                    )
                    # Clean up worktree and return to original directory
                    if using_worktree and work_dir and work_dir.exists():
                        try:
                            # Change back to the original directory before removing worktree
                            os.chdir(cwd)
                            await git_utils.remove_worktree(env, work_dir, cwd=cwd)
                        except Exception as e:
                            env.log_debug("Caught an exception", exc=repr(e))
                            env.log(
                                f"Error cleaning up temporary worktree {work_dir}: {e}",
                                LLMOutputType.TOOL_ERROR,
                            )

        env.log("Agentic loop completed", LLMOutputType.STATUS)
        set_phase("Agentic loop completed")
        display_task_summary(task_results)
        log_file_path = ok.log.get_log_file_path()
        ok.log.console.print(f"Session log file: {log_file_path}\n\n", style="bold green")


async def _main() -> None | SystemExit:
    with eliot.start_action(
        action_type="main",
    ):
        async with trio.open_nursery() as nursery:
            try:
                await work(nursery)
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
