"""
Configuration management for the agent.

This module defines the data structures and logic for managing agent settings,
including plan and implementation configurations, and handles loading settings
from TOML files.

Terminology:
- "Model" is the *data model* -- it is the config type that the agent actually wants to use.
- "Settings" is the *reader* -- it is an auxiliary type that we use to parse the configuration.
  It will be similar to the model, but not exactly the same.
"""

from typing import Any, Literal

from pydantic import AliasGenerator, BaseModel, Field, model_validator
from pydantic_settings import (
    BaseSettings,
    CliApp,
    CliPositionalArg,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
)

import ok.util.pydantic
from ok.util.pydantic import _CliHideDefault, with_metadata


# TODO: idk how to allow env vars, I get "extra inputs are not permitted"

kebab_alias_generator = AliasGenerator(
    validation_alias=lambda field_name: field_name.replace("_", "-"),
    serialization_alias=lambda field_name: field_name.replace("_", "-"),
)
"""Alias generator to convert snake_case field names to kebab-case for TOML settings."""


class PlanModel(BaseModel):
    """Configuration for the planning phase of the agent."""

    planner_extra_prompt: str = Field(default="", description="Additional instructions for *generating* the plan.")
    judge_extra_prompt: str = Field(default="", description="Additional instructions for *evaluating* the plan.")

    model_config = SettingsConfigDict(
        alias_generator=kebab_alias_generator,
        populate_by_name=True,
    )


class ImplementCompletionModel(BaseModel):
    """Configuration for the completion phase of implementation."""

    judge_extra_prompt: str = Field(
        default="",
        description="Additional instructions for *evaluating* whether the implementation is complete. This phase determines if the agent has successfully implemented the task.",
    )

    model_config = SettingsConfigDict(
        alias_generator=kebab_alias_generator,
        populate_by_name=True,
    )


class ImplementModel(BaseModel):
    """Configuration for the implementation phase of the agent."""

    extra_prompt: str = Field(default="", description="Additional prompt for *implementing* the plan.")
    judge_extra_prompt: str = Field(default="", description="Additional prompt for *evaluating* the implementation.")
    max_implementation_attempts: int = Field(
        default=10, description="Maximum number of attempts for the implementation phase."
    )
    max_consecutive_failures: int = Field(
        default=3, description="Maximum number of consecutive failures before giving up."
    )

    completion: ImplementCompletionModel = Field(
        default_factory=ImplementCompletionModel,
        description="Configuration for the completion phase of implementation.",
    )

    model_config = SettingsConfigDict(
        alias_generator=kebab_alias_generator,
        populate_by_name=True,
    )


class MockLLMModel(BaseModel):
    """Configuration for the --mock LLM."""

    delay: int = Field(
        default=5,
        description="Set a 'sleep' inside each mock llm invocation",
    )

    model_config = SettingsConfigDict(
        alias_generator=kebab_alias_generator,
        populate_by_name=True,
    )


class LLMEngineModel(BaseModel):
    """Configuration for the LLM used by the agent."""

    engine: Literal["gemini", "claude", "codex", "openrouter", "opencode", "mock"] = Field(
        default="gemini",
        description="LLM engine to use (e.g., 'gemini', 'claude', 'codex', 'openrouter', 'opencode', 'mock')",
    )
    model: str | None = Field(
        default=None,
        description=(
            "Model to use for the specified LLM engine. For `gemini`, you can use shortcuts 'pro' and 'flash'."
        ),
    )

    model_config = SettingsConfigDict(
        alias_generator=kebab_alias_generator,
        populate_by_name=True,
    )


class TaskModel(BaseModel):
    """
    Configuration for the task to be executed by the agent.
    """

    prompt: str = Field(
        description="Task description or prompt to execute",
    )

    # All of these will use the defaults from the top level ConfigModel if not specified.

    cwd: str | None = Field(
        default=None,
        description="Working directory for task execution",
    )
    base: str | None = Field(
        default=None,
        description="Base branch, commit, or git specifier",
    )
    no_worktree: bool | None = Field(
        default=None,
        description="Work directly in the target directory rather than in a temporary Git worktree.",
    )

    model_config = SettingsConfigDict(
        alias_generator=kebab_alias_generator,
        populate_by_name=True,
    )


