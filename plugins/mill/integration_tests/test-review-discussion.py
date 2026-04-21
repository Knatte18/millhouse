"""
Integration test for mill-review-discussion.py

Sets up a temporary .millhouse/ layout with a seeded slug file, a wiki/
junction pointing at a fixture wiki containing a sample discussion.md,
then invokes mill-review-discussion.py and asserts:
  - Exit 0
  - Valid JSON with type/round/verdict/reviews fields
  - verdict in {APPROVE, REQUEST_CHANGES}
  - reviews has 1 entry, scope == "holistic"
  - review file exists on disk
  - review file has YAML frontmatter with matching verdict:

Also tests the "No active task" error path.

Prerequisites: claude in PATH, valid Claude subscription.

Usage (from hub/):
    python plugins/mill/integration_tests/test-review-discussion.py

Exits 0 on PASS, non-zero with a descriptive error on FAIL.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

import yaml

# Resolve paths relative to this file
_INTEGRATION_TESTS_DIR = Path(__file__).resolve().parent
_MILL_ROOT = _INTEGRATION_TESTS_DIR.parent
_SCRIPTS = _MILL_ROOT / "scripts"
_FIXTURES = _INTEGRATION_TESTS_DIR / "fixtures"

# Ensure scripts/ is importable
sys.path.insert(0, str(_SCRIPTS))
import _junction  # noqa: E402  (after sys.path manipulation)

import subprocess  # noqa: E402


_CONFIG_YAML = """\
paths:
  discussion_file: active/<SLUG>/discussion.md
  plan_dir:        active/<SLUG>/plan/
  reviews_dir:     active/<SLUG>/reviews/

review:
  discussion:
    rounds: 2
    holistic: sonnetmax_tool

  plan:
    rounds: 3
    batch: sonnetmax
    holistic: sonnetmax

  code:
    rounds: 3
    reviewer: sonnetmax
    style: single
"""

_SLUG_FILE_CONTENT = """\
---
slug: test-slug
task_title: "Test discussion review"
---
"""


def _run_script(script: Path, cwd: Path) -> tuple[int, str, str]:
    """Run a Python script; return (exit_code, stdout, stderr)."""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(_SCRIPTS)
    env["PYTHONIOENCODING"] = "utf-8"
    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )
    return result.returncode, result.stdout, result.stderr


def main() -> int:
    tmp_obj = tempfile.TemporaryDirectory(prefix="mill-layer02-test-discussion-")
    tmp = Path(tmp_obj.name)
    failed = False
    try:
        # ---------------------------------------------------------------
        # Setup
        # ---------------------------------------------------------------
        millhouse_dir = tmp / ".millhouse"
        wiki_dir = tmp / "wiki-fixture"
        active_dir = wiki_dir / "active" / "test-slug"
        reviews_dir = active_dir / "reviews"

        millhouse_dir.mkdir()
        active_dir.mkdir(parents=True)
        reviews_dir.mkdir(parents=True)

        (millhouse_dir / ".test-slug.slug.md").write_text(
            _SLUG_FILE_CONTENT, encoding="utf-8"
        )
        (wiki_dir / "config.yaml").write_text(_CONFIG_YAML, encoding="utf-8")

        # Seed discussion fixture
        shutil.copy(_FIXTURES / "sample-discussion.md", active_dir / "discussion.md")

        # Create wiki junction: .millhouse/wiki -> wiki-fixture/
        _junction.create(wiki_dir.resolve(), (millhouse_dir / "wiki").resolve())

        # ---------------------------------------------------------------
        # Test 1: happy path
        # ---------------------------------------------------------------
        print("Test 1: happy path (discussion review)...", file=sys.stderr)

        script = _SCRIPTS / "mill-review-discussion.py"
        exit_code, stdout, stderr = _run_script(script, tmp)

        if exit_code != 0:
            print(f"FAIL: mill-review-discussion.py exited {exit_code}")
            print(f"stderr: {stderr}")
            print(f"stdout: {stdout}")
            failed = True
            return 1

        if not stdout.strip():
            print("FAIL: stdout is empty (expected JSON)")
            failed = True
            return 1

        try:
            result = json.loads(stdout)
        except json.JSONDecodeError as exc:
            print(f"FAIL: stdout is not valid JSON: {stdout!r} ({exc})")
            failed = True
            return 1

        if result.get("type") != "discussion":
            print(f"FAIL: expected type='discussion', got {result.get('type')!r}")
            failed = True
            return 1

        if result.get("round") != 1:
            print(f"FAIL: expected round=1, got {result.get('round')!r}")
            failed = True
            return 1

        if result.get("verdict") not in ("APPROVE", "REQUEST_CHANGES"):
            print(f"FAIL: unexpected verdict {result.get('verdict')!r}")
            failed = True
            return 1

        reviews = result.get("reviews", [])
        if len(reviews) != 1:
            print(f"FAIL: expected reviews length 1, got {len(reviews)}")
            failed = True
            return 1

        if reviews[0].get("scope") != "holistic":
            print(
                f"FAIL: expected reviews[0].scope='holistic', got {reviews[0].get('scope')!r}"
            )
            failed = True
            return 1

        review_file = Path(reviews[0]["file"])
        if not review_file.exists():
            print(f"FAIL: review file does not exist: {review_file}")
            failed = True
            return 1

        review_text = review_file.read_text(encoding="utf-8")
        # Parse YAML frontmatter
        if review_text.startswith("---"):
            fm_end = review_text.index("---", 3)
            fm = yaml.safe_load(review_text[3:fm_end])
        else:
            fm = {}
        entry_verdict = reviews[0]["verdict"]
        if fm.get("verdict") != entry_verdict:
            print(
                f"FAIL: review file frontmatter verdict={fm.get('verdict')!r}, "
                f"expected {entry_verdict!r}"
            )
            print("Review file contents (first 20 lines):")
            for line in review_text.splitlines()[:20]:
                print(f"  {line}")
            failed = True
            return 1

        print("Test 1 PASS", file=sys.stderr)

        # ---------------------------------------------------------------
        # Test 2: error path — no active task (slug file removed)
        # ---------------------------------------------------------------
        print("Test 2: error path (no active task)...", file=sys.stderr)

        slug_file = millhouse_dir / ".test-slug.slug.md"
        slug_file.unlink()

        exit_code2, stdout2, stderr2 = _run_script(script, tmp)

        if exit_code2 == 0:
            print("FAIL: expected exit 1 when no slug file present, got exit 0")
            failed = True
            return 1

        combined = stdout2 + stderr2
        if "No active task" not in combined:
            print(f"FAIL: expected 'No active task' in output, got: {combined!r}")
            failed = True
            return 1

        print("Test 2 PASS", file=sys.stderr)

    except Exception:
        failed = True
        raise
    finally:
        if failed:
            # Leave temp dir in place for inspection — detach from context manager
            tmp_obj._finalizer.detach()  # type: ignore[attr-defined]
            print(
                f"Temp dir preserved for inspection: {tmp}", file=sys.stderr
            )
        else:
            tmp_obj.cleanup()

    print("PASS — all discussion review tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
