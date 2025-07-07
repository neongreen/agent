"""Manages the iterative implementation phase of a task, including code generation, execution, and evaluation."""

from pathlib import Path
from typing import Optional

from .config import AGENT_SETTINGS as config
from .constants import PLAN_FILE, LLMOutputType
from .llm import LLM
from .output_formatter import format_tool_code_output, print_formatted_message
from .ui import status_manager
from .utils import log, run


def implementation_phase(
    *,
    task: str,
    plan: str,
    base_commit: str,
    cwd: Path,
    llm: LLM,
) -> dict:
    """
    Manages the iterative implementation phase of a task.

    This function guides the agent through generating code, executing commands,
    and evaluating the results, with a mechanism for early bailout if progress
    stalls.

    Args:
        task: The description of the task being implemented.
        plan: The implementation plan generated in the planning phase.
        base_commit: The Git commit SHA to base the implementation branch on.
        cwd: The current working directory for task execution as a Path.

    Returns:
        A dictionary containing the status of the implementation and any feedback.
    """
    status_manager.set_phase("Implementation")
    print_formatted_message(f"Starting implementation phase for task: {task}", message_type=LLMOutputType.THOUGHT)

    max_implementation_attempts = 10
    max_consecutive_failures = 3
    consecutive_failures = 0
    commits_made = 0

    # Feedback from evaluating the previous implementation attempt done by the loop
    feedback: Optional[str] = None

    for attempt in range(1, max_implementation_attempts + 1):
        status_manager.set_phase("Implementation", f"{attempt}/{max_implementation_attempts}")
        print_formatted_message(f"Implementation attempt {attempt}", message_type=LLMOutputType.THOUGHT)

        # Ask Gemini to implement next step
        impl_prompt = (
            f"Execution phase. You are implementing this task: {repr(task)}. This is your attempt #{attempt} out of {max_implementation_attempts}.\n\n"
            "Based on this plan:\n\n"
            f"{plan}\n\n"
            f"{f'And the feedback about your previous attempt:\n\n{feedback}\n\n' if feedback else ''}"
            f"Implement the next step for task {repr(task)}.\n"
            "Create files, run commands, and/or write code as needed.\n"
            "When done, output 'IMPLEMENTATION_SUMMARY_START' and then a concise summary of what you did.\n"
            "Your response will help the reviewer of your implementation understand the changes made.\n"
            "Finish your response with 'IMPLEMENTATION_SUMMARY_END'.\n"
        )

        if config.implement.extra_prompt:
            impl_prompt += f"\n\n{config.implement.extra_prompt}"

        status_manager.update_status("Getting implementation from Gemini")
        implementation_summary = llm.run(impl_prompt, yolo=True, cwd=cwd)

        if not implementation_summary:
            status_manager.update_status("Failed to get implementation from Gemini.", style="red")
            try:
                raise Exception("Failed to get implementation from Gemini")
            except Exception as e:
                print_formatted_message(
                    f"Error during implementation: {e}", message_type=LLMOutputType.TOOL_OUTPUT_ERROR
                )
            consecutive_failures += 1
            if consecutive_failures >= max_consecutive_failures:
                log("Too many consecutive failures, giving up", message_type="tool_output_error")
                return {
                    "status": "failed",
                    "feedback": "Too many consecutive failures to get implementation from Gemini",
                }
            continue

        if config.post_implementation_hook_command:
            log(f"Running post-implementation hook: {config.post_implementation_hook_command}", message_type="thought")
            run(
                config.post_implementation_hook_command,
                "Running post-implementation hook command",
                directory=cwd,
                shell=True,
            )

        # Evaluate if it seems reasonable
        log(
            f"Judging the implementation based on the diff. LLM provided this explanation along with its implementation:\n{implementation_summary}",
            message_type="thought",
        )
        eval_prompt = (
            f"Evaluate if this implementation makes progress on the task {repr(task)}.\n"
            "Respond with 'SUCCESS' if it's a good step forward, 'PARTIAL' if it's somewhat helpful, or 'FAILURE' if it's not useful.\n"
            "For 'PARTIAL', provide specific feedback on what could be improved or what remains to be done.\n"
            "For 'FAILURE', list specific reasons why the implementation is inadequate.\n"
            "The implementation is either in the uncommitted changes, in the previous commits, or both.\n"
            "Here is the summary of the implementation:\n\n"
            f"{implementation_summary}\n\n"
            "Here are the uncommitted changes:\n\n"
            f"{format_tool_code_output(run(['git', 'diff', '--', f':!{PLAN_FILE}'], directory=cwd))}\n\n"
            "Here is the diff of the changes made in previous commits:\n\n"
            f"{format_tool_code_output(run(['git', 'diff', base_commit + '..HEAD', '--', f':!{PLAN_FILE}'], directory=cwd))}"
        )

        if config.implement.judge_extra_prompt:
            eval_prompt += f"\n\n{config.implement.judge_extra_prompt}"

        status_manager.update_status("Evaluating implementation")
        evaluation = llm.run(eval_prompt, yolo=True, cwd=cwd)
        if not evaluation:
            status_manager.update_status("Failed to get evaluation from Gemini.", style="red")
            log("Failed to get evaluation from Gemini", message_type="tool_output_error")
            consecutive_failures += 1
            if consecutive_failures >= max_consecutive_failures:
                log("Too many consecutive failures, giving up", message_type="tool_output_error")
                return {"status": "failed", "feedback": "Too many consecutive failures to get evaluation from Gemini"}
            continue

        feedback = evaluation  # Store feedback for next iteration

        if evaluation.upper().startswith("SUCCESS"):
            status_manager.update_status(f"Successful (attempt {attempt}).")
            log(f"Implementation successful in attempt {attempt}", message_type="thought")
            consecutive_failures = 0
            commits_made += 1

            # Generate commit message and commit
            status_manager.update_status("Generating commit message")
            commit_msg_prompt = (
                f"Generate a concise commit message (max 15 words) for this implementation step: {repr(task)}.\n"
                "You *may not* output Markdown, code blocks, or any other formatting.\n"
                "You may only output a single line.\n"
            )
            commit_msg = llm.run(commit_msg_prompt, yolo=False, cwd=cwd)
            if not commit_msg:
                commit_msg = "Implementation step for task"

            status_manager.update_status("Committing implementation")
            run(["git", "add", "."], "Adding implementation files", directory=cwd)
            run(
                ["git", "commit", "-m", f"{commit_msg[:100]}"],
                "Committing implementation",
                directory=cwd,
            )

            # Check if task is complete
            status_manager.update_status("Checking if task is complete...")
            completion_prompt = (
                f"Is the task {repr(task)} now complete based on the work done?\n"
                "You are granted access to tools, commands, and code execution for the *sole purpose* of evaluating whether the task is done.\n"
                "You may not finish your response at 'I have to check ...' or 'I have to inspect files ...' - you must use your tools to check directly.\n"
                "Respond with 'COMPLETE' if fully done, or 'CONTINUE' if more work is needed.\n"
                "If 'CONTINUE', provide specific next steps to take, or objections to address.\n"
                "Here are the uncommitted changes:\n\n"
                f"{format_tool_code_output(run(['git', 'diff', '--', f':!{PLAN_FILE}'], directory=cwd))}\n\n"
                "Here is the diff of the changes made in previous commits:\n\n"
                f"{format_tool_code_output(run(['git', 'diff', base_commit + '..HEAD', '--', f':!{PLAN_FILE}'], directory=cwd))}"
            )

            if config.implement.completion.judge_extra_prompt:
                completion_prompt += f"\n\n{config.implement.completion.judge_extra_prompt}"

            completion_check = llm.run(completion_prompt, yolo=True, cwd=cwd)

            if completion_check and completion_check.upper().startswith("COMPLETE"):
                status_manager.update_status("Task marked as complete.")
                log("Task marked as complete", message_type="thought")
                return {"status": "completed", "feedback": completion_check}

        elif evaluation.upper().startswith("PARTIAL"):
            status_manager.update_status(f"Partial progress (attempt {attempt}).")
            log(f"Partial progress in attempt {attempt}", message_type="thought")
        else:
            status_manager.update_status(f"Failed (attempt {attempt}).", style="red")
            log(f"Implementation failed in attempt {attempt}", message_type="tool_output_error")
            consecutive_failures += 1
            if consecutive_failures >= max_consecutive_failures:
                log("Too many consecutive failures, giving up", message_type="tool_output_error")
                return {"status": "failed", "feedback": "Too many consecutive failures in implementation"}

        # Check if we've made no commits recently
        if attempt >= 5 and commits_made == 0:
            log("No commits made in 5 attempts, giving up", message_type="tool_output_error")
            return {"status": "failed", "feedback": "No commits made in 5 attempts"}

    log(
        f"Implementation incomplete after {max_implementation_attempts} attempts",
        message_type="tool_output_error",
    )
    status_manager.update_status("Incomplete.", style="red")
    return {"status": "incomplete", "feedback": "Implementation incomplete after maximum attempts"}
