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
from .config import AGENT_SETTINGS as config
from .constants import AGENT_TEMP_DIR
from .llm import LLM
from .state_manager import write_state
from .task_orchestrator import process_task
from .ui import status_manager
from .utils import log


def display_task_summary(task_results: list) -> None:
    """Displays a summary of the processed tasks."""
    log("\n--- Task Summary ---", message_type="thought")
    for result in task_results:
        log(f"Prompt: {result['prompt']}", message_type="thought")
        log(f"Status: {result['status']}", message_type="thought")
        if result["worktree"]:
            log(f"Worktree: {result['worktree']}", message_type="thought")
        if result["commit_hash"] != "N/A":
            log(f"Commit: {result['commit_hash']}", message_type="thought")
        if result["error"]:
            log(f"Error: {result['error']}", message_type="tool_output_error")
        log("--------------------", message_type="thought")


def main() -> None:
    """
    Main function to run the agent.

    Parses command-line arguments, sets up the environment, and initiates
    the agentic loop for task processing.
    """
    parser = argparse.ArgumentParser(description="Agentic task processing tool")
    parser.add_argument("--quiet", action="store_true", help="Suppress informational output")
    parser.add_argument("--cwd", help="Working directory for task execution")
    parser.add_argument(
        "--base",
        default=None,
        help="Base branch, commit, or git specifier to switch to before creating a task branch (default: main or from config)",
    )
    parser.add_argument("--claude", action="store_true", help="Use Claude Code CLI instead of Gemini for LLM calls")
    parser.add_argument("--codex", action="store_true", help="Use Codex CLI instead of Gemini for LLM calls")
    parser.add_argument("--openrouter", default=None, help="Use OpenRouter (via Codex); specify the model name")
    parser.add_argument("--opencode", action="store_true", help="Use Opencode CLI instead of Gemini for LLM calls")
    parser.add_argument(
        "--show-config",
        action="store_true",
        help="Show the current configuration and exit",
    )
    parser.add_argument(
        "--no-worktree",
        action="store_true",
        help="Work directly in the target directory rather than in a temporary Git worktree.",
    )
    parser.add_argument("prompt", nargs="*", help="Task(s) to do")

    args = parser.parse_args()

    # Create the agent dir before even doing any logging
    if not AGENT_TEMP_DIR.exists():
        AGENT_TEMP_DIR.mkdir(parents=True, exist_ok=True)

    if args.show_config:
        rich.print(config.model_dump_json(indent=2))
        exit(0)

    if config.quiet_mode:
        # If quiet mode is enabled, suppress informational output
        # This needs to be handled early, before any logging occurs
        pass  # Actual suppression logic would go here or be handled by the logger itself

    log(
        f"Configuration loaded:\n{config.model_dump_json(indent=2)}",
        message_type="thought",
    )

    # Set LLM engine if requested
    if [args.claude, args.codex, args.openrouter is not None].count(True) > 1:
        parser.error("Cannot specify multiple LLM engines at once. Choose one of --claude, --codex, or --openrouter.")

    # This is the only place where LLM() should be instantiated.
    if args.claude:
        llm = LLM(engine="claude", model=None)
    elif args.codex:
        llm = LLM(engine="codex", model=None)
    elif args.openrouter is not None:
        llm = LLM(engine="openrouter", model=args.openrouter)
    elif args.opencode:
        llm = LLM(engine="opencode", model=None)  # The default is set in the LLM class
    else:
        llm = LLM(engine="gemini", model=None)

    effective_cwd = Path(os.path.abspath(str(args.cwd) if args.cwd else os.getcwd()))

    # Ensure the .agent directory exists
    if not AGENT_TEMP_DIR.exists():
        log(f"Creating agent directory at {AGENT_TEMP_DIR}", message_type="thought")
        AGENT_TEMP_DIR.mkdir(parents=True, exist_ok=True)

    # XXX: Initialize state file if it doesn't exist.
    # But actually, always erase the state. We don't have proper resumability yet since we don't save evaluations, etc.
    # if not STATE_FILE.exists():
    write_state({})

    # Determine base branch from args or config
    if args.base is None:
        args.base = config.default_base or "main"

    worktree_path = None
    # Worktree is enabled by default unless --no-worktree is specified
    if not args.no_worktree:
        log("Temporary worktree mode enabled. Will create a git worktree for the task.", message_type="thought")
        worktree_path = Path(tempfile.mkdtemp(prefix="agent_worktree_"))
        try:
            git_utils.add_worktree(worktree_path, rev=args.base, cwd=effective_cwd)
            work_dir = worktree_path
        except Exception as e:
            log(f"Failed to create temporary worktree: {e}", message_type="tool_output_error")
            exit(1)
    else:
        work_dir = effective_cwd

    log(f"Using working directory: {work_dir}", message_type="thought")

    log("Starting agentic loop", message_type="thought")

    try:
        status_manager.init_status_bar()
        status_manager.set_phase("Agent initialized")

        selected_tasks = args.prompt
        task_results = []

        for i, task_prompt in enumerate(selected_tasks, 1):
            log(f"Processing task {i}/{len(selected_tasks)}: '{task_prompt}'", message_type="thought")
            current_worktree_path: Path | None = None
            task_status = "Failed"
            task_commit_hash = "N/A"
            task_error = None

            try:
                # Create a new worktree for each task
                current_worktree_path = Path(tempfile.mkdtemp(prefix=f"agent_task_{i}_"))
                git_utils.add_worktree(current_worktree_path, rev=args.base, cwd=effective_cwd)

                # Change to the new worktree directory
                os.chdir(current_worktree_path)

                process_task(task_prompt, i, base_rev=args.base, cwd=current_worktree_path, llm=llm)
                task_status = "Success"
                task_commit_hash = git_utils.get_current_commit_hash(cwd=current_worktree_path)

            except Exception as e:
                task_error = str(e)
                log(f"Error processing task {i}: {e}", message_type="tool_output_error")
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
                            message_type="tool_output_error",
                        )

        log("Agentic loop completed")
        status_manager.set_phase("Agentic loop completed")
        display_task_summary(task_results)

    finally:
        status_manager.cleanup_status_bar()
        # Ensure we are back in the original effective_cwd
        os.chdir(effective_cwd)


if __name__ == "__main__":
    main()
