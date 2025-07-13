"""Gemini LLM provider."""

from pathlib import Path
from typing import Optional

from ok.env import Env
from ok.llms.base import LLMBase


class Gemini(LLMBase):
    """Gemini LLM provider."""

    async def _run(
        self,
        env: Env,
        prompt: str,
        yolo: bool,
        *,
        cwd: Path,
    ) -> Optional[str]:
        """Runs the Gemini LLM."""
        gemini_model = self.model or "gemini-2.5-flash"
        command = ["gemini", "-m", gemini_model, *(["--yolo"] if yolo else []), "-p", prompt]

        result = await env.run(
            command,
            "Calling Gemini",
            command_human=command[:-1] + ["<prompt>"],
            directory=cwd,
            status_message="Calling Gemini",
            run_timeout_seconds=env.config.llm_timeout_seconds,
        )
        if result.success:
            response = result.stdout.strip()
            if response.startswith("Loaded cached credentials."):
                response = response.split("Loaded cached credentials.", maxsplit=1)[-1].strip()
            return response
        else:
            return None
