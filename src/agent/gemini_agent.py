"""
This module provides functions for interacting with various LLM engines.

It includes functions to set the LLM engine, and to run prompts against
Claude, Codex, OpenRouter, and Gemini CLIs.
"""

import os
import shlex
import tempfile
from pathlib import Path
from typing import Literal, Optional

from .constants import AGENT_STATE_BASE_DIR, AGENT_TEMP_DIR
from .ui import status_manager
from .utils import log, run


LLM_ENGINE = os.getenv("LLM_ENGINE", "gemini")
"""The globally selected LLM engine, defaults to 'gemini'."""
LLM_MODEL = None
"""The globally selected LLM model, if applicable."""


def set_llm_engine(
    engine: Literal["gemini", "claude", "codex", "openrouter", "opencode"], model: Optional[str] = None
) -> None:
    """
    Sets the global LLM engine and optionally the model to be used.

    Args:
        engine: The LLM engine to use ('gemini', 'claude', 'codex', 'openrouter').
        model: The specific model to use with the engine (required for 'openrouter').

    Raises:
        ValueError: If an unknown engine is specified or if a model is not
                    provided for 'openrouter'.
    """
    global LLM_ENGINE, LLM_MODEL
    if engine not in ("gemini", "claude", "codex", "openrouter", "opencode"):
        raise ValueError(f"Unknown engine: {engine}")
    if engine == "openrouter" and model is None:
        raise ValueError("Model must be specified for OpenRouter")
    if engine == "opencode" and model is None:
        model = "github-copilot/gpt-4.1"
    LLM_ENGINE = engine
    LLM_MODEL = model


def run_claude(prompt: str, yolo: bool, *, cwd: Path, phase: Optional[str] = None) -> Optional[str]:
    """
    Runs the Claude Code CLI with the given prompt.

    Args:
        prompt: The prompt to send to Claude.
        yolo: If True, bypasses permissions and sandbox.
        cwd: The current working directory for the command as a Path.

    Returns:
        The response from Claude, or None if the call fails.
    """
    # Build Claude CLI invocation: map yolo to --dangerously-skip-permissions before --print (-p)
    command = ["claude", *(["--dangerously-skip-permissions"] if yolo else []), "-p", prompt]

    log(f"Claude prompt: {prompt}", message_type="thought")
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
        log(f"Claude response: {response}", message_type="thought")
        return response
    else:
        log(f"Claude call failed: {result['stderr']}", message_type="tool_output_error")
        return None


def run_codex(
    prompt: str,
    yolo: bool,
    *,
    model: Optional[str] = None,
    # For custom providers like OpenRouter
    provider_url: Optional[str] = None,
    provider_env_key: Optional[str] = None,
    cwd: Path,
    phase: Optional[str] = None,
) -> Optional[str]:
    """
    Runs the Codex CLI with the given prompt.

    Args:
        prompt: The prompt to send to Codex.
        yolo: If True, bypasses approvals and sandbox.
        model: The specific model to use.
        provider_url: Custom provider URL for Codex.
        provider_env_key: Environment variable key for custom provider API key.
        cwd: The current working directory for the command.

    Returns:
        The response from Codex, or None if the call fails.
    """

    # Codex CLI is noisy so we have to do things differently.
    # Create a file in os temp dir:

    with tempfile.NamedTemporaryFile("r", prefix="agent-codex-output", dir=AGENT_TEMP_DIR, delete=True) as temp_file:
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

        log(f"Codex prompt: {prompt}", message_type="thought")
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
            log(f"Codex response: {response}", message_type="thought")
            return response
        else:
            log(f"Codex call failed: {result['stderr']}", message_type="tool_output_error")
            return None


def run_openrouter(prompt: str, yolo: bool, model: str, *, cwd: Path, phase: Optional[str] = None) -> Optional[str]:
    """
    Runs OpenRouter via the Codex CLI with the given prompt.

    Args:
        prompt: The prompt to send to OpenRouter.
        yolo: If True, bypasses approvals and sandbox.
        model: The specific model to use with OpenRouter.
        cwd: The current working directory for the command as a Path.

    Returns:
        The response from OpenRouter, or None if the call fails.
    """
    provider_url = "https://openrouter.ai/api/v1"
    provider_env_key = "OPENROUTER_API_KEY"
    return run_codex(
        prompt, yolo, model=model, provider_url=provider_url, provider_env_key=provider_env_key, cwd=cwd, phase=phase
    )


