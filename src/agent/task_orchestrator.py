"""Orchestrates the execution of tasks, managing their planning and implementation phases."""

from .constants import PLAN_FILE, STATE_FILE, TaskState
from .git_utils import has_tracked_diff, resolve_commit_specifier, setup_task_branch
from .output_formatter import format_llm_thought, print_formatted_message
from .state_manager import read_state, write_state
from .task_implementation import implementation_phase
from .task_planning import planning_phase
from .ui import status_manager
from .utils import log


def process_task(
    task: str,
    task_num: int,
    *,
    base_rev: str,
    cwd: str,
) -> bool:
    """
    Processes a single task through its planning and implementation phases.

    Args:
        task: The description of the task to process.
        task_num: The sequential number of the task.
        base_rev: The base Git revision (branch, commit, or tag) to start from.
        cwd: The current working directory for task execution.

    Returns:
        True if the task is successfully completed, False otherwise.
    """
    status_manager.set_phase(f"Task {task_num}")
    print_formatted_message(format_llm_thought(f"Processing task {task_num}: {task}"), message_type="thought")

    task_id = f"task_{task_num}"
    state = read_state()

    def current_task_state() -> TaskState:
        """Returns the current state of the task from the state manager."""
        return state.get(task_id, TaskState.PLAN.value)

    print_formatted_message(
        format_llm_thought(f"Current state for {task_id}: {current_task_state()}"), message_type="thought"
    )

    resolved_base_commit_sha = None
    # Set up branch
    if current_task_state() == TaskState.PLAN.value:
        # Resolve the base_branch to a commit SHA before setting up the task branch
        resolved_base_commit_sha = resolve_commit_specifier(base_rev, cwd=cwd)
        if not resolved_base_commit_sha:
            print_formatted_message(f"Failed to resolve base specifier: {base_rev}", message_type="tool_output_error")
            state[task_id] = TaskState.ABORT.value
            write_state(state)
            return False

        if not setup_task_branch(task, task_num, base_rev=resolved_base_commit_sha, cwd=cwd):
            print_formatted_message("Failed to set up task branch", message_type="tool_output_error")
            status_manager.update_status("Failed to set up task branch.", style="red")
            state[task_id] = TaskState.ABORT.value
            write_state(state)
            return False
        state[task_id] = TaskState.PLAN.value
        write_state(state)
    elif current_task_state() == TaskState.IMPLEMENT.value or current_task_state() == TaskState.DONE.value:
        resolved_base_commit_sha = resolve_commit_specifier(base_rev, cwd=cwd)
        if not resolved_base_commit_sha:
            print_formatted_message(
                f"Failed to resolve base specifier: {base_rev} for resuming task", message_type="tool_output_error"
            )
            state[task_id] = TaskState.ABORT.value
            write_state(state)
            return False
    # Planning phase
    plan = None
    if current_task_state() == TaskState.PLAN.value:
        plan = planning_phase(task, cwd=cwd)
        if not plan:
            print_formatted_message("Planning phase failed", message_type="tool_output_error")
            status_manager.update_status("Failed.", style="red")
            state[task_id] = TaskState.ABORT.value
            write_state(state)
            return False
        state[task_id] = TaskState.IMPLEMENT.value
        write_state(state)
    elif current_task_state() == TaskState.IMPLEMENT.value or current_task_state() == TaskState.DONE.value:
        # If already in IMPLEMENT or DONE, try to read the plan from file
        if PLAN_FILE.exists():
            with open(PLAN_FILE, "r") as f:
                plan = f.read()
            print_formatted_message(
                format_llm_thought(f"Resuming from existing {PLAN_FILE.name}"), message_type="thought"
            )
        else:
            print_formatted_message(
                f"No {PLAN_FILE.name} found for resuming, aborting task.", message_type="tool_output_error"
            )
            status_manager.update_status("No plan found for resuming.", style="red")
            state[task_id] = TaskState.ABORT.value
            write_state(state)
            return False

    # Implementation phase
    assert plan is not None, "Plan should not be None at this point"
    success = False
    if current_task_state() == TaskState.IMPLEMENT.value:
        assert resolved_base_commit_sha is not None, "resolved_base_commit_sha should not be None at this point"
        success = implementation_phase(task=task, plan=plan, base_commit=resolved_base_commit_sha, cwd=cwd)
        if success:
            if not has_tracked_diff(cwd=cwd):
                print_formatted_message(
                    format_llm_thought("No tracked changes after implementation, marking as DONE."),
                    message_type="thought",
                )
                state[task_id] = TaskState.DONE.value
            else:
                print_formatted_message(
                    format_llm_thought("Tracked changes remain after implementation, keeping in IMPLEMENT state."),
                    message_type="thought",
                )
                state[task_id] = TaskState.IMPLEMENT.value  # Keep in IMPLEMENT if changes exist
        else:
            state[task_id] = TaskState.ABORT.value
        write_state(state)
    elif current_task_state() == TaskState.DONE.value:
        print_formatted_message(
            format_llm_thought(f"Task {task_num} already marked as DONE, skipping implementation."),
            message_type="thought",
        )
        success = True

    if success:
        print_formatted_message(format_llm_thought(f"Task {task_num} completed successfully"), message_type="thought")
        # Remove the agent state file after a task is done
        try:
            if STATE_FILE.exists():
                STATE_FILE.unlink()
                print_formatted_message(format_llm_thought("Agent state file removed."), message_type="thought")
                status_manager.update_status("Agent state file removed.")
        except OSError as e:
            log(f"Error removing agent state file: {e}", message_type="tool_output_error")
            status_manager.update_status("Error removing agent state file.", style="red")
    else:
        log(f"Task {task_num} failed or incomplete")
        status_manager.update_status(f"Task {task_num} failed or incomplete.", style="red")

    return success
