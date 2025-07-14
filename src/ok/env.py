import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Generator, Optional, Protocol

from ok.config import ConfigModel
from ok.log import LLMOutputType


@dataclass
class RunResult:
    """Represents the result of a shell command execution."""

    exit_code: int
    stdout: str
    stderr: str
    success: bool
    error: Optional[str] = None


class Env(Protocol):
    """
    `Env` contains everything "global" the agent is allowed to use, like a loggger, a config, etc.

    It is threaded throughout the codebase.

    We use it instead of mocks, because LLMs are bad at using mocks apparently.
    """

    config: ConfigModel

    def log(self, message: str, message_type: LLMOutputType, message_human: str | None = None) -> None: ...

    def log_debug(self, message: str, **kwargs) -> None: ...

    async def run(
        self,
        command: str | list[str],
        description=None,
        command_human: Optional[list[str]] = None,
        status_message: Optional[str] = None,
        *,
        directory: Path,
        shell: bool = False,
        # TODO: could take this from the env
        run_timeout_seconds: int,
    ) -> RunResult: ...

    def _get_description(self) -> str: ...

    def _init_ui(self) -> None: ...

    def update_status(self, message: str, style: str = "dim") -> None: ...

    def set_phase(self, phase: str, attempt_info: Optional[str] = None) -> None: ...

    def _cleanup_status_bar(self) -> None: ...

    @contextmanager
    def get_ui_manager(self) -> Generator[None, None, None]: ...
