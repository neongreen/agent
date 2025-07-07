import os
from typing import Optional

from .constants import JUDGE_EXTRA_PROMPT, STATE_FILE, TaskState
from .gemini_agent import run_gemini
from .git_utils import has_tracked_diff, resolve_commit_specifier, setup_task_branch
from .state_manager import read_state, write_state
from .utils import log, run


def planning_phase(task: str, cwd=None) -> Optional[str]:
    """Iterative planning phase with Gemini approval."""
    log(f"Starting planning phase for task: {task}", message_type="thought")

    max_planning_rounds = 5

    plan: Optional[str] = None
    previous_plan: Optional[str] = None
    previous_review: Optional[str] = None

    for round_num in range(1, max_planning_rounds + 1):
        log(f"Planning round {round_num}", message_type="thought")

        # Ask Gemini to create/revise plan
        if round_num == 1:
            plan_prompt = f"""
Create a detailed implementation plan for this task: {repr(task)}. Break it down into specific, actionable steps.
You are granted access to tools, commands, and code execution for the *sole purpose* of gaining knowledge.
You *may not* use these tools to directly implement the task.
Output "PLAN_TEXT_END" after the plan. You may not output anything after that marker.
""".strip()
        else:
            plan_prompt = f"""
Revise the following plan for task {repr(task)} based on the feedback provided:

Previous Plan:
{previous_plan}

Reviewer Feedback:
{previous_review}

Create a better implementation plan.
Output "PLAN_TEXT_END" after the plan. You may not output anything after that marker.
""".strip()

        current_plan = run_gemini(plan_prompt, yolo=True)
        if not current_plan:
            log("Failed to get plan from Gemini", message_type="tool_output_error")
            return None

        # Ask Gemini to review the plan
        review_prompt = f"""Review this plan for task {repr(task)}:

{current_plan}

Respond with either 'APPROVED' if the plan is good enough to implement (even if minor improvements are possible), or 'REJECTED' followed by a list of specific blockers that must be addressed."""

        if JUDGE_EXTRA_PROMPT:
            review_prompt += f"\n\n{JUDGE_EXTRA_PROMPT}"

        current_review = run_gemini(review_prompt, yolo=True)
        if not current_review:
            log("Failed to get plan review from Gemini", message_type="tool_output_error")
            return None

        if current_review.upper().startswith("APPROVED"):
            log(f"Plan approved in round {round_num}", message_type="thought")
            plan = current_plan  # This is the approved plan

            # Commit the approved plan
            plan_path = os.path.join(cwd, "plan.md") if cwd else "plan.md"
            with open(plan_path, "w") as f:
                f.write(f"# Plan for {task}\n\n{plan}")

            # Generate commit message
            commit_msg_prompt = f"Generate a concise commit message (max 15 words) for approving this plan: {task}"
            commit_msg = run_gemini(commit_msg_prompt, yolo=False)
            if not commit_msg:
                commit_msg = "Approved plan for task"

            run(["git", "add", "."], "Adding plan files", directory=cwd)
            run(
                ["git", "commit", "-m", f"[plan.md] {commit_msg[:100]}"],
                "Committing approved plan",
                directory=cwd,
            )

            return plan
        else:
            log(
                f"Plan rejected in round {round_num}: {current_review}",
                message_type="tool_output_error",
            )
            previous_plan = current_plan  # Store for next round's prompt
            previous_review = current_review  # Store for next round's prompt

    log(f"Planning failed after {max_planning_rounds} rounds", message_type="tool_output_error")
    return None


