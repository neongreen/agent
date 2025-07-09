import unittest.mock
from pathlib import Path

from agent.task_implementation import Done, Settings, TaskVerdict, implementation_phase


def test_implementation_phase() -> None:
    # Create a mock for the LLM
    llm_mock = unittest.mock.Mock()

    # Configure the mock's run method to return different values based on the prompt
    def llm_run_side_effect(prompt, *args, **kwargs):
        if "concise commit message" in prompt:
            return "feat: Implement the thing"
        if "Create a detailed implementation plan" in prompt:
            return "This is a mock plan."
        if "Review this plan" in prompt:
            return "APPROVED APPROVED APPROVED\nLooks good"
        if "Evaluate if this step makes progress" in prompt:
            return "SUCCESS SUCCESS SUCCESS\nExcellent progress"
        if "now complete based on the work done" in prompt:
            return "COMPLETE COMPLETE COMPLETE\nLooks good"
        if "Implement the next step" in prompt and "This is your attempt #1" in prompt:
            return "I think I'm done here."
        else:
            raise ValueError(f"Unexpected prompt: {prompt}")

    llm_mock.run.side_effect = llm_run_side_effect

    settings = Settings(
        llm=llm_mock,
        task="test task",
        cwd=Path("/test/cwd"),
        base_commit="main",
    )

    # Patch the dependencies
    with (
        unittest.mock.patch(
            "agent.task_implementation.run",
            return_value={"success": True, "stdout": "", "stderr": ""},
        ) as _mock_run,
        unittest.mock.patch("agent.task_implementation.log") as _mock_log,
        unittest.mock.patch("agent.task_implementation.status_manager.update_status") as _mock_update_status,
        unittest.mock.patch("agent.task_implementation.print_formatted_message") as _mock_print_formatted_message,
    ):
        # Run the implementation phase
        result = implementation_phase(
            task=settings.task,
            base_commit=settings.base_commit,
            cwd=settings.cwd,
            llm=settings.llm,
        )

        # Assert the final result
        assert result == Done(verdict=TaskVerdict.COMPLETE, status="COMPLETE COMPLETE COMPLETE\nLooks good")

        # # Check that `run` was called for git operations
        # assert any("git add" in call.args[0] for call in mock_run.call_args_list)
        # assert any("git commit" in call.args[0] for call in mock_run.call_args_list)

        # # Verify that status updates were made
        # mock_update_status.assert_called()

        # # Verify that log messages were printed
        # mock_log.assert_called()

        # # Verify that formatted messages were printed
        # mock_print_formatted_message.assert_called()
