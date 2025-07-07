import os
from typing import Optional

from .config import AgentConfig
from .constants import STATE_FILE, TaskState
from .gemini_agent import run_gemini
from .git_utils import has_tracked_diff, resolve_commit_specifier, setup_task_branch
from .state_manager import read_state, write_state
from .ui import status_manager
from .utils import log, run


def planning_phase(task: str, cwd=None, config: Optional[AgentConfig] = None) -> Optional[str]:
    """Iterative planning phase with Gemini approval."""
    status_manager.update_status(f"Starting planning phase for task: {task}")
    log(f"Starting planning phase for task: {task}", message_type="thought", config=config)

    max_planning_rounds = 5

    plan: Optional[str] = None
    previous_plan: Optional[str] = None
    previous_review: Optional[str] = None

    for round_num in range(1, max_planning_rounds + 1):
        status_manager.update_status(f"Planning round {round_num}/{max_planning_rounds}")
        log(f"Planning round {round_num}", message_type="thought", config=config)

        # Ask Gemini to create/revise plan
        if round_num == 1:
            plan_prompt = (
                f"Create a detailed implementation plan for this task: {repr(task)}. Break it down into specific, actionable steps.\n"
                "You are granted access to tools, commands, and code execution for the *sole purpose* of gaining knowledge.\n"
                "You *may not* use these tools to directly implement the task.\n"
                'Output "PLAN_TEXT_END" after the plan. You may not output anything after that marker.'
            ).strip()
        else:
            plan_prompt = (
                f"Revise the following plan for task {repr(task)} based on the feedback provided:\n\n"
                "Previous Plan:\n"
                f"{previous_plan}\n\n"
                "Reviewer Feedback:\n"
                f"{previous_review}\n\n"
                "Create a better implementation plan.\n"
                'Output "PLAN_TEXT_END" after the plan. You may not output anything after that marker.'
            ).strip()

        if config and config.plan_planner_extra_prompt:
            plan_prompt += f"\n\n{config.plan_planner_extra_prompt}"

        status_manager.update_status(f"Getting plan from Gemini (round {round_num})...")
        current_plan = run_gemini(plan_prompt, yolo=True)
        if not current_plan:
            status_manager.update_status("Failed to get plan from Gemini.", style="red")
            log("Failed to get plan from Gemini", message_type="tool_output_error")
            return None

        # Ask Gemini to review the plan
        review_prompt = (
            f"Review this plan for task {repr(task)}:\n\n"
            f"{current_plan}\n\n"
            "Respond with either 'APPROVED' if the plan is good enough to implement (even if minor improvements are possible), or 'REJECTED' followed by a list of specific blockers that must be addressed."
        )

        if config and config.plan_judge_extra_prompt:
            review_prompt += f"\n\n{config.plan_judge_extra_prompt}"

        status_manager.update_status(f"Reviewing plan (round {round_num})...")
        current_review = run_gemini(review_prompt, yolo=True)
        if not current_review:
            status_manager.update_status("Failed to get plan review from Gemini.", style="red")
            log("Failed to get plan review from Gemini", message_type="tool_output_error")
            return None

        if current_review.upper().startswith("APPROVED"):
            status_manager.update_status(f"Plan approved in round {round_num}.")
            log(f"Plan approved in round {round_num}", message_type="thought")
            plan = current_plan  # This is the approved plan

            # Commit the approved plan
            plan_path = os.path.join(cwd, "plan.md") if cwd else "plan.md"
            with open(plan_path, "w") as f:
                f.write(f"# Plan for {task}\n\n{plan}")

            # Generate commit message
            status_manager.update_status("Generating commit message for plan...")
            commit_msg_prompt = f"Generate a concise commit message (max 15 words) for approving this plan: {task}"
            commit_msg = run_gemini(commit_msg_prompt, yolo=False)
            if not commit_msg:
                commit_msg = "Approved plan for task"

            status_manager.update_status("Committing approved plan...")
            run(["git", "add", "."], "Adding plan files", directory=cwd)
            run(
                ["git", "commit", "-m", f"[plan.md] {commit_msg[:100]}"],
                "Committing approved plan",
                directory=cwd,
            )

            return plan
        else:
            status_manager.update_status(f"Plan rejected in round {round_num}. Reviewing feedback...")
            log(
                f"Plan rejected in round {round_num}: {current_review}",
                message_type="tool_output_error",
            )
            previous_plan = current_plan  # Store for next round's prompt
            previous_review = current_review  # Store for next round's prompt

    log(f"Planning failed after {max_planning_rounds} rounds", message_type="tool_output_error")
    status_manager.update_status("Planning failed.", style="red")
    return None


