from typing import Any

from pydantic import AliasGenerator, BaseModel, Field, model_validator
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict, TomlConfigSettingsSource

# TODO: idk how to allow env vars, I get "extra inputs are not permitted"

kebab_alias_generator = AliasGenerator(
    validation_alias=lambda field_name: field_name.replace("_", "-"),
    serialization_alias=lambda field_name: field_name.replace("_", "-"),
)


class PlanConfig(BaseModel):
    judge_extra_prompt: str = Field(default="")
    planner_extra_prompt: str = Field(default="")

    model_config = SettingsConfigDict(
        alias_generator=kebab_alias_generator,
        populate_by_name=True,
    )


class ImplementCompletionConfig(BaseModel):
    judge_extra_prompt: str = Field(default="")

    model_config = SettingsConfigDict(
        alias_generator=kebab_alias_generator,
        populate_by_name=True,
    )


class ImplementConfig(BaseModel):
    extra_prompt: str = Field(default="")
    judge_extra_prompt: str = Field(default="")
    completion: ImplementCompletionConfig = ImplementCompletionConfig()

    model_config = SettingsConfigDict(
        alias_generator=kebab_alias_generator,
        populate_by_name=True,
    )


class AgentSettings(BaseSettings):
    default_base: str = Field(
        default="main",
        description="Default base branch, commit, or git specifier to switch to before creating a task branch",
    )
    quiet_mode: bool = Field(default=False, description="Suppress informational output")
    plan: PlanConfig = Field(default_factory=PlanConfig)
    implement: ImplementConfig = Field(default_factory=ImplementConfig)
    post_implementation_hook_command: str = Field(
        default="",
        description="Shell command to run after each implementation step, e.g. 'ruff format'",
    )

    model_config = SettingsConfigDict(
        populate_by_name=True,
        alias_generator=kebab_alias_generator,
        toml_file=".agent.toml",
    )

    # This method removes the $schema field from the settings - it's used in TOML to validate the file
    @model_validator(mode="before")
    @classmethod
    def remove_schema_field(cls, values: Any) -> Any:
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
        # Settings priority:
        # 1. TOML file (config.toml)
        # 2. Default values
        return TomlConfigSettingsSource(settings_cls), init_settings


# Instantiate once and reuse everywhere
__all__ = ["AGENT_SETTINGS", "AgentSettings"]
AGENT_SETTINGS: AgentSettings = AgentSettings()
