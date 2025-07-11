"""Opencode LLM provider."""

from pathlib import Path
from typing import Optional

from agent.constants import AGENT_STATE_BASE_DIR
from agent.llms.base import LLMBase
from agent.logging import LLMOutputType, log
from agent.ui import status_manager
from agent.utils import run


class Opencode(LLMBase):
    """Opencode LLM provider."""

    def __init__(self, model: Optional[str]):
        super().__init__(model)
        if model is None:
            log(
                "Defaulting to GitHub Copilot GPT-4.1 model for Opencode",
                message_type=LLMOutputType.STATUS,
            )
            self.model = "github-copilot/gpt-4.1"

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
        """Runs the Opencode LLM."""
        assert self.model is not None, "Checked in the constructor."
        opencode_path = AGENT_STATE_BASE_DIR / "bin" / "opencode"
        if not opencode_path.exists():
            log(
                f"Opencode CLI (custom version) not found at {opencode_path}. Please run 'mise run build-opencode'.",
                message_type=LLMOutputType.TOOL_ERROR,
            )
            return None
        command = [str(opencode_path), "run", "--print", "--model", self.model, prompt]
        log(prompt, message_type=LLMOutputType.PROMPT)
        result = run(
            command,
            phase or "Calling Opencode",
            command_human=command[:-1] + ["<prompt>"],
            directory=cwd,
            status_message=phase or "Calling Opencode",
            log_stdout=False,
            store_process=True,
        )
        if result.success:
            response = result.stdout.strip()
            content = response.split("Text  ", maxsplit=1)[-1].strip()
            status_manager.update_status("Successful.")
            log(content, message_type=response_type)
            return content
        else:
            return None
