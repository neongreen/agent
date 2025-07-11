"""
This module provides an object for interacting with various LLM engines.
"""

import re
from enum import StrEnum
from typing import Literal, Optional, Type

from agent.llms.base import LLMBase
from agent.llms.claude import Claude
from agent.llms.codex import Codex
from agent.llms.gemini import Gemini
from agent.llms.mock import MockLLM
from agent.llms.opencode import Opencode
from agent.llms.openrouter import OpenRouter


def get_llm(
    engine: Literal["gemini", "claude", "codex", "openrouter", "opencode", "mock"],
    model: Optional[str],
) -> LLMBase:
    """
    Returns an instance of the appropriate LLM class.

    Args:
        engine: The LLM engine to use.
        model: The model to use for the LLM.

    Returns:
        An instance of the appropriate LLM class.
    """
    if engine == "claude":
        return Claude(model)
    elif engine == "codex":
        return Codex(model)
    elif engine == "openrouter":
        return OpenRouter(model)
    elif engine == "gemini":
        return Gemini(model)
    elif engine == "opencode":
        return Opencode(model)
    elif engine == "mock":
        return MockLLM(model)
    else:
        raise ValueError(f"Unknown LLM engine: {engine}.")


### Utils ###


def check_verdict[T: StrEnum](verdict_type: Type[T], judgment: str) -> T | None:
    """
    Checks judge's verdict based on a list of possible verdicts/statuses from an Enum.
    The verdict is expected to be in the **last** line.

    Args:
        verdict_type: A StrEnum class containing possible status values (e.g. ImplementationVerdict).
        judgment: A string with the entire judgment from the LLM.

    Returns:
        An enum member indicating the verdict, or None if not found.
    """
    lines = judgment.strip().splitlines()
    if not lines:
        return None

    last_line = lines[-1].upper()
    matches = re.findall("|".join([r"\b" + re.escape(verdict.upper()) + r"\b" for verdict in verdict_type]), last_line)

    if not matches:
        return None
    else:
        last_verdict = matches[-1]
        for verdict in verdict_type:
            if last_verdict == verdict.upper():
                return verdict
