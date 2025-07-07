import argparse
import json
import os
import re
import sys
import tomllib
from datetime import datetime
from pathlib import Path
from typing import Optional

from .constants import JUDGE_EXTRA_PROMPT, STATE_FILE, TaskState
from .utils import _print_formatted, log, run


def read_state() -> dict:
    if STATE_FILE.exists():
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {}


def write_state(state: dict) -> None:
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def sanitize_branch_name(name: str) -> str:
    """Sanitizes a string to be a valid git branch name."""
    name = name.lower()
    name = re.sub(r"[^a-z0-9/.]+", "-", name)  # Replace invalid characters with a single hyphen
    name = name.strip("-")  # Remove leading/trailing hyphens
    if len(name) > 100:  # Truncate to a reasonable length
        name = name[:100]
    return name


def generate_unique_branch_name(base_name, suggestions: Optional[list[str]] = None, cwd=None):
    """Generates a unique branch name by trying suggestions first, then appending a numerical suffix if necessary."""
    existing_branches_result = run(["git", "branch", "--list"], "Listing existing branches", directory=cwd)
    if not existing_branches_result["success"]:
        log("Failed to list existing branches.", message_type="tool_output_error")
        return None

    existing_branches = [
        line.strip().replace("* ", "") for line in existing_branches_result["stdout"].split("\n") if line.strip()
    ]

    # Try suggested names first
    if suggestions:
        for suggestion in suggestions:
            sanitized_suggestion = sanitize_branch_name(suggestion)
            if sanitized_suggestion and sanitized_suggestion not in existing_branches:
                return sanitized_suggestion

    # Fallback to numerical suffix
    sanitized_base_name = sanitize_branch_name(base_name)
    if not sanitized_base_name:  # Ensure base_name is not empty after sanitization
        sanitized_base_name = "task-branch"  # Default if sanitization results in empty string

    new_branch_name = sanitized_base_name
    counter = 1
    while new_branch_name in existing_branches:
        new_branch_name = f"{sanitized_base_name}-{counter}"
        counter += 1
    return new_branch_name


def has_tracked_diff(cwd=None) -> bool:
    """Checks if there are any tracked changes in the repository."""
    result = run(["git", "status", "--porcelain"], "Checking for tracked changes", directory=cwd)
    if not result["success"]:
        log("Failed to check git status.", message_type="tool_output_error")
        return False
    return bool(result["stdout"].strip())


def resolve_commit_specifier(specifier: str, cwd=None) -> Optional[str]:
    """Resolves a Git commit specifier (branch, tag, SHA, relative) to a full commit SHA."""
    log(f"Resolving commit specifier: {specifier}", message_type="thought")
    command = ["git", "rev-parse", "--verify", specifier]
    result = run(command, f"Resolving {specifier} to commit SHA", directory=cwd)

    if result["success"] and result["stdout"].strip():
        log(f"Resolved {specifier} to {result['stdout'].strip()}", message_type="thought")
        return result["stdout"].strip()
    else:
        log(
            f"Failed to resolve commit specifier: {specifier}. Stderr: {result['stderr']}",
            message_type="tool_output_error",
        )
        return None


def run_gemini(prompt: str, yolo: bool) -> Optional[str]:
    """Run gemini CLI and return the response."""
    command = ["gemini", "-m", "gemini-2.5-flash", *(["--yolo"] if yolo else []), "-p", prompt]

    log(f"Gemini prompt: {prompt}", message_type="thought")
    result = run(command, "Calling Gemini", command_human=command[:-1] + ["<prompt>"])

    if result["success"]:
        response = result["stdout"].strip()
        log(f"Gemini response: {response}", message_type="thought")
        return response
    else:
        log(f"Gemini call failed: {result['stderr']}", message_type="tool_output_error")
        return None


