import argparse
import os
import pprint
import tomllib
from pathlib import Path

from pydantic import ValidationError

from .config import AgentConfig, TomlConfig
from .constants import AGENT_TEMP_DIR, STATE_FILE
from .gemini_agent import set_llm_engine
from .state_manager import write_state
from .task_orchestrator import process_task
from .ui import status_manager
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
    parser.add_argument("--claude", action="store_true", help="Use Claude Code CLI instead of Gemini for LLM calls")
    parser.add_argument("--codex", action="store_true", help="Use Codex CLI instead of Gemini for LLM calls")

    args = parser.parse_args()

    # Set LLM engine if requested
    if args.claude and args.codex:
        parser.error("Cannot specify both --claude and --codex")

    if args.claude:
        set_llm_engine("claude")
    elif args.codex:
        set_llm_engine("codex")

    # Create configuration object
    config = AgentConfig(quiet_mode=args.quiet)

    # Determine effective working directory
    effective_cwd = args.cwd if args.cwd else os.getcwd()
    effective_cwd = os.path.abspath(effective_cwd)

    # Ensure the .agent directory exists
    if not AGENT_TEMP_DIR.exists():
        log(f"Creating agent directory at {AGENT_TEMP_DIR}", message_type="thought", config=config)
        AGENT_TEMP_DIR.mkdir(parents=True, exist_ok=True)

    # Initialize state file if it doesn't exist
    if not STATE_FILE.exists():
        write_state({})

    # Use the effective working directory
    cwd = effective_cwd
    log(f"Using working directory: {cwd}", message_type="thought", config=config)

    # Read the config
    # (todo: should we read from .agent.toml in the currently checked out commit, or in base?)
    # (and if base -- well, how do we determine the base? it's in the config)
    agent_toml_path = Path(effective_cwd) / ".agent.toml"
    if agent_toml_path.exists():
        try:
            with open(agent_toml_path, "rb") as f:
                config_toml_raw = tomllib.load(f)
            try:
                config_toml = TomlConfig.model_validate(config_toml_raw)
                config.update_from_toml(config_toml)
                # Print the config values
                log(f"Loaded agent configuration from {agent_toml_path}", message_type="thought", config=config)

                log(
                    "Configuration resolved to:\n" + pprint.pformat(vars(config)), message_type="thought", config=config
                )
            except ValidationError as e:
                log(f"Error validating .agent.toml: {e}", message_type="tool_output_error", config=config)
        except Exception as e:
            log(f"Error reading or parsing .agent.toml: {e}", message_type="tool_output_error", config=config)

    # TODO: don't detect default like this!
    if "base" not in args or args.base == "main":  # Check if --base was not provided or is still default 'main'
        args.base = config.default_base or "main"

    log("Starting agentic loop", message_type="thought", config=config)

    try:
        status_manager.init_status_bar()
        status_manager.set_phase("Agent initialized")

        selected_tasks = [args.prompt]

        # Process each selected task
        for i, task in enumerate(selected_tasks, 1):
            try:
                process_task(task, i, args.base, cwd, config)
            except Exception as e:
                log(f"Error processing task {i}: {e}", message_type="tool_output_error", config=config)

        log("Agentic loop completed", config=config)
        status_manager.set_phase("Agentic loop completed")

    finally:
        status_manager.cleanup_status_bar()


if __name__ == "__main__":
    main()
