"""
Main entry point for the agent application.

This module handles command-line argument parsing, configuration loading,
and orchestration of the agent's task processing.
"""

import argparse
import os
import tempfile

import rich

from . import git_utils
from .config import AGENT_SETTINGS as config
from .constants import AGENT_TEMP_DIR
from .gemini_agent import set_llm_engine
from .state_manager import write_state
from .task_orchestrator import process_task
from .ui import status_manager
from .utils import log


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
    parser.add_argument(
        "--show-config",
        action="store_true",
        help="Show the current configuration and exit",
    )
    parser.add_argument(
        "--worktree",
        action="store_true",
        help="Create a git worktree in a temporary folder and perform work there.",
    )
    parser.add_argument("prompt", nargs="?", default="", help="Task to do")

    args = parser.parse_args()

    # Create the agent dir before even doing any logging
    if not AGENT_TEMP_DIR.exists():
        AGENT_TEMP_DIR.mkdir(parents=True, exist_ok=True)

    # TODO: --quiet should be handled before here, also with Pydantic
    if args.show_config:
        rich.print(config.model_dump_json(indent=2))
        exit(0)
    else:
        if not args.prompt:
            parser.error("You haven't specified a prompt. See --help for usage.")
            exit(1)
        log(
            f"Configuration loaded:\n{config.model_dump_json(indent=2)}",
            message_type="thought",
        )

    # Set LLM engine if requested
    if [args.claude, args.codex, args.openrouter is not None].count(True) > 1:
        parser.error("Cannot specify multiple LLM engines at once. Choose one of --claude, --codex, or --openrouter.")

    if args.claude:
        set_llm_engine("claude")
    elif args.codex:
        set_llm_engine("codex")
    elif args.openrouter is not None:
        set_llm_engine("openrouter", model=args.openrouter)
    else:
        set_llm_engine("gemini")

    # Determine effective working directory (where we will be looking for the repo, etc)
    effective_cwd = str(args.cwd) if args.cwd else os.getcwd()
    effective_cwd = os.path.abspath(effective_cwd)

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

    if args.worktree:
        log("Temporary worktree mode enabled. Will create a git worktree for the task.", message_type="thought")
        worktree_path = tempfile.mkdtemp(prefix="agent_worktree_")
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

        selected_tasks = [args.prompt]

        # Process each selected task
        for i, task in enumerate(selected_tasks, 1):
            try:
                process_task(task, i, base_rev=args.base, cwd=work_dir)
            except Exception as e:
                log(f"Error processing task {i}: {e}", message_type="tool_output_error")

        log("Agentic loop completed")
        status_manager.set_phase("Agentic loop completed")

    finally:
        status_manager.cleanup_status_bar()
        if worktree_path:
            try:
                git_utils.remove_worktree(worktree_path, cwd=work_dir)
            except Exception as e:
                log(f"Error cleaning up temporary worktree: {e}", message_type="tool_output_error")


if __name__ == "__main__":
    main()
