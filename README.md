# Agent

## Description

This tool provides an agentic loop for processing tasks.

## Features

- Task discovery from prompts or files
- Iterative planning phase with Gemini approval
- Iterative implementation phase with Gemini evaluation
- Git branch management for each task
- Configurable via `.agent.toml`

## Installation

1. **Install `uv`**
2. **Run:** `uv run python -m src.main`

## Usage

### Basic Usage

To process a single task, provide the task description as a prompt:

```bash
uv run python -m src.main "Implement a new user authentication module"
```

### Multi-Task Mode

If your prompt contains multiple distinct tasks, you can use the `--multi` flag to have the agent discover and allow you to select tasks:
```bash
uv run python -m src.main "Refactor the database layer, then add a new API endpoint for user profiles."

```bash
uv run python -m src.main --multi "Refactor the database layer, then add a new API endpoint for user profiles."
```

The agent will list the discovered tasks and prompt you to select which ones to process.
Each task will be processed in its own git branch starting from the specified base.
Tasks are *parallel*, not sequential.

### Specifying Working Directory

You can specify a different working directory for the agent to operate in using the `--cwd` flag:

```bash
uv run python -m src.main "Fix bug in login flow" --cwd /path/to/your/project
```

### Specifying Base Branch

By default, the agent will create task branches from `main`. You can specify a different base branch, commit, or git specifier using the `--base` flag:

```bash
uv run python -m src.main "Add feature X" --base develop
```

### Suppressing Output

To suppress informational output from the agent, use the `--quiet` flag:

```bash
uv run python -m src.main "Optimize image loading" --quiet
```

### Choosing LLM CLI

By default, the agent uses the Gemini CLI for language model calls.
To use the Claude Code CLI instead, pass the `--claude` flag:

```bash
uv run python -m src.main --claude "Implement feature X"
```

## Configuration

The agent can be configured using a `.agent.toml` file in the project root directory.
This file allows you to set default behaviors and provide additional instructions for the agent's planning phase.

Sample `.agent.toml`:

```toml
# Specifies the default base branch, commit, or git specifier to use when creating task branches.
# If not set, `main` is used as the default.
default-base = "HEAD"

# If set to true, suppresses informational output from the agent.
quiet-mode = false

# Specifies a shell command to execute after each implementation phase round.
# This command will be executed after Gemini provides an implementation, but before it is evaluated.
# This can be used for custom hooks, like running linters or tests.
post-implementation-hook-command = ''
# Example:
# post-implementation-hook-command = "echo 'Hook executed!'"
# post-implementation-hook-command = "npm test"
# post-implementation-hook-command = "ruff check ."

[plan]
# Provides an additional prompt to the Gemini model during the plan review process.
# This can be used to enforce specific rules or guidelines for plans.
judge-extra-prompt = """
  You must reject the plan if it proposes writing tests.
  """

# Provides an additional prompt to the Gemini model during the planning phase.
# This can be used to guide the agent's planning process.
planner-extra-prompt = ""

[implement]
# Provides an additional prompt to the Gemini model during the implementation phase.
# This can be used to guide the agent's implementation process.
extra-prompt = ""

# Provides an additional prompt to the Gemini model during the implementation review process.
# This can be used to enforce specific rules or guidelines for implementations.
judge-extra-prompt = ""

[implement.completion]
# Provides an additional prompt to the Gemini model during the implementation completion review process.
# This can be used to enforce specific rules or guidelines for completed implementations.
judge-extra-prompt = ""
```

## License

This project is licensed under the MIT License.