class ConfigModel(BaseModel, populate_by_name=True, alias_generator=kebab_alias_generator):
    """
    ConfigModel defines the configuration for the agent.
    Currently it is equivalent to the `.ok.toml` config file.
    It's intended to be used by most of the agent code.
    """

    # Timeout for any shell command run with `run` (in seconds)
    run_timeout_seconds: int = Field(
        default=10,
        description="Maximum time (in seconds) allowed for any shell command, excluding LLM calls",
    )
    # Timeout for LLM calls (in seconds)
    llm_timeout_seconds: int = Field(
        default=300,
        description="Maximum time (in seconds) allowed for any LLM call",
    )

    quiet: bool = Field(
        default=False,
        description="Suppress informational output",
    )

    plan: PlanModel = Field(default_factory=PlanModel, description="Configuration for the planning phase.")
    implement: ImplementModel = Field(
        default_factory=ImplementModel, description="Configuration for the implementation phase."
    )
    llm: LLMEngineModel = Field(
        default_factory=LLMEngineModel, description="Configuration for the LLM used by the agent."
    )
    mock_cfg: MockLLMModel = Field(default_factory=MockLLMModel, description="Configuration for the --mock LLM.")
    tasks: list[TaskModel] = with_metadata(
        Field([], description="Configuration for the tasks to be executed by the agent.", alias="tasks"),
        _CliHideDefault,
    )
    post_implementation_hook_command: str = with_metadata(
        Field(
            default="",
            description="Shell command to run after each implementation step, e.g. 'ruff format'",
        ),
        _CliHideDefault,
    )

    post_implementation_check_command: str = with_metadata(
        Field(
            default="",
            description="Shell command to run after the post-implementation-hook-command. If it fails, the agent makes another attempt and its stdout/stderr is the feedback.",
        ),
        _CliHideDefault,
    )

    # Global defaults for tasks, will be overridden by individual task settings if specified.
    cwd: str | None = with_metadata(
        Field(
            default=None,
            description="Working directory for task execution. (default: current working directory)",
        ),
        _CliHideDefault,
    )
    base: str = Field(
        default="HEAD",
        description="Base branch, commit, or git specifier for tasks.",
    )
    no_worktree: bool = Field(
        default=False,
        description="Work directly in the target directory rather than in a temporary Git worktree.",
    )


class ConfigFileSettings(ConfigModel, BaseSettings, toml_file=".ok.toml"):
    """
    Reading `ConfigModel` from the config file.
    """

    @model_validator(mode="before")
    @classmethod
    def remove_schema_field(cls, values: Any) -> Any:
        """
        Removes the '$schema' field from the settings, which is used in TOML
        for file validation but not needed internally.
        """
        if isinstance(values, dict):
            values.pop("$schema", None)
        return values

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return TomlConfigSettingsSource(settings_cls), init_settings


class CliSettings(ConfigFileSettings, cli_hide_none_type=True):
    # CliSettings extends ConfigFileSettings with a) CLI-specific fields and b) CLI overrides for config values.

    """
    ok agent
    """

    # `exclude` means that this field is not part of the config model, just a CLI-only field.

    show_config: bool = Field(
        default=False,
        description="Print the current configuration and exit",
        exclude=True,
    )

    gemini: bool = Field(
        default=False,  # It is actually going to be the default since we set it in the model_validator
        description="Use gemini-cli as the LLM",
        exclude=True,
    )
    claude: bool = Field(
        default=False,
        description="Use Claude Code as the LLM",
        exclude=True,
    )
    codex: bool = Field(
        default=False,
        description="Use Codex CLI as the LLM",
        exclude=True,
    )
    openrouter: bool = Field(
        default=False,
        description="Use openrouter (via Codex) as the LLM",
        exclude=True,
    )
    opencode: bool = Field(
        default=False,
        description="Use OpenCode as the LLM",
        exclude=True,
    )
    mock: bool = Field(
        default=False,
        description="Use mock LLM (for testing purposes)",
        exclude=True,
    )

    # TODO: what is before/after?
    @model_validator(mode="after")
    def validate_llm_engine(self) -> "CliSettings":
        """
        Validates that only one LLM engine is specified.
        Raises ValueError if multiple engines are set to True.
        """
        engines = [
            self.gemini,
            self.claude,
            self.codex,
            self.openrouter,
            self.opencode,
            self.mock,
        ]
        if engines.count(True) > 1:
            raise ValueError(
                "Cannot specify multiple LLM engines at once. Choose one of --gemini, --claude, --codex, --openrouter, --opencode, or --mock."
            )
        else:
            if self.gemini:
                self.llm.engine = "gemini"
            elif self.claude:
                self.llm.engine = "claude"
            elif self.codex:
                self.llm.engine = "codex"
            elif self.openrouter:
                self.llm.engine = "openrouter"
            elif self.opencode:
                self.llm.engine = "opencode"
            elif self.mock:
                self.llm.engine = "mock"
        return self

    prompts: CliPositionalArg[list[str]] = Field(
        default=[],
        description="Task prompt, can be specified multiple times to do multiple tasks in a row",
        exclude=True,
    )

    @model_validator(mode="after")
    def validate_tasks(self) -> "CliSettings":
        """
        Translate positional task arguments into the task prompt list.
        """

        if self.tasks and self.prompts:
            raise ValueError("Cannot specify both --tasks and positional task arguments. Use one or the other.")
        self.tasks = [TaskModel(prompt=prompt) for prompt in self.prompts]
        return self


def get_settings() -> CliSettings:
    """
    Gets everything from config files, CLI, etc.
    """
    return CliApp.run(
        CliSettings,
        cli_settings_source=ok.util.pydantic.CliSettingsSource(CliSettings),
    )


if __name__ == "__main__":
    # If this module is run directly, show the CLI help.
    # This is useful for testing or debugging purposes.
    #
    #     python src/ok/config.py --help
    #
    settings = get_settings()
    if settings.show_config:
        print(settings.model_dump_json(indent=2))
        exit(0)
