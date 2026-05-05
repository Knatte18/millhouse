"""Shared CLI helpers for the review subsystem. Today exposes one helper:
print_error(exc) — formats a ReviewError with an uppercase ERROR: prefix and
an optional one-line hint when the message is from resolve_ref_paths. Used by
millpy-review-discussion.py, millpy-review-plan.py, millpy-review-code.py."""
import sys

from _review_common import ReviewError


def print_error(exc: ReviewError) -> None:
    print(f"ERROR: {exc}", file=sys.stderr)
    if str(exc).startswith("[resolve_ref_paths]"):
        print(
            "Hint: check the plan card referencing this file; if the file is"
            " intentionally deleted, list it under Deletes: in that card.",
            file=sys.stderr,
        )
