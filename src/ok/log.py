import os
from datetime import datetime
from enum import StrEnum, auto
from pathlib import Path
from typing import Callable

import eliot
import eliot.json
from eliot import FileDestination, register_exception_extractor
from ok.constants import OK_STATE_BASE_DIR


class LLMOutputType(StrEnum):
    """Represents the different types of LLM outputs."""

    PLAN = auto()
    """Proposed plan by the LLM."""
    EVALUATION = auto()
    """Evaluation by the judge."""
    STATUS = auto()
    """Some kind of status message."""

    ERROR = auto()
    """Error message."""
    PROMPT = auto()
    """The prompt sent to the LLM."""
    LLM_RESPONSE = auto()
    """Any generic response from the LLM."""
    TOOL_EXECUTION = auto()
    """Calling any command (shell, etc)."""
    TOOL_OUTPUT = auto()
    """Output from a tool execution."""
    TOOL_ERROR = auto()
    """Error from a tool execution."""


def log_json_encoder(obj):
    """
    Custom JSON encoder that builds on Eliot's JSON encoder but doesn't fail on non-serializable objects.
    """

    try:
        return eliot.json.json_default(obj)
    except TypeError:
        return repr(obj)


# TODO: get rid of this global state
_logging_initialized = False
_log_file_path: Path | None = None


def init_logging() -> None:
    global _logging_initialized
    global _log_file_path
    if _logging_initialized:
        return
    _logging_initialized = True

    # Initialize Eliot logging
    timestamp = datetime.now().strftime("%Y-%m-%dT%H%M%S")
    _log_file_path = OK_STATE_BASE_DIR / "logs" / f"log-{timestamp}_{os.getpid()}.json"
    _log_file_path.parent.mkdir(parents=True, exist_ok=True)
    eliot.add_destinations(FileDestination(file=open(_log_file_path, "ab"), json_default=log_json_encoder))

    # For Trio
    register_exception_extractor(BaseExceptionGroup, lambda e: {"str": repr(e)})


def get_log_file_path() -> Path | None:
    return _log_file_path


def real_log(
    message: str,
    message_type: LLMOutputType,
    message_human: str | None = None,
) -> None:
    """
    Simple logging function that respects quiet mode.

    Arguments:
        message: The message to log to the log file.
        message_type: The type of the message, used for formatting.
        message_human: Optional human-readable message to display in the console. Should be formatted as Markdown.
          If not provided, `message` will be used.
        quiet: If provided, overrides the global quiet mode setting.
    """

    init_logging()

    eliot.log_message(f"log.{message_type}", str=message, **({"human": message_human} if message_human else {}))


def format_as_markdown_blockquote(text: str) -> str:
    """
    Formats the given text as a Markdown blockquote.
    """
    lines = text.splitlines()
    blockquote_lines = [f"> {line}" for line in lines]
    return "\n".join(blockquote_lines)
