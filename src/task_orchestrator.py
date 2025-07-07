from typing import Optional

from .config import AgentConfig
from .constants import PLAN_FILE, STATE_FILE, TaskState
from .git_utils import has_tracked_diff, resolve_commit_specifier, setup_task_branch
from .state_manager import read_state, write_state
from .task_implementation import implementation_phase
from .task_planning import planning_phase
from .ui import status_manager
from .utils import log


def process_task(
    task: str, task_num: int, base_specifier: str, cwd: Optional[str] = None, config: Optional[AgentConfig] = None
) -> bool:
    """Process a single task through planning and implementation."""
    status_manager.set_phase(f"Task {task_num}")
    log(f"Processing task {task_num}: {task}", message_type="thought", config=config)

    task_id = f"task_{task_num}"
    state = read_state()

    def current_task_state() -> TaskState:
        return state.get(task_id, TaskState.PLAN.value)

    log(f"Current state for {task_id}: {current_task_state()}", message_type="thought")

    # Set up branch
    if current_task_state() == TaskState.PLAN.value:
        # Resolve the base_branch to a commit SHA before setting up the task branch
        resolved_base_commit_sha = resolve_commit_specifier(base_specifier, cwd)
        if not resolved_base_commit_sha:
            log(f"Failed to resolve base specifier: {base_specifier}", message_type="tool_output_error")
            state[task_id] = TaskState.ABORT.value
            write_state(state)
            return False

        if not setup_task_branch(task, task_num, resolved_base_commit_sha, cwd):
            log("Failed to set up task branch", message_type="tool_output_error")
            status_manager.update_status("Failed to set up task branch.", style="red")
            state[task_id] = TaskState.ABORT.value
            write_state(state)
            return False
        state[task_id] = TaskState.PLAN.value
        write_state(state)
    # Planning phase
    plan = None
    if current_task_state() == TaskState.PLAN.value:
        plan = planning_phase(task, cwd, config)
        if not plan:
            log("Planning phase failed", config=config)
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
            log(f"Resuming from existing {PLAN_FILE.name}", message_type="thought")
        else:
            log(f"No {PLAN_FILE.name} found for resuming, aborting task.", message_type="tool_output_error")
            status_manager.update_status("No plan found for resuming.", style="red")
            state[task_id] = TaskState.ABORT.value
            write_state(state)
            return False

    # Implementation phase
    success = False
    if current_task_state() == TaskState.IMPLEMENT.value:
        success = implementation_phase(task, plan, resolved_base_commit_sha, cwd, config)
        if success:
            if not has_tracked_diff(cwd):
                log("No tracked changes after implementation, marking as DONE.", message_type="thought")
                state[task_id] = TaskState.DONE.value
            else:
                log(
                    "Tracked changes remain after implementation, keeping in IMPLEMENT state.",
                    message_type="thought",
                )
                state[task_id] = TaskState.IMPLEMENT.value  # Keep in IMPLEMENT if changes exist
        else:
            state[task_id] = TaskState.ABORT.value
        write_state(state)
    elif current_task_state() == TaskState.DONE.value:
        log(f"Task {task_num} already marked as DONE, skipping implementation.", message_type="thought")
        success = True

    if success:
        log(f"Task {task_num} completed successfully")
        # Remove the agent state file after a task is done
        try:
            if STATE_FILE.exists():
                STATE_FILE.unlink()
                log("Agent state file removed.", message_type="thought")
                status_manager.update_status("Agent state file removed.")
        except OSError as e:
            log(f"Error removing agent state file: {e}", message_type="tool_output_error")
            status_manager.update_status("Error removing agent state file.", style="red")
    else:
        log(f"Task {task_num} failed or incomplete")
        status_manager.update_status(f"Task {task_num} failed or incomplete.", style="red")

    return success
