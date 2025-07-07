import argparse
import os
import sys
import tomllib
from pathlib import Path

from .config import AgentConfig
from .constants import STATE_FILE
from .gemini_agent import choose_tasks, discover_tasks
from .state_manager import write_state
from .task_processor import process_task
from .utils import log


def main() -> None:
    parser = argparse.ArgumentParser(description="Agentic task processing tool")
    parser.add_argument("prompt", help="Task source prompt or file path")
    parser.add_argument("--quiet", action="store_true", help="Suppress informational output")
    parser.add_argument("--cwd", help="Working directory for task execution")

    # Initialize default_base_from_toml before parsing args
    default_base_from_toml = "main"

    parser.add_argument(
        "--base",
        default=default_base_from_toml,
        help="Base branch, commit, or git specifier to switch to before creating a task branch (default: main or from .agent.toml)",
    )
    parser.add_argument(
        "--multi", action="store_true", help="Treat prompt as an instruction to find task, rather than a single task"
    )

    args = parser.parse_args()

    # Create configuration object
    agent_config = AgentConfig(quiet_mode=args.quiet)

    # Determine effective working directory
    effective_cwd = args.cwd if args.cwd else os.getcwd()
    effective_cwd = os.path.abspath(effective_cwd)

    # Initialize state file if it doesn't exist
    if not STATE_FILE.exists():
        write_state({})

    # Use the effective working directory
    cwd = effective_cwd
    log(f"Using working directory: {cwd}", message_type="thought", config=agent_config)

    # Update default_base_from_toml from .agent.toml if it exists in the effective_cwd
    agent_toml_path = Path(effective_cwd) / ".agent.toml"
    if agent_toml_path.exists():
        try:
            with open(agent_toml_path, "rb") as f:
                config = tomllib.load(f)
            if "default-base" in config:
                default_base_from_toml = config["default-base"]
                log(
                    f"Using default-base from .agent.toml: {default_base_from_toml}",
                    message_type="thought",
                    config=agent_config,
                )
            if "plan" in config and "judge-extra-prompt" in config["plan"]:
                judge_extra_prompt_from_toml = config["plan"]["judge-extra-prompt"]
                log(
                    f"Using plan.judge-extra-prompt from .agent.toml: {judge_extra_prompt_from_toml}",
                    message_type="thought",
                    config=agent_config,
                )
            else:
                judge_extra_prompt_from_toml = ""
        except Exception as e:
            log(f"Error reading or parsing .agent.toml: {e}", message_type="tool_output_error", config=agent_config)

    # Re-set the default for --base argument if it was not explicitly provided by the user
    # and a value was found in .agent.toml
    if "base" not in args or args.base == "main":  # Check if --base was not provided or is still default 'main'
        args.base = default_base_from_toml

    # Update agent config with judge extra prompt
    agent_config.judge_extra_prompt = judge_extra_prompt_from_toml

    log("Starting agentic loop", message_type="thought", config=agent_config)

    if args.multi:
        # Find tasks
        log("Treating prompt as an instruction to discover tasks", message_type="thought", config=agent_config)
        tasks = discover_tasks(args.prompt, cwd)
        if not tasks:
            log("No tasks discovered", message_type="thought", config=agent_config)
            sys.exit(1)
        selected_tasks = choose_tasks(tasks)
        if not selected_tasks:
            log("No tasks selected", message_type="thought", config=agent_config)
            sys.exit(0)
    else:
        selected_tasks = [args.prompt]

    # Process each selected task
    for i, task in enumerate(selected_tasks, 1):
        try:
            process_task(task, i, args.base, cwd, agent_config)
        except Exception as e:
            log(f"Error processing task {i}: {e}", message_type="tool_output_error", config=agent_config)

    log("Agentic loop completed", config=agent_config)


if __name__ == "__main__":
    main()
