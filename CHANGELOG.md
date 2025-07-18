# CHANGELOG

`[OK]` denotes changes made by this agent.
`[CLINE]` is for the Cline extension.
`[COPILOT]` is for GitHub Copilot.

## v0-next

## v0-2025.07.14

Added:

- All config options are now available as CLI flags, and vice versa.
- `[OK]` Log file location is printed at the end of the run.
- Added support for timeouts for shell command and LLM calls.
- `[COPILOT]` The agent does plan refinement before starting another step.

Changed:

- The default base commit is now `HEAD` instead of `main`.
- The default base config option is just `base` instead of `default_base`.
- `[COPILOT]` Tinkering with the lack-of-progress stopping.

Fixed:

- Ctrl+C now works for real!!! (I spent half a day on this.)
- Stdout/stderr formatting (again).

Internal:

- `[COPILOT+EMILY]` Refactored everything to use `Env` instead of mocking `run` and `log`.
- `[OK+EMILY]` Removed some user-facing debug output.
- Switched to dprint for formatting.

AI failures:

- 🔴 OK flash: asked it to document non-obvious things (Ctrl+C, Pydantic).
  It failed, and for Ctrl+C it was actually wrong about `SystemExit`.

- 🔴 OK flash: asked it to create an integration test showing that running naked `ok` outputs help.
  It failed and only committed a `.txt` file showing that it *doesn't* output help.
  (Which is true, but the AI should've fixed it.)

- 🔴 OK flash: asked to add hard timeouts for tests.
  It mucked around for a while. I gave up and added a very simple `pytest-timeout` one-line integration.

## v0-2025.07.12

Added:

- `[OK+EMILY]` Gemini now understands "pro" and "flash" as synonyms for `gemini-2.5-pro` and `gemini-2.5-flash`.
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
- ~~The summary table works now.~~
  - (2025.07.14) Actually no, it still doesn't.

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
