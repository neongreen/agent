import subprocess
from pathlib import Path

import pytest

from agent.git_utils import (
    add_worktree,
    get_current_branch,
    get_current_commit_hash,
    get_existing_branch_names,
    has_tracked_diff,
    remove_worktree,
    resolve_commit_specifier,
    sanitize_branch_name,
)


def test_sanitize_branch_name_invalid_chars() -> None:
    """Test that sanitize_branch_name removes invalid characters."""
    raw: str = "Feature/New Stuff!*?"
    cleaned: str = sanitize_branch_name(raw)
    assert cleaned == "feature/new-stuff"


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
    # Set user config for commits
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_path, check=True)
    # Create initial commit
    (repo_path / "README.md").write_text("# Test Repo")
    subprocess.run(["git", "add", "README.md"], cwd=repo_path, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo_path, check=True)
    return repo_path


def test_get_existing_branch_names(git_repo: Path) -> None:
    """
    Test that get_existing_branch_names returns the default branch after repo init.

    Args:
        git_repo: Path to the temporary git repository.
    """
    branches: list[str] = get_existing_branch_names(cwd=str(git_repo))
    assert any(b in branches for b in ["master", "main"])


def test_has_tracked_diff_false(git_repo: Path) -> None:
    """
    Test that has_tracked_diff returns False when there are no staged changes.

    Args:
        git_repo: Path to the temporary git repository.
    """
    assert not has_tracked_diff(cwd=str(git_repo))


def test_has_tracked_diff_true(git_repo: Path) -> None:
    """
    Test that has_tracked_diff returns True when there are staged changes.

    Args:
        git_repo: Path to the temporary git repository.
    """
    # Modify file
    (git_repo / "README.md").write_text("# Modified")
    subprocess.run(["git", "add", "README.md"], cwd=git_repo, check=True)
    assert has_tracked_diff(cwd=str(git_repo))


def test_resolve_commit_specifier(git_repo: Path) -> None:
    """
    Test that resolve_commit_specifier returns the correct commit hash for full hash,
    short hash, branch name, and HEAD.

    Args:
        git_repo: Path to the temporary git repository.
    """
    commit_hash: str | None = get_current_commit_hash(cwd=str(git_repo))
    if commit_hash is None:
        pytest.skip("No commit hash available")
    # Full hash
    resolved_full: str | None = resolve_commit_specifier(commit_hash, cwd=str(git_repo))
    assert resolved_full == commit_hash
    # Short hash
    short_hash = commit_hash[:7]
    resolved_short: str | None = resolve_commit_specifier(short_hash, cwd=str(git_repo))
    assert resolved_short == commit_hash
    # Branch name
    branch: str | None = get_current_branch(cwd=str(git_repo))
    if branch is not None:
        resolved_branch: str | None = resolve_commit_specifier(branch, cwd=str(git_repo))
        assert resolved_branch == commit_hash
    # HEAD
    resolved_head: str | None = resolve_commit_specifier("HEAD", cwd=str(git_repo))
    assert resolved_head == commit_hash


def test_get_current_branch(git_repo: Path) -> None:
    """
    Test that get_current_branch returns the default branch name.

    Args:
        git_repo: Path to the temporary git repository.
    """
    branch: str | None = get_current_branch(cwd=str(git_repo))
    assert branch in ["master", "main"]


def test_get_current_commit_hash(git_repo: Path) -> None:
    """
    Test that get_current_commit_hash returns a valid commit hash.

    Args:
        git_repo: Path to the temporary git repository.
    """
    commit_hash: str | None = get_current_commit_hash(cwd=str(git_repo))
    assert commit_hash is not None
    assert len(commit_hash) == 40


def test_add_and_remove_worktree(git_repo: Path, tmp_path: Path) -> None:
    """
    Test that add_worktree creates a new worktree and remove_worktree deletes it.

    Args:
        git_repo: Path to the temporary git repository.
        tmp_path: Temporary directory provided by pytest.
    """
    # Add a new worktree
    worktree_path: Path = tmp_path / "worktree"
    commit_hash: str | None = get_current_commit_hash(cwd=str(git_repo))
    if commit_hash is None:
        pytest.skip("No commit hash available")
    added: bool = add_worktree(str(worktree_path), rev=commit_hash, cwd=str(git_repo))
    assert added
    assert worktree_path.exists()
    # Remove the worktree
    removed: bool = remove_worktree(str(worktree_path), cwd=str(git_repo))
    assert removed
    assert not (worktree_path / ".git").exists()
