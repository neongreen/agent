import unittest.mock
from pathlib import Path
from unittest.mock import patch


llm_mock = unittest.mock.Mock()
run_mock = unittest.mock.Mock()
update_status_mock = unittest.mock.Mock()
set_phase_mock = unittest.mock.Mock()
log_mock = unittest.mock.Mock()


# TODO: figure out a more robust way to do these mocks, LLM is struggling with writing tests


@patch("ok.llms.base.LLMBase", llm_mock)
@patch("ok.utils.run", run_mock)
@patch("ok.ui.update_status", update_status_mock)
@patch("ok.ui.set_phase", set_phase_mock)
@patch("ok.log.log", log_mock)
async def test_implementation_phase_with_refinement() -> None:
    """
    Test the implementation phase when the completion judge returns feedback, triggering planner refinement.
    """
    from ok.config import ConfigModel
    from ok.task_implementation import Settings, implementation_phase
    from ok.utils import RunResult

    call_log = []
    refinement_called = [False]

    async def llm_run_side_effect(prompt, *args, **kwargs):
        call_log.append(prompt)
        if "Create a detailed implementation plan" in prompt:
            return "Initial plan."
        if "Review this plan" in prompt:
            return "Looks good\nAPPROVED APPROVED APPROVED"
        if "Evaluate if these changes make progress" in prompt:
            return "Progress made\nSUCCESS SUCCESS SUCCESS"
        if "now complete based on the work done" in prompt:
            # First time, trigger refinement; second time, finish
            if not refinement_called[0]:
                refinement_called[0] = True
                return "Needs more work on edge cases.\nCONTINUE CONTINUE CONTINUE"
            else:
                return "All done.\nCOMPLETE COMPLETE COMPLETE"
        if "Revise the following plan" in prompt:
            return "Revised plan with edge cases."
        if "Execution phase" in prompt and "This is your attempt #1" in prompt:
            return "Did some work."
        if "concise commit message" in prompt:
            return "feat: Implement the thing"
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
        llm=llm_mock,
        task="test task with refinement",
        cwd=Path("/test/cwd"),
        base_commit="main",
        config=ConfigModel(),
    )

    result = await implementation_phase(
        task=settings.task,
        base_commit=settings.base_commit,
        cwd=settings.cwd,
        llm=settings.llm,
        config=settings.config,
    )

    # The planner should have been called twice: initial and refinement
    plan_prompts = [
        p for p in call_log if "Create a detailed implementation plan" in p or "Revise the following plan" in p
    ]
    assert len(plan_prompts) == 2, f"Expected 2 planning prompts, got {len(plan_prompts)}"
    # The final result should still be a Done object (could be CONTINUE or COMPLETE depending on further logic)
    assert hasattr(result, "verdict")


@patch("ok.llms.base.LLMBase", llm_mock)
@patch("ok.utils.run", run_mock)
@patch("ok.ui.update_status", update_status_mock)
@patch("ok.ui.set_phase", set_phase_mock)
@patch("ok.log.log", log_mock)
async def test_implementation_phase() -> None:
    from ok.config import ConfigModel
    from ok.task_implementation import Done, Settings, TaskVerdict, implementation_phase
    from ok.utils import RunResult

    # Configure the mock's run method to return different values based on the prompt
    async def llm_run_side_effect(prompt, *args, **kwargs):
        if "concise commit message" in prompt:
            return "feat: Implement the thing"
        if "Create a detailed implementation plan" in prompt:
            return "This is a mock plan."
        if "Review this plan" in prompt:
            return "Looks good\nAPPROVED APPROVED APPROVED"
        if "Evaluate if these changes make progress" in prompt:
            return "Excellent progress\nSUCCESS SUCCESS SUCCESS"
        if "now complete based on the work done" in prompt:
            return "Looks good\nCOMPLETE COMPLETE COMPLETE"
        if "Execution phase" in prompt and "This is your attempt #1" in prompt:
            return "I think I'm done here."
        else:
            raise ValueError(f"The mock LLM doesn't know how to respond to this prompt: {repr(prompt)}")

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
        llm=llm_mock,
        task="test task",
        cwd=Path("/test/cwd"),
        base_commit="main",
        config=ConfigModel(),
    )

    # Run the implementation phase
    result = await implementation_phase(
        task=settings.task,
        base_commit=settings.base_commit,
        cwd=settings.cwd,
        llm=settings.llm,
        config=settings.config,
    )

    # Assert the final result
    assert result == Done(verdict=TaskVerdict.COMPLETE, status="Looks good\nCOMPLETE COMPLETE COMPLETE")

    # # Check that `run` was called for git operations
    # assert any("git add" in call.args[0] for call in mock_run.call_args_list)
    # assert any("git commit" in call.args[0] for call in mock_run.call_args_list)

    # # Verify that status updates were made
    # mock_update_status.assert_called()

    # # Verify that log messages were printed
    # mock_log.assert_called()

    # # Verify that formatted messages were printed
    # (print_formatted_message is now internal; assert log call if needed)
