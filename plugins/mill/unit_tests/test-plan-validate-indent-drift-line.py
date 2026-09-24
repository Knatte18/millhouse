"""Unit tests for the ``line`` locator on requirements-quote-indent-drift errors.

Standalone file with hand-written batch text; each fixture puts the target card below a
preamble and an earlier card so the asserted line is neither 1 nor the first fence.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

import _plan_validate  # noqa: E402

SOURCE_TEXT = "alpha\nbeta\n    gamma\n    delta\n"

_PREAMBLE = (
    "# Batch: demo\n"
    "\n"
    "## Cards\n"
    "\n"
    "### Card 1: earlier\n"
    "\n"
    "- **Edits:**\n"
    "  - `src/target.py`\n"
    "- **Requirements:**\n"
    "  - nothing quoted here\n"
    "\n"
    "### Card 2: target\n"
    "\n"
    "- **Edits:**\n"
    "  - `src/target.py`\n"
)


def _run_check(requirements: str) -> tuple[list[dict], list[str]]:
    """Run the drift check on a batch whose card 2 carries ``requirements``; return errors and batch lines."""
    text = _PREAMBLE + "- **Requirements:**\n" + requirements + "- **Commit:** x\n"
    with tempfile.TemporaryDirectory() as tmp:
        project_root = Path(tmp) / "project"
        (project_root / "src").mkdir(parents=True)
        (project_root / "src" / "target.py").write_text(SOURCE_TEXT, encoding="utf-8")
        batch_path = Path(tmp) / "01-demo.md"
        batch_path.write_text(text, encoding="utf-8")
        errors = _plan_validate._check_requirements_quote_indent_drift(
            [batch_path], project_root, None,
        )
    return errors, text.splitlines()


def _fence_open_lines(batch_lines: list[str]) -> list[int]:
    """1-based lines of every opening fence delimiter at or after the target card heading."""
    heading = next(i for i, l in enumerate(batch_lines) if l.startswith("### Card 2"))
    opens: list[int] = []
    in_fence = False
    for index in range(heading, len(batch_lines)):
        if batch_lines[index].lstrip().startswith("```"):
            in_fence = not in_fence
            if in_fence:
                opens.append(index + 1)
    return opens


def _assert_line(error: dict, expected: int) -> None:
    if error["line"] != expected:
        raise AssertionError(f"expected line {expected}, got {error['line']}: {error}")
    if f"(line {expected}" not in error["message"]:
        raise AssertionError(f"message lacks '(line {expected}': {error['message']}")


def test_strip_pass_reports_fence_line() -> None:
    errors, batch_lines = _run_check(
        "  - Quote:\n"
        "  ```\n"
        "    alpha\n"
        "    beta\n"
        "  ```\n"
    )
    opens = _fence_open_lines(batch_lines)
    if len(errors) != 1:
        raise AssertionError(f"expected 1 error, got {errors}")
    _assert_line(errors[0], opens[0])
    print("PASS: test_strip_pass_reports_fence_line")


def test_add_pass_reports_fence_line() -> None:
    errors, batch_lines = _run_check(
        "  - Quote:\n"
        "  ```\n"
        "gamma\n"
        "delta\n"
        "  ```\n"
    )
    opens = _fence_open_lines(batch_lines)
    if len(errors) != 1 or "adding" not in errors[0]["message"]:
        raise AssertionError(f"expected 1 add-pass error, got {errors}")
    _assert_line(errors[0], opens[0])
    print("PASS: test_add_pass_reports_fence_line")


def test_sibling_indent_reports_fence_line() -> None:
    errors, batch_lines = _run_check(
        "  - Old:\n"
        "  ```\n"
        "alpha\n"
        "beta\n"
        "  ```\n"
        "  - New:\n"
        "  ```\n"
        "    brand new\n"
        "  ```\n"
    )
    opens = _fence_open_lines(batch_lines)
    if len(errors) != 1 or "new/replacement code" not in errors[0]["message"]:
        raise AssertionError(f"expected 1 sibling error, got {errors}")
    _assert_line(errors[0], opens[1])
    print("PASS: test_sibling_indent_reports_fence_line")


def test_clean_fence_then_drifting_fence_reports_second_line() -> None:
    errors, batch_lines = _run_check(
        "  - Clean:\n"
        "  ```\n"
        "alpha\n"
        "beta\n"
        "  ```\n"
        "  - Drifting:\n"
        "  ```\n"
        "      gamma\n"
        "      delta\n"
        "  ```\n"
    )
    opens = _fence_open_lines(batch_lines)
    if len(errors) != 1:
        raise AssertionError(f"expected 1 error, got {errors}")
    if errors[0]["line"] == opens[0]:
        raise AssertionError("error reported the clean first fence's line")
    _assert_line(errors[0], opens[1])
    print("PASS: test_clean_fence_then_drifting_fence_reports_second_line")


def main() -> int:
    try:
        test_strip_pass_reports_fence_line()
        test_add_pass_reports_fence_line()
        test_sibling_indent_reports_fence_line()
        test_clean_fence_then_drifting_fence_reports_second_line()
        print("All test-plan-validate-indent-drift-line unit tests passed.")
        return 0
    except AssertionError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
