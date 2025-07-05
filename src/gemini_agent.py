import os
import re
from typing import Optional
from .utils import log, _print_formatted, run
from .ui import status_manager


def run_gemini(prompt: str, yolo: bool) -> Optional[str]:
    """Run gemini CLI and return the response."""
    command = ["gemini", "-m", "gemini-2.5-flash", *(["--yolo"] if yolo else []), "-p", prompt]

    log(f"Gemini prompt: {prompt}", message_type="thought")
    status_manager.update_status(f"Calling Gemini with prompt: {prompt[:50]}...")
    result = run(command, "Calling Gemini", command_human=command[:-1] + ["<prompt>"])

    if result["success"]:
        response = result["stdout"].strip()
        status_manager.update_status("Gemini call successful.")
        log(f"Gemini response: {response}", message_type="thought")
        return response
    else:
        log(f"Gemini call failed: {result['stderr']}", message_type="tool_output_error")
        return None


def discover_tasks(prompt_text, cwd=None):
    """Use Gemini to discover tasks from the given prompt."""
    status_manager.update_status("Discovering tasks...")
    log("Discovering tasks from prompt", message_type="thought")

    # Check if prompt_text is a file path
    if os.path.exists(prompt_text) and os.path.isfile(prompt_text):
        try:
            with open(prompt_text, "r", encoding="utf-8") as f:
                file_content = f.read()
            gemini_prompt = f"Extract distinct independent tasks from this file content: {file_content}. Each task should be a complete, standalone objective - NOT a breakdown or plan. If it's asking for multiple things, list each as a separate task. If it's one thing, return one task. Return as a numbered list."
        except Exception as e:
            log(f"Error reading file {prompt_text}: {e}", message_type="tool_output_error")
            return []
    else:
        gemini_prompt = (
            f"Analyze this instruction and identify distinct independent tasks: {prompt_text}\n"
            "If the instruction references external resources (like git commits, files, APIs, etc.) that you need to examine to identify the actual tasks, do the exploration and then identify the tasks.\n"
            "If it's a simple direct instruction (like 'create a hello world program'), return exactly one task.\n"
            "If it explicitly mentions multiple separate tasks, list each one.\n"
            "Return as a numbered list with clear task descriptions."
        )

    response = run_gemini(gemini_prompt, yolo=True)
    if not response:
        return []

    # Parse tasks from response
    tasks = []
    for line in response.split("\n"):
        line = line.strip()
        if not line:
            continue

        # Look for numbered items or bullet points
        if re.match(r"^(\d+\.|\*|-)", line):
            task_title = re.sub(r"^(\d+\.|\*|-)\s*", "", line).strip()
            if task_title:
                tasks.append(task_title)

    return tasks


def choose_tasks(tasks):
    """Present tasks to user and get their selection."""
    if not tasks:
        log("No tasks discovered.", message_type="thought")
        return []

    _print_formatted("Discovered tasks:")
    for i, task in enumerate(tasks, 1):
        _print_formatted(f"{i}. {task}")
    status_manager.update_status("Awaiting task selection...")

    while True:
        try:
            if len(tasks) == 1:
                selected_input = input("Press Enter to select this task, or 'q' to quit: ").strip()
                if selected_input == "":
                    return [tasks[0]]
            else:
                selected_input = input("Enter task numbers (space/comma separated) or 'q' to quit: ").strip()

            if selected_input.lower() == "q":
                return []

            selected_numbers = re.split(r"[,\s]+", selected_input)
            selected_tasks = []

            for num_str in selected_numbers:
                try:
                    num = int(num_str)
                    if 1 <= num <= len(tasks):
                        selected_tasks.append(tasks[num - 1])
                    else:
                        _print_formatted(f"Task number '{num}' not found. Try again.", message_type="tool_output_error")
                        selected_tasks = []
                        break
                except ValueError:
                    _print_formatted(f"Invalid number '{num_str}'. Try again.", message_type="tool_output_error")
                    selected_tasks = []
                    break

            if selected_tasks:
                return selected_tasks

        except (EOFError, KeyboardInterrupt):
            return []
