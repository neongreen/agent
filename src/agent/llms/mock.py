"""Mock LLM for testing purposes."""

import tomllib
from pathlib import Path
from typing import Optional

from agent.llms.base import LLMBase
from agent.logging import LLMOutputType


class MockLLM(LLMBase):
    """Mock LLM that reads responses from a TOML file."""

    def __init__(self, model: Optional[str] = None):
        """
        Initializes the MockLLM.

        Args:
            model: The model to use for the LLM (not used by this class).
        """
        super().__init__(model)
        with open("mock_llm_data.toml", "rb") as f:
            self.mock_data = tomllib.load(f)

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
        """
        Runs the LLM with the given prompt.

        Args:
            prompt: The prompt to run.
            yolo: Whether to bypass safety checks.
            cwd: The current working directory.
            phase: The current phase of the agent.
            step_number: The current step number.
            attempt_number: The current attempt number.
            response_type: The type of response to log.

        Returns:
            The response from the LLM, or None if an error occurred.
        """
        for item in self.mock_data.get("prompts", []):
            if item.get("prompt") == prompt:
                return item.get("response")
        return "No mock response found for this prompt."
