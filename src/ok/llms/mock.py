"""Mock LLM for testing purposes."""

import re
import tomllib
from pathlib import Path
from typing import Optional

import trio

from ok.llms.base import LLMBase


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
        for item in self.mock_data.get("prompts", []):
            if not isinstance(item, dict) or "prompt" not in item or "response" not in item:
                raise ValueError(f"Each prompt must be a dictionary with 'prompt' and 'response' keys, found: {item}")
            try:
                re.compile(item["prompt"])
            except re.error as e:
                raise ValueError(f"Invalid regex in prompt: {item['prompt']}\nError: {e}") from None

    async def _run(
        self,
        prompt: str,
        yolo: bool,
        *,
        cwd: Path,
        config,
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
            if re.match(item.get("prompt"), prompt, re.MULTILINE | re.DOTALL):
                return item.get("response")
        return "No mock response found for this prompt."
