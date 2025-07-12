"""OpenRouter LLM provider."""

import os
from pathlib import Path
from typing import Optional

from agent.llms.codex import Codex


class OpenRouter(Codex):
    """OpenRouter LLM provider."""

    def __init__(self, model: Optional[str]):
        super().__init__(model)
        if model is None:
            raise ValueError("Model must be specified for OpenRouter.")
        if "OPENROUTER_API_KEY" not in os.environ:
            raise ValueError("OPENROUTER_API_KEY must be set for OpenRouter.")

    async def _run(
        self,
        prompt: str,
        yolo: bool,
        *,
        cwd: Path,
    ) -> Optional[str]:
        """Runs the OpenRouter LLM."""
        provider_url = "https://openrouter.ai/api/v1"
        provider_env_key = "OPENROUTER_API_KEY"
        return await self._run_codex(
            prompt,
            yolo,
            model=self.model,
            provider_url=provider_url,
            provider_env_key=provider_env_key,
            cwd=cwd,
        )
