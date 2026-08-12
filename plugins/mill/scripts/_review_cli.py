"""Shared CLI helpers for the review subsystem.
Today exposes two helpers:
print_error(exc) — formats a ReviewError with an uppercase ERROR: prefix and an optional one-line
hint when the message is from resolve_ref_paths.
Used by millpy-review-discussion.py, millpy-review-plan.py, millpy-review-code.py.
print_error_envelope(review_type, msg) — emits an ERROR-shaped JSON envelope on stdout and a
human-readable error message on stderr."""
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


def print_error_envelope(
    review_type: str, msg: str, *, error_kind: str = "usage", round: int = 0
) -> None:
    """Emit ERROR-shaped JSON envelope on stdout and human-readable error on stderr.

    The envelope mirrors ReviewResult.to_dict()'s key set with zeroed counts and an empty
    findings list, so a consumer that reads either shape sees the same keys.

    Args:
        review_type: One of "discussion", "plan", or "code".
        msg: Error message to include in both stderr and the JSON envelope.
        error_kind: Bucket for the error's origin — "usage" (default) for a
            pre-reviewer failure (bad args, missing config, load failure), or
            "reviewer" for a failure inside the reviewer's own finalize step.
        round: Review round number this error belongs to. Defaults to 0.
    """
    print(f"ERROR: {msg}", file=sys.stderr)
    envelope = {
        "type": review_type,
        "round": round,
        "verdict": "ERROR",
        "blocking_count": 0,
        "nit_count": 0,
        "findings": [],
        "reviews": [
            {
                "scope": "holistic",
                "verdict": "ERROR",
                "error": msg,
                "error_kind": error_kind,
                "findings": [],
            }
        ],
    }
    print(json.dumps(envelope))
