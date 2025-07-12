"""Utility functions for interacting with Git repositories."""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

import trio

from ok.constants import TASK_META_DIR
from ok.llms.base import LLMBase
from ok.logging import LLMOutputType, log
from ok.util.eliot import log_call
from ok.utils import run


def sanitize_branch_name(name: str) -> str:
    """
    Sanitizes a string to be a valid git branch name.

    Args:
        name: The string to sanitize.

    Returns:
        A sanitized string suitable for a Git branch name.
    """
    if not name.strip():
        return "no-name"
    name = name.lower()
    name = re.sub(r"[^a-z0-9/]+", "-", name)  # Replace invalid characters with a single hyphen
    name = name.strip("-")  # Remove leading/trailing hyphens
    if len(name) > 100:  # Truncate to a reasonable length
        name = name[:100]
    return name


@log_call
async def get_existing_branch_names(*, cwd: Path) -> list[str]:
    """
    Gets a list of all local Git branch names.

    Args:
        cwd: The current working directory.

    Returns:
        A list of existing branch names.
    """
    result = await run(
        ["git", "for-each-ref", "--format=%(refname:short)", "refs/heads/"],
        "Listing existing branches",
        directory=cwd,
    )
    if not result.success:
        log("Failed to list existing branches.", LLMOutputType.TOOL_ERROR)
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


@log_call
async def generate_branch_name(suggestions: list[str], *, cwd: Path) -> str:
    """
    Generates a unique branch name by trying suggestions first.
    If all of the suggestions are taken (branch already exists), it appends a numerical suffix to the first suggestion.

    Args:
        suggestions: A list of suggested branch names to try first.
        cwd: The current working directory.

    Returns:
        A unique branch name with the "ok/" prefix added.
    """

    existing_branches = await get_existing_branch_names(cwd=cwd)

    suggestions = ["ok/" + sanitize_branch_name(s) for s in suggestions if s.strip()]
    if not suggestions:
        suggestions = ["ok/idk/task"]

    # Try suggested names first
    for suggestion in suggestions:
        if suggestion not in existing_branches:
            return suggestion

    # Fallback to numerical suffix
    new_branch_name = suggestions[0]
    counter = 1
    while new_branch_name in existing_branches:
        new_branch_name = f"{suggestions[0]}-{counter}"
        counter += 1
    return new_branch_name


@log_call
async def resolve_commit_specifier(specifier: str, *, cwd: Path) -> Optional[str]:
    """
    Resolves a Git commit specifier (branch, tag, SHA, relative) to a full commit SHA.

    Args:
        specifier: The Git commit specifier.
        cwd: The current working directory.

    Returns:
        The full commit SHA, or None if resolution fails.
    """
    log(f"Resolving commit specifier: {specifier}", LLMOutputType.STATUS)
    command = ["git", "rev-parse", "--verify", specifier]
    result = await run(command, f"Resolving {specifier} to commit SHA", directory=cwd)

    if result.success and result.stdout.strip():
        log(f"Resolved {specifier} to {result.stdout.strip()}", LLMOutputType.STATUS)
        return result.stdout.strip()
    else:
        log(
            f"Failed to resolve commit specifier: {specifier}. Stderr: {result.stderr}",
            LLMOutputType.TOOL_ERROR,
        )
        return None


@log_call(include_args=["task", "task_num", "base_rev", "cwd"])
async def setup_task_branch(task, task_num, *, base_rev: str, cwd: Path, llm: LLMBase) -> bool:
    """
    Set up git branch for task.

    Args:
        task: Task description.
        task_num: Task number (always 1 for now)
        base_rev: Base branch, commit, or git specifier to base the task branch on.
        cwd: Optional working directory (defaults to current directory).

    Returns:
        True if the branch was set up successfully, False otherwise.
    """
    log(f"Setting up branch for task {task_num}: {task}", LLMOutputType.STATUS)

    # Decide on the branch name
    allowed_types = [
        "fix",
        "chore",
        "refactor",
        "feat",
        "docs",
        "style",
        "perf",
        "test",
        "build",
        "ci",
        "revert",
        "wip",
    ]

    # Get branch name suggestions from LLM
    branch_prompt = (
        f"Generate 5 short, descriptive, and valid git branch names for the task: '{task}'.\n"
        "The names should be lowercase, use hyphens instead of spaces, and avoid special characters.\n"
        "The names should follow the format 'type/description', where 'type' is one of the following: "
        f"{', '.join(allowed_types)}.\n"
        "Example: 'feat/add-login', 'docs/contributing'. Return as a comma-separated list.\n"
        "You *may not* include anything else in the response. Do not include Markdown, code blocks, or any other formatting.\n"
        "You may only output a single line."
    )

    suggestions_response = await llm.run(branch_prompt, yolo=False, cwd=cwd, response_type=LLMOutputType.LLM_RESPONSE)
    if suggestions_response:
        suggestions = [s.strip() for s in suggestions_response.split(",") if s.strip()]
    else:
        suggestions = []

    branch_name = await generate_branch_name(suggestions, cwd=cwd)

    # Create the branch
    result = await run(
        ["git", "switch", "-c", branch_name, base_rev],
        f"Creating task branch {branch_name}",
        directory=cwd,
    )

    if not result.success:
        log(f"Failed to create branch {branch_name}", message_type=LLMOutputType.TOOL_ERROR)
        return False

    # Write task metadata
    task_meta = {
        "number": task_num,
        "description": task,
        "branch": branch_name,
        "timestamp": datetime.now().isoformat(),
    }

    # Ensure the task_meta directory exists
    full_task_meta_dir = cwd / TASK_META_DIR
    full_task_meta_dir.mkdir(parents=True, exist_ok=True)

    task_meta_path = full_task_meta_dir / f"task-{task_num}.json"

    async with await trio.open_file(task_meta_path, "w") as file:
        await file.write(json.dumps(task_meta, indent=2))

    log(f"Created task branch and metadata for task {task_num}", LLMOutputType.STATUS)
    return True


