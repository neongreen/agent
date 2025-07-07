from dataclasses import dataclass


@dataclass
class AgentConfig:
    """Configuration for the agent."""

    quiet_mode: bool = False
    judge_extra_prompt: str = ""
