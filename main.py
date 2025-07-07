import argparse
import datetime
import json
import os
import re
import subprocess
import sys
from typing import Optional, TypedDict

# Global variables
LOG_FILE = ".agentic-log"
QUIET_MODE = False


def log(message, quiet=None) -> None:
    """Simple logging function that respects quiet mode."""
    if quiet is None:
        quiet = QUIET_MODE

    log_entry = {"timestamp": datetime.datetime.now().isoformat(), "message": message}

    if not quiet:
        print(message)

    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry) + "\n")


class RunResult(TypedDict):
    exit_code: int
    stdout: str
    stderr: str
    success: bool


def run(command: list[str], description=None, directory=None) -> RunResult:
    """Run command and log it."""

    if description:
        log(f"Executing: {description}")

    log(f"Running command: {command}")

    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False, cwd=directory)

        if result.returncode != 0:
            log(f"Command failed with exit code {result.returncode}")
            log(f"Stderr: {result.stderr}")

        log(f"Stdout: {result.stdout}")
        log(f"Stderr: {result.stderr}")

        return {
            "exit_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "success": result.returncode == 0,
        }

    except Exception as e:
        log(f"Error running command: {e}")
        return {"exit_code": -1, "stdout": "", "stderr": str(e), "success": False}


def run_gemini(prompt) -> str | None:
    """Run gemini CLI and return the response."""
    escaped_prompt = prompt.replace('"', '\\"')
    command = ["gemini", "-m", "gemini-2.5-flash", "-y", "-p", f"{escaped_prompt}"]

    log(f"Gemini prompt: {prompt}")

    result = run(command, "Calling Gemini")

    if result["success"]:
        response = result["stdout"].strip()
        log(f"Gemini response: {response}")
        return response
    else:
        log(f"Gemini call failed: {result['stderr']}")
        return None


def discover_tasks(prompt_text, cwd=None):
    """Use Gemini to discover tasks from the given prompt."""
    log("Discovering tasks from prompt")

    # Check if prompt_text is a file path
    if os.path.exists(prompt_text) and os.path.isfile(prompt_text):
        try:
            with open(prompt_text, "r", encoding="utf-8") as f:
                file_content = f.read()
            gemini_prompt = f"Extract distinct independent tasks from this file content: {file_content}. Each task should be a complete, standalone objective - NOT a breakdown or plan. If it's asking for multiple things, list each as a separate task. If it's one thing, return one task. Return as a numbered list."
        except Exception as e:
            log(f"Error reading file {prompt_text}: {e}")
            return []
    else:
        gemini_prompt = f"""Analyze this instruction and identify distinct independent tasks: {prompt_text}

If the instruction references external resources (like git commits, files, APIs, etc.) that you need to examine to identify the actual tasks, do the exploration and then identify the tasks.

If it's a simple direct instruction (like 'create a hello world program'), return exactly one task.

If it explicitly mentions multiple separate tasks, list each one.

Return as a numbered list with clear task descriptions."""

    response = run_gemini(gemini_prompt)
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
        log("No tasks discovered.")
        return []

    print("Discovered tasks:")
    for i, task in enumerate(tasks, 1):
        print(f"{i}. {task}")

    while True:
        try:
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
                        print(f"Task number '{num}' not found. Try again.")
                        selected_tasks = []
                        break
                except ValueError:
                    print(f"Invalid number '{num_str}'. Try again.")
                    selected_tasks = []
                    break

            if selected_tasks:
                return selected_tasks

        except (EOFError, KeyboardInterrupt):
            return []


def setup_task_branch(task, task_num, cwd=None) -> bool:
    """Set up git branch for task."""
    log(f"Setting up branch for task {task_num}: {task}")

    # Switch to main first
    result = run(["git", "switch", "main"], "Switching to main branch", directory=cwd)
    if not result["success"]:
        log("Failed to switch to main branch")
        return False

    # Create and switch to task branch
    branch_name = f"task-{task_num}"
    result = run(["git", "switch", "-c", branch_name], f"Creating task branch {branch_name}", directory=cwd)

    if not result["success"]:
        log(f"Failed to create branch {branch_name}")
        return False

    # Write task metadata
    task_meta = {"number": task_num, "title": task, "timestamp": datetime.datetime.now().isoformat()}

    task_meta_path = os.path.join(cwd, ".task-meta") if cwd else ".task-meta"
    with open(task_meta_path, "w") as f:
        json.dump(task_meta, f, indent=2)

    log(f"Created task branch and metadata for task {task_num}")
    return True


def planning_phase(task: str, cwd=None) -> Optional[str]:
    """Iterative planning phase with Gemini approval."""
    log(f"Starting planning phase for task: {task}")

    max_planning_rounds = 5

    plan: Optional[str] = None

    for round_num in range(1, max_planning_rounds + 1):
        log(f"Planning round {round_num}")

        # Ask Gemini to create/revise plan
        if round_num == 1:
            plan_prompt = f"Create a detailed implementation plan for this task: {task}. Break it down into specific, actionable steps."
        else:
            plan_prompt = f"Revise the plan for task '{task}' addressing the previous feedback. Create a better implementation plan."

        plan = run_gemini(plan_prompt)
        if not plan:
            log("Failed to get plan from Gemini")
            return None

        # Ask Gemini to review the plan
        review_prompt = f"Review this plan for task '{task}':\n\n{plan}\n\nRespond with either 'APPROVED' if the plan is good enough to implement (even if minor improvements are possible), or 'REJECTED' followed by a list of specific blockers that must be addressed."

        review = run_gemini(review_prompt)
        if not review:
            log("Failed to get plan review from Gemini")
            return None

        if review.upper().startswith("APPROVED"):
            log(f"Plan approved in round {round_num}")

            # Commit the approved plan
            plan_path = os.path.join(cwd, "plan.md") if cwd else "plan.md"
            with open(plan_path, "w") as f:
                f.write(f"# Plan for {task}\n\n{plan}")

            # Generate commit message
            commit_msg_prompt = f"Generate a concise commit message (max 15 words) for approving this plan: {task}"
            commit_msg = run_gemini(commit_msg_prompt)
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
            log(f"Plan rejected in round {round_num}: {review}")

    log(f"Planning failed after {max_planning_rounds} rounds")
    return None


