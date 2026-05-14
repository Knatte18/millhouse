"""
Integration test for millpy-review-code.py

The .millhouse/ layout, wiki junction, and slug file are placed inside
$tmp/project/ (not directly in $tmp/) because the code backend uses
cwd=project_root for its git commands (git merge-base, git diff).

Setup:
  1. Init git repo in $tmp/project/ with main branch.
  2. Create base-file.py, commit as "base" on main.
  3. Checkout task-branch; apply sample-code-diff.patch; commit.
  4. Seed .millhouse/ + wiki junction + slug file inside $tmp/project/.
  5. Seed active/test-slug/plan/00-overview.md in the fixture wiki.
  6. Invoke millpy-review-code.py with cwd=$tmp/project/.

Assertions:
  - Exit 0
  - Valid JSON with type="code", reviews length 1, scope="holistic"
  - review file exists, has matching verdict: in frontmatter

Also tests the "No active task" error path.

Prerequisites: claude in PATH, valid Claude subscription, git in PATH.

Usage (from hub/):
    python plugins/mill/integration_tests/test-review-code.py

Exits 0 on PASS, non-zero with a descriptive error on FAIL.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid
from pathlib import Path


# Resolve paths relative to this file
_INTEGRATION_TESTS_DIR = Path(__file__).resolve().parent
_MILL_ROOT = _INTEGRATION_TESTS_DIR.parent
_HUB = _MILL_ROOT.parent.parent          # plugins/mill -> plugins -> hub
_SCRIPTS = _MILL_ROOT / "scripts"
_PLUGIN_ROOT = _MILL_ROOT
_FIXTURES = _INTEGRATION_TESTS_DIR / "fixtures"
_SCRATCH = _HUB / ".scratch"

# Ensure scripts/ is importable
sys.path.insert(0, str(_SCRIPTS))
import _junction  # noqa: E402  (after sys.path manipulation)
import _review_common  # noqa: E402
import _safe_rmtree  # noqa: E402


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
task_title: "Test code review"
---
"""

_PLAN_OVERVIEW_CONTENT = """\
---
kind: plan-overview
task: Test code review
verify: N/A
dev-server: N/A
approved: true
started: 20260420-100000
batches: [core]
root: .
---

# Test code review — Plan

## Context

Small refactor of base-file.py: add input validation to `greet()`, introduce
a `slugify()` helper with lru_cache.

## All Files Touched

- base-file.py
"""

_BASE_FILE_CONTENT = '''\
"""base-file.py — simple utility module used as a code-review test fixture."""
from __future__ import annotations


def greet(name: str) -> str:
    """Return a greeting string for the given name."""
    return f"Hello, {name}!"


def add(a: int, b: int) -> int:
    """Return the sum of two integers."""
    return a + b


def main() -> None:
    print(greet("world"))
    print(add(1, 2))


if __name__ == "__main__":
    main()
'''

_MODIFIED_FILE_CONTENT = '''\
"""base-file.py — simple utility module used as a code-review test fixture."""
from __future__ import annotations

import re
from functools import lru_cache


def greet(name: str) -> str:
    """Return a greeting string for the given name."""
    if not name:
        raise ValueError("name must not be empty")
    return f"Hello, {name}!"


@lru_cache(maxsize=128)
def slugify(text: str) -> str:
    """Return a URL-safe slug of text."""
    slug = re.sub(r"\\s+", "-", text.strip().lower())
    slug = re.sub(r"[^a-z0-9-]", "", slug)
    return slug


def main() -> None:
    print(greet("world"))
    print(slugify("Hello World"))
    print(slugify("Hello World"))  # cached hit


if __name__ == "__main__":
    main()
'''


def _git(project_root: Path, *args: str) -> None:
    """Run a git command inside project_root, raise on non-zero exit."""
    result = subprocess.run(
        ["git", "-C", str(project_root), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} failed (exit {result.returncode}): "
            f"{result.stderr.strip()}"
        )


def _run_script(script: Path, cwd: Path) -> tuple[int, str, str]:
    """Run a Python script; return (exit_code, stdout, stderr)."""
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    result = subprocess.run(
        ["uv", "run", "--project", str(_PLUGIN_ROOT), str(script)],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )
    return result.returncode, result.stdout, result.stderr


