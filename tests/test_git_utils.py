import subprocess
from pathlib import Path
from typing import Optional

import pytest

from ok.config import ConfigModel
from ok.env import Env, RunResult
from ok.git_utils import (
    add_worktree,
    get_current_branch,
    get_current_commit_hash,
    get_existing_branch_names,
    remove_worktree,
    resolve_commit_specifier,
    sanitize_branch_name,
)
from ok.utils import real_run


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """
    Pytest fixture that creates a temporary git repository with an initial commit.

    Args:
        tmp_path: Temporary directory provided by pytest.

    Returns:
        Path to the initialized git repository.
    """
    repo_path: Path = tmp_path / "repo"
    repo_path.mkdir()
    subprocess.run(["git", "init"], cwd=repo_path, check=True)
    subprocess.run(["git", "checkout", "-b", "main"], cwd=repo_path, check=True)
    # Set user config for commits
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_path, check=True)
    # Create initial commit
    (repo_path / "README.md").write_text("# Test Repo")
    subprocess.run(["git", "add", "README.md"], cwd=repo_path, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo_path, check=True)
    return repo_path


class MockEnv(Env):
    def __init__(self):
        self.config = ConfigModel(run_timeout_seconds=5, llm_timeout_seconds=5)

    def log(self, message: str, message_type=None, message_human: str | None = None) -> None:
        print(f"{message_type}: {message}")

    def log_debug(self, message: str, **kwargs) -> None:
        print(f"DEBUG: {message} {kwargs}")

    async def run(
        self,
        command: str | list[str],
        description=None,
        command_human: Optional[list[str]] = None,
        status_message: Optional[str] = None,
        *,
        directory: Path,
        shell: bool = False,
        run_timeout_seconds: int,
    ) -> RunResult:
        return await real_run(
            env=self,
            command=command,
            description=description,
            command_human=command_human,
            status_message=status_message,
            directory=directory,
            shell=shell,
            run_timeout_seconds=run_timeout_seconds,
        )


@pytest.fixture
def env() -> MockEnv:
    """
    Pytest fixture that provides a temporary environment for testing.

    Returns:
        Env: A temporary environment object.
    """
    return MockEnv()


def test_sanitize_branch_name_invalid_chars() -> None:
    """Test that sanitize_branch_name removes invalid characters."""

    raw: str = "Feature/New Stuff.Is Here!*?"
    cleaned: str = sanitize_branch_name(raw)
    assert cleaned == "feature/new-stuff-is-here"


def test_sanitize_branch_name_leading_trailing_hyphens() -> None:
    """Test that sanitize_branch_name strips leading/trailing hyphens."""

    raw: str = "-Feature/New Stuff-"
    cleaned: str = sanitize_branch_name(raw)
    assert cleaned == "feature/new-stuff"


def test_sanitize_branch_name_empty_string() -> None:
    """Test that sanitize_branch_name returns 'no-name' for empty input."""

    raw: str = ""
    cleaned: str = sanitize_branch_name(raw)
    assert cleaned == "no-name"


async def test_get_existing_branch_names(env: Env, git_repo: Path) -> None:
    """
    Test that get_existing_branch_names returns the default branch after repo init.

    Args:
        git_repo: Path to the temporary git repository.
    """
    branches: list[str] = await get_existing_branch_names(env, cwd=git_repo)
    assert any(b in branches for b in ["master", "main"])


async def test_resolve_commit_specifier(env: Env, git_repo: Path) -> None:
    """
    Test that resolve_commit_specifier returns the correct commit hash for full hash,
    short hash, branch name, and HEAD.

    Args:
        git_repo: Path to the temporary git repository.
    """

    commit_hash: str | None = await get_current_commit_hash(env, cwd=git_repo)
    if commit_hash is None:
        pytest.fail("No commit hash available")
    # Full hash
    resolved_full: str | None = await resolve_commit_specifier(env, commit_hash, cwd=git_repo)
    assert resolved_full == commit_hash
    # Short hash
    short_hash = commit_hash[:7]
    resolved_short: str | None = await resolve_commit_specifier(env, short_hash, cwd=git_repo)
    assert resolved_short == commit_hash
    # Branch name
    branch: str | None = await get_current_branch(env, cwd=git_repo)
    if branch is not None:
        resolved_branch: str | None = await resolve_commit_specifier(env, branch, cwd=git_repo)
        assert resolved_branch == commit_hash
    # HEAD
    resolved_head: str | None = await resolve_commit_specifier(env, "HEAD", cwd=git_repo)
    assert resolved_head == commit_hash


async def test_get_current_branch(env: Env, git_repo: Path) -> None:
    """
    Test that get_current_branch returns the default branch name.

    Args:
        git_repo: Path to the temporary git repository.
    """
    branch: str | None = await get_current_branch(env, cwd=git_repo)
    assert branch in ["master", "main"]


async def test_get_current_commit_hash(env: Env, git_repo: Path) -> None:
    """
    Test that get_current_commit_hash returns a valid commit hash.

    Args:
        git_repo: Path to the temporary git repository.
    """
    commit_hash: str | None = await get_current_commit_hash(env, cwd=git_repo)
    assert commit_hash is not None
    assert len(commit_hash) == 40


async def test_add_and_remove_worktree(env: Env, git_repo: Path, tmp_path: Path) -> None:
    """
    Test that add_worktree creates a new worktree and remove_worktree deletes it.

    Args:
        git_repo: Path to the temporary git repository.
        tmp_path: Temporary directory provided by pytest.
    """

    # Add a new worktree
    worktree_path: Path = tmp_path / "worktree"
    commit_hash: str | None = await get_current_commit_hash(env, cwd=git_repo)
    if commit_hash is None:
        pytest.fail("No commit hash available")
    added: bool = await add_worktree(env, worktree_path, rev=commit_hash, cwd=git_repo)
    assert added
    assert worktree_path.exists()
    # Remove the worktree
    removed: bool = await remove_worktree(env, worktree_path, cwd=git_repo)
    assert removed
    assert not (worktree_path / ".git").exists()


async def test_add_worktree_with_main_revision(env: Env, git_repo: Path, tmp_path: Path) -> None:
    """
    Test what happens if we have a repo at main and create a worktree with revision=main.

    This will fail if the `add_worktree` uses the provided revision directly without resolving it to a commit.
    """
    from ok.git_utils import add_worktree, get_existing_branch_names

    # Ensure 'main' branch exists (or skip if not)
    branches = await get_existing_branch_names(env, cwd=git_repo)
    assert "main" in branches, "Main branch should exist in the test repository"

    worktree_path = tmp_path / "worktree_main"
    added: bool = await add_worktree(env, worktree_path, rev="main", cwd=git_repo)
    assert added
