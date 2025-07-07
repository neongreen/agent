"""
This module provides an object for interacting with various LLM engines.

It includes methods to set the LLM engine, and to run prompts against
Claude, Codex, OpenRouter, Opencode, and Gemini CLIs.
"""

import os
import tempfile
from enum import Enum
from pathlib import Path
from typing import Literal, Optional, Type

from .constants import AGENT_STATE_BASE_DIR, AGENT_TEMP_DIR
from .output_formatter import LLMOutputType
from .ui import status_manager
from .utils import log, run


class LLM:
    def __init__(
        self,
        engine: Literal["gemini", "claude", "codex", "openrouter", "opencode"],
        model: Optional[str],
    ):
        self.engine = engine
        self.model = model

        if engine == "gemini":
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

        if engine == "openrouter" and model is None:
            raise ValueError("Model must be specified for OpenRouter engine.")
        if engine == "opencode" and model is None:
            self.model = "github-copilot/gpt-4.1"

    def run(
        self, prompt: str, yolo: bool, *, cwd: Path, phase: Optional[str] = None, response_type: LLMOutputType
    ) -> Optional[str]:
        if self.engine == "claude":
            return self._run_claude(prompt, yolo, cwd=cwd, phase=phase, response_type=response_type)
        elif self.engine == "codex":
            return self._run_codex(prompt, yolo, model=self.model, cwd=cwd, phase=phase, response_type=response_type)
        elif self.engine == "openrouter":
            assert self.model is not None, "Checked in the constructor."
            return self._run_openrouter(
                prompt, yolo, model=self.model, cwd=cwd, phase=phase, response_type=response_type
            )
        elif self.engine == "gemini":
            return self._run_gemini(prompt, yolo, model=self.model, cwd=cwd, phase=phase, response_type=response_type)
        elif self.engine == "opencode":
            assert self.model is not None, "Checked in the constructor."
            return self._run_opencode(prompt, yolo, model=self.model, cwd=cwd, phase=phase, response_type=response_type)
        else:
            raise ValueError(f"Unknown LLM engine: {self.engine}.")

    def _run_claude(
        self,
        prompt: str,
        yolo: bool,
        *,
        cwd: Path,
        phase: Optional[str] = None,
        response_type: LLMOutputType,
    ) -> Optional[str]:
        command = ["claude", *(["--dangerously-skip-permissions"] if yolo else []), "-p", prompt]
        log(prompt, message_type=LLMOutputType.PROMPT)
        result = run(
            command,
            "Calling Claude",
            command_human=command[:-1] + ["<prompt>"],
            directory=cwd,
            status_message=phase or "Calling Claude",
            log_stdout=False,
        )
        if result["success"]:
            response = result["stdout"].strip()
            status_manager.update_status("Successful.")
            log(response, message_type=response_type)
            return response
        else:
            return None

    def _run_codex(
        self,
        prompt: str,
        yolo: bool,
        *,
        cwd: Path,
        model: Optional[str] = None,
        provider_url: Optional[str] = None,
        provider_env_key: Optional[str] = None,
        phase: Optional[str] = None,
        response_type: LLMOutputType,
    ) -> Optional[str]:
        with tempfile.NamedTemporaryFile(
            "r", prefix="agent-codex-output", dir=AGENT_TEMP_DIR, delete=True
        ) as temp_file:
            temp_file_path = os.path.join(AGENT_TEMP_DIR, temp_file.name)
            command = [
                "codex",
                *(["--dangerously-bypass-approvals-and-sandbox"] if yolo else ["--ask-for-approval=never"]),
                *(
                    [
                        "-c=model_provider=custom",
                        "-c=model_providers.custom.name=custom",
                        f"-c=model_providers.custom.base_url={provider_url}",
                    ]
                    if provider_url
                    else []
                ),
                *([f"-c=model_providers.custom.env_key={provider_env_key}"] if provider_env_key else []),
                "exec",
                *(["--model", model] if model else []),
                f"--output-last-message={temp_file_path}",
                prompt,
            ]
            log(prompt, message_type=LLMOutputType.PROMPT)
            result = run(
                command,
                "Calling Codex",
                command_human=command[:-1] + ["<prompt>"],
                directory=cwd,
                status_message=phase or "Calling Codex",
                log_stdout=False,
            )
            if result["success"]:
                status_manager.update_status("Successful.")
                response = temp_file.read().strip()
                log(response, message_type=response_type)
                return response
            else:
                return None

    def _run_openrouter(
        self,
        prompt: str,
        yolo: bool,
        model: str,
        *,
        cwd: Path,
        phase: Optional[str] = None,
        response_type: LLMOutputType,
    ) -> Optional[str]:
        provider_url = "https://openrouter.ai/api/v1"
        provider_env_key = "OPENROUTER_API_KEY"
        return self._run_codex(
            prompt,
            yolo,
            model=model,
            provider_url=provider_url,
            provider_env_key=provider_env_key,
            cwd=cwd,
            phase=phase,
            response_type=response_type,
        )

    def _run_gemini(
        self,
        prompt: str,
        yolo: bool,
        model: Optional[str] = None,
        *,
        cwd: Path,
        phase: Optional[str] = None,
        response_type: LLMOutputType,
    ) -> Optional[str]:
        gemini_model = model or "gemini-2.5-flash"
        command = ["gemini", "-m", gemini_model, *(["--yolo"] if yolo else []), "-p", prompt]
        log(prompt, message_type=LLMOutputType.PROMPT)
        result = run(
            command,
            phase or "Calling Gemini",
            command_human=command[:-1] + ["<prompt>"],
            directory=cwd,
            status_message=phase or "Calling Gemini",
            log_stdout=False,
        )
        if result["success"]:
            response = result["stdout"].strip()
            status_manager.update_status("Successful.")
            log(response, message_type=response_type)
            return response
        else:
            return None

    def _run_opencode(
        self,
        prompt: str,
        yolo: bool,
        model: str,
        *,
        cwd: Path,
        phase: Optional[str] = None,
        response_type: LLMOutputType,
    ) -> Optional[str]:
        opencode_path = AGENT_STATE_BASE_DIR / "bin" / "opencode"
        if not opencode_path.exists():
            log(
                f"Opencode CLI (custom version) not found at {opencode_path}. Please run 'mise run build-opencode'.",
                message_type=LLMOutputType.TOOL_ERROR,
            )
            return None
        command = [str(opencode_path), "run", "--print", "--model", model, prompt]
        log(prompt, message_type=LLMOutputType.PROMPT)
        result = run(
            command,
            phase or "Calling Opencode",
            command_human=command[:-1] + ["<prompt>"],
            directory=cwd,
            status_message=phase or "Calling Opencode",
            log_stdout=False,
        )
        if result["success"]:
            response = result["stdout"].strip()
            content = response.split("Text  ", maxsplit=1)[-1].strip()
            status_manager.update_status("Successful.")
            log(content, message_type=response_type)
            return content
        else:
            return None


### Utils ###


def check_verdict[T: Enum](verdict_type: Type[T], judgment: str) -> T | None:
    """
    Checks judge's verdict based on a list of possible verdicts/statuses from an Enum.

    This function assumes you asked the LLM to repeat the verdict several times in the first line.
    This is necessary because Opencode sometimes outputs misspelled verdicts.

    Args:
        verdict_type: An Enum class containing possible status values (e.g. ImplementationVerdict).
        judgment: A string with the entire judgment from the LLM.

    Returns:
        An Enum member indicating the verdict, or None if not found.
    """
    first_line = judgment.split("\n", 1)[0].upper()
    for verdict in verdict_type:
        if verdict.value in first_line:
            return verdict
    return None
