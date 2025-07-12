# CHANGELOG

`[OK]` denotes changes made by this agent.
`[CLINE]` is for the Cline extension.

## v0-next

Added:

- All config options are now available as CLI flags, and vice versa.

Changed:

- The default base commit is now `HEAD` instead of `main`.
- The default base config option is just `base` instead of `default_base`.

Fixed:

- Stdout/stderr formatting (again).

## v0-2025.07.12

Added:

- `[OK]` The new `post-implementation-check-command` setting runs a command after post-implementation hook.
  If it fails, the agent will make another attempt without going to the judge first.
- `[CLINE]` The `--mock` option to use a mock (data from a file) instead of an LLM.
- `[CLINE]` The `--mock-delay` option to set a sleep duration for each mock LLM invocation.
- Many more logs.

Changed:

- The agent is now called `ok` because all the good tools have two-letter names (jj, uv, ty, rg, fd).
  - The branch prefix is now `ok/` instead of `agent/`.
  - The config file is now `.ok.toml` instead of `.agent.toml`.
- Logs are now written to a file in the `~/.ok/logs/` directory, one file per run.

Fixed:

- `[OK]` Ctrl+C now stops the agent and shuts down the LLM process. (Partial fix)
- `[OK]` Feedback about previous attempts is now rendered as a Markdown blockquote.
- `[CLINE]` Don't complain when there are no changes to commit.
- Worked around gemini-cli outputting "Loaded cached credentials." in the response.
- Asking LLMs to output the verdict in the last line of their response - maybe it will improve verdict detection.
- The summary table works now.

Internal:

- `[CLINE]` Moved to Trio for async code.
- `[CLINE]` Refactored the `LLM` class, centralized logging in `LLMBase`.
- Added a mock test for the implementation phase.
- `mise run ok` runs the agent from a separate venv.

## v0-2025.07.09

Fixed:

- Plans render more nicely (as blockquotes)

Removed:

- `quiet` is no longer in the config (for now), although it's possible it never worked anyway

Internal:

- Agent loop is now a state machine
- Logging via Eliot

## v0-2025.07.07

Added:

- Gemini: Tell the user whether `GEMINI_API_KEY` is set
- `--model` option to specify the model

Changed:

- `--openrouter` is now a boolean flag. The model for OpenRouter is now specified using the `--model` argument.

Fixed:

- Better prompts for judge verdicts to work around GPT 4.1 issues
- Worktree creation no longer fails when basing off the currently checked-out branch
- Worktrees are no longer created twice (once at the start and once for each task)
- `--no-worktree` is actually respected now
- Miscellaneous logging fixes

## v0-2025.07.06

Added:

- Support for [Opencode](https://opencode.ai) and thus for GitHub Copilot as well

Fixed:

- Prettier logging

## v0-2025.07.05

Added:

- Initial version with support for Claude Code, Codex CLI, Gemini CLI, and OpenRouter (via Codex)
