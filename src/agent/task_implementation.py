"""Manages the iterative step phase of a task, including code generation, execution, and evaluation."""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Literal, Optional, assert_never

from .config import AGENT_SETTINGS as config
from .constants import PLAN_FILE
from .llm import LLM, check_verdict
from .output_formatter import LLMOutputType, print_formatted_message
from .ui import status_manager
from .utils import format_tool_code_output, log, run


class StepVerdict(Enum):
    """Enum for possible verdicts from the step judge."""

    SUCCESS = "SUCCESS"
    """Work done here is a good step forward."""
    PARTIAL = "PARTIAL"
    """Keep work done in this step so far, but it needs more iteration."""
    FAILURE = "FAILURE"
    """Work done in this step is not useful and should be discarded."""


class TaskVerdict(Enum):
    """Enum for possible verdicts from the task completion judge."""

    COMPLETE = "COMPLETE"
    """Task is fully completed."""
    CONTINUE = "CONTINUE"
    """More work is needed."""


# States

# Solving a task
# - consists of multiple steps
#   - and each step consists of multiple attempts


@dataclass(frozen=True, slots=True)
class TaskState:
    """Base class for all states."""

    steps_made: int
    """How many steps were made since the start of working on this task"""

    consecutive_failed_steps: int
    """How many failing attempts we have made in a row"""


@dataclass(frozen=True, slots=True)
class StepState(TaskState):
    """Base class for all states happening while working on a step."""

    attempt: int
    """The current attempt number inside the step - how many times we've tried to finish it."""
    consecutive_failed_attempts: int
    """The number of consecutive failures (not success/partial) in the current step."""
    feedback: Optional[str]
    """Judge's feedback from the previous attempt"""


@dataclass(frozen=True, slots=True)
class ReadyForWork:
    """
    Represents the initial state where the agent is ready to start working on a task.
    """


@dataclass(frozen=True, slots=True)
class Attempt(StepState):
    """Represents the state where the agent is actively working on a attempt."""


# ────────────────────────────── Evaluate state ──────────────────────────────
@dataclass(frozen=True, slots=True)
class Evaluate(StepState):
    """
    Represents the state where the agent reviews the just‑generated step and decides on a verdict.
    """

    step_summary: str
    """Natural‑language summary of the work done in the current attempt"""


# ───────────────────── ReviewCompletion state ─────────────────────
@dataclass(frozen=True, slots=True)
class ReviewCompletion(StepState):
    """
    After a successful step, commit the changes and ask whether the overall task is finished.
    """


@dataclass(frozen=True, slots=True)
class Complete:
    """
    Represents the state where the task step is complete.
    """

    status: Optional[str] = None
    """A message indicating the completion status."""
    attempt: int = 0
    """The iteration number at which the step was completed."""


@dataclass(frozen=True, slots=True)
class Failed:
    """
    Represents the state where the task step has failed.
    """

    status: Optional[str] = None
    """A message indicating the failure status."""
    attempt: int = 0
    """The iteration number at which the step failed."""


type State = ReadyForWork | Attempt | Evaluate | ReviewCompletion | Complete | Failed

# Events


@dataclass(frozen=True, slots=True)
class Tick:
    """Keep going."""


type Event = Tick


@dataclass(frozen=True, slots=True)
class Settings:
    task: str
    plan: str
    base_attempt: str
    cwd: Path
    llm: LLM
    max_step_attempts: int = 10
    max_consecutive_failures: int = 3


