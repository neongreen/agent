import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Generator, Optional

from rich.console import Console
from rich.live import Live
from rich.padding import Padding
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TaskID, TextColumn, TimeElapsedColumn

import eliot

import ok.log
from ok.config import ConfigModel
from ok.env import Env, RunResult
from ok.log import LLMOutputType
from ok.utils import real_run


@dataclass
class RichEnv(Env):
    config: ConfigModel
    console: Console = field(default_factory=Console, init=False)
    main_console: Optional[Console] = field(default=None, init=False)
    live: Optional[Live] = field(default=None, init=False)
    _progress: Optional[Progress] = field(default=None, init=False)
    _task_id: Optional[TaskID] = field(default=None, init=False)
    _current_phase: Optional[str] = field(default=None, init=False)
    _current_attempt_info: Optional[str] = field(default=None, init=False)
    _last_message: Optional[str] = field(default=None, init=False)
    _action_start_time: Optional[float] = field(default=None, init=False)

    def __post_init__(self):
        ok.log.init_logging()

    def log(self, message: str, message_type: LLMOutputType, message_human: str | None = None) -> None:
        if self.main_console is None:
            raise ValueError("Main console is not initialized")

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        try:
            if message_type == LLMOutputType.STATUS:
                self.main_console.print(Panel(Markdown(now + ": " + (message_human or message)), title="Status", title_align="left", border_style="magenta"))

            elif message_type == LLMOutputType.PLAN:
                self.main_console.print(Panel(Markdown(now + ": " + (message_human or message)), title="Proposed plan", title_align="left", border_style="green"))
            elif message_type == LLMOutputType.EVALUATION:
                self.main_console.print(
                    Panel(Markdown(now + ": " + (message_human or message)), title="Reviewer evaluation", title_align="left", border_style="yellow")
                )
            elif message_type == LLMOutputType.TOOL_EXECUTION:
                self.main_console.print(Panel(Markdown(now + ": " + (message_human or message)), title="Tool execution", title_align="left", border_style="cyan"))
            elif message_type == LLMOutputType.TOOL_OUTPUT:
                self.main_console.print(Panel(Markdown(now + ": " + (message_human or message)), title="Tool output", title_align="left", border_style="white"))
            elif message_type == LLMOutputType.TOOL_ERROR:
                self.main_console.print(Panel(Markdown(now + ": " + (message_human or message)), title="Tool error", title_align="left", border_style="red"))
            elif message_type == LLMOutputType.ERROR:
                self.main_console.print(Panel(Markdown(now + ": " + (message_human or message)), title="Error", title_align="left", border_style="red"))
            elif message_type == LLMOutputType.PROMPT:
                self.main_console.print(Panel(Markdown(now + ": " + (message_human or message)), title="Prompt", title_align="left", border_style="bright_blue"))
            elif message_type == LLMOutputType.LLM_RESPONSE:
                self.main_console.print(
                    Panel(Markdown(now + ": " + (message_human or message)), title="LLM response", title_align="left", border_style="bright_magenta")
                )
            else:
                self.main_console.print(now + ": " + (message_human or message))
        except MarkupError:
            self.main_console.print(Panel(Text.from_markup(now + ": " + (message_human or message))))

        ok.log.real_log(message, message_type, message_human=message_human)

    def log_debug(self, message: str, **kwargs) -> None:
        eliot.log_message("log", message=message, **kwargs)

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

    def _get_description(self) -> str:
        desc = self._current_phase or ""
        if self._current_attempt_info:
            desc += f" (attempt {self._current_attempt_info})"
        if self._last_message:
            desc += f": {self._last_message}"
        return desc or "Initializing..."

    def _init_ui(self) -> None:
        if self._progress is None:
            self._progress = Progress(
                SpinnerColumn(style="green"),
                TextColumn("[bold magenta]{task.description}"),
                TimeElapsedColumn(),
                console=self.console,
            )
            self._task_id = self._progress.add_task(self._get_description(), total=None)
            self._action_start_time = time.time()

            self.live = Live(
                Padding(self._progress, (0, 0, 1, 0)),
                console=self.console,
                refresh_per_second=5,
                vertical_overflow="visible",
            )
            self.main_console = self.live.console
            self.live.start()

    def update_status(self, message: str, style: str = "dim") -> None:
        self._last_message = message
        if self._action_start_time is None:
            self._action_start_time = time.time()
        if self._progress and self._task_id is not None:
            self._progress.update(self._task_id, description=self._get_description())

    def set_phase(self, phase: str, attempt_info: Optional[str] = None) -> None:
        self._current_phase = phase
        self._current_attempt_info = attempt_info
        self._last_message = None
        self._action_start_time = time.time()
        if self._progress and self._task_id is not None:
            self._progress.update(self._task_id, description=self._get_description())

    def _cleanup_status_bar(self) -> None:
        if self.live:
            self.live.stop()
            self.live = None
        if self._progress is not None:
            self._progress = None
            self._task_id = None
        self._current_phase = None
        self._last_message = None
        self._action_start_time = None

    @contextmanager
    def get_ui_manager(self) -> Generator[None, None, None]:
        self._init_ui()
        try:
            yield
        finally:
            self._cleanup_status_bar()
