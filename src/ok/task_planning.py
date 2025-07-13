"""Handles the planning phase of the agent's execution, including iterative plan generation and review."""

from enum import StrEnum, auto
from pathlib import Path
from typing import Optional, assert_never

import trio

from ok.constants import PLAN_FILE
from ok.env import Env
from ok.llm import check_verdict
from ok.llms.base import LLMBase
from ok.log import LLMOutputType, format_as_markdown_blockquote
from ok.ui import set_phase, update_status
from ok.util.eliot import log_call


@log_call(include_args=["task", "cwd"])
async def planning_phase(
    env: Env,
    task: str,
    *,
    cwd: Path,
    llm: LLMBase,
    previous_plan: Optional[str] = None,
    previous_review: Optional[str] = None,
) -> Optional[str]:
    """
    Iterative planning phase with Gemini approval.

    Args:
        task: The task description.
        cwd: The current working directory as a Path.

    Returns:
        The approved plan as a string, or None if planning failed.
    """
    set_phase("Planning")
    env.log(f"Starting planning phase for task: {task}", message_type=LLMOutputType.STATUS)

    max_planning_rounds = 5

    plan: Optional[str] = None
    # Use arguments if provided
    prev_plan = previous_plan
    prev_review = previous_review

    for round_num in range(1, max_planning_rounds + 1):
        set_phase("Planning", f"{round_num}/{max_planning_rounds}")
        env.log((f"Planning round {round_num}"), message_type=LLMOutputType.STATUS)

        # Ask Gemini to create/revise plan
        if round_num == 1 and not (prev_plan and prev_review):
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
                f"{prev_plan}\n\n"
                "Reviewer Feedback:\n"
                f"{prev_review}\n\n"
                "Create a better implementation plan.\n"
                'Output the text of the plan, and then "This is the end of the plan". You may not output anything after that.'
            ).strip()

        if env.config.plan.planner_extra_prompt:
            plan_prompt += f"\n\n{env.config.plan.planner_extra_prompt}"

        update_status("Getting a plan")
        raw_plan = await llm.run(
            env,
            plan_prompt,
            yolo=True,
            cwd=cwd,
            response_type=LLMOutputType.PLAN,
        )
        current_plan = format_as_markdown_blockquote(raw_plan) if raw_plan else None
        if not current_plan:
            update_status("Failed to get a plan.", style="red")
            env.log("Failed to get a plan", message_type=LLMOutputType.ERROR)
            return None

        # Ask Gemini to review the plan
        review_prompt = (
            f"Review this plan for task {repr(task)}:\n\n"
            f"{current_plan}\n\n"
            "After you are done, output your review as a single message using this template:\n\n"
            "    I am the plan judge.\n\n"
            "    Feedback: [[your plan feedback]]\n\n"
            "    List of objections to address: [[list of objections to address, or 'None']]\n\n"
            "    Verdict: [[your verdict]], end of plan review.\n\n"
            "Your verdict must be one of the following:\n"
            "  - APPROVED APPROVED APPROVED if the plan is good enough to implement (even if minor improvements are possible);\n"
            "  - REJECTED REJECTED REJECTED if the plan must be revised.\n"
        )

        if env.config.plan.judge_extra_prompt:
            review_prompt += f"\n\n{env.config.plan.judge_extra_prompt}"

        update_status("Reviewing plan")

        raw_review = await llm.run(
            env,
            review_prompt,
            yolo=True,
            cwd=cwd,
            response_type=LLMOutputType.EVALUATION,
        )
        current_review = format_as_markdown_blockquote(raw_review) if raw_review else None
        current_verdict = check_verdict(PlanVerdict, raw_review or "")

        if not current_review:
            update_status("Failed to get a plan evaluation.", style="red")
            env.log("LLM provided no output", message_type=LLMOutputType.ERROR)

        elif not current_verdict:
            update_status("Failed to get a plan verdict.", style="red")
            env.log(
                f"Couldn't determine the verdict from the plan evaluation. Evaluation was:\n\n{current_review}",
                message_type=LLMOutputType.ERROR,
            )

        elif current_verdict == PlanVerdict.APPROVED:
            update_status(f"Approved in round {round_num}.")
            env.log((f"Plan approved in round {round_num}"), message_type=LLMOutputType.STATUS)
            env.log(current_plan, message_type=LLMOutputType.PLAN)

            plan = current_plan  # This is the approved plan

            # Write the approved plan to a file (not committed)
            PLAN_FILE.parent.mkdir(parents=True, exist_ok=True)
            async with await trio.open_file(PLAN_FILE, "w") as file:
                await file.write(f"# Plan for {task}\n\n{plan}")

            return plan

        elif current_verdict == PlanVerdict.REJECTED:
            update_status(f"Plan rejected in round {round_num}.")
            env.log(f"Plan rejected in round {round_num}", message_type=LLMOutputType.STATUS)
            prev_plan = current_plan  # Store for next round's prompt
            prev_review = current_review  # Store for next round's prompt

        else:
            assert_never(current_verdict)

    env.log(f"Planning failed after {max_planning_rounds} rounds", message_type=LLMOutputType.ERROR)
    update_status("Planning failed.", style="red")
    return None


class PlanVerdict(StrEnum):
    """
    Enum for verdicts from the plan evaluation judge.
    """

    APPROVED = auto()
    REJECTED = auto()
