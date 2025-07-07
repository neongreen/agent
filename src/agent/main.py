"""
Main entry point for the agent application.

This module handles command-line argument parsing, configuration loading,
and orchestration of the agent's task processing.
"""

import argparse
import os
import tempfile
from pathlib import Path

import rich

from . import git_utils
from .cli_settings import CLISettings
from .config import AGENT_SETTINGS as config
from .constants import AGENT_TEMP_DIR
from .llm import LLM
from .output_formatter import LLMOutputType, display_task_summary
from .state_manager import write_state
from .task_orchestrator import process_task
from .ui import status_manager
from .utils import log


def main() -> None:
    """
    Main entry point for the agent application.

    This module handles command-line argument parsing, configuration loading,
    and orchestration of the agent's task processing.

    Parses command-line arguments, sets up the environment, and initiates
    the agentic loop for task processing.
    """
    parser = argparse.ArgumentParser(description="Agentic loop")
    parser.add_argument("--quiet", action="store_true", help="Suppress informational output")
    parser.add_argument("--cwd", type=str, default=None, help="Working directory for task execution")
    parser.add_argument("--base", type=str, default=None, help="Base branch, commit, or git specifier")
    parser.add_argument("--claude", action="store_true", help="Use Claude Code CLI instead of Gemini for LLM calls")
    parser.add_argument("--codex", action="store_true", help="Use Codex CLI instead of Gemini for LLM calls")
    parser.add_argument(
        "--openrouter", type=str, default=None, help="Use OpenRouter (via Codex); specify the model name"
    )
    parser.add_argument("--opencode", action="store_true", help="Use Opencode CLI instead of Gemini for LLM calls")
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
        rich.print(config.model_dump_json(indent=2))
        exit(0)

    if config.quiet_mode:
        # If quiet mode is enabled, suppress informational output
        # This needs to be handled early, before any logging occurs
        # Actual suppression logic would go here or be handled by the logger itself
        pass

    log(
        f"Configuration loaded:\n{config.model_dump_json(indent=2)}",
        LLMOutputType.STATUS,
    )

    if [cli_settings.claude, cli_settings.codex, cli_settings.openrouter is not None].count(True) > 1:
        raise ValueError(
            "Cannot specify multiple LLM engines at once. Choose one of --claude, --codex, --openrouter, or --opencode."
        )

    # This is the only place where LLM() should be instantiated.
    if cli_settings.claude:
        llm = LLM(engine="claude", model=None)
    elif cli_settings.codex:
        llm = LLM(engine="codex", model=None)
    elif cli_settings.openrouter is not None:
        llm = LLM(engine="openrouter", model=cli_settings.openrouter)
    elif cli_settings.opencode:
        llm = LLM(engine="opencode", model=None)
    else:
        llm = LLM(engine="gemini", model=None)

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

    worktree_path = None
    # Worktree is enabled by default unless --no-worktree is specified
    if not cli_settings.no_worktree:
        log(
            "Temporary worktree mode enabled. Will create a git worktree for the task.",
            LLMOutputType.STATUS,
        )
        worktree_path = Path(tempfile.mkdtemp(prefix="agent_worktree_"))
        try:
            git_utils.add_worktree(worktree_path, rev=base, cwd=effective_cwd)
            work_dir = worktree_path
        except Exception as e:
            log(f"Failed to create temporary worktree: {e}", LLMOutputType.TOOL_ERROR)
            exit(1)
    else:
        work_dir = effective_cwd

    log(f"Using working directory: {work_dir}", LLMOutputType.STATUS)

    log("Starting agentic loop", LLMOutputType.STATUS)

    try:
        status_manager.init_status_bar()
        status_manager.set_phase("Agent initialized")

        selected_tasks = cli_settings.prompt or []
        task_results = []

        for i, task_prompt in enumerate(selected_tasks, 1):
            log(f"Processing task {i}/{len(selected_tasks)}: '{task_prompt}'", LLMOutputType.STATUS)
            current_worktree_path: Path | None = None
            task_status = "Failed"
            task_commit_hash = "N/A"
            task_error = None

            try:
                # Create a new worktree for each task
                current_worktree_path = Path(tempfile.mkdtemp(prefix=f"agent_task_{i}_"))
                git_utils.add_worktree(current_worktree_path, rev=base, cwd=effective_cwd)

                # Change to the new worktree directory
                os.chdir(current_worktree_path)
                process_task(task_prompt, i, base_rev=base, cwd=current_worktree_path, llm=llm)
                task_status = "Success"
                task_commit_hash = git_utils.get_current_commit_hash(cwd=current_worktree_path)
            except Exception as e:
                task_error = str(e)
                log(f"Error processing task {i}: {e}", LLMOutputType.TOOL_ERROR)
            finally:
                task_results.append(
                    {
                        "prompt": task_prompt,
                        "status": task_status,
                        "worktree": str(current_worktree_path) if current_worktree_path else None,
                        "commit_hash": task_commit_hash,
                        "error": task_error,
                    }
                )
                # Clean up worktree and return to original directory
                if current_worktree_path and current_worktree_path.exists():
                    try:
                        # Change back to the original working directory before removing worktree
                        os.chdir(effective_cwd)
                        git_utils.remove_worktree(current_worktree_path, cwd=effective_cwd)
                    except Exception as e:
                        log(
                            f"Error cleaning up temporary worktree {current_worktree_path}: {e}",
                            LLMOutputType.TOOL_ERROR,
                        )

        log("Agentic loop completed", LLMOutputType.STATUS)
        status_manager.set_phase("Agentic loop completed")
        display_task_summary(task_results)

    finally:
        status_manager.cleanup_status_bar()
        # Ensure we are back in the original effective_cwd
        os.chdir(effective_cwd)


if __name__ == "__main__":
    main()
