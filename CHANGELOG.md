# CHANGELOG

## v0-next

Internal:
- Added a mock test for the implementation phase

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