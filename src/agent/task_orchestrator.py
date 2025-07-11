"""Orchestrates the execution of tasks, managing their planning and implementation phases."""

from pathlib import Path
from typing import assert_never

from eliot import log_call

from agent.constants import STATE_FILE, TaskState
from agent.git_utils import resolve_commit_specifier, setup_task_branch
from agent.llm import LLM
from agent.output_formatter import LLMOutputType, print_formatted_message
from agent.state_manager import read_state
from agent.task_implementation import Done, TaskVerdict, implementation_phase
from agent.ui import status_manager
from agent.utils import log


@log_call(include_args=["task", "task_num", "base_rev", "cwd"])
def process_task(
    task: str,
    task_num: int,
    *,
    base_rev: str,
    cwd: Path,
    llm: LLM,
) -> Done:
    """
    Processes a single task through its planning and implementation phases.

    Args:
        task: The description of the task to process.
        task_num: The sequential number of the task.
        base_rev: The base Git revision (branch, commit, or tag) to start from.
        cwd: The current working directory for task execution as a Path.

    Returns:
        Implementation status.
    """
    status_manager.set_phase(f"Task {task_num}")
    print_formatted_message((f"Processing task {task_num}: {task}"), message_type=LLMOutputType.STATUS)

    task_id = f"task_{task_num}"
    state = read_state()

    print_formatted_message(
        (f"Attempting to set up task branch for task {task_num}"), message_type=LLMOutputType.STATUS
    )

    resolved_base_commit_sha = resolve_commit_specifier(base_rev, cwd=cwd)
    if not resolved_base_commit_sha:
        print_formatted_message(f"Failed to resolve base specifier: {base_rev}", message_type=LLMOutputType.TOOL_ERROR)
        result = Done(
            verdict="failed",
            status=f"Failed to resolve base specifier: {base_rev}",
        )

    # Set up branch
    elif not setup_task_branch(task, task_num, base_rev=resolved_base_commit_sha, cwd=cwd, llm=llm):
        print_formatted_message("Failed to set up task branch", message_type=LLMOutputType.TOOL_ERROR)
        result = Done(
            verdict="failed",
            status="Failed to set up task branch",
        )

    else:
        result = implementation_phase(task=task, base_commit=resolved_base_commit_sha, cwd=cwd, llm=llm)

    # Planning phase
    # plan: Optional[str] = None
    # result: ImplementationPhaseResult = ImplementationPhaseResult(
    #     status="failed", feedback="Implementation not attempted"
    # )

    # TODO: ohhhhhhh so we can actually check for plan and check resumability of whatever;
    # and in the implementation state machine we don't think about that
    # if current_task_state() == TaskState.PLAN:
    #     plan, state = _handle_plan_state(task, cwd, llm, task_id, state)
    # elif current_task_state() in [TaskState.IMPLEMENT, TaskState.DONE]:
    #     plan, state = _handle_resume_state(task_id, state)

    # # Implementation phase
    # if plan is not None:
    #     if current_task_state() == TaskState.IMPLEMENT:
    #         result, state = _handle_implement_state(task, plan, resolved_base_commit_sha, cwd, llm, task_id, state)
    #     elif current_task_state() == TaskState.DONE:
    #         result = _handle_done_state(task_num)

    match result.verdict:
        case TaskVerdict.COMPLETE:
            state[task_id] = TaskState.DONE
            print_formatted_message((f"Task {task_num} completed successfully"), message_type=LLMOutputType.STATUS)
        case TaskVerdict.CONTINUE:
            state[task_id] = TaskState.IMPLEMENT
            print_formatted_message(
                f"Task {task_num} not completed, but some work was done.", message_type=LLMOutputType.STATUS
            )
        case "failed":
            state[task_id] = TaskState.ABORT
            print_formatted_message(f"Task {task_num} failed: {result.status}", message_type=LLMOutputType.ERROR)
        case "interrupted":
            state[task_id] = TaskState.ABORT
            print_formatted_message(f"Task {task_num} interrupted: {result.status}", message_type=LLMOutputType.ERROR)
        case _:
            assert_never(result.verdict)

    # Remove the agent state file after a task is done
    # TODO: for now it's actually "always"
    try:
        if STATE_FILE.exists():
            STATE_FILE.unlink()
            print_formatted_message(("Agent state file removed."), message_type=LLMOutputType.STATUS)
            status_manager.update_status("Agent state file removed.")
    except OSError as e:
        log(f"Error removing agent state file: {e}", message_type=LLMOutputType.ERROR)
        status_manager.update_status("Error removing agent state file.", style="red")

    return result
