"""
Configuration management for the agent.

This module defines the data structures and logic for managing agent settings,
including plan and implementation configurations, and handles loading settings
from TOML files.
"""

from typing import Any

from pydantic import AliasGenerator, BaseModel, Field, model_validator
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict, TomlConfigSettingsSource

# TODO: idk how to allow env vars, I get "extra inputs are not permitted"

kebab_alias_generator = AliasGenerator(
    validation_alias=lambda field_name: field_name.replace("_", "-"),
    serialization_alias=lambda field_name: field_name.replace("_", "-"),
)
"""Alias generator to convert snake_case field names to kebab-case for TOML settings."""


class PlanConfig(BaseModel):
    """Configuration for the planning phase of the agent."""

    planner_extra_prompt: str = Field(default="", description="Additional instructions for *generating* the plan.")
    judge_extra_prompt: str = Field(default="", description="Additional instructions for *evaluating* the plan.")

    model_config = SettingsConfigDict(
        alias_generator=kebab_alias_generator,
        populate_by_name=True,
    )


class ImplementCompletionConfig(BaseModel):
    """Configuration for the completion phase of implementation."""

    judge_extra_prompt: str = Field(
        default="",
        description="Additional instructions for *evaluating* whether the implementation is complete. This phase determines if the agent has successfully implemented the task.",
    )

    model_config = SettingsConfigDict(
        alias_generator=kebab_alias_generator,
        populate_by_name=True,
    )


class ImplementConfig(BaseModel):
    """Configuration for the implementation phase of the agent."""

    extra_prompt: str = Field(default="", description="Additional prompt for *implementing* the plan.")
    judge_extra_prompt: str = Field(default="", description="Additional prompt for *evaluating* the implementation.")
    completion: ImplementCompletionConfig = Field(
        default_factory=ImplementCompletionConfig,
        description="Configuration for the completion phase of implementation.",
    )

    model_config = SettingsConfigDict(
        alias_generator=kebab_alias_generator,
        populate_by_name=True,
    )


class AgentSettings(BaseSettings):
    """
    AgentSettings defines the configuration for the agent.
    """

    default_base: str = Field(
        default="main",
        description="Default base branch, commit, or git specifier to switch to before creating a task branch",
    )
    quiet_mode: bool = Field(default=False, description="Suppress informational output")
    plan: PlanConfig = Field(default_factory=PlanConfig, description="Configuration for the planning phase.")
    implement: ImplementConfig = Field(
        default_factory=ImplementConfig, description="Configuration for the implementation phase."
    )
    post_implementation_hook_command: str = Field(
        default="",
        description="Shell command to run after each implementation step, e.g. 'ruff format'",
    )

    model_config = SettingsConfigDict(
        populate_by_name=True,
        alias_generator=kebab_alias_generator,
        toml_file=".agent.toml",
    )

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
        """
        Customizes the order of settings sources.

        Settings are loaded with the following priority:
        1. TOML file ('.agent.toml')
        2. Default values
        """
        return env_settings, TomlConfigSettingsSource(settings_cls), init_settings


# Instantiate once and reuse everywhere
__all__ = ["AGENT_SETTINGS", "AgentSettings"]
AGENT_SETTINGS: AgentSettings = AgentSettings()
