"""Opencode LLM provider."""

from pathlib import Path
from typing import Optional

from ok.constants import OK_STATE_BASE_DIR
from ok.llms.base import LLMBase
from ok.utils import run


class Opencode(LLMBase):
    """Opencode LLM provider."""

    async def _run(
        self,
        prompt: str,
        yolo: bool,
        *,
        cwd: Path,
    ) -> Optional[str]:
        """Runs the Opencode LLM."""
        if self.model is None:
            self.model = "github-copilot/gpt-4.1"
        opencode_path = OK_STATE_BASE_DIR / "bin" / "opencode"
        if not opencode_path.exists():
            # This is a fatal error, so we can't use the logger.
            # The logger is initialized in the main function, but this is called before that.
            # TODO: Fix this.
            print(f"Opencode CLI (custom version) not found at {opencode_path}. Please run 'mise run build-opencode'.")
            return None
        command = [str(opencode_path), "run", "--print", "--model", self.model, prompt]
        result = await run(
            command,
            "Calling Opencode",
            command_human=command[:-1] + ["<prompt>"],
            directory=cwd,
            status_message="Calling Opencode",
            log_stdout=False,
            store_process=True,
        )
        if result.success:
            response = result.stdout.strip()
            content = response.split("Text  ", maxsplit=1)[-1].strip()
            return content
        else:
            return None