def transition(
    state: State,
    event: Event,
    settings: Settings,
) -> State:
    """
    single‑step transition for the task‑execution state‑machine

    all long‑running side‑effects (llm calls, git commands, etc.) are executed
    inside the relevant branches, so the caller only needs to keep feeding
    events until a terminal state (`Complete` or `Failed`) is reached
    """
    log(
        f"Entering transition with state: {state.__class__.__name__}, event: {event.__class__.__name__}",
        message_type=LLMOutputType.DEBUG,
    )
    match state, event:
        # ────────────────────────────── terminal states ──────────────────────────────
        case Complete(), _:
            return _handle_complete_state(state, settings)

        case Failed(), _:
            return _handle_failed_state(state, settings)

        # ─────────────────────────────── bootstrapping ───────────────────────────────
        case ReadyForWork(), Tick():
            return _handle_ready_for_work_state()

        # ─────────────────────────────── main work loop ──────────────────────────────
        case Attempt(
            attempt=attempt,
            consecutive_failed_attempts=consecutive_failed_attempts,
            consecutive_failed_steps=consecutive_failed_steps,
            steps_made=steps_made,
            feedback=feedback,
        ), Tick():
            return _handle_attempt_state(
                attempt,
                consecutive_failed_attempts,
                consecutive_failed_steps,
                steps_made,
                feedback,
                settings,
            )

        # ────────────────────────────── evaluation loop ──────────────────────────────
        case Evaluate(
            attempt=attempt,
            consecutive_failed_attempts=consecutive_failed_attempts,
            consecutive_failed_steps=consecutive_failed_steps,
            steps_made=steps_made,
            feedback=feedback,
            step_summary=step_summary,
        ), Tick():
            return _handle_evaluate_state(
                attempt,
                consecutive_failed_attempts,
                consecutive_failed_steps,
                steps_made,
                feedback,
                step_summary,
                settings,
            )

        # ─────────────────── completion‑review loop ───────────────────
        case ReviewCompletion(
            attempt=attempt,
            consecutive_failed_attempts=consecutive_failed_attempts,
            consecutive_failed_steps=consecutive_failed_steps,
            steps_made=steps_made,
            feedback=feedback,
        ), Tick():
            return _handle_review_completion_state(
                attempt,
                consecutive_failed_attempts,
                consecutive_failed_steps,
                steps_made,
                feedback,
                settings,
            )

        # ────────────────────────────── fallback guard ───────────────────────────────
        case _, _:
            log(
                f"Unhandled transition from {state} with event {event}",
                message_type=LLMOutputType.ERROR,
            )
            return state


def _get_step_summary(settings: Settings, attempt: int, feedback: Optional[str]) -> Optional[str]:
    """
    Generate the implementation prompt for a single attempt, invoke the LLM,
    and return its natural‑language summary of work done.

    The LLM must start its reply with 'My summary of the step:' and finish with
    'This is the end of the attempt summary'.  Return `None` when the model
    fails to produce a response.
    """
    impl_prompt = (
        f"Execution phase. You are implementing this task: {repr(settings.task)}. This is your attempt #{attempt} out of {settings.max_step_attempts}.\n"
        "\n"
        "Based on this plan:\n"
        "\n"
        f"{settings.plan}\n"
        "\n"
        f"{f'And the feedback about your previous attempt:\n\n{feedback}\n\n' if feedback else ''}"
        f"Implement the next step for task {repr(settings.task)}.\n"
        "Create files, run commands, and/or write code as needed.\n"
        "When done, output a concise summary of what you did, starting with 'My summary of the step:'.\n"
        "Your response will help the reviewer of your step understand the changes made.\n"
        "Finish your response with 'This is the end of the attempt summary'.\n"
    )

    if config.implement.extra_prompt:
        impl_prompt += f"""\n\n{config.implement.extra_prompt}"""

    status_manager.update_status("Getting step")
    return settings.llm.run(impl_prompt, yolo=True, cwd=settings.cwd, response_type=LLMOutputType.LLM_RESPONSE)


