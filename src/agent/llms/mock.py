"""Mock LLM for testing purposes."""

import tomllib
from pathlib import Path
from typing import Optional

import trio

from agent.llms.base import LLMBase


class MockLLM(LLMBase):
    """Mock LLM that reads responses from a TOML file."""

    def __init__(self, model: Optional[str] = None, mock_delay: int = 5):
        """
        Initializes the MockLLM.

        Args:
            model: The model to use for the LLM (not used by this class).
            mock_delay: The delay in seconds to wait before returning a response.
        """
        super().__init__(model)
        self.mock_delay = mock_delay
        with open("mock_llm_data.toml", "rb") as f:
            self.mock_data = tomllib.load(f)

    async def _run(
        self,
        prompt: str,
        yolo: bool,
        *,
        cwd: Path,
    ) -> Optional[str]:
        """
        Runs the LLM with the given prompt.

        Args:
            prompt: The prompt to run.
            yolo: Whether to bypass safety checks.
            cwd: The current working directory.

        Returns:
            The response from the LLM, or None if an error occurred.
        """
        await trio.sleep(self.mock_delay)
        for item in self.mock_data.get("prompts", []):
            if item.get("prompt") == prompt:
                return item.get("response")
        return "No mock response found for this prompt."
