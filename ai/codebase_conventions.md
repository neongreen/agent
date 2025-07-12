# Codebase Conventions

This document outlines the conventions and patterns used throughout this codebase for various common tasks.

## Command Line Argument Parsing

Command-line arguments are parsed using Pydantic's `CliApp` and `BaseSettings` from `pydantic-settings`.
The `CliSettings` class in `src/ok/config.py` extends `OkSettings` and defines all available CLI arguments.

Positional arguments are handled using `CliPositionalArg`.

The `init_settings()` function in `src/ok/config.py` is responsible for loading settings from CLI and the `.ok.toml` file.

`src/ok/util/pydantic.py` contains customizations for how CLI arguments are parsed.

## Configuration Parsing

Configuration is managed using Pydantic's `BaseSettings` and `pydantic-settings`.\
The `OkSettings` class in `src/ok/config.py` defines the overall structure of the config file.

Settings are loaded with the following priority: CLI args, then the `.ok.toml` file, and finally default values.

The `config.schema.json` file defines the schema for configuration validation.
This schema is generated automatically from the Pydantic models.

## Mock LLM

CLI supports the `--mock` option to use a mock LLM instead of a real one.

Mocking of LLM responses is handled by the `MockLLM` class in `src/ok/llms/mock.py`.\
This class reads predefined prompt-response pairs from `mock_llm_data.toml`.\
Prompts are matched using regular expressions, allowing for flexible mock responses based on the input prompt.

## Logging

Logging in this codebase is handled by the `src/ok/log.py` module, which utilizes the `eliot` library for structured logging.\
Logs are written to JSON files located in `~/.ok/logs/`.\
The `init_logging()` function sets up the logging destination.

The primary function for logging is `log()`, which takes a `message`, `message_type` (an `LLMOutputType` enum member), and optional `message_human` (for console display).
The `message` is logged both to the file and printed to the console.
If `message_human` is provided, it is printed to the console, while `message` is logged in JSON format.

Structured logging is not supported by `log()` yet.

## External LLM Calls

External LLM calls are abstracted through the `LLMBase` class in `src/ok/llms/base.py`.\
Specific LLM providers (e.g., Gemini, Claude) implement this base class.\
The `run()` method in `LLMBase` handles common concerns like logging the prompt and response, and error handling.\
The actual interaction with the LLM API is implemented in the `_run()` abstract method of each specific LLM class.

When making an LLM call, the `run()` method is invoked with the prompt, a `yolo` flag (to bypass safety checks), the current working directory (`cwd`), and metadata like `phase`, `step_number`, `attempt_number`, and `response_type` for logging purposes.

The project does not do API calls directly in the codebase.
It uses CLI tools like `gemini`, `claude`, etc.

## Trio Usage

`trio` is used throughout the codebase for asynchronous programming, providing a framework for structured concurrency.

You'll find `import trio` in modules that perform I/O operations or manage concurrent tasks, such as `src/ok/git_utils.py`, `src/ok/llms/mock.py`, `src/ok/main.py`, `src/ok/task_planning.py`, and `src/ok/utils.py`.

TODO: how do we read files with trio? how do we start subprocesses?

## Utility Functions Placement

General utility functions are typically placed in `src/ok/utils.py`.
This module contains common helper functions that are broadly applicable across different parts of the agent, such as `run()` for executing shell commands asynchronously.

For more specialized utilities, especially those related to a specific third-party library or a particular domain, a dedicated submodule within `src/ok/util/` might be created.\
For example, `src/ok/util/eliot.py` contains utilities for `eliot` logging.

## New LLM Integration

To integrate a new LLM, create a new Python file within the `src/ok/llms/` directory.\
This new LLM class must inherit from `LLMBase` (defined in `src/ok/llms/base.py`) and implement the asynchronous `_run()` method.\
The `_run()` method is responsible for the actual interaction with the LLM API, taking the prompt, `yolo` flag, and current working directory as arguments, and returning the LLM's response as a string or `None` on error.\
The `LLMBase` class handles common logging and error handling around this `_run()` method.

For example, `src/ok/llms/gemini.py` shows how the Gemini LLM is integrated, using the `run()` utility function to execute an external `gemini` command-line tool.

## Agentic Loop Flow and Extension

The agentic loop orchestrates the overall process of task execution, from planning to implementation and verification.\
The core flow is managed across several key modules:

- **`src/ok/main.py`**: This is the primary entry point.\
  It initializes the application, loads configuration, sets up the LLM, and iterates through each task defined in the configuration, delegating the processing of individual tasks to `task_orchestrator.py`.

- **`src/ok/task_orchestrator.py`**: This module manages the lifecycle of a single task.\
  It's responsible for setting up the Git environment (e.g., creating worktrees), resolving base commits, and then initiating the `implementation_phase` for the task.

- **`src/ok/task_planning.py`**: This module handles the iterative planning phase.\
  It's invoked by the `implementation_phase` (specifically, within the `_handle_StartingTask` state).\
  It interacts with the LLM to generate and refine a detailed plan for the task until it's approved.

- **`src/ok/task_implementation.py`**: This module contains the state machine that drives the iterative implementation of a task.\
  It defines various states (e.g., `StartingTask`, `StartingStep`, `JudgingAttempt`, `JudgingStep`, `FinalizingTask`) and transitions between them.\
  It manages attempts to implement parts of the task, evaluates the results, and determines if more iterations are needed or if the task is complete.

**Extending the Agentic Loop:**

To add a new step or modify the flow of the agentic loop, you would primarily interact with the state machine defined in `src/ok/task_implementation.py`.

1. **Define a New State**: If your new step represents a distinct phase in the task implementation, define a new `dataclass` for it, inheriting from an appropriate base state (e.g., `TaskState`, `StepState`, `AttemptState`).

2. **Add to `State` Type**: Include your new state in the `type State` union.

3. **Implement `_handle_YourNewState`**: Create an asynchronous function `_handle_YourNewState(settings: Settings, state: YourNewState) -> NextState` that encapsulates the logic for your new state.\
   This function should perform the necessary actions and return the next state in the flow.

4. **Add Transition in `transition()`**: In the `transition()` function, add a new `case` statement to handle the transition from your new state (or to your new state from an existing one) when a `Tick()` event occurs.

5. **Modify Existing Transitions**: Adjust the `_handle_...` functions of existing states to transition to your new state at the appropriate point in the workflow.\
   For example, if your new step comes after planning, the `_handle_StartingTask` or `_handle_StartingStep` might need to be updated.