def _get_and_process_step_summary(settings: Settings, attempt: int, feedback: Optional[str]) -> Optional[str]:
    """
    Call `_get_step_summary`, run the optional post‑implementation hook, and
    handle status/logging.  Returns the step summary or `None` on failure.
    """
    step_summary = _get_step_summary(settings, attempt, feedback)
    if not step_summary:
        status_manager.update_status("Failed to get step.", style="red")
        log("Failed to get step", message_type=LLMOutputType.ERROR)
        return None

    if hasattr(config, "post_implementation_hook_command") and config.post_implementation_hook_command:
        run(
            config.post_implementation_hook_command,
            "Running post-step hook command",
            directory=settings.cwd,
            shell=True,
        )
    return step_summary


def _evaluate_step(settings: Settings, step_summary: Optional[str]) -> tuple[Optional[StepVerdict], Optional[str]]:
    eval_prompt = (
        f"Evaluate if this step makes progress on the task {repr(settings.task)}.\n"
        "The first line of your response must be:\n"
        "  - SUCCESS SUCCESS SUCCESS if it's a good step forward;\n"
        "  - PARTIAL PARTIAL PARTIAL if it's somewhat helpful;\n"
        "  - FAILURE FAILURE FAILURE if it's not useful.\n"
        "For the 'success' verdict, provide a brief comment on the step.\n"
        "For the 'partial' verdict, provide specific feedback on what could be improved or what remains to be done.\n"
        "For the 'failure' verdict, list specific reasons why the step is inadequate.\n"
        "The step is either in the uncommitted changes, in the previous attempts, or both.\n"
        "Here is the summary of the step:\n\n"
        f"{step_summary}\n\n"
        "Here are the uncommitted changes:\n\n"
        f"{format_tool_code_output(run(['git', 'diff', '--', f':!{PLAN_FILE}'], directory=settings.cwd), 'diff')}\n\n"
        "Here is the diff of the changes made in previous attempts:\n\n"
        f"{format_tool_code_output(run(['git', 'diff', settings.base_attempt + '..HEAD', '--', f':!{PLAN_FILE}'], directory=settings.cwd), 'diff')}\n\n"
        "To remind you: you *must* output the *final* verdict in the first line of your response.\n"
        "If you need to do any checks, do them before outputting the verdict.\n"
    )

    if config.implement.judge_extra_prompt:
        eval_prompt += f"\n\n{config.implement.judge_extra_prompt}"

    status_manager.update_status("Evaluating step")
    evaluation = settings.llm.run(eval_prompt, yolo=True, cwd=settings.cwd, response_type=LLMOutputType.EVALUATION)
    verdict = check_verdict(StepVerdict, evaluation or "")
    return verdict, evaluation


@dataclass(frozen=True)
class StepPhaseResult:
    status: TaskVerdict | Literal["failed"]
    feedback: Optional[str] = None
    attempt: int = 0


def _generate_commit_message(settings: Settings) -> str:
    """Generate and return a concise, single‑line commit message for the current step."""
    status_manager.update_status("Generating commit message")
    commit_msg_prompt = (
        f"Generate a concise commit message (max 15 words) for this step: {repr(settings.task)}.\n"
        "You *may not* output Markdown, code blocks, or any other formatting.\n"
        "You may only output a single line.\n"
    )
    commit_msg = settings.llm.run(
        commit_msg_prompt,
        yolo=False,
        cwd=settings.cwd,
        response_type=LLMOutputType.LLM_RESPONSE,
    )
    if not commit_msg:
        commit_msg = "Step for task"
    return commit_msg


def _commit_step(settings: Settings, commit_msg: str) -> None:
    """Stage and commit the changes for this step."""
    status_manager.update_status("Committing step")
    run(["git", "add", "."], "Adding files", directory=settings.cwd)
    run(
        ["git", "commit", "-m", f"{commit_msg[:100]}"],
        "Committing step",
        directory=settings.cwd,
    )


