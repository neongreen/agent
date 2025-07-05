from dataclasses import dataclass
from typing import Optional


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

    # TODO: use nicer parsing
    def update_from_toml(self, config: dict) -> None:
        """Update the agent configuration from a TOML config dictionary."""
        self.default_base = config.get(
            "default-base",
            self.default_base,
        )
        self.quiet_mode = config.get(
            "quiet-mode",
            self.quiet_mode,
        )
        self.plan_judge_extra_prompt = config.get("plan", {}).get(
            "judge-extra-prompt",
            self.plan_judge_extra_prompt,
        )
        self.plan_planner_extra_prompt = config.get("plan", {}).get(
            "planner-extra-prompt",
            self.plan_planner_extra_prompt,
        )
        self.implement_extra_prompt = config.get("implement", {}).get(
            "extra-prompt",
            self.implement_extra_prompt,
        )
        self.implement_judge_extra_prompt = config.get("implement", {}).get(
            "judge-extra-prompt",
            self.implement_judge_extra_prompt,
        )
        self.implement_completion_judge_extra_prompt = (
            config.get("implement", {})
            .get("completion", {})
            .get(
                "judge-extra-prompt",
                self.implement_completion_judge_extra_prompt,
            )
        )
