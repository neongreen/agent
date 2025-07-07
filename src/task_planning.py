from typing import Optional

from .config import AgentConfig
from .constants import PLAN_FILE
from .gemini_agent import run_gemini
from .ui import status_manager
from .utils import log


def planning_phase(task: str, cwd=None, config: Optional[AgentConfig] = None) -> Optional[str]:
    """Iterative planning phase with Gemini approval."""
    status_manager.set_phase("Planning")
    log(f"Starting planning phase for task: {task}", message_type="thought", config=config)

    max_planning_rounds = 5

    plan: Optional[str] = None
    previous_plan: Optional[str] = None
    previous_review: Optional[str] = None

    for round_num in range(1, max_planning_rounds + 1):
        status_manager.set_phase("Planning", f"{round_num}/{max_planning_rounds}")
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

        status_manager.update_status("Getting plan from Gemini")
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

        status_manager.update_status("Reviewing plan")
        current_review = run_gemini(review_prompt, yolo=True)
        if not current_review:
            status_manager.update_status("Failed to get plan review from Gemini.", style="red")
            log("Failed to get plan review from Gemini", message_type="tool_output_error")
            return None

        if current_review.upper().startswith("APPROVED"):
            status_manager.update_status(f"Approved in round {round_num}.")
            log(f"Plan approved in round {round_num}", message_type="thought")
            plan = current_plan  # This is the approved plan

            # Write the approved plan to a file (not committed)
            PLAN_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(PLAN_FILE, "w") as f:
                f.write(f"# Plan for {task}\n\n{plan}")

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
