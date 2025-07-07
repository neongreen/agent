# Agent

## Description

This tool provides an agentic loop for processing tasks.

## Features

- Iterative planning phase with Gemini approval
- Iterative implementation phase with Gemini evaluation
- Git branch management for each task
- Configurable via `.agent.toml`

## Installation

Install `uv`, then:

```bash
uvx git+https://github.com/neongreen/agent
```

This runs the agent from the latest commit on the `main` branch of the repository.

## Usage

### Basic Usage

To process a single task, provide the task description as a prompt:

```bash
uvx git+https://github.com/neongreen/agent "Implement a new user authentication module"
```


### Specifying Working Directory

You can specify a different working directory for the agent to operate in using the `--cwd` flag:

```bash
uvx git+https://github.com/neongreen/agent "Fix bug in login flow" --cwd /path/to/your/project
```

### Specifying Base Branch

By default, the agent will create task branches from `main`. You can specify a different base branch, commit, or git specifier using the `--base` flag:

```bash
uvx git+https://github.com/neongreen/agent "Add feature X" --base develop
```

### Suppressing Output

To suppress informational output from the agent, use the `--quiet` flag:

```bash
uvx git+https://github.com/neongreen/agent "Optimize image loading" --quiet
```

### Choosing LLM CLI

By default, the agent uses the Gemini CLI for language model calls.
To use the Claude Code CLI instead, pass the `--claude` flag:

```bash
uvx git+https://github.com/neongreen/agent --claude "Implement feature X"
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

## Dev notes

To run from source locally, run:

```bash
uv sync
uv run agent
```

## License

This project is licensed under the MIT License.