def _evaluate_task_completion(settings: Settings) -> tuple[Optional[TaskVerdict], Optional[str]]:
    """Ask the LLM whether the overall task is finished after this step."""
    status_manager.update_status("Checking if task is complete...")
    completion_prompt = (
        f"Is the task {repr(settings.task)} now complete based on the work done?\n"
        "You are granted access to tools, commands, and code execution for the *sole purpose* of evaluating whether the task is done.\n"
        "You may not finish your response at 'I have to check ...' or 'I have to inspect files ...' - you must use your tools to check directly.\n"
        "The first line of your response must be:\n"
        "  - COMPLETE COMPLETE COMPLETE if the task is fully done;\n"
        "  - CONTINUE CONTINUE CONTINUE if more work is needed.\n"
        "If 'continue', provide specific next steps to take, or objections to address.\n"
        "Here are the uncommitted changes:\n\n"
        f"{format_tool_code_output(run(['git', 'diff', '--', f':!{PLAN_FILE}'], directory=settings.cwd), 'diff')}\n\n"
        "Here is the diff of the changes made in previous attempts:\n\n"
        f"{format_tool_code_output(run(['git', 'diff', settings.base_attempt + '..HEAD', '--', f':!{PLAN_FILE}'], directory=settings.cwd), 'diff')}\n\n"
        "To remind you: you *must* output the *final* verdict in the first line of your response.\n"
        "If you need to do any checks, do them before outputting the verdict.\n"
    )

    if config.implement.completion.judge_extra_prompt:
        completion_prompt += f"\n\n{config.implement.completion.judge_extra_prompt}"

    completion_evaluation = settings.llm.run(
        completion_prompt,
        yolo=True,
        cwd=settings.cwd,
        response_type=LLMOutputType.EVALUATION,
    )
    completion_verdict = check_verdict(TaskVerdict, completion_evaluation or "")
    return completion_verdict, completion_evaluation


def _handle_successful_step(settings: Settings, attempt: int, steps_made: int) -> StepPhaseResult:
    # 1. generate commit message and commit the step
    commit_msg = _generate_commit_message(settings)
    _commit_step(settings, commit_msg)

    # 2. ask the LLM whether the task is done
    completion_verdict, completion_evaluation = _evaluate_task_completion(settings)

    # 3. interpret the verdict and produce a StepPhaseResult
    if not completion_evaluation:
        status_manager.update_status("Failed to get a task completion evaluation.", style="red")
        log("LLM provided no output", message_type=LLMOutputType.ERROR)
        return StepPhaseResult(
            status="failed",
            feedback="Failed to get a task completion evaluation",
        )

    elif not completion_verdict:
        status_manager.update_status("Failed to get a task completion verdict.", style="red")
        log(
            f"Couldn't determine the verdict from the task completion evaluation. Evaluation was:\n\n{completion_evaluation}",
            message_type=LLMOutputType.ERROR,
        )
        return StepPhaseResult(
            status="failed",
            feedback="Couldn't determine the verdict from the task completion evaluation",
        )

    match completion_verdict:
        case TaskVerdict.COMPLETE:
            status_manager.update_status("Task marked as complete.")
            log("Task marked as complete", message_type=LLMOutputType.STATUS)
            return StepPhaseResult(
                status=TaskVerdict.COMPLETE,
                feedback=completion_evaluation,
                attempt=attempt,
            )

        case TaskVerdict.CONTINUE:
            status_manager.update_status("Task not complete, continuing step.")
            log("Task not complete, continuing step", message_type=LLMOutputType.STATUS)
            return StepPhaseResult(
                status=TaskVerdict.CONTINUE,
                feedback=completion_evaluation,
                attempt=attempt,
            )

        case other:
            assert_never(other)


@dataclass(frozen=True)
class ImplementationPhaseResult:
    """
    Result of the implementation phase.
    Contains the status, feedback, and attempt number.
    """

    status: Literal["complete", "failed", "interrupted"]
    feedback: Optional[str] = None
    attempt: int = 0


