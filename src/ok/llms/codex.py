"""Codex LLM provider."""

import os
import tempfile
from pathlib import Path
from typing import Optional

from ok.constants import OK_TEMP_DIR
from ok.env import Env
from ok.llms.base import LLMBase


class Codex(LLMBase):
    """Codex LLM provider."""

    async def _run(self, env: Env, prompt: str, yolo: bool, *, cwd: Path) -> Optional[str]:
        """Runs the Codex LLM."""
        return await self._run_codex(env, prompt, yolo, model=self.model, cwd=cwd)

    async def _run_codex(
        self,
        env: Env,
        prompt: str,
        yolo: bool,
        *,
        cwd: Path,
        model: Optional[str] = None,
        provider_url: Optional[str] = None,
        provider_env_key: Optional[str] = None,
    ) -> Optional[str]:
        with tempfile.NamedTemporaryFile("r", prefix="ok-codex-output", dir=OK_TEMP_DIR, delete=True) as temp_file:
            temp_file_path = os.path.join(OK_TEMP_DIR, temp_file.name)
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
            result = await env.run(
                command,
                "Calling Codex",
                command_human=command[:-1] + ["<prompt>"],
                directory=cwd,
                run_timeout_seconds=env.config.llm_timeout_seconds,
            )
            if result.success:
                response = temp_file.read().strip()
                return response
            else:
                return None
