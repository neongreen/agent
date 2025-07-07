from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class CLISettings(BaseSettings):
    quiet: bool = Field(
        default=False,
        description="Suppress informational output",
        alias="quiet",
    )
    cwd: Optional[str] = Field(
        default=None,
        description="Working directory for task execution",
        alias="cwd",
    )
    base: Optional[str] = Field(
        default=None,
        description="Base branch, commit, or git specifier",
        alias="base",
    )
    claude: bool = Field(
        default=False,
        description="Use Claude Code CLI instead of Gemini for LLM calls",
        alias="claude",
    )
    codex: bool = Field(
        default=False,
        description="Use Codex CLI instead of Gemini for LLM calls",
        alias="codex",
    )
    openrouter: Optional[str] = Field(
        default=None,
        description="Use OpenRouter (via Codex); specify the model name",
        alias="openrouter",
    )
    opencode: bool = Field(
        default=False,
        description="Use Opencode CLI instead of Gemini for LLM calls",
        alias="opencode",
    )
    show_config: bool = Field(
        default=False,
        description="Show the current configuration and exit",
        alias="show-config",
    )
    no_worktree: bool = Field(
        default=False,
        description="Work directly in the target directory rather than in a temporary Git worktree.",
        alias="no-worktree",
    )
    prompt: Optional[list[str]] = Field(
        default=None,
        description="Task(s) to do",
        alias="prompt",
    )

    model_config = SettingsConfigDict(
        populate_by_name=True,
        extra="allow",
    )
