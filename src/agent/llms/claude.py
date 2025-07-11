"""Claude LLM provider."""

from pathlib import Path
from typing import Optional

from agent.llms.base import LLMBase
from agent.logging import LLMOutputType, log
from agent.ui import update_status
from agent.utils import run


class Claude(LLMBase):
    """Claude LLM provider."""

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
        """Runs the Claude LLM."""
        command = ["claude", *(["--dangerously-skip-permissions"] if yolo else []), "-p", prompt]
        log(prompt, message_type=LLMOutputType.PROMPT)
        result = run(
            command,
            "Calling Claude",
            command_human=command[:-1] + ["<prompt>"],
            directory=cwd,
            status_message=phase or "Calling Claude",
            log_stdout=False,
            store_process=True,
        )
        if result.success:
            response = result.stdout.strip()
            update_status("Successful.")
            log(response, message_type=response_type)
            return response
        else:
            return None