def implementation_phase(
    *,
    task: str,
    plan: str,
    base_attempt: str,
    cwd: Path,
    llm: LLM,
) -> ImplementationPhaseResult:
    """
    high‑level driver that repeatedly feeds events into the state‑machine
    until a terminal state is reached
    """
    status_manager.set_phase("Step")
    print_formatted_message(
        f"Starting step phase for task: {task}",
        message_type=LLMOutputType.STATUS,
    )

    state: State = ReadyForWork()
    settings = Settings(
        task=task,
        plan=plan,
        base_attempt=base_attempt,
        cwd=cwd,
        llm=llm,
    )

    try:
        # kick‑off
        log(f"debug: transition {state} with Tick event", message_type=LLMOutputType.DEBUG)
        state = transition(state, Tick(), settings)

        # main loop: keep working while we're in `Attempt`, `Evaluate`, or `ReviewCompletion`
        while isinstance(state, (Attempt, Evaluate, ReviewCompletion)):
            log(f"debug: transition {state} with Tick event", message_type=LLMOutputType.DEBUG)
            state = transition(state, Tick(), settings)

        log(f"debug: final state {state}", message_type=LLMOutputType.DEBUG)

    except KeyboardInterrupt:
        log(
            "Step interrupted by user (KeyboardInterrupt)",
            message_type=LLMOutputType.ERROR,
        )
        status_manager.update_status("Interrupted by user.", style="red")
        return ImplementationPhaseResult(
            status="interrupted",
            feedback="Step interrupted by user",
        )

    # collapse terminal states into a uniform result
    if isinstance(state, Complete):
        return ImplementationPhaseResult(
            status="complete",
            feedback=state.status,
            attempt=state.attempt,
        )
    elif isinstance(state, Failed):
        return ImplementationPhaseResult(
            status="failed",
            feedback=state.status,
            attempt=state.attempt,
        )
    elif isinstance(state, ReadyForWork):
        log("Step phase ended without any attempts made", message_type=LLMOutputType.ERROR)
        return ImplementationPhaseResult(
            status="failed",
            feedback="No attempts made in step phase",
            attempt=0,
        )
    else:
        assert_never(state)


# ────────────────────────────── Transitions ──────────────────────────────


def _handle_review_completion_state(
    state: ReviewCompletion,
    settings: Settings,
) -> Complete | Attempt:
    completion_result = _handle_successful_step(settings, attempt, steps_made)

    match completion_result.status:
        case TaskVerdict.COMPLETE:
            return Complete(status=completion_result.feedback, attempt=attempt)
        case TaskVerdict.CONTINUE:
            return Attempt(
                attempt=attempt + 1,
                consecutive_failed_steps=0,
                consecutive_failed_attempts=0,
                steps_made=steps_made + 1,
                feedback=completion_result.feedback,
            )
        case "failed":
            log("Failed to evaluate task completion", message_type=LLMOutputType.ERROR)
            return Attempt(
                attempt=attempt + 1,
                consecutive_failed_steps=consecutive_failed_steps + 1,
                consecutive_failed_attempts=consecutive_failed_attempts + 1,
                steps_made=steps_made,
                feedback="Failed to evaluate task completion",
            )
        case other:
            assert_never(other)


