"""Base class for LLM providers."""

import subprocess
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from ok.logging import LLMOutputType, log


class LLMBase(ABC):
    """Abstract base class for LLM providers."""

    def __init__(self, model: Optional[str]):
        """
        Initializes the LLMBase.

        Args:
            model: The model to use for the LLM.
        """
        self.model = model
        self.llm_process: Optional[subprocess.Popen] = None

    async def run(
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

        log(prompt, message_type=LLMOutputType.PROMPT)
        try:
            response = await self._run(prompt, yolo, cwd=cwd)
            if response is not None:
                log(f"LLM response: {response}", message_type=response_type)
            return response
        except Exception as e:
            log(f"Error running LLM: {e}", message_type=LLMOutputType.ERROR)
            return None

    @abstractmethod
    async def _run(
        self,
        prompt: str,
        yolo: bool,
        *,
        cwd: Path,
    ) -> Optional[str]:
        """
        Runs the LLM with the given prompt. No logging, no status updates, etc.
        """
        raise NotImplementedError

    def terminate_llm_process(self) -> Optional[int]:
        """
        Terminates the LLM process if it's running.

        Returns:
            The PID of the killed process, or None if no process was found.
        """
        if self.llm_process and self.llm_process.poll() is None:
            pid = self.llm_process.pid
            log(f"Terminating LLM process with PID: {pid}", message_type=LLMOutputType.STATUS)
            self.llm_process.terminate()
            try:
                self.llm_process.wait(timeout=5)  # Wait for 5 seconds for graceful termination
            except subprocess.TimeoutExpired:
                log(f"LLM process {pid} did not terminate gracefully, killing it.", message_type=LLMOutputType.STATUS)
                self.llm_process.kill()
            self.llm_process = None
            return pid
        return None