def discover_tasks(prompt_text, cwd=None):
    """Use Gemini to discover tasks from the given prompt."""
    log("Discovering tasks from prompt", message_type="thought")

    # Check if prompt_text is a file path
    if os.path.exists(prompt_text) and os.path.isfile(prompt_text):
        try:
            with open(prompt_text, "r", encoding="utf-8") as f:
                file_content = f.read()
            gemini_prompt = f"Extract distinct independent tasks from this file content: {file_content}. Each task should be a complete, standalone objective - NOT a breakdown or plan. If it's asking for multiple things, list each as a separate task. If it's one thing, return one task. Return as a numbered list."
        except Exception as e:
            log(f"Error reading file {prompt_text}: {e}", message_type="tool_output_error")
            return []
    else:
        gemini_prompt = f"""Analyze this instruction and identify distinct independent tasks: {prompt_text}

If the instruction references external resources (like git commits, files, APIs, etc.) that you need to examine to identify the actual tasks, do the exploration and then identify the tasks.

If it's a simple direct instruction (like 'create a hello world program'), return exactly one task.

If it explicitly mentions multiple separate tasks, list each one.

Return as a numbered list with clear task descriptions."""

    response = run_gemini(gemini_prompt, yolo=True)
    if not response:
        return []

    # Parse tasks from response
    tasks = []
    for line in response.split("\n"):
        line = line.strip()
        if not line:
            continue

        # Look for numbered items or bullet points
        if re.match(r"^(\d+\.|\*|-)", line):
            task_title = re.sub(r"^(\d+\.|\*|-)\s*", "", line).strip()
            if task_title:
                tasks.append(task_title)

    return tasks


def choose_tasks(tasks):
    """Present tasks to user and get their selection."""
    if not tasks:
        log("No tasks discovered.", message_type="thought")
        return []

    _print_formatted("Discovered tasks:")
    for i, task in enumerate(tasks, 1):
        _print_formatted(f"{i}. {task}")

    while True:
        try:
            if len(tasks) == 1:
                selected_input = input("Press Enter to select this task, or 'q' to quit: ").strip()
                if selected_input == "":
                    return [tasks[0]]
            else:
                selected_input = input("Enter task numbers (space/comma separated) or 'q' to quit: ").strip()

            if selected_input.lower() == "q":
                return []

            selected_numbers = re.split(r"[,\s]+", selected_input)
            selected_tasks = []

            for num_str in selected_numbers:
                try:
                    num = int(num_str)
                    if 1 <= num <= len(tasks):
                        selected_tasks.append(tasks[num - 1])
                    else:
                        _print_formatted(f"Task number '{num}' not found. Try again.", message_type="tool_output_error")
                        selected_tasks = []
                        break
                except ValueError:
                    _print_formatted(f"Invalid number '{num_str}'. Try again.", message_type="tool_output_error")
                    selected_tasks = []
                    break

            if selected_tasks:
                return selected_tasks

        except (EOFError, KeyboardInterrupt):
            return []


def setup_task_branch(task, task_num, base: str, cwd=None) -> bool:
    """Set up git branch for task."""
    log(f"Setting up branch for task {task_num}: {task}", message_type="thought")

    # Create and switch to task branch
    base_branch_name = f"task-{task_num}"

    # Get branch name suggestions from Gemini
    branch_prompt = f"Generate 5 short, descriptive, and valid git branch names for the task: '{task}'. The names should be lowercase, use hyphens instead of spaces, and avoid special characters. Example: 'feature/add-login', 'bugfix/fix-auth-flow'. Return as a comma-separated list."
    suggestions_response = run_gemini(branch_prompt, yolo=False)
    suggestions = []
    if suggestions_response:
        suggestions = [s.strip() for s in suggestions_response.split(",") if s.strip()]

    branch_name = generate_unique_branch_name(base_branch_name, suggestions, cwd)
    if not branch_name:
        return False
    result = run(
        ["git", "switch", "-c", branch_name, base],
        f"Creating task branch {branch_name}",
        directory=cwd,
    )

    if not result["success"]:
        log(f"Failed to create branch {branch_name}", message_type="tool_output_error")
        return False

    # Write task metadata
    task_meta = {"number": task_num, "title": task, "timestamp": datetime.now().isoformat()}

    task_meta_path = os.path.join(cwd, ".task-meta") if cwd else ".task-meta"
    with open(task_meta_path, "w") as f:
        json.dump(task_meta, f, indent=2)

    log(f"Created task branch and metadata for task {task_num}", message_type="thought")
    return True


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
            completion_prompt = f"Is the task {repr(task)} now complete based on the work done? Respond with 'COMPLETE' if fully done, or 'CONTINUE' if more work is needed."
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