def _handle_evaluate_state(
    attempt: int,
    consecutive_failed_attempts: int,
    consecutive_failed_steps: int,
    steps_made: int,
    feedback: Optional[str],
    step_summary: str,
    settings: Settings,
) -> State:
    # 2️⃣  judge the step ---------------------------------------------------------
    verdict, evaluation = _evaluate_step(settings, step_summary)
    log(f"debug: step verdict {verdict}", message_type=LLMOutputType.DEBUG)
    if not verdict:
        consecutive_failed_attempts += 1
        if consecutive_failed_attempts >= settings.max_consecutive_failures:
            return Failed(
                status="Too many consecutive failures to evaluate step",
                attempt=attempt,
            )
        return Attempt(
            attempt=attempt + 1,
            consecutive_failed_steps=consecutive_failed_steps,
            consecutive_failed_attempts=consecutive_failed_attempts,
            steps_made=steps_made,
            feedback=evaluation or "Failed to evaluate step",
        )

    # 3️⃣  branch on verdict ------------------------------------------------------
    match verdict:
        case StepVerdict.SUCCESS:
            # hand over to the completion‑review state
            return ReviewCompletion(
                attempt=attempt,
                consecutive_failed_steps=consecutive_failed_steps,
                consecutive_failed_attempts=consecutive_failed_attempts,
                steps_made=steps_made,
                feedback=evaluation,
            )

        case StepVerdict.PARTIAL:
            return Attempt(
                attempt=attempt + 1,
                consecutive_failed_steps=consecutive_failed_steps,
                consecutive_failed_attempts=consecutive_failed_attempts,
                steps_made=steps_made,
                feedback=evaluation,
            )

        case StepVerdict.FAILURE:
            consecutive_failed_attempts += 1
            if consecutive_failed_attempts >= settings.max_consecutive_failures:
                return Failed(
                    status="Too many consecutive failures in step",
                    attempt=attempt,
                )
            return Attempt(
                attempt=attempt + 1,
                consecutive_failed_steps=consecutive_failed_steps + 1,
                consecutive_failed_attempts=consecutive_failed_attempts,
                steps_made=steps_made,
                feedback=evaluation,
            )

        case other:
            assert_never(other)


def _handle_attempt_state(
    attempt: int,
    consecutive_failed_attempts: int,
    consecutive_failed_steps: int,
    steps_made: int,
    feedback: Optional[str],
    settings: Settings,
) -> State:
    # hard stop if we've run out of attempts
    if attempt > settings.max_step_attempts:
        return Failed(
            status=f"Exceeded maximum step attempts ({attempt})",
            attempt=attempt,
        )

    # 1️⃣  generate a step summary ------------------------------------------------
    step_summary = _get_and_process_step_summary(settings, attempt, feedback)
    if not step_summary:
        consecutive_failed_attempts += 1
        if consecutive_failed_attempts >= settings.max_consecutive_failures:
            return Failed(
                status=f"Too many consecutive failures ({consecutive_failed_attempts}) to generate attempt summary",
                attempt=attempt,
            )
        return Attempt(
            attempt=attempt + 1,
            consecutive_failed_steps=consecutive_failed_steps,
            consecutive_failed_attempts=consecutive_failed_attempts,
            steps_made=steps_made,
            feedback=feedback,
        )

    # after generating a valid step summary, hand over to the Evaluate state
    return Evaluate(
        attempt=attempt,
        consecutive_failed_steps=consecutive_failed_steps,
        consecutive_failed_attempts=consecutive_failed_attempts,
        steps_made=steps_made,
        feedback=feedback,
        step_summary=step_summary,
    )


def _handle_ready_for_work_state() -> State:
    return Attempt(
        attempt=1,
        consecutive_failed_steps=0,
        consecutive_failed_attempts=0,
        steps_made=0,
        feedback=None,
    )


def _handle_failed_state(state: Failed, settings: Settings) -> State:
    _perform_final_cleanup(settings.cwd)
    return state


def _handle_complete_state(state: Complete, settings: Settings) -> State:
    log("Transitioning from Complete state.", message_type=LLMOutputType.DEBUG)
    _perform_final_cleanup(settings.cwd)
    return state


def _perform_final_cleanup(cwd: Path):
    try:
        diff = run(["git", "diff", "--quiet"], "Checking for uncommitted changes", directory=cwd)
        if not diff["success"]:
            run(["git", "add", "."], "Adding remaining files before final attempt", directory=cwd)
            run(
                ["git", "attempt", "-m", "Final attempt (auto)"],
                "Final attempt after step phase",
                directory=cwd,
            )
    except Exception as e:
        log(f"Failed to make final attempt: {e}", message_type=LLMOutputType.TOOL_ERROR)
