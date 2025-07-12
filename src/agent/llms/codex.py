"""Codex LLM provider."""

import os
import tempfile
from pathlib import Path
from typing import Optional

from agent.constants import AGENT_TEMP_DIR
from agent.llms.base import LLMBase
from agent.utils import run


class Codex(LLMBase):
    """Codex LLM provider."""

    async def _run(self, prompt: str, yolo: bool, *, cwd: Path) -> Optional[str]:
        """Runs the Codex LLM."""
        return await self._run_codex(prompt, yolo, model=self.model, cwd=cwd)

    async def _run_codex(
        self,
        prompt: str,
        yolo: bool,
        *,
        cwd: Path,
        model: Optional[str] = None,
        provider_url: Optional[str] = None,
        provider_env_key: Optional[str] = None,
    ) -> Optional[str]:
        with tempfile.NamedTemporaryFile(
            "r", prefix="agent-codex-output", dir=AGENT_TEMP_DIR, delete=True
        ) as temp_file:
            temp_file_path = os.path.join(AGENT_TEMP_DIR, temp_file.name)
            command = [
                "codex",
                *(["--dangerously-bypass-approvals-and-sandbox"] if yolo else ["--ask-for-approval=never"]),
                *(
                    [
                        "-c=model_provider=custom",
                        "-c=model_providers.custom.name=custom",
                        f"-c=model_providers.custom.base_url={provider_url}",
                    ]
                    if provider_url
                    else []
                ),
                *([f"-c=model_providers.custom.env_key={provider_env_key}"] if provider_env_key else []),
                "exec",
                *(["--model", model] if model else []),
                f"--output-last-message={temp_file_path}",
                prompt,
            ]
            result = await run(
                command,
                "Calling Codex",
                command_human=command[:-1] + ["<prompt>"],
                directory=cwd,
                log_stdout=False,
                store_process=True,
            )
            if result.success:
                response = temp_file.read().strip()
                return response
            else:
                return None