def run_gemini(
    prompt: str, yolo: bool, model: Optional[str] = None, *, cwd: Path, phase: Optional[str] = None
) -> Optional[str]:
    """
    Runs the Gemini CLI with the given prompt.

    Args:
        prompt: The prompt to send to Gemini.
        yolo: If True, bypasses approvals and sandbox.
        model: The specific Gemini model to use (defaults to 'gemini-2.5-flash').
        cwd: The current working directory for the command as a Path.

    Returns:
        The response from Gemini, or None if the call fails.
    """
    gemini_model = model or "gemini-2.5-flash"
    command = ["gemini", "-m", gemini_model, *(["--yolo"] if yolo else []), "-p", prompt]

    log(f"Gemini prompt: {prompt}", message_type="thought")
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
        log(f"Gemini response: {response}", message_type="thought")
        return response
    else:
        log(f"Gemini call failed: {result['stderr']}", message_type="tool_output_error")
        return None


def run_opencode(
    prompt: str, yolo: bool, model: Optional[str] = None, *, cwd: Path, phase: Optional[str] = None
) -> Optional[str]:
    opencode_model = model or "github-copilot/gpt-4.1"

    # We need a version with print mode:
    # https://github.com/sst/opencode/pull/533

    opencode_path = AGENT_STATE_BASE_DIR / "bin" / "opencode"
    if not opencode_path.exists():
        log(
            f"Opencode CLI (custom version) not found at {opencode_path}. Please run 'mise run build-opencode'.",
            message_type="error",
        )
        return None

    # command = [str(opencode_path), "run", "--print", "--output-format=json", "--model", opencode_model, prompt]
    command = [str(opencode_path), "run", "--print", "--model", opencode_model, prompt]

    # Temporarily adding this for debug since opencode is new
    log(f"Opencode command: {shlex.join(command)}", message_type="debug")

    # Opencode is always YOLO
    log(f"Opencode prompt: {prompt}", message_type="thought")

    result = run(
        command,
        phase or "Calling Opencode",
        command_human=command[:-1] + ["<prompt>"],
        directory=cwd,
        status_message=phase or "Calling Opencode",
        log_stdout=False,
    )

    if result["success"]:
        # response_json = result["stdout"].strip()
        # # TODO: check type, subtype, is_error
        # try:
        #     response: dict = json.loads(response_json)
        #     content = response.get("result", "")
        # except Exception as e:
        #     log(f"Failed to parse Opencode response as JSON: {e}", message_type="tool_output_error")
        #     return None
        # status_manager.update_status("Successful.")
        # log(f"Opencode response: {content}", message_type="thought")
        # return content

        response = result["stdout"].strip()
        content = response.split("Text  ", maxsplit=1)[-1].strip()
        status_manager.update_status("Successful.")
        log(f"Opencode response: {content}", message_type="thought")
        return content
    else:
        log(f"Opencode call failed: {result['stderr']}", message_type="tool_output_error")
        return None


def run_llm(prompt: str, yolo: bool, *, cwd: Path, phase: Optional[str] = None) -> Optional[str]:
    """
    Run selected LLM CLI and return the response.

    Args:
        prompt: The prompt to send to the LLM.
        yolo: If True, bypasses approvals and sandbox.
        cwd: The current working directory for the command as a Path.
        phase: Optional phase description.

    Returns:
        The response from the selected LLM, or None if the call fails.
    """
    # Dispatch to the selected engine
    if LLM_ENGINE == "claude":
        return run_claude(prompt, yolo, cwd=cwd, phase=phase)
    elif LLM_ENGINE == "codex":
        return run_codex(prompt, yolo, model=LLM_MODEL, cwd=cwd, phase=phase)
    elif LLM_ENGINE == "openrouter":
        if LLM_MODEL is None:
            raise ValueError("Model must be specified for OpenRouter")
        return run_openrouter(prompt, yolo, model=LLM_MODEL, cwd=cwd, phase=phase)
    elif LLM_ENGINE == "gemini":
        return run_gemini(prompt, yolo, model=LLM_MODEL, cwd=cwd, phase=phase)
    elif LLM_ENGINE == "opencode":
        return run_opencode(prompt, yolo, model=LLM_MODEL, cwd=cwd, phase=phase)
    else:
        raise ValueError(
            f"Unknown LLM engine: {LLM_ENGINE}. Supported engines: gemini, claude, codex, openrouter, opencode."
        )
