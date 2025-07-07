"""Handles the planning phase of the agent's execution, including iterative plan generation and review."""

from pathlib import Path
from typing import Optional

from .config import AGENT_SETTINGS as config
from .constants import PLAN_FILE
from .llm import LLM
from .output_formatter import LLMOutputType, format_llm_thought, format_reviewer_feedback, print_formatted_message
from .ui import status_manager
from .utils import log


def planning_phase(task: str, *, cwd: Path, llm: LLM) -> Optional[str]:
    """
    Iterative planning phase with Gemini approval.

    Args:
        task: The task description.
        cwd: The current working directory as a Path.

    Returns:
        The approved plan as a string, or None if planning failed.
    """
    status_manager.set_phase("Planning")
    print_formatted_message(
        format_llm_thought(f"Starting planning phase for task: {task}"), message_type=LLMOutputType.THOUGHT
    )

    max_planning_rounds = 5

    plan: Optional[str] = None
    previous_plan: Optional[str] = None
    previous_review: Optional[str] = None

    for round_num in range(1, max_planning_rounds + 1):
        status_manager.set_phase("Planning", f"{round_num}/{max_planning_rounds}")
        print_formatted_message(format_llm_thought(f"Planning round {round_num}"), message_type=LLMOutputType.THOUGHT)

        # Ask Gemini to create/revise plan
        if round_num == 1:
            plan_prompt = (
                f"Create a detailed implementation plan for this task: {repr(task)}. Break it down into specific, actionable steps.\n"
                "You are granted access to tools, commands, and code execution for the *sole purpose* of gaining knowledge.\n"
                "You *may not* use these tools to directly implement the task.\n"
                'Output the text of the plan, and then "PLAN_END" on a new line. You may not output anything after that marker.'
            ).strip()
        else:
            plan_prompt = (
                f"Revise the following plan for task {repr(task)} based on the feedback provided:\n\n"
                "Previous Plan:\n"
                f"{previous_plan}\n\n"
                "Reviewer Feedback:\n"
                f"{previous_review}\n\n"
                "Create a better implementation plan.\n"
                'Output the text of the plan, and then "PLAN_END" on a new line. You may not output anything after that marker.'
            ).strip()

        if config.plan.planner_extra_prompt:
            plan_prompt += f"\n\n{config.plan.planner_extra_prompt}"

        status_manager.update_status("Getting plan from Gemini")
        current_plan = llm.run(plan_prompt, yolo=True, cwd=cwd)
        if not current_plan:
            status_manager.update_status("Failed to get plan from Gemini.", style="red")
            print_formatted_message("Failed to get plan from Gemini", message_type=LLMOutputType.TOOL_OUTPUT_ERROR)
            return None

        # Ask Gemini to review the plan
        review_prompt = (
            f"Review this plan for task {repr(task)}:\n\n"
            f"{current_plan}\n\n"
            "Respond with either 'APPROVED' if the plan is good enough to implement (even if minor improvements are possible), or 'REJECTED' followed by a list of specific blockers that must be addressed."
        )

        if config.plan.judge_extra_prompt:
            review_prompt += f"\n\n{config.plan.judge_extra_prompt}"

        status_manager.update_status("Reviewing plan")
        current_review = llm.run(review_prompt, yolo=True, cwd=cwd)
        if not current_review:
            status_manager.update_status("Failed to get plan review from Gemini.", style="red")
            print_formatted_message(
                "Failed to get plan review from Gemini", message_type=LLMOutputType.TOOL_OUTPUT_ERROR
            )
            return None

        # Jul 2025: Opencode is special and outputs "VED" instead of "APPROVED" sometimes (...often)
        if current_review.upper().startswith("APPROVED") or current_review.upper().startswith("VED"):
            status_manager.update_status(f"Approved in round {round_num}.")
            print_formatted_message(
                format_llm_thought(f"Plan approved in round {round_num}"), message_type=LLMOutputType.THOUGHT
            )
            print_formatted_message(current_plan, message_type=LLMOutputType.PLAN)

            plan = current_plan  # This is the approved plan

            # Write the approved plan to a file (not committed)
            PLAN_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(PLAN_FILE, "w") as f:
                f.write(f"# Plan for {task}\n\n{plan}")

            return plan
        else:
            status_manager.update_status(f"Plan rejected in round {round_num}. Reviewing feedback...")
            print_formatted_message(
                format_reviewer_feedback(f"Plan rejected in round {round_num}: {current_review}"),
                message_type=LLMOutputType.FEEDBACK,
            )
            previous_plan = current_plan  # Store for next round's prompt
            previous_review = current_review  # Store for next round's prompt

    log(f"Planning failed after {max_planning_rounds} rounds", message_type="tool_output_error")
    status_manager.update_status("Planning failed.", style="red")
    return None
