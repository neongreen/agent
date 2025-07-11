"""Codex LLM provider."""

import os
import tempfile
from pathlib import Path
from typing import Optional

from agent.constants import AGENT_TEMP_DIR
from agent.llms.base import LLMBase
from agent.logging import LLMOutputType, log
from agent.ui import status_manager
from agent.utils import run


class Codex(LLMBase):
    """Codex LLM provider."""

    def run(
        self,
        prompt: str,
        yolo: bool,
        *,
        cwd: Path,
        phase: Optional[str] = None,
        step_number: Optional[int] = None,
        attempt_number: Optional[int] = None,
        response_type: LLMOutputType,
    ) -> Optional[str]:
        """Runs the Codex LLM."""
        return self._run_codex(prompt, yolo, model=self.model, cwd=cwd, phase=phase, response_type=response_type)

    def _run_codex(
        self,
        prompt: str,
        yolo: bool,
        *,
        cwd: Path,
        model: Optional[str] = None,
        provider_url: Optional[str] = None,
        provider_env_key: Optional[str] = None,
        phase: Optional[str] = None,
        response_type: LLMOutputType,
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
            log(prompt, message_type=LLMOutputType.PROMPT)
            result = run(
                command,
                "Calling Codex",
                command_human=command[:-1] + ["<prompt>"],
                directory=cwd,
                status_message=phase or "Calling Codex",
                log_stdout=False,
                store_process=True,
            )
            if result.success:
                status_manager.update_status("Successful.")
                response = temp_file.read().strip()
                log(response, message_type=response_type)
                return response
            else:
                return None
