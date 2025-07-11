"""Handles the planning phase of the agent's execution, including iterative plan generation and review."""

from enum import Enum
from pathlib import Path
from typing import Optional, assert_never

from eliot import log_call

from agent.config import AGENT_SETTINGS as config
from agent.constants import PLAN_FILE
from agent.llm import LLM, check_verdict
from agent.output_formatter import LLMOutputType, print_formatted_message
from agent.ui import status_manager
from agent.utils import format_as_markdown_blockquote, log


@log_call
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
    print_formatted_message(f"Starting planning phase for task: {task}", message_type=LLMOutputType.STATUS)

    max_planning_rounds = 5

    plan: Optional[str] = None
    previous_plan: Optional[str] = None
    previous_review: Optional[str] = None

    for round_num in range(1, max_planning_rounds + 1):
        status_manager.set_phase("Planning", f"{round_num}/{max_planning_rounds}")
        print_formatted_message((f"Planning round {round_num}"), message_type=LLMOutputType.STATUS)

        # Ask Gemini to create/revise plan
        if round_num == 1:
            plan_prompt = (
                f"Create a detailed implementation plan for this task: {repr(task)}. Break it down into specific, actionable steps.\n"
                "You are granted access to tools, commands, and code execution for the *sole purpose* of gaining knowledge.\n"
                "You *may not* use these tools to directly implement the task.\n"
                'Output the text of the plan, and then "This is the end of the plan". You may not output anything after that.'
            ).strip()
        else:
            plan_prompt = (
                f"Revise the following plan for task {repr(task)} based on the feedback provided:\n\n"
                "Previous Plan:\n"
                f"{previous_plan}\n\n"
                "Reviewer Feedback:\n"
                f"{previous_review}\n\n"
                "Create a better implementation plan.\n"
                'Output the text of the plan, and then "This is the end of the plan". You may not output anything after that.'
            ).strip()

        if config.plan.planner_extra_prompt:
            plan_prompt += f"\n\n{config.plan.planner_extra_prompt}"

        status_manager.update_status("Getting a plan")
        raw_plan = llm.run(
            plan_prompt,
            yolo=True,
            cwd=cwd,
            phase="Getting a plan",
            step_number=1,
            attempt_number=round_num,
            response_type=LLMOutputType.PLAN,
        )
        current_plan = format_as_markdown_blockquote(raw_plan) if raw_plan else None
        if not current_plan:
            status_manager.update_status("Failed to get a plan.", style="red")
            print_formatted_message("Failed to get a plan", message_type=LLMOutputType.ERROR)
            return None

        # Ask LLM to review the plan.
        # We want the review text to have something before and after the verdict -
        # otherwise OpenCode likes outputting e.g. "VED" instead of "APPROVED".
        review_prompt = (
            f"Review this plan for task {repr(task)}:\n\n"
            f"{current_plan}\n\n"
            "After you are done, output your review as a single message using this template:\n\n"
            "    I am the plan judge.\n\n"
            "    Feedback: [[your plan feedback]]\n\n"
            "    List of objections to address: [[list of objections to address, or 'None']]\n\n"
            "    Verdict: [[your verdict]], end of plan review.\n\n"
            "Your verdict must be one of the following:\n"
            "- APPROVED APPROVED APPROVED if the plan is good enough to implement (even if minor improvements are possible);\n"
            "- REJECTED REJECTED REJECTED if the plan must be revised.\n"
        )

        if config.plan.judge_extra_prompt:
            review_prompt += f"\n\n{config.plan.judge_extra_prompt}"

        status_manager.update_status("Reviewing plan")

        raw_review = llm.run(
            review_prompt,
            yolo=True,
            cwd=cwd,
            phase="Reviewing plan",
            step_number=1,
            attempt_number=round_num,
            response_type=LLMOutputType.EVALUATION,
        )
        current_review = format_as_markdown_blockquote(raw_review) if raw_review else None
        current_verdict = check_verdict(PlanVerdict, raw_review or "")

        if not current_review:
            status_manager.update_status("Failed to get a plan evaluation.", style="red")
            log("LLM provided no output", message_type=LLMOutputType.ERROR)

        elif not current_verdict:
            status_manager.update_status("Failed to get a plan verdict.", style="red")
            log(
                f"Couldn't determine the verdict from the plan evaluation. Evaluation was:\n\n{current_review}",
                message_type=LLMOutputType.ERROR,
            )

        elif current_verdict == PlanVerdict.APPROVED:
            status_manager.update_status(f"Approved in round {round_num}.")
            print_formatted_message((f"Plan approved in round {round_num}"), message_type=LLMOutputType.STATUS)
            print_formatted_message(current_plan, message_type=LLMOutputType.PLAN)

            plan = current_plan  # This is the approved plan

            # Write the approved plan to a file (not committed)
            PLAN_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(PLAN_FILE, "w") as f:
                f.write(f"# Plan for {task}\n\n{plan}")

            return plan

        elif current_verdict == PlanVerdict.REJECTED:
            status_manager.update_status(f"Plan rejected in round {round_num}.")
            log(f"Plan rejected in round {round_num}", message_type=LLMOutputType.STATUS)
            previous_plan = current_plan  # Store for next round's prompt
            previous_review = current_review  # Store for next round's prompt

        else:
            assert_never(current_verdict)

    log(f"Planning failed after {max_planning_rounds} rounds", message_type=LLMOutputType.ERROR)
    status_manager.update_status("Planning failed.", style="red")
    return None


class PlanVerdict(Enum):
    """
    Enum for verdicts from the plan evaluation judge.
    """

    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