def main() -> None:
    global QUIET_MODE

    parser = argparse.ArgumentParser(description="Agentic task processing tool")
    parser.add_argument("prompt", help="Task source prompt or file path")
    parser.add_argument("--quiet", action="store_true", help="Suppress informational output")
    parser.add_argument("--cwd", help="Working directory for task execution")

    # Initialize default_base_from_toml before parsing args
    default_base_from_toml = "main"

    parser.add_argument(
        "--base",
        default=default_base_from_toml,
        help="Base branch, commit, or git specifier to switch to before creating a task branch (default: main or from .agent.toml)",
    )
    parser.add_argument(
        "--multi", action="store_true", help="Treat prompt as an instruction to find task, rather than a single task"
    )

    args = parser.parse_args()

    QUIET_MODE = args.quiet

    # Determine effective working directory
    effective_cwd = args.cwd if args.cwd else os.getcwd()
    effective_cwd = os.path.abspath(effective_cwd)

    # Initialize state file if it doesn't exist
    if not STATE_FILE.exists():
        write_state({})

    # Use the effective working directory
    cwd = effective_cwd
    log(f"Using working directory: {cwd}", message_type="thought")

    # Update default_base_from_toml from .agent.toml if it exists in the effective_cwd
    agent_toml_path = Path(effective_cwd) / ".agent.toml"
    if agent_toml_path.exists():
        try:
            with open(agent_toml_path, "rb") as f:
                config = tomllib.load(f)
            if "default-base" in config:
                default_base_from_toml = config["default-base"]
                log(
                    f"Using default-base from .agent.toml: {default_base_from_toml}",
                    message_type="thought",
                )
            if "plan" in config and "judge-extra-prompt" in config["plan"]:
                judge_extra_prompt_from_toml = config["plan"]["judge-extra-prompt"]
                log(
                    f"Using plan.judge-extra-prompt from .agent.toml: {judge_extra_prompt_from_toml}",
                    message_type="thought",
                )
            else:
                judge_extra_prompt_from_toml = ""
        except Exception as e:
            log(f"Error reading or parsing .agent.toml: {e}", message_type="tool_output_error")

    # Re-set the default for --base argument if it was not explicitly provided by the user
    # and a value was found in .agent.toml
    if "base" not in args or args.base == "main":  # Check if --base was not provided or is still default 'main'
        args.base = default_base_from_toml

    global JUDGE_EXTRA_PROMPT
    JUDGE_EXTRA_PROMPT = judge_extra_prompt_from_toml

    log("Starting agentic loop", message_type="thought")

    if args.multi:
        # Find tasks
        log("Treating prompt as an instruction to discover tasks", message_type="thought")
        tasks = discover_tasks(args.prompt, cwd)
        if not tasks:
            log("No tasks discovered", message_type="thought")
            sys.exit(1)
        selected_tasks = choose_tasks(tasks)
        if not selected_tasks:
            log("No tasks selected", message_type="thought")
            sys.exit(0)
    else:
        selected_tasks = [args.prompt]

    # Process each selected task
    for i, task in enumerate(selected_tasks, 1):
        try:
            process_task(task, i, args.base, cwd)
        except Exception as e:
            log(f"Error processing task {i}: {e}", message_type="tool_output_error")

    log("Agentic loop completed")


if __name__ == "__main__":
    main()
