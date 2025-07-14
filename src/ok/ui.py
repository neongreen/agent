"""Manages the UI for the agent, including a split view for logs and status."""
from contextlib import contextmanager
from typing import Generator

from ok.env import Env


@contextmanager
def get_ui_manager(env: Env) -> Generator[None, None, None]:
    """A context manager for the UI."""
    env._init_ui()
    try:
        yield
    finally:
        env._cleanup_status_bar()
