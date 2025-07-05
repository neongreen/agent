from dataclasses import dataclass
from typing import Optional

from pydantic import BaseModel, Field


class PlanConfig(BaseModel):
    judge_extra_prompt: Optional[str] = Field(None, alias="judge-extra-prompt")
    planner_extra_prompt: Optional[str] = Field(None, alias="planner-extra-prompt")


class ImplementCompletionConfig(BaseModel):
    judge_extra_prompt: Optional[str] = Field(None, alias="judge-extra-prompt")


class ImplementConfig(BaseModel):
    extra_prompt: Optional[str] = Field(None, alias="extra-prompt")
    judge_extra_prompt: Optional[str] = Field(None, alias="judge-extra-prompt")
    completion: Optional[ImplementCompletionConfig] = None


class TomlConfig(BaseModel):
    default_base: Optional[str] = Field(None, alias="default-base")
    quiet_mode: Optional[bool] = Field(None, alias="quiet-mode")
    plan: Optional[PlanConfig] = None
    implement: Optional[ImplementConfig] = None


@dataclass
class AgentConfig:
    """Configuration for the agent."""

    default_base: Optional[str] = None
    quiet_mode: bool = False
    plan_judge_extra_prompt: str = ""
    plan_planner_extra_prompt: str = ""
    implement_extra_prompt: str = ""
    implement_judge_extra_prompt: str = ""
    implement_completion_judge_extra_prompt: str = ""

    def update_from_toml(self, config: TomlConfig) -> None:
        """Update the agent configuration from a TOML config object."""
        if config.default_base is not None:
            self.default_base = config.default_base
        if config.quiet_mode is not None:
            self.quiet_mode = config.quiet_mode
        if config.plan and config.plan.judge_extra_prompt is not None:
            self.plan_judge_extra_prompt = config.plan.judge_extra_prompt
        if config.plan and config.plan.planner_extra_prompt is not None:
            self.plan_planner_extra_prompt = config.plan.planner_extra_prompt
        if config.implement and config.implement.extra_prompt is not None:
            self.implement_extra_prompt = config.implement.extra_prompt
        if config.implement and config.implement.judge_extra_prompt is not None:
            self.implement_judge_extra_prompt = config.implement.judge_extra_prompt
        if (
            config.implement
            and config.implement.completion
            and config.implement.completion.judge_extra_prompt is not None
        ):
            self.implement_completion_judge_extra_prompt = config.implement.completion.judge_extra_prompt
