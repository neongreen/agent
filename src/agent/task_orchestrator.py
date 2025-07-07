"""Orchestrates the execution of tasks, managing their planning and implementation phases."""

from pathlib import Path

from .constants import PLAN_FILE, STATE_FILE, TaskState
from .git_utils import has_tracked_diff, resolve_commit_specifier, setup_task_branch
from .llm import LLM
from .output_formatter import LLMOutputType, print_formatted_message
from .state_manager import read_state, write_state
from .task_implementation import ImplementationPhaseResult
from .task_implementation import implementation_phase as implementation_phase
from .task_planning import planning_phase
from .ui import status_manager
from .utils import log


def process_task(
    task: str,
    task_num: int,
    *,
    base_rev: str,
    cwd: Path,
    llm: LLM,
) -> ImplementationPhaseResult:
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

    def current_task_state() -> TaskState:
        """Returns the current state of the task from the state manager."""
        return state.get(task_id, TaskState.PLAN)

    print_formatted_message(
        (f"Attempting to set up task branch for task {task_num}"), message_type=LLMOutputType.STATUS
    )

    resolved_base_commit_sha = resolve_commit_specifier(base_rev, cwd=cwd)
    if not resolved_base_commit_sha:
        print_formatted_message(f"Failed to resolve base specifier: {base_rev}", message_type=LLMOutputType.TOOL_ERROR)
        state[task_id] = TaskState.ABORT
        write_state(state)
        return ImplementationPhaseResult(status="failed", feedback="Failed to resolve base specifier")

    # Set up branch
    if not setup_task_branch(task, task_num, base_rev=resolved_base_commit_sha, cwd=cwd, llm=llm):
        print_formatted_message("Failed to set up task branch", message_type=LLMOutputType.TOOL_ERROR)
        status_manager.update_status("Failed to set up task branch.", style="red")
        state[task_id] = TaskState.ABORT
        write_state(state)
        return ImplementationPhaseResult(status="failed", feedback="Failed to set up task branch")

    # Planning phase
    plan = None

    match current_task_state():
        case TaskState.PLAN:
            plan = planning_phase(task, cwd=cwd, llm=llm)
            if not plan:
                print_formatted_message("Planning phase failed", message_type=LLMOutputType.ERROR)
                status_manager.update_status("Failed.", style="red")
                state[task_id] = TaskState.ABORT
                write_state(state)
                return ImplementationPhaseResult(status="failed", feedback="Planning phase failed")
            state[task_id] = TaskState.IMPLEMENT
            write_state(state)

        case TaskState.IMPLEMENT | TaskState.DONE:
            # If already in IMPLEMENT or DONE, try to read the plan from file
            if PLAN_FILE.exists():
                with open(PLAN_FILE, "r") as f:
                    plan = f.read()
                print_formatted_message(f"Resuming from existing {PLAN_FILE.name}", message_type=LLMOutputType.STATUS)
            else:
                print_formatted_message(
                    f"No {PLAN_FILE.name} found for resuming, aborting task.", message_type=LLMOutputType.ERROR
                )
                status_manager.update_status("No plan found for resuming.", style="red")
                state[task_id] = TaskState.ABORT
                write_state(state)
                return ImplementationPhaseResult(status="failed", feedback="No plan found for resuming")

    # Implementation phase
    assert plan is not None, "Plan should not be None at this point"
    result: ImplementationPhaseResult = ImplementationPhaseResult(
        status="failed", feedback="Implementation not attempted"
    )

    if current_task_state() == TaskState.IMPLEMENT:
        assert resolved_base_commit_sha is not None, "resolved_base_commit_sha should not be None at this point"
        result = implementation_phase(task=task, plan=plan, base_attempt=resolved_base_commit_sha, cwd=cwd, llm=llm)
        if result.status == "complete":
            if not has_tracked_diff(cwd=cwd):
                print_formatted_message(
                    "No tracked changes after implementation, marking as DONE.",
                    message_type=LLMOutputType.STATUS,
                )
                state[task_id] = TaskState.DONE
            else:
                print_formatted_message(
                    "Tracked changes remain after implementation, keeping in IMPLEMENT state.",
                    message_type=LLMOutputType.STATUS,
                )
                state[task_id] = TaskState.IMPLEMENT  # Keep in IMPLEMENT if changes exist
        else:
            state[task_id] = TaskState.ABORT
        write_state(state)

    elif current_task_state() == TaskState.DONE:
        print_formatted_message(
            f"Task {task_num} already marked as DONE, skipping implementation.",
            message_type=LLMOutputType.STATUS,
        )
        result = ImplementationPhaseResult(status="complete", feedback="Task already marked as DONE")

    if result.status == "complete":
        print_formatted_message((f"Task {task_num} completed successfully"), message_type=LLMOutputType.STATUS)
        # Remove the agent state file after a task is done
        try:
            if STATE_FILE.exists():
                STATE_FILE.unlink()
                print_formatted_message(("Agent state file removed."), message_type=LLMOutputType.STATUS)
                status_manager.update_status("Agent state file removed.")
        except OSError as e:
            log(f"Error removing agent state file: {e}", message_type=LLMOutputType.ERROR)
            status_manager.update_status("Error removing agent state file.", style="red")

    else:
        log(f"Task {task_num} failed or incomplete", message_type=LLMOutputType.ERROR)
        status_manager.update_status(f"Task {task_num} failed or incomplete.", style="red")

    return result
