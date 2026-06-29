"""Unit tests for millpy-validate-plan.py CLI main().

Tests invoke main() in-process via importlib, patching helpers that require
real git/wiki state. Four test paths: clean/dirty fixture, --skip-check single,
and --skip-check multiple. find_active_slug is patched via return_value which
accepts the new (git_root, wiki_path, cfg) signature without assertion changes.
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest.mock
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

_VALIDATE_PLAN_PATH = HUB / "plugins" / "mill" / "scripts" / "millpy-validate-plan.py"

_spec = importlib.util.spec_from_file_location("millpy_validate_plan", str(_VALIDATE_PLAN_PATH))
_vp_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_vp_mod)


# ---------------------------------------------------------------------------
# Fixture helpers (same style as test-plan-validate.py)
# ---------------------------------------------------------------------------

def _make_overview(batches: list[dict]) -> str:
    entries = []
    for b in batches:
        deps = b.get("depends-on", [])
        deps_yaml = "[" + ", ".join(f'"{d}"' for d in deps) + "]"
        entries.append(
            f"  - name: {b['name']}\n"
            f"    file: {b['file']}\n"
            f"    depends-on: {deps_yaml}\n"
            f"    verify: null"
        )
    batch_list = "\n".join(entries)
    return (
        "# Overview\n\n"
        "```yaml\n"
        'task: test\nslug: test-slug\nroot: ""\n'
        "```\n\n"
        "## Batch Index\n\n"
        "```yaml\n"
        f"batches:\n{batch_list}\n"
        "```\n"
    )


def _make_batch_file(name: str, *, missing_fields: set | None = None) -> str:
    missing_fields = missing_fields or set()
    parts = [
        f"# Batch: {name}\n\n",
        "```yaml\n",
        f"task: test\nbatch: {name}\ncards: 1\nverify: null\ndepends-on: []\n",
        "```\n\n",
        "## Cards\n\n",
        "### Card 1: card 1\n\n",
    ]
    if "Context" not in missing_fields:
        parts.append("- **Context:** none\n")
    if "Edits" not in missing_fields:
        parts.append("- **Edits:** none\n")
    if "Creates" not in missing_fields:
        parts.append("- **Creates:** none\n")
    if "Deletes" not in missing_fields:
        parts.append("- **Deletes:** none\n")
    if "Moves" not in missing_fields:
        parts.append("- **Moves:** none\n")
    if "Requirements" not in missing_fields:
        parts.append("- **Requirements:**\n  See scope.\n")
    if "Commit" not in missing_fields:
        parts.append(f"- **Commit:** feat({name}): card 1\n")
    return "".join(parts)


def _write_plan(plan_dir: Path, overview_text: str, batches: list) -> None:
    plan_dir.mkdir(parents=True, exist_ok=True)
    (plan_dir / "00-overview.md").write_text(overview_text, encoding="utf-8")
    for filename, content in batches:
        (plan_dir / filename).write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_cli_clean_exits_zero_no_findings() -> int:
    """Clean fixture: main() exits 0 and JSON envelope has no errors."""
    with tempfile.TemporaryDirectory() as tmpdir:
        fixture_root = Path(tmpdir)
        plan_dir = fixture_root / "plan"
        wiki_dir = fixture_root / "wiki"
        wiki_dir.mkdir()

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file("alpha")
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        slug = "test-slug"
        cfg = {"paths": {"plan_dir": "plan"}}
        captured = io.StringIO()

        orig = os.getcwd()
        os.chdir(str(fixture_root))
        try:
            with unittest.mock.patch("_paths.resolve_git_root", return_value=fixture_root), \
                 unittest.mock.patch("_paths.resolve_wiki_path", return_value=wiki_dir), \
                 unittest.mock.patch("_review_common.load_config", return_value=cfg), \
                 unittest.mock.patch("_review_common.find_active_slug", return_value=slug), \
                 unittest.mock.patch("_review_common.resolve_path", return_value=plan_dir), \
                 contextlib.redirect_stdout(captured):
                rc = _vp_mod.main()
        finally:
            os.chdir(orig)

        try:
            assert rc == 0, f"expected exit 0, got {rc}"
            output = captured.getvalue().strip()
            data = json.loads(output)
            assert data["errors"] == [], f"expected no errors, got {data['errors']}"
            assert data["summary"] == "no findings", f"unexpected summary: {data['summary']!r}"
            print("PASS test_cli_clean_exits_zero_no_findings")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_cli_clean_exits_zero_no_findings: {exc}", file=sys.stderr)
            return 1


def test_cli_dirty_exits_one_card_missing_field() -> int:
    """Dirty fixture (card missing Context): main() exits 1 and JSON contains card-missing-field."""
    with tempfile.TemporaryDirectory() as tmpdir:
        fixture_root = Path(tmpdir)
        plan_dir = fixture_root / "plan"
        wiki_dir = fixture_root / "wiki"
        wiki_dir.mkdir()

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file("alpha", missing_fields={"Context"})
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        slug = "test-slug"
        cfg = {"paths": {"plan_dir": "plan"}}
        captured = io.StringIO()

        orig = os.getcwd()
        os.chdir(str(fixture_root))
        try:
            with unittest.mock.patch("_paths.resolve_git_root", return_value=fixture_root), \
                 unittest.mock.patch("_paths.resolve_wiki_path", return_value=wiki_dir), \
                 unittest.mock.patch("_review_common.load_config", return_value=cfg), \
                 unittest.mock.patch("_review_common.find_active_slug", return_value=slug), \
                 unittest.mock.patch("_review_common.resolve_path", return_value=plan_dir), \
                 contextlib.redirect_stdout(captured):
                rc = _vp_mod.main()
        finally:
            os.chdir(orig)

        try:
            assert rc == 1, f"expected exit 1, got {rc}"
            output = captured.getvalue().strip()
            data = json.loads(output)
            error_checks = [e["check"] for e in data["errors"]]
            assert "card-missing-field" in error_checks, (
                f"expected card-missing-field in {error_checks}"
            )
            print("PASS test_cli_dirty_exits_one_card_missing_field")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_cli_dirty_exits_one_card_missing_field: {exc}", file=sys.stderr)
            return 1


def test_cli_skip_check_suppresses_target_check() -> int:
    """--skip-check wiki-config-mutation: exit 0, no errors despite mill-config.yaml in Edits:."""
    with tempfile.TemporaryDirectory() as tmpdir:
        fixture_root = Path(tmpdir)
        plan_dir = fixture_root / "plan"
        wiki_dir = fixture_root / "wiki"
        wiki_dir.mkdir()
        (fixture_root / "mill-config.yaml").write_text("", encoding="utf-8")

        batch_text = (
            "# Batch: alpha\n\n"
            "```yaml\n"
            "task: test\nbatch: alpha\ncards: 1\nverify: null\ndepends-on: []\n"
            "```\n\n"
            "## Cards\n\n"
            "### Card 1: card 1\n\n"
            "- **Context:** none\n"
            "- **Edits:** `mill-config.yaml`\n"
            "- **Creates:** none\n"
            "- **Deletes:** none\n"
            "- **Moves:** none\n"
            "- **Requirements:**\n  See scope.\n"
            "- **Commit:** feat(alpha): card 1\n"
        )
        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        _write_plan(plan_dir, overview, [("01-alpha.md", batch_text)])

        slug = "test-slug"
        cfg = {"paths": {"plan_dir": "plan"}}
        captured = io.StringIO()

        orig = os.getcwd()
        os.chdir(str(fixture_root))
        try:
            with unittest.mock.patch("_paths.resolve_git_root", return_value=fixture_root), \
                 unittest.mock.patch("_paths.resolve_wiki_path", return_value=wiki_dir), \
                 unittest.mock.patch("_review_common.load_config", return_value=cfg), \
                 unittest.mock.patch("_review_common.find_active_slug", return_value=slug), \
                 unittest.mock.patch("_review_common.resolve_path", return_value=plan_dir), \
                 contextlib.redirect_stdout(captured):
                rc = _vp_mod.main(["--skip-check", "wiki-config-mutation"])
        finally:
            os.chdir(orig)

        try:
            assert rc == 0, f"expected exit 0, got {rc}"
            output = captured.getvalue().strip()
            data = json.loads(output)
            assert data["errors"] == [], f"expected no errors, got {data['errors']}"
            print("PASS test_cli_skip_check_suppresses_target_check")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_cli_skip_check_suppresses_target_check: {exc}", file=sys.stderr)
            return 1


def test_cli_multiple_skip_checks_suppress_multiple_checks() -> int:
    """Multiple --skip-check flags: exit 0, no errors despite wiki-config-mutation and card-missing-field."""
    with tempfile.TemporaryDirectory() as tmpdir:
        fixture_root = Path(tmpdir)
        plan_dir = fixture_root / "plan"
        wiki_dir = fixture_root / "wiki"
        wiki_dir.mkdir()
        (fixture_root / "mill-config.yaml").write_text("", encoding="utf-8")

        batch_text = (
            "# Batch: alpha\n\n"
            "```yaml\n"
            "task: test\nbatch: alpha\ncards: 1\nverify: null\ndepends-on: []\n"
            "```\n\n"
            "## Cards\n\n"
            "### Card 1: card 1\n\n"
            "- **Context:** none\n"
            "- **Edits:** `mill-config.yaml`\n"
            "- **Creates:** none\n"
            "- **Deletes:** none\n"
            "- **Moves:** none\n"
            "- **Requirements:**\n  See scope.\n"
            # Commit: field intentionally omitted to trigger card-missing-field
        )
        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        _write_plan(plan_dir, overview, [("01-alpha.md", batch_text)])

        slug = "test-slug"
        cfg = {"paths": {"plan_dir": "plan"}}
        captured = io.StringIO()

        orig = os.getcwd()
        os.chdir(str(fixture_root))
        try:
            with unittest.mock.patch("_paths.resolve_git_root", return_value=fixture_root), \
                 unittest.mock.patch("_paths.resolve_wiki_path", return_value=wiki_dir), \
                 unittest.mock.patch("_review_common.load_config", return_value=cfg), \
                 unittest.mock.patch("_review_common.find_active_slug", return_value=slug), \
                 unittest.mock.patch("_review_common.resolve_path", return_value=plan_dir), \
                 contextlib.redirect_stdout(captured):
                rc = _vp_mod.main(["--skip-check", "wiki-config-mutation", "--skip-check", "card-missing-field"])
        finally:
            os.chdir(orig)

        try:
            assert rc == 0, f"expected exit 0, got {rc}"
            output = captured.getvalue().strip()
            data = json.loads(output)
            assert data["errors"] == [], f"expected no errors, got {data['errors']}"
            print("PASS test_cli_multiple_skip_checks_suppress_multiple_checks")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_cli_multiple_skip_checks_suppress_multiple_checks: {exc}", file=sys.stderr)
            return 1


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def main() -> int:
    tests = [
        test_cli_clean_exits_zero_no_findings,
        test_cli_dirty_exits_one_card_missing_field,
        test_cli_skip_check_suppresses_target_check,
        test_cli_multiple_skip_checks_suppress_multiple_checks,
    ]

    errors = 0
    for t in tests:
        try:
            rc = t()
            if rc != 0:
                errors += 1
        except Exception as exc:
            errors += 1
            print(f"FAIL {t.__name__} (unexpected {type(exc).__name__}): {exc}", file=sys.stderr)

    if errors:
        print(f"\n{errors} test(s) FAILED", file=sys.stderr)
        return 1
    print("All millpy-validate-plan unit tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
