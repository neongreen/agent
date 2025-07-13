"""Claude LLM provider."""

from pathlib import Path
from typing import Optional

from ok.env import Env
from ok.llms.base import LLMBase


class Claude(LLMBase):
    """Claude LLM provider."""

    async def _run(self, env: Env, prompt: str, yolo: bool, *, cwd: Path) -> Optional[str]:
        """Runs the Claude LLM."""
        command = ["claude", *(["--dangerously-skip-permissions"] if yolo else []), "-p", prompt]
        result = await env.run(
            command,
            "Calling Claude",
            command_human=command[:-1] + ["<prompt>"],
            directory=cwd,
            run_timeout_seconds=env.config.llm_timeout_seconds,
        )
        if result.success:
            response = result.stdout.strip()
            return response
        else:
            return None
