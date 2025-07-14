import unittest.mock
from pathlib import Path
from unittest.mock import patch

import pytest

from ok.config import ConfigModel
from ok.env import Env, RunResult


class MockEnv(Env):
    def __init__(self):
        self.config = ConfigModel(run_timeout_seconds=5, llm_timeout_seconds=5)
        self.update_status = unittest.mock.Mock()
        self.set_phase = unittest.mock.Mock()

    def log(self, message: str, message_type=None, message_human: str | None = None) -> None:
        pass

    def log_debug(self, message: str, **kwargs) -> None:
        pass

    async def run(
        self,
        command: str | list[str],
        description=None,
        command_human=None,
        status_message=None,
        *,
        directory: Path,
        shell: bool = False,
        run_timeout_seconds: int = 5,
    ) -> RunResult:
        return RunResult(
            success=True,
            stdout="",
            stderr="",
            exit_code=0,
            error=None,
        )


@pytest.fixture
def env() -> MockEnv:
    return MockEnv()


llm_mock = unittest.mock.Mock()
run_mock = unittest.mock.Mock()
log_mock = unittest.mock.Mock()


@patch("ok.llms.base.LLMBase", llm_mock)
async def test_implementation_phase_failure(env: MockEnv) -> None:
    """
    Tests the implementation_phase function's behavior when the LLM and run mocks simulate repeated failures at various steps.

    Specifically:
    - The LLM fails to generate an implementation plan (returns None).
    - The LLM returns failure messages for commit, progress, and completion prompts.

    In this case, we expect the implementation phase to return a Done object with a verdict of 'failed'.
    """
    from ok.task_implementation import Settings, implementation_phase
    from ok.utils import RunResult

    # Configure the mock's run method to simulate repeated failures
    async def llm_run_side_effect(env_arg, prompt, *args, **kwargs):
        if "concise commit message" in prompt:
            return "fail: Could not complete the task"
        if "implementation plan" in prompt:
            return None  # Simulate plan generation failure
        if "Review this plan" in prompt:
            return "Looks fine\nAPPROVED APPROVED APPROVED"
        if "Evaluate if these changes make progress" in prompt:
            return "No progress made\nFAILURE FAILURE FAILURE"
        if "now complete based on the work done" in prompt:
            return "Not done\nCONTINUE CONTINUE CONTINUE"
        if "Execution phase. You are implementing this task" in prompt or "Implement the next step" in prompt:
            return "Attempted but failed."
        return ""

    llm_mock.run.side_effect = llm_run_side_effect

    async def run_side_effect(*args, **kwargs):
        return RunResult(
            success=True,
            stdout="",
            stderr="",
            exit_code=0,
            error=None,
        )

    run_mock.side_effect = run_side_effect

    settings = Settings(
        env=env,
        llm=llm_mock,
        task="test failing task",
        cwd=Path("/test/cwd"),
        base_commit="main",
        config=env.config,
    )

    # Run the implementation phase
    result = await implementation_phase(
        env,
        task=settings.task,
        base_commit=settings.base_commit,
        cwd=settings.cwd,
        llm=settings.llm,
    )

    # Assert the final result is a failure (Done with verdict 'failed')
    assert getattr(result, "verdict", None) == "failed"
    env.set_phase.assert_called()
    env.update_status.assert_called()