def implementation_phase(task, plan, base_commit: str, cwd=None, config: Optional[AgentConfig] = None) -> bool:
    """
    Iterative implementation phase with early bailout.

    Arguments:
        base_commit: *commit* to switch to before starting the implementation.
    """
    status_manager.update_status(f"Starting implementation phase for task: {task}")
    log(f"Starting implementation phase for task: {task}", message_type="thought", config=config)

    max_implementation_attempts = 10
    max_consecutive_failures = 3
    consecutive_failures = 0
    commits_made = 0

    for attempt in range(1, max_implementation_attempts + 1):
        status_manager.update_status(f"Implementation attempt {attempt}/{max_implementation_attempts}")
        log(f"Implementation attempt {attempt}", message_type="thought")

        # Ask Gemini to implement next step
        impl_prompt = (
            f"Execution phase. Based on this plan:\n\n"
            f"{plan}\n\n"
            f"Implement the next step for task {repr(task)}.\n"
            "Create files, run commands, and/or write code as needed.\n"
            "When done, provide a concise summary of what you did.\n"
            "Your response will help the reviewer of your implementation understand the changes made.\n"
        ).strip()

        if config and config.implement_extra_prompt:
            impl_prompt += f"\n\n{config.implement_extra_prompt}"

        status_manager.update_status(f"Getting implementation from Gemini (attempt {attempt})...")
        implementation_summary = run_gemini(impl_prompt, yolo=True)

        if config and config.post_implementation_hook_command:
            log(f"Running post-implementation hook: {config.post_implementation_hook_command}", message_type="thought")
            run(
                config.post_implementation_hook_command,
                "Running post-implementation hook command",
                directory=cwd,
                shell=True,
            )

        if not implementation_summary:
            status_manager.update_status("Failed to get implementation from Gemini.", style="red")
            log("Failed to get implementation summary from Gemini", message_type="tool_output_error")
            consecutive_failures += 1
            if consecutive_failures >= max_consecutive_failures:
                log("Too many consecutive failures, giving up", message_type="tool_output_error")
                return False
            continue

        # Evaluate if it seems reasonable
        log(
            f"Judging the implementation based on the diff. Gemini provided this explanation along with its implementation:\n{implementation_summary}",
            message_type="thought",
        )
        eval_prompt = (
            f"Evaluate if this implementation makes progress on the task {repr(task)}.\n"
            "Respond with 'SUCCESS' if it's a good step forward, 'PARTIAL' if it's somewhat helpful, or 'FAILURE' if it's not useful.\n"
            "For 'PARTIAL', provide specific feedback on what could be improved or what remains to be done.\n"
            "For 'FAILURE', list specific reasons why the implementation is inadequate.\n"
            "Here is the summary of the implementation:\n\n"
            f"{implementation_summary}\n\n"
            "Here is the diff of the changes made:\n\n"
            f"{run(['git', 'diff', base_commit + '..HEAD'], directory=cwd)['stdout']}"
        )

        if config and config.implement_judge_extra_prompt:
            eval_prompt += f"\n\n{config.implement_judge_extra_prompt}"

        status_manager.update_status(f"Evaluating implementation (attempt {attempt})...")
        evaluation = run_gemini(eval_prompt, yolo=True)
        if not evaluation:
            status_manager.update_status("Failed to get evaluation from Gemini.", style="red")
            log("Failed to get evaluation from Gemini", message_type="tool_output_error")
            consecutive_failures += 1
            if consecutive_failures >= max_consecutive_failures:
                log("Too many consecutive failures, giving up", message_type="tool_output_error")
                return False
            continue

        if evaluation.upper().startswith("SUCCESS"):
            status_manager.update_status(f"Implementation successful (attempt {attempt}).")
            log(f"Implementation successful in attempt {attempt}", message_type="thought")
            consecutive_failures = 0
            commits_made += 1

            # Generate commit message and commit
            status_manager.update_status("Generating commit message for implementation...")
            commit_msg_prompt = (
                f"Generate a concise commit message (max 15 words) for this implementation step: {repr(task)}"
            )
            commit_msg = run_gemini(commit_msg_prompt, yolo=False)
            if not commit_msg:
                commit_msg = "Implementation step for task"

            status_manager.update_status("Committing implementation...")
            run(["git", "add", "."], "Adding implementation files", directory=cwd)
            run(
                ["git", "commit", "-m", f"{commit_msg[:100]}"],
                "Committing implementation",
                directory=cwd,
            )

            # Check if task is complete
            status_manager.update_status("Checking if task is complete...")
            completion_prompt = (
                f"Is the task {repr(task)} now complete based on the work done?"
                "You are granted access to tools, commands, and code execution for the *sole purpose* of evaluating whether the task is done."
                "The work has been done in the current git branch, and you can inspect the files, run commands, and check the diffs."
                "You may not finish your response at 'I have to check ...' or 'I have to inspect files ...' - you must use your tools to check directly."
                "Respond with 'COMPLETE' if fully done, or 'CONTINUE' if more work is needed."
                "If 'CONTINUE', provide specific next steps to take, or objections to address."
            )

            if config and config.implement_completion_judge_extra_prompt:
                completion_prompt += f"\n\n{config.implement_completion_judge_extra_prompt}"

            completion_check = run_gemini(completion_prompt, yolo=True)

            if completion_check and completion_check.upper().startswith("COMPLETE"):
                status_manager.update_status("Task marked as complete.")
                log("Task marked as complete", message_type="thought")
                return True

        elif evaluation.upper().startswith("PARTIAL"):
            status_manager.update_status(f"Partial progress (attempt {attempt}).")
            log(f"Partial progress in attempt {attempt}", message_type="thought")
        else:
            status_manager.update_status(f"Implementation failed (attempt {attempt}).", style="red")
            log(f"Implementation failed in attempt {attempt}", message_type="tool_output_error")
            consecutive_failures += 1
            if consecutive_failures >= max_consecutive_failures:
                log("Too many consecutive failures, giving up", message_type="tool_output_error")
                return False

        # Check if we've made no commits recently
        if attempt >= 5 and commits_made == 0:
            log("No commits made in 5 attempts, giving up", message_type="tool_output_error")
            return False

    log(
        f"Implementation incomplete after {max_implementation_attempts} attempts",
        message_type="tool_output_error",
    )
    status_manager.update_status("Implementation incomplete.", style="red")
    return False


