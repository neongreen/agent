"""Claude LLM provider."""

from pathlib import Path
from typing import Optional

from agent.llms.base import LLMBase
from agent.utils import run


class Claude(LLMBase):
    """Claude LLM provider."""

    async def _run(self, prompt: str, yolo: bool, *, cwd: Path) -> Optional[str]:
        """Runs the Claude LLM."""
        command = ["claude", *(["--dangerously-skip-permissions"] if yolo else []), "-p", prompt]
        result = await run(
            command,
            "Calling Claude",
            command_human=command[:-1] + ["<prompt>"],
            directory=cwd,
            log_stdout=False,
            store_process=True,
        )
        if result.success:
            response = result.stdout.strip()
            return response
        else:
            return None