def implementation_phase(task, plan, cwd=None) -> bool:
    """Iterative implementation phase with early bailout."""
    log(f"Starting implementation phase for task: {task}", message_type="thought")

    max_implementation_attempts = 10
    max_consecutive_failures = 3
    consecutive_failures = 0
    commits_made = 0

    for attempt in range(1, max_implementation_attempts + 1):
        log(f"Implementation attempt {attempt}", message_type="thought")

        # Ask Gemini to implement next step
        impl_prompt = f"""
Execution phase. Based on this plan:

{plan}

Implement the next step for task {repr(task)}.
Create files, run commands, and/or write code as needed.
When done, provide a concise summary of what you did.
Your response will help the reviewer of your implementation understand the changes made.
""".strip()

        implementation_summary = run_gemini(impl_prompt, yolo=True)
        if not implementation_summary:
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
        eval_prompt = f"""
Evaluate if this implementation makes progress on the task {repr(task)}.
Respond with 'SUCCESS' if it's a good step forward, 'PARTIAL' if it's somewhat helpful, or 'FAILURE' if it's not useful.
For 'PARTIAL', provide specific feedback on what could be improved or what remains to be done.
For 'FAILURE', list specific reasons why the implementation is inadequate.
Here is the summary of the implementation:

{implementation_summary}

Here is the diff of the changes made:

{run(["git", "diff"], directory=cwd)["stdout"]}
"""

        evaluation = run_gemini(eval_prompt, yolo=True)
        if not evaluation:
            log("Failed to get evaluation from Gemini", message_type="tool_output_error")
            consecutive_failures += 1
            if consecutive_failures >= max_consecutive_failures:
                log("Too many consecutive failures, giving up", message_type="tool_output_error")
                return False
            continue

        if evaluation.upper().startswith("SUCCESS"):
            log(f"Implementation successful in attempt {attempt}", message_type="thought")
            consecutive_failures = 0
            commits_made += 1

            # Generate commit message and commit
            commit_msg_prompt = (
                f"Generate a concise commit message (max 15 words) for this implementation step: {repr(task)}"
            )
            commit_msg = run_gemini(commit_msg_prompt, yolo=False)
            if not commit_msg:
                commit_msg = "Implementation step for task"

            run(["git", "add", "."], "Adding implementation files", directory=cwd)
            run(
                ["git", "commit", "-m", f"{commit_msg[:100]}"],
                "Committing implementation",
                directory=cwd,
            )

            # Check if task is complete
            completion_prompt = f"Is the task {repr(task)} now complete based on the work done? Respond with 'COMPLETE' if fully done, or 'CONTINUE' if more work is needed. You are granted access to tools, commands, and code execution for the *sole purpose* of evaluating whether the task is done. You should also use the tools to inspect git log and diffs of commits to inform your decision. If 'CONTINUE', provide specific next steps to take, or objections to address."
            completion_check = run_gemini(completion_prompt, yolo=True)

            if completion_check and completion_check.upper().startswith("COMPLETE"):
                log("Task marked as complete", message_type="thought")
                return True

        elif evaluation.upper().startswith("PARTIAL"):
            log(f"Partial progress in attempt {attempt}", message_type="thought")
        else:
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
    return False


def process_task(task: str, task_num: int, base_branch: str, cwd: Optional[str] = None) -> bool:
    """Process a single task through planning and implementation."""
    log(f"Processing task {task_num}: {task}", message_type="thought")

    task_id = f"task_{task_num}"
    state = read_state()

    def current_task_state() -> TaskState:
        return state.get(task_id, TaskState.PLAN.value)

    log(f"Current state for {task_id}: {current_task_state()}", message_type="thought")

    # Set up branch
    if current_task_state() == TaskState.PLAN.value:
        # Resolve the base_branch to a commit SHA before setting up the task branch
        resolved_base_commit_sha = resolve_commit_specifier(base_branch, cwd)
        if not resolved_base_commit_sha:
            log(f"Failed to resolve base specifier: {base_branch}", message_type="tool_output_error")
            state[task_id] = TaskState.ABORT.value
            write_state(state)
            return False

        if not setup_task_branch(task, task_num, resolved_base_commit_sha, cwd):
            log("Failed to set up task branch", message_type="tool_output_error")
            state[task_id] = TaskState.ABORT.value
            write_state(state)
            return False
        state[task_id] = TaskState.PLAN.value
        write_state(state)
    # Planning phase
    plan = None
    if current_task_state() == TaskState.PLAN.value:
        plan = planning_phase(task, cwd)
        if not plan:
            log("Planning phase failed")
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
        else:
            log("No plan.md found for resuming, aborting task.", message_type="tool_output_error")
            state[task_id] = TaskState.ABORT.value
            write_state(state)
            return False

    # Implementation phase
    success = False
    if current_task_state() == TaskState.IMPLEMENT.value:
        success = implementation_phase(task, plan, cwd)
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
        except OSError as e:
            log(f"Error removing agent state file: {e}", message_type="tool_output_error")
    else:
        log(f"Task {task_num} failed or incomplete")

    return success
