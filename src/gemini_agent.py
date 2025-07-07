import os
from typing import Optional

from .ui import status_manager
from .utils import log, run

# Engine selection: 'gemini' or 'claude'
LLM_ENGINE = os.getenv("LLM_ENGINE", "gemini")


def set_llm_engine(engine: str) -> None:
    """Set which LLM CLI to use: 'gemini' or 'claude'."""
    global LLM_ENGINE
    if engine not in ("gemini", "claude"):
        raise ValueError(f"Unknown engine: {engine}")
    LLM_ENGINE = engine


def run_claude(prompt: str, yolo: bool) -> Optional[str]:
    """Run Claude Code CLI and return the response."""
    # Build Claude CLI invocation: map yolo to --dangerously-skip-permissions before --print (-p)
    command = ["claude"]
    if yolo:
        command.append("--dangerously-skip-permissions")
    command.extend(["-p", prompt])

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


def run_gemini(prompt: str, yolo: bool) -> Optional[str]:
    """Run selected LLM CLI (Gemini or Claude) and return the response."""
    # Dispatch to the selected engine
    if LLM_ENGINE == "claude":
        return run_claude(prompt, yolo)

    command = ["gemini", "-m", "gemini-2.5-flash", *(["--yolo"] if yolo else []), "-p", prompt]

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
