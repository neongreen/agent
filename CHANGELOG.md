# CHANGELOG

## v0-2025.07.07

Added:
- Gemini: Tell the user whether `GEMINI_API_KEY` is set

Fixed:
- Better prompts for judge verdicts to work around GPT 4.1 issues
- Worktree creation no longer fails when basing off the currently checked-out branch
- Worktrees are no longer created twice (once at the start and once for each task)
- Miscellaneous logging fixes

## v0-2025.07.06

Added:
- Support for [Opencode](https://opencode.ai) and thus for GitHub Copilot as well

Fixed:
- Prettier logging

## v0-2025.07.05

Added:
- Initial version with support for Claude Code, Codex CLI, Gemini CLI, and OpenRouter (via Codex)