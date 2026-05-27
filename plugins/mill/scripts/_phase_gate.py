"""Phase gate helpers for mill-go.

Provides decision logic for handling edge cases in mill-go's phase transitions,
particularly when working state files (e.g., _mill/status.md) have been removed
by interrupted merge/teardown operations.
"""


def absent_status_halt_message(task: dict | None, slug: str) -> str:
    """Generate a halt message when _mill/status.md is missing.

    Called by mill-go Entry Step 5 when status_path does not exist,
    indicating that mill-merge's cleanup ran but did not complete.
    Converts a wiki task dict into a readable error message.

    Args:
        task: Task dict from wiki _client.get_task, or None if not found.
        slug: Task slug.

    Returns:
        A readable message explaining the state and suggested action.
    """
    if task is None:
        return (
            f"_mill/status.md is absent and {slug} is not in Home.md -- "
            "cannot determine state. Inspect manually."
        )

    status = task.get("status")

    if status in ("ready-to-merge", "pr-pending"):
        return (
            f"_mill/status.md is absent and wiki shows {status} for {slug} -- "
            "mill-merge has likely run cleanup but not completed. Run /mill-merge to resume teardown."
        )

    if status == "done":
        return f"Task {slug} is already merged. Nothing to do."

    return (
        f"_mill/status.md is absent and wiki state is {status} -- "
        "unexpected; inspect manually."
    )
