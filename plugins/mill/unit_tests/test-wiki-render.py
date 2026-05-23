"""Unit tests for wiki._render render function.

Covers: empty task list, task grouping/ordering, status markers,
proposal file generation, brief text, and sidebar rendering.
"""
from __future__ import annotations

import sys
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

from wiki._render import render  # noqa: E402


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

    # --- (1) Empty task list ---
    try:
        result = render([])
        assert "Home.md" in result, "Home.md missing from render result"
        assert result["Home.md"] == "# Tasks\n", f"Empty Home.md incorrect: {result['Home.md']!r}"
        assert "_Sidebar.md" in result, "_Sidebar.md missing from render result"
        assert not any(k.startswith("proposal-") for k in result.keys()), "No proposal files should exist for empty list"
        ok("empty task list")
    except Exception as exc:
        fail("empty task list", exc)

    # --- (2) Ungrouped tasks appear before grouped ---
    try:
        tasks = [
            {"slug": "grouped", "title": "Grouped Task", "group": "A", "brief": "", "body": "", "status": None},
            {"slug": "ungrouped", "title": "Ungrouped Task", "group": None, "brief": "", "body": "", "status": None},
        ]
        result = render(tasks)
        home_content = result["Home.md"]
        ungrouped_pos = home_content.find("## Ungrouped Task")
        grouped_pos = home_content.find("## Grouped Task")
        assert ungrouped_pos != -1, "Ungrouped task not found in Home.md"
        assert grouped_pos != -1, "Grouped task not found in Home.md"
        assert ungrouped_pos < grouped_pos, "Ungrouped task should appear before grouped task"
        ok("ungrouped tasks appear before grouped")
    except Exception as exc:
        fail("ungrouped tasks appear before grouped", exc)

    # --- (3) Group order A->B->C->D->Z ---
    try:
        tasks = [
            {"slug": "z-task", "title": "Z Task", "group": "Z", "brief": "", "body": "", "status": None},
            {"slug": "a-task", "title": "A Task", "group": "A", "brief": "", "body": "", "status": None},
            {"slug": "d-task", "title": "D Task", "group": "D", "brief": "", "body": "", "status": None},
        ]
        result = render(tasks)
        home_content = result["Home.md"]
        a_pos = home_content.find("# Layer A")
        d_pos = home_content.find("# Layer D")
        z_pos = home_content.find("# Layer Z")
        assert a_pos != -1, "Layer A not found"
        assert d_pos != -1, "Layer D not found"
        assert z_pos != -1, "Layer Z not found"
        assert a_pos < d_pos < z_pos, f"Group order incorrect: A at {a_pos}, D at {d_pos}, Z at {z_pos}"
        ok("group order A->B->C->D->Z")
    except Exception as exc:
        fail("group order A->B->C->D->Z", exc)

    # --- (4) Status markers ---
    try:
        tasks = [
            {"slug": "s1", "title": "Active Task", "group": None, "brief": "", "body": "", "status": "active"},
            {"slug": "s2", "title": "Done Task", "group": None, "brief": "", "body": "", "status": "done"},
            {"slug": "s3", "title": "No Status", "group": None, "brief": "", "body": "", "status": None},
            {"slug": "s4", "title": "Blocked Task", "group": None, "brief": "", "body": "", "status": "blocked"},
        ]
        result = render(tasks)
        home_content = result["Home.md"]
        assert "[s1] [active]" in home_content, "Active status marker not found"
        assert "[s2] [done]" in home_content, "Done status marker not found"
        assert "[s3]" in home_content, "No-status entry not found"
        assert home_content.count("[s3]") == 1, "Should have exactly one [s3] without marker"
        assert "[s4] [blocked]" not in home_content, "Blocked status should not emit marker"
        ok("status markers")
    except Exception as exc:
        fail("status markers", exc)

    # --- (5) Proposal file generated for non-empty body ---
    try:
        tasks = [
            {"slug": "with-body", "title": "Has Proposal", "group": None, "brief": "", "body": "proposal content here", "status": None},
        ]
        result = render(tasks)
        assert "proposal-with-body.md" in result, "proposal-with-body.md not generated"
        assert result["proposal-with-body.md"] == "proposal content here", "Proposal content mismatch"
        home_content = result["Home.md"]
        assert "[[Has Proposal]](proposal-with-body.md)" in home_content, "Sidebar link not found"
        ok("proposal file generated for non-empty body")
    except Exception as exc:
        fail("proposal file generated for non-empty body", exc)

    # --- (6) No proposal file for empty body ---
    try:
        tasks = [
            {"slug": "no-body", "title": "No Proposal", "group": None, "brief": "", "body": "", "status": None},
        ]
        result = render(tasks)
        assert not any(k.startswith("proposal-") for k in result.keys()), "No proposal files should exist"
        assert "_Sidebar.md" in result, "_Sidebar.md should exist"
        sidebar_content = result["_Sidebar.md"]
        assert "No Proposal" in sidebar_content, "Task title should be in sidebar"
        assert "[[No Proposal]]" not in sidebar_content, "Should not have link syntax without body"
        ok("no proposal file for empty body")
    except Exception as exc:
        fail("no proposal file for empty body", exc)

    # --- (7) Brief appears in Home.md body ---
    try:
        tasks = [
            {"slug": "with-brief", "title": "Brief Task", "group": None, "brief": "Short summary.", "body": "", "status": None},
        ]
        result = render(tasks)
        home_content = result["Home.md"]
        assert "## Brief Task" in home_content, "Title not found"
        assert "[with-brief]" in home_content, "Slug not found"
        assert "Short summary." in home_content, "Brief text not found"
        lines = home_content.split("\n")
        brief_idx = None
        for i, line in enumerate(lines):
            if line == "Short summary.":
                brief_idx = i
                break
        assert brief_idx is not None, "Brief line not found"
        assert brief_idx > 0 and lines[brief_idx - 1] == "", "Brief should follow blank line"
        ok("brief appears in Home.md body")
    except Exception as exc:
        fail("brief appears in Home.md body", exc)

    # --- (8) Task with empty brief ---
    try:
        tasks = [
            {"slug": "no-brief", "title": "No Brief Task", "group": None, "brief": "", "body": "", "status": None},
        ]
        result = render(tasks)
        home_content = result["Home.md"]
        lines = home_content.split("\n")
        for i, line in enumerate(lines):
            if "[no-brief]" in line:
                if i + 1 < len(lines):
                    next_line = lines[i + 1]
                    assert next_line == "", f"Line after slug should be blank, got {next_line!r}"
                break
        ok("task with empty brief")
    except Exception as exc:
        fail("task with empty brief", exc)

    print("", file=sys.stderr)
    if failed:
        print(f"FAIL -- {failed} of {passed + failed}", file=sys.stderr)
        return 1
    print(f"PASS -- all {passed} tests", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
