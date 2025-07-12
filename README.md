# ok

## Description

This is an agentic loop for processing tasks.
It's ok.

## Features

- Agentic loop
- Judging stuff
- Configurable

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

### Worktree Mode

The agent uses Git worktrees by default for task implementations. This provides a clean, isolated environment for changes.

To disable worktree mode, use the `--no-worktree` flag:

```bash
uvx git+https://github.com/neongreen/agent "Implement feature Y" --no-worktree
```

This will perform the work in the current directory (or in the `--cwd` directory if specified).

### Suppressing Output

To suppress informational output from the agent, use the `--quiet` flag:

```bash
uvx git+https://github.com/neongreen/agent "Optimize image loading" --quiet
```

### Choosing LLM CLI

By default, the agent uses the Gemini CLI for language model calls.

- `--claude` - Use Claude Code
- `--codex` - Use [OpenAI Codex](https://github.com/openai/codex) CLI
- `--openrouter` - Use OpenRouter (via Codex CLI). This is a boolean flag.
- `--opencode` - Use [Opencode CLI](https://opencode.ai) for LLM calls (uses `github-copilot/gpt-4.1` by default)
- `--model MODEL` - Specify the model to use for any of the above

```bash
# Use Claude Code
uvx git+https://github.com/neongreen/agent --claude "Implement feature X"

# Use OpenAI Codex; for some reason `codex` doesn't grab its own key from its own config when ran non-interactively
OPENAI_API_KEY=$(jq -r .OPENAI_API_KEY ~/.codex/auth.json) uvx git+https://github.com/neongreen/agent --codex "Implement feature X"

# Use OpenRouter with a specific model
OPENROUTER_API_KEY=... uvx git+https://github.com/neongreen/agent --openrouter --model "x-ai/grok-3" "Implement feature X"

# Use Opencode CLI (uses github-copilot/gpt-4.1 by default)
uvx git+https://github.com/neongreen/agent --opencode "Implement feature X"
```

CLI tools must be installed beforehand.

## Configuration

The agent can be configured using a `.ok.toml` file in the project root directory.
This file allows you to set default behaviors and provide additional instructions for the agent's planning phase.

Sample `.ok.toml`:

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
uv run ok
```

If running from a diffent folder:

```bash
uvx --from ../agent --no-cache --isolated ok <prompt>
```

### JSON Schema for Configuration

The configuration schema (`config.schema.json`) is autogenerated from the Pydantic models in `agent.config`.

To generate the schema, run:

```bash
mise run generate-schema
```

To validate the schema against the current `.ok.toml`, run:

```bash
mise run check-schema
```

## License

This project is licensed under the MIT License.
