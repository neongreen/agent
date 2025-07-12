"""Orchestrates the execution of tasks, managing their planning and implementation phases."""

from pathlib import Path
from typing import assert_never

from ok.config import OkSettings
from ok.constants import STATE_FILE, TaskState
from ok.git_utils import resolve_commit_specifier, setup_task_branch
from ok.llms.base import LLMBase
from ok.log import LLMOutputType, log
from ok.state_manager import read_state
from ok.task_implementation import Done, TaskVerdict, implementation_phase
from ok.ui import set_phase, update_status
from ok.util.eliot import log_call


@log_call(include_args=["task", "task_num", "base_rev", "cwd"])
async def process_task(
    task: str,
    task_num: int,
    *,
    base_rev: str,
    cwd: Path,
    llm: LLMBase,
    config: OkSettings,
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
    set_phase(f"Task {task_num}")
    log((f"Processing task {task_num}: {task}"), message_type=LLMOutputType.STATUS)

    task_id = f"task_{task_num}"
    state = read_state()

    log((f"Attempting to set up task branch for task {task_num}"), message_type=LLMOutputType.STATUS)

    resolved_base_commit_sha = await resolve_commit_specifier(base_rev, cwd=cwd)
    if not resolved_base_commit_sha:
        log(f"Failed to resolve base specifier: {base_rev}", message_type=LLMOutputType.TOOL_ERROR)
        result = Done(
            verdict="failed",
            status=f"Failed to resolve base specifier: {base_rev}",
        )

    # Set up branch
    elif not await setup_task_branch(task, task_num, base_rev=resolved_base_commit_sha, cwd=cwd, llm=llm):
        log("Failed to set up task branch", message_type=LLMOutputType.TOOL_ERROR)
        result = Done(
            verdict="failed",
            status="Failed to set up task branch",
        )

    else:
        result = await implementation_phase(
            task=task,
            base_commit=resolved_base_commit_sha,
            cwd=cwd,
            llm=llm,
            config=config,
        )

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
            log((f"Task {task_num} completed successfully"), message_type=LLMOutputType.STATUS)
        case TaskVerdict.CONTINUE:
            state[task_id] = TaskState.IMPLEMENT
            log(f"Task {task_num} not completed, but some work was done.", message_type=LLMOutputType.STATUS)
        case "failed":
            state[task_id] = TaskState.ABORT
            log(f"Task {task_num} failed: {result.status}", message_type=LLMOutputType.ERROR)
        case "interrupted":
            state[task_id] = TaskState.ABORT
            log(f"Task {task_num} interrupted: {result.status}", message_type=LLMOutputType.ERROR)
        case _:
            assert_never(result.verdict)

    # Remove the agent state file after a task is done
    # TODO: for now it's actually "always"
    try:
        if STATE_FILE.exists():
            STATE_FILE.unlink()
            log(("Agent state file removed."), message_type=LLMOutputType.STATUS)
            update_status("Agent state file removed.")
    except OSError as e:
        log(f"Error removing agent state file: {e}", message_type=LLMOutputType.ERROR)
        update_status("Error removing agent state file.", style="red")

    return result
