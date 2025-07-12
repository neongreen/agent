from rich.table import Table

from ok.log import console
from ok.utils import TaskResult


def display_task_summary(task_results: list[TaskResult]) -> None:
    """
    Displays a summary of all executed tasks.
    """
    table = Table(title="Task execution summary", title_justify="left")
    table.add_column("Task prompt", style="cyan", no_wrap=False)
    table.add_column("Status", style="magenta")
    table.add_column("Last commit", style="yellow")
    table.add_column("Error", style="red", no_wrap=False)

    for result in task_results:
        table.add_row(result.task, result.status, result.last_commit_hash, result.error or "-")

    console.print(table)
    console.print("\n", end="")
