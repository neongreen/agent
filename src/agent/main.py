"""
Main entry point for the agent application.

This module handles command-line argument parsing, configuration loading,
and orchestration of the agent's task processing.
"""

import argparse
import os
import signal
import sys
import tempfile
from pathlib import Path

import rich

from agent import git_utils
from agent.cli_settings import CLISettings
from agent.config import AGENT_SETTINGS as config
from agent.constants import AGENT_TEMP_DIR
from agent.llm import get_llm
from agent.logging import LLMOutputType, display_task_summary
from agent.state_manager import write_state
from agent.task_orchestrator import process_task
from agent.ui import get_ui_manager, set_phase
from agent.utils import log


_llm_instance = None


def _signal_handler(signum, frame):
    global _llm_instance
    if _llm_instance:
        pid = _llm_instance.terminate_llm_process()
        if pid:
            print(f"LLM process with PID {pid} killed.")
    sys.exit(1)


def main() -> None:
    """
    Main entry point for the agent application.

    This module handles command-line argument parsing, configuration loading,
    and orchestration of the agent's task processing.

    Parses command-line arguments, sets up the environment, and initiates
    the agentic loop for task processing.
    """
    global _llm_instance

    signal.signal(signal.SIGINT, _signal_handler)

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
    if not AGENT_TEMP_DIR.exists():
        AGENT_TEMP_DIR.mkdir(parents=True, exist_ok=True)

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
            from agent.llms.mock import MockLLM

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

        # Ensure the .agent directory exists
        if not AGENT_TEMP_DIR.exists():
            log(f"Creating agent directory at {AGENT_TEMP_DIR}", message_type=LLMOutputType.STATUS)
            AGENT_TEMP_DIR.mkdir(parents=True, exist_ok=True)

        # XXX: Initialize state file if it doesn't exist.
        # But actually, always erase the state. We don't have proper resumability yet since we don't save evaluations, etc.
        # if not STATE_FILE.exists():
        write_state({})

        base = cli_settings.base if cli_settings.base is not None else config.default_base or "main"

        log(f"Repo directory: {effective_cwd}", LLMOutputType.STATUS)

        log("Starting agentic loop", LLMOutputType.STATUS)

        set_phase("Agent initialized")

        selected_tasks = cli_settings.prompt or []
        task_results = []

        for i, task_prompt in enumerate(selected_tasks, 1):
            log(f"Processing task {i}/{len(selected_tasks)}: '{task_prompt}'", LLMOutputType.STATUS)
            work_dir: Path | None = None
            using_worktree: bool = False
            task_status = "Failed"
            task_commit_hash = "N/A"
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
                    work_dir = Path(tempfile.mkdtemp(prefix=f"agent_task_{i}_"))
                    git_utils.add_worktree(work_dir, rev=base, cwd=effective_cwd)
                    using_worktree = True

                os.chdir(work_dir)
                process_task(task_prompt, i, base_rev=base, cwd=work_dir, llm=_llm_instance)
                task_status = "Success"
                task_commit_hash = git_utils.get_current_commit_hash(cwd=work_dir)
            except Exception as e:
                task_error = str(e)
                log(f"Error processing task {i}: {e}", LLMOutputType.TOOL_ERROR)
            finally:
                task_results.append(
                    {
                        "prompt": task_prompt,
                        "status": task_status,
                        "work_dir": str(work_dir) if work_dir else None,
                        "commit_hash": task_commit_hash,
                        "error": task_error,
                    }
                )
                # Clean up worktree and return to original directory
                if using_worktree and work_dir and work_dir.exists():
                    try:
                        # Change back to the original directory before removing worktree
                        os.chdir(effective_cwd)
                        git_utils.remove_worktree(work_dir, cwd=effective_cwd)
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


if __name__ == "__main__":
    main()
