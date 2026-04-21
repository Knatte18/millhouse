"""
Integration test for mill-review-plan.py

Sets up a temporary .millhouse/ layout with a seeded slug file, a wiki/
junction pointing at a fixture wiki containing a sample plan (00-overview.md
+ 01-core.md), then invokes mill-review-plan.py and asserts:
  - Exit 0
  - Valid JSON with type/round/verdict/reviews fields
  - verdict in {APPROVE, REQUEST_CHANGES}
  - reviews has 2 entries (1 batch + 1 holistic)
  - reviews contains entry with scope "01-core" and entry with scope "holistic"
  - each entry's file exists on disk
  - each review file has YAML frontmatter with matching verdict:

Also tests the "No active task" error path.

Prerequisites: claude in PATH, valid Claude subscription.

Usage (from hub/):
    python plugins/mill/integration_tests/test-review-plan.py

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
task_title: "Test plan review"
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
    tmp_obj = tempfile.TemporaryDirectory(prefix="mill-layer02-test-plan-")
    tmp = Path(tmp_obj.name)
    failed = False
    try:
        # ---------------------------------------------------------------
        # Setup
        # ---------------------------------------------------------------
        millhouse_dir = tmp / ".millhouse"
        wiki_dir = tmp / "wiki-fixture"
        plan_dir = wiki_dir / "active" / "test-slug" / "plan"
        reviews_dir = wiki_dir / "active" / "test-slug" / "reviews"

        millhouse_dir.mkdir()
        plan_dir.mkdir(parents=True)
        reviews_dir.mkdir(parents=True)

        (millhouse_dir / ".test-slug.slug.md").write_text(
            _SLUG_FILE_CONTENT, encoding="utf-8"
        )
        (wiki_dir / "config.yaml").write_text(_CONFIG_YAML, encoding="utf-8")

        # 01-core.md has a "Reads: plugins/mill/scripts/_render.py" directive.
        # The plan backend resolves Reads: paths relative to project_root (cwd).
        # Mirror the real file at $tmp/plugins/mill/scripts/_render.py.
        reads_target = tmp / "plugins" / "mill" / "scripts"
        reads_target.mkdir(parents=True)
        shutil.copy(_SCRIPTS / "_render.py", reads_target / "_render.py")

        shutil.copy(_FIXTURES / "sample-plan" / "00-overview.md", plan_dir / "00-overview.md")
        shutil.copy(_FIXTURES / "sample-plan" / "01-core.md", plan_dir / "01-core.md")

        # Create wiki junction: .millhouse/wiki -> wiki-fixture/
        _junction.create(wiki_dir.resolve(), (millhouse_dir / "wiki").resolve())

        # ---------------------------------------------------------------
        # Test 1: happy path
        # ---------------------------------------------------------------
        print("Test 1: happy path (plan review)...", file=sys.stderr)

        script = _SCRIPTS / "mill-review-plan.py"
        exit_code, stdout, stderr = _run_script(script, tmp)

        if exit_code != 0:
            print(f"FAIL: mill-review-plan.py exited {exit_code}")
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

        if result.get("type") != "plan":
            print(f"FAIL: expected type='plan', got {result.get('type')!r}")
            failed = True
            return 1

        if result.get("verdict") not in ("APPROVE", "REQUEST_CHANGES"):
            print(f"FAIL: unexpected verdict {result.get('verdict')!r}")
            failed = True
            return 1

        reviews = result.get("reviews", [])
        if len(reviews) != 2:
            print(
                f"FAIL: expected reviews length 2 (1 batch + 1 holistic), got {len(reviews)}"
            )
            failed = True
            return 1

        scopes = [r.get("scope") for r in reviews]
        if "01-core" not in scopes:
            print(f"FAIL: no reviews entry with scope='01-core'. Scopes present: {scopes}")
            failed = True
            return 1

        if "holistic" not in scopes:
            print(f"FAIL: no reviews entry with scope='holistic'. Scopes present: {scopes}")
            failed = True
            return 1

        for entry in reviews:
            review_file = Path(entry["file"])
            if not review_file.exists():
                print(
                    f"FAIL: review file does not exist for scope {entry.get('scope')!r}: "
                    f"{review_file}"
                )
                failed = True
                return 1

            review_text = review_file.read_text(encoding="utf-8")
            if review_text.startswith("---"):
                fm_end = review_text.index("---", 3)
                fm = yaml.safe_load(review_text[3:fm_end])
            else:
                fm = {}
            entry_verdict = entry["verdict"]
            if fm.get("verdict") != entry_verdict:
                print(
                    f"FAIL: review file for scope {entry.get('scope')!r} "
                    f"frontmatter verdict={fm.get('verdict')!r}, expected {entry_verdict!r}"
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
            tmp_obj._finalizer.detach()  # type: ignore[attr-defined]
            print(
                f"Temp dir preserved for inspection: {tmp}", file=sys.stderr
            )
        else:
            tmp_obj.cleanup()

    print("PASS — all plan review tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
