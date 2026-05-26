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

    # --- (2) Alphabetic group order then None last ---
    try:
        tasks = [
            {"slug": "b-task", "id": 1, "title": "B Task", "group": "B", "brief": "", "body": "", "status": None},
            {"slug": "a-task", "id": 0, "title": "A Task", "group": "A", "brief": "", "body": "", "status": None},
            {"slug": "c-task", "id": 2, "title": "C Task", "group": "C", "brief": "", "body": "", "status": None},
            {"slug": "ungrouped", "id": 3, "title": "Ungrouped Task", "group": None, "brief": "", "body": "", "status": None},
        ]
        result = render(tasks)
        home_content = result["Home.md"]
        a_pos = home_content.find("# Layer A")
        b_pos = home_content.find("# Layer B")
        c_pos = home_content.find("# Layer C")
        ungrouped_pos = home_content.find("Ungrouped Task")
        assert a_pos != -1, "Layer A not found"
        assert b_pos != -1, "Layer B not found"
        assert c_pos != -1, "Layer C not found"
        assert ungrouped_pos != -1, "Ungrouped task not found"
        assert a_pos < b_pos < c_pos < ungrouped_pos, f"Group order incorrect: A at {a_pos}, B at {b_pos}, C at {c_pos}, None at {ungrouped_pos}"
        ok("alphabetic group order then None last")
    except Exception as exc:
        fail("alphabetic group order then None last", exc)

    # --- (3) Empty groups are skipped ---
    try:
        tasks = [
            {"slug": "a-task", "id": 0, "title": "A Task", "group": "A", "brief": "", "body": "", "status": None},
            {"slug": "c-task", "id": 1, "title": "C Task", "group": "C", "brief": "", "body": "", "status": None},
        ]
        result = render(tasks)
        home_content = result["Home.md"]
        a_pos = home_content.find("# Layer A")
        b_pos = home_content.find("# Layer B")
        c_pos = home_content.find("# Layer C")
        assert a_pos != -1, "Layer A should exist"
        assert b_pos == -1, "Layer B should not exist (no tasks)"
        assert c_pos != -1, "Layer C should exist"
        ok("empty groups are skipped")
    except Exception as exc:
        fail("empty groups are skipped", exc)

    # --- (4) Accept any letter A-Z, not just hardcoded subset ---
    try:
        tasks = [
            {"slug": "m-task", "id": 0, "title": "M Task", "group": "M", "brief": "", "body": "", "status": None},
            {"slug": "q-task", "id": 1, "title": "Q Task", "group": "Q", "brief": "", "body": "", "status": None},
            {"slug": "z-task", "id": 2, "title": "Z Task", "group": "Z", "brief": "", "body": "", "status": None},
        ]
        result = render(tasks)
        home_content = result["Home.md"]
        m_pos = home_content.find("# Layer M")
        q_pos = home_content.find("# Layer Q")
        z_pos = home_content.find("# Layer Z")
        assert m_pos != -1, "Layer M should render"
        assert q_pos != -1, "Layer Q should render"
        assert z_pos != -1, "Layer Z should render"
        ok("accept any letter A-Z")
    except Exception as exc:
        fail("accept any letter A-Z", exc)

    # --- (5) Status markers ---
    try:
        tasks = [
            {"slug": "s1", "id": 0, "title": "Active Task", "group": None, "brief": "", "body": "", "status": "active"},
            {"slug": "s2", "id": 1, "title": "Done Task", "group": None, "brief": "", "body": "", "status": "done"},
            {"slug": "s3", "id": 2, "title": "No Status", "group": None, "brief": "", "body": "", "status": None},
            {"slug": "s4", "id": 3, "title": "Ready Task", "group": None, "brief": "", "body": "", "status": "ready-to-merge"},
        ]
        result = render(tasks)
        home_content = result["Home.md"]
        assert "[s1] [active]" in home_content, "Active status marker not found"
        assert "[s2] [done]" in home_content, "Done status marker not found"
        assert "[s3]\n" in home_content, "No-status entry not found"
        assert "[s4] [ready-to-merge]" in home_content, "Ready-to-merge status marker not found"
        ok("status markers")
    except Exception as exc:
        fail("status markers", exc)

    # --- (6) Status [s] never emitted (treated as None) ---
    try:
        tasks = [
            {"slug": "s-status", "id": 0, "title": "S Status Task", "group": None, "brief": "", "body": "", "status": "s"},
        ]
        result = render(tasks)
        home_content = result["Home.md"]
        assert "[s-status] [s]" not in home_content, "Status [s] should never be emitted"
        assert "[s-status]\n" in home_content, "Should have [slug] with no marker"
        ok("status [s] never emitted")
    except Exception as exc:
        fail("status [s] never emitted", exc)

    # --- (7) Status [abandoned] is emitted ---
    try:
        tasks = [
            {"slug": "abandoned-task", "id": 0, "title": "Abandoned", "group": None, "brief": "", "body": "", "status": "abandoned"},
        ]
        result = render(tasks)
        home_content = result["Home.md"]
        assert "[abandoned-task] [abandoned]" in home_content, "Status [abandoned] should be emitted"
        ok("status [abandoned] is emitted")
    except Exception as exc:
        fail("status [abandoned] is emitted", exc)

    # --- (8) Proposal file generated for non-empty body ---
    try:
        tasks = [
            {"slug": "with-body", "id": 0, "title": "Has Proposal", "group": None, "brief": "", "body": "proposal content here", "status": None},
        ]
        result = render(tasks)
        assert "proposal-with-body.md" in result, "proposal-with-body.md not generated"
        assert result["proposal-with-body.md"] == "proposal content here", "Proposal content mismatch"
        sidebar_content = result["_Sidebar.md"]
        assert "- [**#000:** Has Proposal](proposal-with-body.md)" in sidebar_content, "Sidebar bullet link not found"
        ok("proposal file generated for non-empty body")
    except Exception as exc:
        fail("proposal file generated for non-empty body", exc)

    # --- (9) No proposal file for empty body ---
    try:
        tasks = [
            {"slug": "no-body", "id": 0, "title": "No Proposal", "group": None, "brief": "", "body": "", "status": None},
        ]
        result = render(tasks)
        assert not any(k.startswith("proposal-") for k in result.keys()), "No proposal files should exist"
        assert "_Sidebar.md" in result, "_Sidebar.md should exist"
        sidebar_content = result["_Sidebar.md"]
        assert "- **#000:** No Proposal" in sidebar_content, "Task bullet should be in sidebar"
        assert "[**#000:** No Proposal](" not in sidebar_content, "Should not have link syntax without body"
        ok("no proposal file for empty body")
    except Exception as exc:
        fail("no proposal file for empty body", exc)

    # --- (10) Brief appears in Home.md body ---
    try:
        tasks = [
            {"slug": "with-brief", "id": 0, "title": "Brief Task", "group": None, "brief": "Short summary.", "body": "", "status": None},
        ]
        result = render(tasks)
        home_content = result["Home.md"]
        assert "## **#000:** Brief Task" in home_content, "Title not found"
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

    # --- (11) Task with empty brief ---
    try:
        tasks = [
            {"slug": "no-brief", "id": 0, "title": "No Brief Task", "group": None, "brief": "", "body": "", "status": None},
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

    # --- (13) Done tasks move to # Done bucket, last after Unspecified ---
    try:
        tasks = [
            {"slug": "a-task", "id": 0, "title": "A Task", "group": "A", "brief": "", "body": "", "status": None},
            {"slug": "done-1", "id": 1, "title": "Finished A", "group": "A", "brief": "", "body": "", "status": "done"},
            {"slug": "ungrouped", "id": 2, "title": "Ungrouped", "group": None, "brief": "", "body": "", "status": None},
            {"slug": "done-2", "id": 3, "title": "Finished Z", "group": "Z", "brief": "", "body": "", "status": "done"},
        ]
        result = render(tasks)
        home_content = result["Home.md"]
        layer_a = home_content.find("# Layer A")
        unspecified = home_content.find("# Unspecified")
        done_header = home_content.find("# Done")
        assert layer_a != -1, "Layer A header missing"
        assert unspecified != -1, "Unspecified header missing"
        assert done_header != -1, "Done header missing"
        assert layer_a < unspecified < done_header, "Order: Layer A, Unspecified, Done"
        # done tasks keep their original group prefix
        assert "## **#001:** Finished A [A]" in home_content, "done task should retain [A] suffix"
        assert "## **#003:** Finished Z [Z]" in home_content, "done task should retain [Z] suffix"
        # Active a-task should be under Layer A, not Done
        a_pos = home_content.find("## **#000:** A Task [A]")
        assert a_pos != -1 and a_pos < done_header, "Active A task should be in Layer A section, not Done"
        ok("done tasks bucketed under # Done after Unspecified")
    except Exception as exc:
        fail("done tasks bucketed under # Done after Unspecified", exc)

    # --- (12) Two consecutive renders produce byte-identical output ---
    try:
        tasks = [
            {"slug": "task-a", "id": 0, "title": "Task A", "group": "B", "brief": "Brief A", "body": "", "status": "active"},
            {"slug": "task-b", "id": 1, "title": "Task B", "group": "A", "brief": "Brief B", "body": "content", "status": None},
        ]
        result1 = render(tasks)
        result2 = render(tasks)
        assert result1 == result2, "Two consecutive renders should produce identical dicts"
        for key in result1:
            assert result1[key] == result2[key], f"File {key} differs between renders"
        ok("two consecutive renders produce byte-identical output")
    except Exception as exc:
        fail("two consecutive renders produce byte-identical output", exc)

    print("", file=sys.stderr)
    if failed:
        print(f"FAIL -- {failed} of {passed + failed}", file=sys.stderr)
        return 1
    print(f"PASS -- all {passed} tests", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