def implementation_phase(task, plan, cwd=None) -> bool:
    """Iterative implementation phase with early bailout."""
    log(f"Starting implementation phase for task: {task}")

    max_implementation_attempts = 10
    max_consecutive_failures = 3
    consecutive_failures = 0
    commits_made = 0

    for attempt in range(1, max_implementation_attempts + 1):
        log(f"Implementation attempt {attempt}")

        # Ask Gemini to implement next step
        impl_prompt = f"Based on this plan:\n\n{plan}\n\nImplement the next step for task '{task}'. Provide specific code, commands, or files to create. Be concrete and actionable."

        implementation = run_gemini(impl_prompt)
        if not implementation:
            log("Failed to get implementation from Gemini")
            consecutive_failures += 1
            if consecutive_failures >= max_consecutive_failures:
                log("Too many consecutive failures, giving up")
                return False
            continue

        # Try to execute the implementation
        log(f"Attempting to execute implementation: {implementation}")

        # Evaluate if it seems reasonable
        eval_prompt = f"Evaluate if this implementation makes progress on the task '{task}':\n\n{implementation}\n\nRespond with 'SUCCESS' if it's a good step forward, 'PARTIAL' if it's somewhat helpful, or 'FAILURE' if it's not useful."

        evaluation = run_gemini(eval_prompt)
        if not evaluation:
            log("Failed to get evaluation from Gemini")
            consecutive_failures += 1
            if consecutive_failures >= max_consecutive_failures:
                log("Too many consecutive failures, giving up")
                return False
            continue

        if evaluation.upper().startswith("SUCCESS"):
            log(f"Implementation successful in attempt {attempt}")
            consecutive_failures = 0
            commits_made += 1

            # Generate commit message and commit
            commit_msg_prompt = f"Generate a concise commit message (max 15 words) for this implementation step: {task}"
            commit_msg = run_gemini(commit_msg_prompt)
            if not commit_msg:
                commit_msg = "Implementation step for task"

            run(["git", "add", "."], "Adding implementation files", directory=cwd)
            run(
                ["git", "commit", "-m", f"{commit_msg[:100]}"],
                "Committing implementation",
                directory=cwd,
            )

            # Check if task is complete
            completion_prompt = f"Is the task '{task}' now complete based on the work done? Respond with 'COMPLETE' if fully done, or 'CONTINUE' if more work is needed."
            completion_check = run_gemini(completion_prompt)

            if completion_check and completion_check.upper().startswith("COMPLETE"):
                log("Task marked as complete")
                return True

        elif evaluation.upper().startswith("PARTIAL"):
            log(f"Partial progress in attempt {attempt}")
            consecutive_failures = 0
        else:
            log(f"Implementation failed in attempt {attempt}")
            consecutive_failures += 1
            if consecutive_failures >= max_consecutive_failures:
                log("Too many consecutive failures, giving up")
                return False

        # Check if we've made no commits recently
        if attempt >= 5 and commits_made == 0:
            log("No commits made in 5 attempts, giving up")
            return False

    log(f"Implementation incomplete after {max_implementation_attempts} attempts")
    return False


def process_task(task, task_num, cwd=None):
    """Process a single task through planning and implementation."""
    log(f"Processing task {task_num}: {task}")

    # Set up branch
    if not setup_task_branch(task, task_num, cwd):
        log("Failed to set up task branch")
        return False

    # Planning phase
    plan = planning_phase(task, cwd)
    if not plan:
        log("Planning phase failed")
        return False

    # Implementation phase
    success = implementation_phase(task, plan, cwd)

    if success:
        log(f"Task {task_num} completed successfully")
    else:
        log(f"Task {task_num} failed or incomplete")

    return success


def main() -> None:
    global QUIET_MODE

    parser = argparse.ArgumentParser(description="Agentic task processing tool")
    parser.add_argument("prompt", help="Task source prompt or file path")
    parser.add_argument("--quiet", action="store_true", help="Suppress informational output")
    parser.add_argument("--cwd", help="Working directory for task execution")

    args = parser.parse_args()

    QUIET_MODE = args.quiet

    # Validate working directory
    cwd = args.cwd
    if cwd:
        if not os.path.exists(cwd):
            print(f"Error: Working directory '{cwd}' does not exist")
            sys.exit(1)
        if not os.path.isdir(cwd):
            print(f"Error: '{cwd}' is not a directory")
            sys.exit(1)
        cwd = os.path.abspath(cwd)
        log(f"Using working directory: {cwd}")

    log("Starting agentic loop")

    # Discover tasks
    tasks = discover_tasks(args.prompt, cwd)
    if not tasks:
        log("No tasks discovered")
        sys.exit(1)

    # Let user choose tasks
    selected_tasks = choose_tasks(tasks)
    if not selected_tasks:
        log("No tasks selected")
        sys.exit(0)

    # Process each selected task
    for i, task in enumerate(selected_tasks, 1):
        try:
            process_task(task, i, cwd)
        except Exception as e:
            log(f"Error processing task {i}: {e}")

    log("Agentic loop completed")


if __name__ == "__main__":
    main()
