"""Shared CLI helpers for the review subsystem. Today exposes two helpers:
print_error(exc) — formats a ReviewError with an uppercase ERROR: prefix and
an optional one-line hint when the message is from resolve_ref_paths. Used by
millpy-review-discussion.py, millpy-review-plan.py, millpy-review-code.py.
print_error_envelope(review_type, msg) — emits an ERROR-shaped JSON envelope
on stdout and a human-readable error message on stderr."""
import json
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


def print_error_envelope(review_type: str, msg: str) -> None:
    """Emit ERROR-shaped JSON envelope on stdout and human-readable error on stderr.

    Args:
        review_type: One of "discussion", "plan", or "code".
        msg: Error message to include in both stderr and the JSON envelope.
    """
    print(f"ERROR: {msg}", file=sys.stderr)
    envelope = {
        "type": review_type,
        "round": 0,
        "verdict": "ERROR",
        "blocking_count": 0,
        "reviews": [{"scope": "holistic", "verdict": "ERROR", "error": msg}],
    }
    print(json.dumps(envelope))