def main() -> int:
    _SCRATCH.mkdir(parents=True, exist_ok=True)
    tmp = _SCRATCH / f"mill-layer02-test-code-{uuid.uuid4().hex[:8]}"
    tmp.mkdir()
    failed = False
    try:
        project_root = tmp / "project"
        project_root.mkdir()

        # ---------------------------------------------------------------
        # Setup: git repo
        # ---------------------------------------------------------------
        _git(project_root, "init", "--initial-branch=main")
        _git(project_root, "config", "user.email", "test@mill")
        _git(project_root, "config", "user.name", "mill-test")

        base_file = project_root / "base-file.py"
        base_file.write_text(_BASE_FILE_CONTENT, encoding="utf-8")
        _git(project_root, "add", "base-file.py")
        _git(project_root, "commit", "-m", "base")

        _git(project_root, "checkout", "-b", "task-branch")

        # Instead of applying a brittle patch fixture, write the modified
        # base-file.py directly and commit. Diff is generated naturally by
        # `git diff main..HEAD` inside the code-review backend.
        base_file.write_text(_MODIFIED_FILE_CONTENT, encoding="utf-8")
        _git(project_root, "add", "base-file.py")
        _git(project_root, "commit", "-m", "apply diff")

        # ---------------------------------------------------------------
        # Setup: .millhouse/ + wiki fixture inside project_root
        # ---------------------------------------------------------------
        millhouse_dir = project_root / ".millhouse"
        wiki_dir = project_root / "wiki-fixture"
        plan_dir = wiki_dir / "active" / "test-slug" / "plan"
        reviews_dir = wiki_dir / "active" / "test-slug" / "reviews"

        millhouse_dir.mkdir()
        plan_dir.mkdir(parents=True)
        reviews_dir.mkdir(parents=True)

        (millhouse_dir / ".test-slug.slug.md").write_text(
            _SLUG_FILE_CONTENT, encoding="utf-8"
        )
        (wiki_dir / "config.yaml").write_text(_CONFIG_YAML, encoding="utf-8")
        (plan_dir / "00-overview.md").write_text(_PLAN_OVERVIEW_CONTENT, encoding="utf-8")

        # Create wiki junction: .millhouse/wiki -> wiki-fixture/
        _junction.create(wiki_dir.resolve(), (millhouse_dir / "wiki").resolve())

        # ---------------------------------------------------------------
        # Test 1: happy path
        # ---------------------------------------------------------------
        print("Test 1: happy path (code review)...", file=sys.stderr)

        script = _SCRIPTS / "millpy-review-code.py"
        exit_code, stdout, stderr = _run_script(script, project_root)

        if exit_code != 0:
            print(f"FAIL: millpy-review-code.py exited {exit_code}")
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

        if result.get("type") != "code":
            print(f"FAIL: expected type='code', got {result.get('type')!r}")
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

        # Use production parse_verdict — no duplicate YAML-block parser in tests.
        file_verdict = _review_common.parse_verdict(review_file.read_text(encoding="utf-8"))
        entry_verdict = reviews[0]["verdict"]
        if file_verdict != entry_verdict:
            print(
                f"FAIL: review file verdict={file_verdict!r}, "
                f"expected {entry_verdict!r} (matching reviews[0].verdict)"
            )
            failed = True
            return 1

        print("Test 1 PASS", file=sys.stderr)

        # ---------------------------------------------------------------
        # Test 2: error path — no active task (slug file removed)
        # ---------------------------------------------------------------
        print("Test 2: error path (no active task)...", file=sys.stderr)

        slug_file = millhouse_dir / ".test-slug.slug.md"
        slug_file.unlink()

        exit_code2, stdout2, stderr2 = _run_script(script, project_root)

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
            print(f"Scratch dir preserved for inspection: {tmp}", file=sys.stderr)
        else:
            _safe_rmtree.safe_rmtree(tmp, allowed_root=tmp, ignore_errors=True)

    print("PASS — all code review tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