def process_task(
    task: str, task_num: int, base_specifier: str, cwd: Optional[str] = None, config: Optional[AgentConfig] = None
) -> bool:
    """Process a single task through planning and implementation."""
    status_manager.update_status(f"Processing task {task_num}: {task}")
    log(f"Processing task {task_num}: {task}", message_type="thought", config=config)

    task_id = f"task_{task_num}"
    state = read_state()

    def current_task_state() -> TaskState:
        return state.get(task_id, TaskState.PLAN.value)

    log(f"Current state for {task_id}: {current_task_state()}", message_type="thought")
    status_manager.update_status(f"Current task state: {current_task_state()}")

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
            status_manager.update_status("Planning phase failed.", style="red")
            state[task_id] = TaskState.ABORT.value
            write_state(state)
            return False
        state[task_id] = TaskState.IMPLEMENT.value
        write_state(state)
    elif current_task_state() == TaskState.IMPLEMENT.value or current_task_state() == TaskState.DONE.value:
        # If already in IMPLEMENT or DONE, try to read the plan from file
        plan_path = os.path.join(cwd, "plan.md") if cwd else "plan.md"
        if os.path.exists(plan_path):
            with open(plan_path, "r") as f:
                plan = f.read()
            log("Resuming from existing plan.md", message_type="thought")
            status_manager.update_status("Resuming from existing plan.")
        else:
            log("No plan.md found for resuming, aborting task.", message_type="tool_output_error")
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
        status_manager.update_status(f"Task {task_num} completed successfully.")
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
