"""Unit tests for _plan_validate.compute_next_card_number.

Kept as its own standalone file rather than appended to test-plan-validate.py
(323KB) -- see 00-overview.md's "new standalone test file" Shared Decision.
Uses minimal local fixtures, not any import from the existing giant test file.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

from _plan_validate import (  # noqa: E402
    PlanDAGError,
    _check_card_numbering,
    compute_next_card_number,
)


def _write_batch_file(plan_dir: Path, filename: str, card_nums: list[int]) -> None:
    """
    Write a minimal batch file containing only ``### Card N:`` heading lines.

    This minimal shape is sufficient for compute_next_card_number's own logic,
    since it delegates to _parse_cards, which only requires the heading line
    per card (confirmed by reading its `^###\\s+Card\\s+(\\d+)\\s*:` regex).
    """
    plan_dir.mkdir(parents=True, exist_ok=True)
    text = "".join(f"### Card {n}: t\n" for n in card_nums)
    (plan_dir / filename).write_text(text, encoding="utf-8")


def test_compute_next_card_number_simple() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        plan_dir = Path(tmp)
        _write_batch_file(plan_dir, "01-alpha.md", [1, 2, 3])
        result = compute_next_card_number(plan_dir, "01-alpha")
        if result != 4:
            raise AssertionError(f"expected 4, got {result}")
    print("PASS: test_compute_next_card_number_simple")


def test_compute_next_card_number_empty_batch() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        plan_dir = Path(tmp)
        _write_batch_file(plan_dir, "01-alpha.md", [])
        result = compute_next_card_number(plan_dir, "01-alpha")
        if result != 1:
            raise AssertionError(f"expected 1, got {result}")
    print("PASS: test_compute_next_card_number_empty_batch")


def test_compute_next_card_number_collision_raises() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        plan_dir = Path(tmp)
        _write_batch_file(plan_dir, "01-alpha.md", [1, 2, 3])
        _write_batch_file(plan_dir, "02-beta.md", [4, 5])
        try:
            compute_next_card_number(plan_dir, "01-alpha")
        except PlanDAGError as exc:
            message = str(exc)
            if "01-alpha" not in message or "02-beta" not in message:
                raise AssertionError(
                    f"expected message to name both batches, got: {message}"
                ) from exc
        else:
            raise AssertionError("expected PlanDAGError to be raised")
    print("PASS: test_compute_next_card_number_collision_raises")


def test_compute_next_card_number_unknown_batch_raises() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        plan_dir = Path(tmp)
        _write_batch_file(plan_dir, "01-alpha.md", [1, 2, 3])
        try:
            compute_next_card_number(plan_dir, "99-nonexistent")
        except PlanDAGError:
            pass
        else:
            raise AssertionError("expected PlanDAGError to be raised")
    print("PASS: test_compute_next_card_number_unknown_batch_raises")


def _numbering_errors(files: dict[str, list[int]]) -> list[dict]:
    with tempfile.TemporaryDirectory() as tmp:
        plan_dir = Path(tmp)
        for filename, nums in files.items():
            _write_batch_file(plan_dir, filename, nums)
        paths = [plan_dir / filename for filename in sorted(files)]
        return _check_card_numbering(paths)


def test_card_numbering_starts_above_one_flagged() -> None:
    errors = _numbering_errors({"01-a.md": [2, 3]})
    if len(errors) != 1 or errors[0]["card"] != 1:
        raise AssertionError(f"expected one card-1 error, got {errors}")
    if "starts at 2, not 1" not in errors[0]["message"]:
        raise AssertionError(f"minimum not named: {errors[0]['message']}")
    print("PASS: test_card_numbering_starts_above_one_flagged")


def test_card_numbering_starts_at_one_clean() -> None:
    errors = _numbering_errors({"01-a.md": [1, 2]})
    if errors:
        raise AssertionError(f"expected no errors, got {errors}")
    print("PASS: test_card_numbering_starts_at_one_clean")


def test_card_numbering_two_batches_clean() -> None:
    errors = _numbering_errors({"01-a.md": [1, 2], "02-b.md": [3, 4]})
    if errors:
        raise AssertionError(f"expected no errors, got {errors}")
    print("PASS: test_card_numbering_two_batches_clean")


def test_card_numbering_minimum_in_later_batch_named() -> None:
    errors = _numbering_errors({"01-a.md": [3, 4], "02-b.md": [2]})
    starts = [e for e in errors if "starts at" in e["message"]]
    if len(starts) != 1 or starts[0]["batch"] != "02-b":
        raise AssertionError(f"expected error naming 02-b, got {errors}")
    print("PASS: test_card_numbering_minimum_in_later_batch_named")


def test_card_numbering_empty_plan_clean() -> None:
    errors = _numbering_errors({"01-a.md": [], "02-b.md": []})
    if errors:
        raise AssertionError(f"expected no errors, got {errors}")
    print("PASS: test_card_numbering_empty_plan_clean")


def main() -> int:
    try:
        test_card_numbering_starts_above_one_flagged()
        test_card_numbering_starts_at_one_clean()
        test_card_numbering_two_batches_clean()
        test_card_numbering_minimum_in_later_batch_named()
        test_card_numbering_empty_plan_clean()
        test_compute_next_card_number_simple()
        test_compute_next_card_number_empty_batch()
        test_compute_next_card_number_collision_raises()
        test_compute_next_card_number_unknown_batch_raises()
        print("All test-plan-validate-card-numbering unit tests passed.")
        return 0
    except AssertionError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
