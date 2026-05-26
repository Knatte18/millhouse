"""Unit tests for wiki._parse parse_home_md function.

Covers: layer header with parenthetical suffix, info-only headings, multi-paragraph
brief collapsing, [s] status, [abandoned] status, and title stripping.
"""
from __future__ import annotations

import sys
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

from wiki._parse import parse_home_md  # noqa: E402


def main() -> int:
    passed = 0
    failed = 0

    def ok(name: str) -> None:
        nonlocal passed
        passed += 1
        print(f"PASS: {name}")

    def fail(name: str, exc: Exception) -> None:
        nonlocal failed
        failed += 1
        print(f"FAIL: {name}: {exc}", file=sys.stderr)

    # --- (1) Layer header with parenthetical suffix ---
    try:
        content = """# Layer D (isolated -- run alone)

## Task Title
[task-slug]
"""
        result = parse_home_md(content)
        assert len(result) == 1, f"Should parse 1 task, got {len(result)}"
        task = result[0]
        assert task.get("group") == "D", f"Group should be D, got {task.get('group')}"
        assert task.get("slug") == "task-slug", f"Slug should be task-slug, got {task.get('slug')}"
        ok("layer header with parenthetical suffix")
    except Exception as exc:
        fail("layer header with parenthetical suffix", exc)

    # --- (2) Info-only heading produces no task entry ---
    try:
        content = """## (warn) wiki/config.yaml — read-only do not edit

Some informational text here.

## Real Task
[real-task]
"""
        result = parse_home_md(content)
        assert len(result) == 1, f"Should parse 1 task (info-only heading skipped), got {len(result)}"
        task = result[0]
        assert task.get("slug") == "real-task", f"Only real-task should be parsed, got {task.get('slug')}"
        ok("info-only heading produces no task entry")
    except Exception as exc:
        fail("info-only heading produces no task entry", exc)

    # --- (3) Multi-paragraph brief collapses ---
    try:
        content = """## Task Title
[task-slug]

This is the first paragraph.

This is the second paragraph.

This is the third paragraph.

## Next Task
[next]
"""
        result = parse_home_md(content)
        assert len(result) == 2, f"Should parse 2 tasks, got {len(result)}"
        task = result[0]
        brief = task.get("brief", "")
        assert "first paragraph" in brief and "second paragraph" in brief and "third paragraph" in brief, f"All paragraphs should be in brief: {brief!r}"
        assert brief.count("\n") == 0, f"Brief should be single line (collapsed), got {brief!r}"
        ok("multi-paragraph brief collapses")
    except Exception as exc:
        fail("multi-paragraph brief collapses", exc)

    # --- (4) [s] parses to status = None ---
    try:
        content = """## Task Title
[task-slug] [s]
"""
        result = parse_home_md(content)
        assert len(result) == 1, f"Should parse 1 task, got {len(result)}"
        task = result[0]
        assert task.get("status") is None, f"Status should be None for [s], got {task.get('status')!r}"
        ok("[s] parses to status = None")
    except Exception as exc:
        fail("[s] parses to status = None", exc)

    # --- (5) [abandoned] parses to status = "abandoned" ---
    try:
        content = """## Task Title
[task-slug] [abandoned]
"""
        result = parse_home_md(content)
        assert len(result) == 1, f"Should parse 1 task, got {len(result)}"
        task = result[0]
        assert task.get("status") == "abandoned", f"Status should be 'abandoned', got {task.get('status')!r}"
        ok("[abandoned] parses to status = 'abandoned'")
    except Exception as exc:
        fail("[abandoned] parses to status = 'abandoned'", exc)

    # --- (6) Title with numeric prefix and group code strips correctly ---
    try:
        content = """## 30 (D) -- Adopt V3 wiki module in V2 scripts
[task-slug]
"""
        result = parse_home_md(content)
        assert len(result) == 1, f"Should parse 1 task, got {len(result)}"
        task = result[0]
        title = task.get("title", "")
        assert "30" not in title, f"Numeric prefix should be stripped from title: {title!r}"
        assert "(D)" not in title, f"Group code should be stripped from title: {title!r}"
        assert "Adopt V3 wiki module in V2 scripts" in title, f"Main title text should remain: {title!r}"
        ok("title with numeric prefix and group code strips correctly")
    except Exception as exc:
        fail("title with numeric prefix and group code strips correctly", exc)

    # --- (7) Proposal link format [[slug]](proposal-slug.md) is recognized ---
    try:
        content = """## Task Title
[[task-slug]](proposal-task-slug.md)

Brief text.
"""
        result = parse_home_md(content)
        assert len(result) == 1, f"Should parse 1 task, got {len(result)}"
        task = result[0]
        assert task.get("slug") == "task-slug", f"Slug should be task-slug, got {task.get('slug')}"
        ok("proposal link format is recognized")
    except Exception as exc:
        fail("proposal link format is recognized", exc)

    # --- (8) Multiple statuses supported ---
    try:
        content = """## Task A
[task-a] [active]

## Task B
[task-b] [ready-to-merge]

## Task C
[task-c] [done]

## Task D
[task-d] [pr-pending]

## Task E
[task-e] [blocked]
"""
        result = parse_home_md(content)
        assert len(result) == 5, f"Should parse 5 tasks, got {len(result)}"
        by_slug = {t["slug"]: t for t in result}
        assert by_slug["task-a"]["status"] == "active", "active status"
        assert by_slug["task-b"]["status"] == "ready-to-merge", "ready-to-merge status"
        assert by_slug["task-c"]["status"] == "done", "done status"
        assert by_slug["task-d"]["status"] == "pr-pending", "pr-pending status"
        assert by_slug["task-e"]["status"] == "blocked", "blocked status"
        ok("multiple statuses supported")
    except Exception as exc:
        fail("multiple statuses supported", exc)

    # --- (9) Parse Home.md header text without title ---
    try:
        content = """# Tasks

## Task Title
[task-slug]
"""
        result = parse_home_md(content)
        assert len(result) == 1, f"Should parse 1 task, got {len(result)}"
        task = result[0]
        assert task.get("title") == "Task Title", f"Title should be 'Task Title', got {task.get('title')!r}"
        ok("parse Home.md with standard header")
    except Exception as exc:
        fail("parse Home.md with standard header", exc)

    print("", file=sys.stderr)
    if failed:
        print(f"FAIL -- {failed} of {passed + failed}", file=sys.stderr)
        return 1
    print(f"PASS -- all {passed} tests", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