@log_call
async def get_current_branch(*, cwd: Path) -> Optional[str]:
    """
    Gets the current active Git branch name.

    Args:
        cwd: The current working directory.

    Returns:
        The current branch name, or None if not found.
    """
    result = await run(["git", "rev-parse", "--abbrev-ref", "HEAD"], "Getting current branch", directory=cwd)
    if result.success:
        return result.stdout.strip()
    else:
        log(f"Failed to get current branch. Stderr: {result.stderr}", LLMOutputType.TOOL_ERROR)
        return None


@log_call
async def get_current_commit_hash(*, cwd: Path) -> Optional[str]:
    """
    Gets the current commit hash.

    Args:
        cwd: The current working directory.

    Returns:
        The current commit hash, or None if not found.
    """
    result = await run(["git", "rev-parse", "HEAD"], "Getting current commit hash", directory=cwd)
    if result.success:
        return result.stdout.strip()
    else:
        log(
            f"Failed to get current commit hash. Stderr: {result.stderr}",
            message_type=LLMOutputType.TOOL_ERROR,
        )
        return None


@log_call
async def add_worktree(path: Path, *, rev: str, cwd: Path) -> bool:
    """
    Adds a new git worktree at the specified path, based on the given revision.

    Args:
        path: The path where the worktree should be added.
        rev: The revision (commit-ish) to base the worktree on.
        cwd: The current working directory.

    Returns:
        True if the worktree was added successfully, False otherwise.
    """
    log(f"Adding worktree at {path} for revision {rev}", LLMOutputType.STATUS)
    commit = await resolve_commit_specifier(rev, cwd=cwd)
    if not commit:
        log(f"Could not resolve revision {rev} to a commit.", message_type=LLMOutputType.TOOL_ERROR)
        return False
    command = ["git", "worktree", "add", str(path), commit]
    result = await run(command, f"Adding worktree at {path}", directory=cwd)
    if result.success:
        log(f"Successfully added worktree at {path}", message_type=LLMOutputType.STATUS)
        return True
    else:
        log(
            f"Failed to add worktree at {path}. Stderr: {result.stderr}",
            message_type=LLMOutputType.TOOL_ERROR,
        )
        return False


@log_call
async def remove_worktree(path: Path, *, cwd: Path) -> bool:
    """
    Removes a git worktree at the specified path.

    Args:
        path: The path to the worktree to remove.
        cwd: The current working directory.

    Returns:
        True if the worktree was removed successfully, False otherwise.
    """
    log(f"Removing worktree at {path}", message_type=LLMOutputType.STATUS)
    command = ["git", "worktree", "remove", "--force", str(path)]
    result = await run(command, f"Removing worktree {path}", directory=cwd)
    if result.success:
        log(f"Successfully removed worktree at {path}", message_type=LLMOutputType.STATUS)
        return True
    else:
        log(
            f"Failed to remove worktree at {path}. Stderr: {result.stderr}",
            LLMOutputType.TOOL_ERROR,
        )
        return False


@log_call
async def has_uncommitted_changes(*, cwd: Path) -> bool:
    """
    Checks if there are any uncommitted changes (staged or unstaged) in the repository.

    Args:
        cwd: The current working directory.

    Returns:
        True if there are uncommitted changes, False otherwise.
    """
    result = await run(["git", "status", "--porcelain"], "Checking for uncommitted changes", directory=cwd)
    if result.success:
        return bool(result.stdout.strip())
    else:
        log(
            f"Failed to check for uncommitted changes. Stderr: {result.stderr}",
            LLMOutputType.TOOL_ERROR,
        )
        return False
