import json
import os
import re
from datetime import datetime
from typing import Optional

from .gemini_agent import run_gemini
from .utils import log, run


def sanitize_branch_name(name: str) -> str:
    """Sanitizes a string to be a valid git branch name."""
    name = name.lower()
    name = re.sub(r"[^a-z0-9/.]+", "-", name)  # Replace invalid characters with a single hyphen
    name = name.strip("-")  # Remove leading/trailing hyphens
    if len(name) > 100:  # Truncate to a reasonable length
        name = name[:100]
    return name


def generate_unique_branch_name(base_name, suggestions: Optional[list[str]] = None, cwd=None):
    """Generates a unique branch name by trying suggestions first, then appending a numerical suffix if necessary."""
    existing_branches_result = run(["git", "branch", "--list"], "Listing existing branches", directory=cwd)
    if not existing_branches_result["success"]:
        log("Failed to list existing branches.", message_type="tool_output_error")
        return None

    existing_branches = [
        line.strip().replace("* ", "") for line in existing_branches_result["stdout"].split("\n") if line.strip()
    ]

    # Try suggested names first
    if suggestions:
        for suggestion in suggestions:
            sanitized_suggestion = sanitize_branch_name(suggestion)
            if sanitized_suggestion and sanitized_suggestion not in existing_branches:
                return sanitized_suggestion

    # Fallback to numerical suffix
    sanitized_base_name = sanitize_branch_name(base_name)
    if not sanitized_base_name:  # Ensure base_name is not empty after sanitization
        sanitized_base_name = "task-branch"  # Default if sanitization results in empty string

    new_branch_name = sanitized_base_name
    counter = 1
    while new_branch_name in existing_branches:
        new_branch_name = f"{sanitized_base_name}-{counter}"
        counter += 1
    return new_branch_name


def has_tracked_diff(cwd=None) -> bool:
    """Checks if there are any tracked changes in the repository."""
    result = run(["git", "status", "--porcelain"], "Checking for tracked changes", directory=cwd)
    if not result["success"]:
        log("Failed to check git status.", message_type="tool_output_error")
        return False
    return bool(result["stdout"].strip())


def resolve_commit_specifier(specifier: str, cwd=None) -> Optional[str]:
    """Resolves a Git commit specifier (branch, tag, SHA, relative) to a full commit SHA."""
    log(f"Resolving commit specifier: {specifier}", message_type="thought")
    command = ["git", "rev-parse", "--verify", specifier]
    result = run(command, f"Resolving {specifier} to commit SHA", directory=cwd)

    if result["success"] and result["stdout"].strip():
        log(f"Resolved {specifier} to {result['stdout'].strip()}", message_type="thought")
        return result["stdout"].strip()
    else:
        log(
            f"Failed to resolve commit specifier: {specifier}. Stderr: {result['stderr']}",
            message_type="tool_output_error",
        )
        return None


def setup_task_branch(task, task_num, base: str, cwd=None) -> bool:
    """Set up git branch for task."""
    log(f"Setting up branch for task {task_num}: {task}", message_type="thought")

    # Create and switch to task branch
    base_branch_name = f"task-{task_num}"

    # Get branch name suggestions from Gemini
    branch_prompt = (
        f"Generate 5 short, descriptive, and valid git branch names for the task: '{task}'. "
        "The names should be lowercase, use hyphens instead of spaces, and avoid special characters. "
        "Example: 'feature/add-login', 'bugfix/fix-auth-flow'. Return as a comma-separated list."
    )
    suggestions_response = run_gemini(branch_prompt, yolo=False)
    suggestions = []
    if suggestions_response:
        suggestions = [s.strip() for s in suggestions_response.split(",") if s.strip()]

    branch_name = generate_unique_branch_name(base_branch_name, suggestions, cwd)
    if not branch_name:
        return False
    result = run(
        ["git", "switch", "-c", branch_name, base],
        f"Creating task branch {branch_name}",
        directory=cwd,
    )

    if not result["success"]:
        log(f"Failed to create branch {branch_name}", message_type="tool_output_error")
        return False

    # Write task metadata
    task_meta = {"number": task_num, "title": task, "timestamp": datetime.now().isoformat()}

    task_meta_path = os.path.join(cwd, ".task-meta") if cwd else ".task-meta"
    with open(task_meta_path, "w") as f:
        json.dump(task_meta, f, indent=2)

    log(f"Created task branch and metadata for task {task_num}", message_type="thought")
    return True
