"""Unit tests for _plan_validate._check_cross_batch_build_break.

Kept as its own standalone file rather than appended to test-plan-validate.py
(584KB) -- see 00-overview.md's "cross-batch-build-break test lives in its own
new file" Shared Decision. Uses minimal local fixtures, not any import from the
existing giant test file.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

import _plan_validate  # noqa: E402


def _write_overview(
    plan_dir: Path,
    batches: list[dict],
    *,
    overview_verify: str | None,
) -> Path:
    """
    Write a minimal 00-overview.md with a frontmatter `verify:` field and a Batch Index.

    Each `batches` dict: {name, file, depends-on (list of batch-name strings)}.
    `overview_verify`: rendered into the frontmatter's own top-level `verify:` field --
        ``None`` renders as the literal ``verify: null``, gating the check off;
        a string renders verbatim, gating the check on.
    """
    entries = []
    for b in batches:
        deps = b["depends-on"]
        deps_yaml = "[" + ", ".join(f'"{d}"' for d in deps) + "]"
        entries.append(
            f"  - name: {b['name']}\n"
            f"    file: {b['file']}\n"
            f"    depends-on: {deps_yaml}"
        )
    batch_list = "\n".join(entries)
    frontmatter_verify = "null" if overview_verify is None else overview_verify
    text = (
        "# Overview\n\n"
        "```yaml\n"
        "task: test\nslug: test-slug\nroot: \"\"\n"
        f"verify: {frontmatter_verify}\n"
        "```\n\n"
        "## Batch Index\n\n"
        "```yaml\n"
        f"batches:\n{batch_list}\n"
        "```\n"
    )
    plan_dir.mkdir(parents=True, exist_ok=True)
    overview_path = plan_dir / "00-overview.md"
    overview_path.write_text(text, encoding="utf-8")
    return overview_path


def _write_batch_file(
    plan_dir: Path,
    filename: str,
    requirements: str,
    *,
    depends_on: list[str] | None = None,
) -> None:
    """
    Write a minimal batch file: a single ``### Card 1:`` heading and a Requirements: field.

    `_check_cross_batch_build_break` reads only the Requirements: field via
    `_parse_cards`/`_extract_requirements_text` and the Batch Index via
    `extract_batch_index` -- no Context:/Edits:/Creates:/Deletes:/Moves:/Commit: fields
    are needed for this check's own logic, though real plan files always have them.

    `depends_on`, when given, prepends a minimal frontmatter `depends-on:` block matching
    this repo's `depends-on-batch-mismatch` convention that a batch's own frontmatter and the
    overview Batch Index entry must agree (card 14, scenario 2).
    """
    plan_dir.mkdir(parents=True, exist_ok=True)
    text = f"### Card 1: t\n\n- **Requirements:**\n  {requirements}\n"
    if depends_on is not None:
        deps_yaml = "[" + ", ".join(f'"{d}"' for d in depends_on) + "]"
        text = f"```yaml\ndepends-on: {deps_yaml}\n```\n\n{text}"
    (plan_dir / filename).write_text(text, encoding="utf-8")


def test_fires_on_stale_cross_batch_reference() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        plan_dir = Path(tmp)
        overview_path = _write_overview(
            plan_dir,
            [
                {"name": "alpha", "file": "01-alpha.md", "depends-on": []},
                {"name": "beta", "file": "02-beta.md", "depends-on": []},
            ],
            overview_verify="pytest",
        )
        _write_batch_file(
            plan_dir, "01-alpha.md",
            "Rename `Engine.HeaderText` to `Engine.StatusLineText`.",
        )
        _write_batch_file(
            plan_dir, "02-beta.md",
            "Update the caller that still reads `Engine.HeaderText`.",
        )
        overview_text = overview_path.read_text(encoding="utf-8")
        batch_files = [plan_dir / "01-alpha.md", plan_dir / "02-beta.md"]
        errors = _plan_validate._check_cross_batch_build_break(
            batch_files, overview_path, overview_text,
        )
        if len(errors) != 1:
            raise AssertionError(f"expected exactly one error, got: {errors}")
        error = errors[0]
        if error["check"] != "cross-batch-build-break":
            raise AssertionError(f"wrong check key: {error}")
        if error["batch"] != "beta":
            raise AssertionError(f"wrong batch: {error}")
        if error["path"] != "Engine.HeaderText":
            raise AssertionError(f"wrong path: {error}")
    print("PASS: test_fires_on_stale_cross_batch_reference")


def test_does_not_fire_with_depends_on_edge() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        plan_dir = Path(tmp)
        overview_path = _write_overview(
            plan_dir,
            [
                {"name": "alpha", "file": "01-alpha.md", "depends-on": []},
                {"name": "beta", "file": "02-beta.md", "depends-on": ["alpha"]},
            ],
            overview_verify="pytest",
        )
        _write_batch_file(
            plan_dir, "01-alpha.md",
            "Rename `Engine.HeaderText` to `Engine.StatusLineText`.",
        )
        _write_batch_file(
            plan_dir, "02-beta.md",
            "Update the caller that still reads `Engine.HeaderText`.",
            depends_on=["alpha"],
        )
        overview_text = overview_path.read_text(encoding="utf-8")
        batch_files = [plan_dir / "01-alpha.md", plan_dir / "02-beta.md"]
        errors = _plan_validate._check_cross_batch_build_break(
            batch_files, overview_path, overview_text,
        )
        if errors:
            raise AssertionError(f"expected no errors, got: {errors}")
    print("PASS: test_does_not_fire_with_depends_on_edge")


def test_skipped_when_overview_verify_is_null() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        plan_dir = Path(tmp)
        overview_path = _write_overview(
            plan_dir,
            [
                {"name": "alpha", "file": "01-alpha.md", "depends-on": []},
                {"name": "beta", "file": "02-beta.md", "depends-on": []},
            ],
            overview_verify=None,
        )
        _write_batch_file(
            plan_dir, "01-alpha.md",
            "Rename `Engine.HeaderText` to `Engine.StatusLineText`.",
        )
        _write_batch_file(
            plan_dir, "02-beta.md",
            "Update the caller that still reads `Engine.HeaderText`.",
        )
        overview_text = overview_path.read_text(encoding="utf-8")
        batch_files = [plan_dir / "01-alpha.md", plan_dir / "02-beta.md"]
        errors = _plan_validate._check_cross_batch_build_break(
            batch_files, overview_path, overview_text,
        )
        if errors:
            raise AssertionError(f"expected no errors, got: {errors}")
    print("PASS: test_skipped_when_overview_verify_is_null")


def test_file_deletion_prose_does_not_false_positive() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        plan_dir = Path(tmp)
        overview_path = _write_overview(
            plan_dir,
            [
                {"name": "alpha", "file": "01-alpha.md", "depends-on": []},
                {"name": "beta", "file": "02-beta.md", "depends-on": []},
            ],
            overview_verify="pytest",
        )
        _write_batch_file(
            plan_dir, "01-alpha.md",
            "Remove `plugins/mill/scripts/old_helper.py`.",
        )
        _write_batch_file(
            plan_dir, "02-beta.md",
            "Replaces `plugins/mill/scripts/old_helper.py` with the new module.",
        )
        overview_text = overview_path.read_text(encoding="utf-8")
        batch_files = [plan_dir / "01-alpha.md", plan_dir / "02-beta.md"]
        errors = _plan_validate._check_cross_batch_build_break(
            batch_files, overview_path, overview_text,
        )
        if errors:
            raise AssertionError(f"expected no errors, got: {errors}")
    print("PASS: test_file_deletion_prose_does_not_false_positive")


def main() -> int:
    tests = [
        test_fires_on_stale_cross_batch_reference,
        test_does_not_fire_with_depends_on_edge,
        test_skipped_when_overview_verify_is_null,
        test_file_deletion_prose_does_not_false_positive,
    ]
    failed = 0
    for test in tests:
        try:
            test()
        except AssertionError as exc:
            print(f"FAIL: {test.__name__}: {exc}", file=sys.stderr)
            failed += 1
    if failed:
        print(f"{failed} of {len(tests)} tests failed.", file=sys.stderr)
        return 1
    print("All test-plan-validate-cross-batch-build-break unit tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
