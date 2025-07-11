"""Gemini LLM provider."""

import os
from pathlib import Path
from typing import Optional

from agent.llms.base import LLMBase
from agent.logging import LLMOutputType, log
from agent.ui import update_status
from agent.utils import run


class Gemini(LLMBase):
    """Gemini LLM provider."""

    def __init__(self, model: Optional[str]):
        super().__init__(model)
        if "GEMINI_API_KEY" in os.environ:
            log(
                "GEMINI_API_KEY is set; gemini-cli will be using the provided key",
                message_type=LLMOutputType.STATUS,
            )
        else:
            log(
                "GEMINI_API_KEY not found in environment; gemini-cli will be using whatever auth it uses by default",
                message_type=LLMOutputType.STATUS,
            )

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
        """Runs the Gemini LLM."""
        gemini_model = self.model or "gemini-2.5-flash"
        command = ["gemini", "-m", gemini_model, *(["--yolo"] if yolo else []), "-p", prompt]
        log(prompt, message_type=LLMOutputType.PROMPT)
        status_message = phase or "Calling Gemini"
        if step_number is not None:
            status_message = f"Step {step_number}: {status_message}"
        if attempt_number is not None:
            status_message = f"{status_message}, Attempt {attempt_number}"

        result = run(
            command,
            status_message,
            command_human=command[:-1] + ["<prompt>"],
            directory=cwd,
            status_message=status_message,
            log_stdout=False,
            store_process=True,
        )
        if result.success:
            self.llm_process = result.process
            response = result.stdout.strip()
            if response.startswith("Loaded cached credentials."):
                response = response.split("Loaded cached credentials.", maxsplit=1)[-1].strip()
            update_status("Successful.")
            log(response, message_type=response_type)
            return response
        else:
            return None
