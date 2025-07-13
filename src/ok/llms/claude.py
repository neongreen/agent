"""Claude LLM provider."""

from pathlib import Path
from typing import Optional

from ok.llms.base import LLMBase
from ok.utils import run


class Claude(LLMBase):
    """Claude LLM provider."""

    async def _run(self, prompt: str, yolo: bool, *, cwd: Path, config) -> Optional[str]:
        """Runs the Claude LLM."""
        command = ["claude", *(["--dangerously-skip-permissions"] if yolo else []), "-p", prompt]
        result = await run(
            command,
            "Calling Claude",
            command_human=command[:-1] + ["<prompt>"],
            directory=cwd,
            run_timeout_seconds=config.llm_timeout_seconds,
        )
        if result.success:
            response = result.stdout.strip()
            return response
        else:
            return None
