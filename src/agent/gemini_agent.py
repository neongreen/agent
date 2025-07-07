import os
import tempfile
from typing import Optional

from .constants import AGENT_TEMP_DIR
from .ui import status_manager
from .utils import log, run

# Engine selection: 'gemini', 'claude', or 'codex'
LLM_ENGINE = os.getenv("LLM_ENGINE", "gemini")


def set_llm_engine(engine: str) -> None:
    """Set which LLM CLI to use: 'gemini', 'claude', or 'codex'."""
    global LLM_ENGINE
    if engine not in ("gemini", "claude", "codex"):
        raise ValueError(f"Unknown engine: {engine}")
    LLM_ENGINE = engine


def run_claude(prompt: str, yolo: bool) -> Optional[str]:
    """Run Claude Code CLI and return the response."""
    # Build Claude CLI invocation: map yolo to --dangerously-skip-permissions before --print (-p)
    command = ["claude", *(["--dangerously-skip-permissions"] if yolo else []), "-p", prompt]

    log(f"Claude prompt: {prompt}", message_type="thought")
    status_manager.set_phase("Calling Claude")
    result = run(command, "Calling Claude", command_human=command[:-1] + ["<prompt>"])

    if result["success"]:
        response = result["stdout"].strip()
        status_manager.update_status("Successful.")
        log(f"Claude response: {response}", message_type="thought")
        return response
    else:
        log(f"Claude call failed: {result['stderr']}", message_type="tool_output_error")
        return None


def run_codex(prompt: str, yolo: bool, model: Optional[str] = None) -> Optional[str]:
    """Run Codex CLI and return the response."""

    # Codex CLI is noisy so we have to do things differently.
    # Create a file in os temp dir:

    with tempfile.NamedTemporaryFile("r", prefix="agent-codex-output", dir=AGENT_TEMP_DIR, delete=True) as temp_file:
        temp_file_path = os.path.join(AGENT_TEMP_DIR, temp_file.name)

        command = [
            "codex",
            *(["--dangerously-bypass-approvals-and-sandbox"] if yolo else ["--ask-for-approval=never"]),
            "exec",
            f"--output-last-message={temp_file_path}",
            prompt,
        ]

        log(f"Codex prompt: {prompt}", message_type="thought")
        status_manager.set_phase("Calling Codex")
        result = run(command, "Calling Codex", command_human=command[:-1] + ["<prompt>"])

        if result["success"]:
            status_manager.update_status("Successful.")
            response = temp_file.read().strip()
            log(f"Codex response: {response}", message_type="thought")
            return response
        else:
            log(f"Codex call failed: {result['stderr']}", message_type="tool_output_error")
            return None


def run_llm(prompt: str, yolo: bool, model: Optional[str] = None) -> Optional[str]:
    """Run selected LLM CLI (Gemini, Claude, or Codex) and return the response."""
    # Dispatch to the selected engine
    if LLM_ENGINE == "claude":
        return run_claude(prompt, yolo)
    elif LLM_ENGINE == "codex":
        return run_codex(prompt, yolo, model)

    # Default to Gemini
    gemini_model = model or "gemini-2.5-flash"
    command = ["gemini", "-m", gemini_model, *(["--yolo"] if yolo else []), "-p", prompt]

    log(f"Gemini prompt: {prompt}", message_type="thought")
    status_manager.set_phase("Calling Gemini")
    result = run(command, "Calling Gemini", command_human=command[:-1] + ["<prompt>"])

    if result["success"]:
        response = result["stdout"].strip()
        status_manager.update_status("Successful.")
        log(f"Gemini response: {response}", message_type="thought")
        return response
    else:
        log(f"Gemini call failed: {result['stderr']}", message_type="tool_output_error")
        return None
