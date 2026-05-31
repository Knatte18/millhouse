"""Unit tests for wiki._render render function.

Covers: compute_layers algorithm, extended_title, render_order, empty task list,
task grouping/ordering, status markers, proposal file generation, brief text,
Depends-on lines, and sidebar rendering.
"""
from __future__ import annotations

import sys
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

from wiki._render import compute_layers, extended_title, render_order, render  # noqa: E402


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

    # --- (2) Topo levels A/B/C (C depends on B depends on A) ---
    try:
        tasks = [
            {"slug": "a-task", "id": 0, "title": "A Task", "depends_on": [], "isolated": False, "deferred": False, "brief": "", "body": "", "status": None},
            {"slug": "b-task", "id": 1, "title": "B Task", "depends_on": ["a-task"], "isolated": False, "deferred": False, "brief": "", "body": "", "status": None},
            {"slug": "c-task", "id": 2, "title": "C Task", "depends_on": ["b-task"], "isolated": False, "deferred": False, "brief": "", "body": "", "status": None},
        ]
        layers = compute_layers(tasks)
        assert layers["a-task"] == "A", f"A should be layer A, got {layers['a-task']}"
        assert layers["b-task"] == "B", f"B should be layer B, got {layers['b-task']}"
        assert layers["c-task"] == "C", f"C should be layer C, got {layers['c-task']}"
        result = render(tasks)
        home_content = result["Home.md"]
        a_pos = home_content.find("# Layer A")
        b_pos = home_content.find("# Layer B")
        c_pos = home_content.find("# Layer C")
        assert a_pos != -1, "Layer A not found"
        assert b_pos != -1, "Layer B not found"
        assert c_pos != -1, "Layer C not found"
        assert a_pos < b_pos < c_pos, f"Layer order incorrect: A at {a_pos}, B at {b_pos}, C at {c_pos}"
        ok("topo levels A/B/C")
    except Exception as exc:
        fail("topo levels A/B/C", exc)

    # --- (3) Empty layers are skipped ---
    try:
        tasks = [
            {"slug": "x-task", "id": 0, "title": "X Task", "depends_on": [], "isolated": False, "deferred": False, "brief": "", "body": "", "status": None},
            {"slug": "y-task", "id": 1, "title": "Y Task", "depends_on": ["x-task"], "isolated": False, "deferred": False, "brief": "", "body": "", "status": None},
        ]
        result = render(tasks)
        home_content = result["Home.md"]
        a_pos = home_content.find("# Layer A")
        b_pos = home_content.find("# Layer B")
        c_pos = home_content.find("# Layer C")
        assert a_pos != -1, "Layer A should exist"
        assert b_pos != -1, "Layer B should exist"
        assert c_pos == -1, "Layer C should not exist (no tasks)"
        ok("empty layers are skipped")
    except Exception as exc:
        fail("empty layers are skipped", exc)

    # --- (4) Accept any letter A-Z via deep dep chains ---
    try:
        # Build chain for M-level (13 hops): A0 <- A1 <- ... <- A12 (M = 13th letter)
        m_tasks = []
        for i in range(13):
            slug = f"m-dep-{i}"
            deps = [] if i == 0 else [f"m-dep-{i-1}"]
            m_tasks.append({"slug": slug, "id": i, "title": f"M Dep {i}", "depends_on": deps, "isolated": False, "deferred": False, "brief": "", "body": "", "status": None})
        # Build chain for Q-level (17 hops)
        q_tasks = []
        for i in range(17):
            slug = f"q-dep-{i}"
            deps = [] if i == 0 else [f"q-dep-{i-1}"]
            q_tasks.append({"slug": slug, "id": i + 13, "title": f"Q Dep {i}", "depends_on": deps, "isolated": False, "deferred": False, "brief": "", "body": "", "status": None})
        # Z-task via isolated
        z_task = [{"slug": "z-task", "id": 30, "title": "Z Task", "depends_on": [], "isolated": True, "deferred": False, "brief": "", "body": "", "status": None}]
        tasks = m_tasks + q_tasks + z_task
        layers = compute_layers(tasks)
        assert layers["m-dep-12"] == "M", f"M task should be layer M, got {layers['m-dep-12']}"
        assert layers["q-dep-16"] == "Q", f"Q task should be layer Q, got {layers['q-dep-16']}"
        assert layers["z-task"] == "Z", f"Z task should be layer Z, got {layers['z-task']}"
        result = render(tasks)
        home_content = result["Home.md"]
        m_pos = home_content.find("# Layer M")
        q_pos = home_content.find("# Layer Q")
        z_pos = home_content.find("# Layer Z")
        assert m_pos != -1, "Layer M should render"
        assert q_pos != -1, "Layer Q should render"
        assert z_pos != -1, "Layer Z should render"
        ok("accept any letter A-Z via deep dep chains")
    except Exception as exc:
        fail("accept any letter A-Z via deep dep chains", exc)

    # --- (5) Status markers ---
    try:
        tasks = [
            {"slug": "s1", "id": 0, "title": "Active Task", "depends_on": [], "isolated": False, "deferred": False, "brief": "", "body": "", "status": "active"},
            {"slug": "s2", "id": 1, "title": "Done Task", "depends_on": [], "isolated": False, "deferred": False, "brief": "", "body": "", "status": "done"},
            {"slug": "s3", "id": 2, "title": "No Status", "depends_on": [], "isolated": False, "deferred": False, "brief": "", "body": "", "status": None},
            {"slug": "s4", "id": 3, "title": "Ready Task", "depends_on": [], "isolated": False, "deferred": False, "brief": "", "body": "", "status": "ready-to-merge"},
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
            {"slug": "s-status", "id": 0, "title": "S Status Task", "depends_on": [], "isolated": False, "deferred": False, "brief": "", "body": "", "status": "s"},
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
            {"slug": "abandoned-task", "id": 0, "title": "Abandoned", "depends_on": [], "isolated": False, "deferred": False, "brief": "", "body": "", "status": "abandoned"},
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
            {"slug": "with-body", "id": 0, "title": "Has Proposal", "depends_on": [], "isolated": False, "deferred": False, "brief": "", "body": "proposal content here", "status": None},
        ]
        result = render(tasks)
        assert "proposal-with-body.md" in result, "proposal-with-body.md not generated"
        assert result["proposal-with-body.md"] == "proposal content here", "Proposal content mismatch"
        sidebar_content = result["_Sidebar.md"]
        assert "- [**#000:** Has Proposal [A]](proposal-with-body.md)" in sidebar_content, "Sidebar bullet link with [A] suffix not found"
        ok("proposal file generated for non-empty body")
    except Exception as exc:
        fail("proposal file generated for non-empty body", exc)

    # --- (9) No proposal file for empty body ---
    try:
        tasks = [
            {"slug": "no-body", "id": 0, "title": "No Proposal", "depends_on": [], "isolated": False, "deferred": False, "brief": "", "body": "", "status": None},
        ]
        result = render(tasks)
        assert not any(k.startswith("proposal-") for k in result.keys()), "No proposal files should exist"
        assert "_Sidebar.md" in result, "_Sidebar.md should exist"
        sidebar_content = result["_Sidebar.md"]
        assert "- **#000:** No Proposal [A]" in sidebar_content, "Task bullet should be in sidebar with [A] suffix"
        assert "[**#000:** No Proposal [A]](" not in sidebar_content, "Should not have link syntax without body"
        ok("no proposal file for empty body")
    except Exception as exc:
        fail("no proposal file for empty body", exc)

    # --- (10) Brief appears in Home.md body ---
    try:
        tasks = [
            {"slug": "with-brief", "id": 0, "title": "Brief Task", "depends_on": [], "isolated": False, "deferred": False, "brief": "Short summary.", "body": "", "status": None},
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
            {"slug": "no-brief", "id": 0, "title": "No Brief Task", "depends_on": [], "isolated": False, "deferred": False, "brief": "", "body": "", "status": None},
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

    # --- (13) Done tasks move to # Done bucket, no Unspecified section ---
    try:
        tasks = [
            {"slug": "a-task", "id": 0, "title": "A Task", "depends_on": [], "isolated": False, "deferred": False, "brief": "", "body": "", "status": None},
            {"slug": "done-1", "id": 1, "title": "Finished A", "depends_on": [], "isolated": False, "deferred": False, "brief": "", "body": "", "status": "done"},
            {"slug": "isolated-task", "id": 2, "title": "Isolated", "depends_on": [], "isolated": True, "deferred": False, "brief": "", "body": "", "status": None},
            {"slug": "done-2", "id": 3, "title": "Finished Z", "depends_on": [], "isolated": False, "deferred": False, "brief": "", "body": "", "status": "done"},
        ]
        result = render(tasks)
        home_content = result["Home.md"]
        layer_a = home_content.find("# Layer A")
        unspecified = home_content.find("# Unspecified")
        done_header = home_content.find("# Done")
        assert layer_a != -1, "Layer A header missing"
        assert unspecified == -1, "Unspecified header should not exist"
        assert done_header != -1, "Done header missing"
        assert layer_a < done_header, "Order: Layer A before Done"
        # done tasks should NOT have layer suffix
        assert "## **#001:** Finished A\n" in home_content, "done task should not have suffix"
        assert "## **#003:** Finished Z\n" in home_content, "done task should not have suffix"
        assert "## **#001:** Finished A [A]" not in home_content, "done task should not have [A]"
        assert "## **#003:** Finished Z [Z]" not in home_content, "done task should not have [Z]"
        # Active a-task should be under Layer A, not Done
        a_pos = home_content.find("## **#000:** A Task [A]")
        assert a_pos != -1 and a_pos < done_header, "Active A task should be in Layer A section, not Done"
        ok("done tasks bucketed under # Done, no Unspecified")
    except Exception as exc:
        fail("done tasks bucketed under # Done, no Unspecified", exc)

    # --- (12) Two consecutive renders produce byte-identical output ---
    try:
        tasks = [
            {"slug": "task-a", "id": 0, "title": "Task A", "depends_on": [], "isolated": False, "deferred": False, "brief": "Brief A", "body": "", "status": "active"},
            {"slug": "task-b", "id": 1, "title": "Task B", "depends_on": ["task-a"], "isolated": False, "deferred": False, "brief": "Brief B", "body": "content", "status": None},
        ]
        result1 = render(tasks)
        result2 = render(tasks)
        assert result1 == result2, "Two consecutive renders should produce identical dicts"
        for key in result1:
            assert result1[key] == result2[key], f"File {key} differs between renders"
        ok("two consecutive renders produce byte-identical output")
    except Exception as exc:
        fail("two consecutive renders produce byte-identical output", exc)

    # --- NEW TESTS FOR compute_layers, extended_title, render_order ---

    # (a) Done-dep promotion: task A (done) and task B with depends_on: ["A"]
    try:
        tasks = [
            {"slug": "a-task", "id": 0, "title": "A Task", "depends_on": [], "isolated": False, "deferred": False, "brief": "", "body": "", "status": "done"},
            {"slug": "b-task", "id": 1, "title": "B Task", "depends_on": ["a-task"], "isolated": False, "deferred": False, "brief": "", "body": "", "status": None},
        ]
        layers = compute_layers(tasks)
        assert layers["b-task"] == "A", f"B should be promoted to layer A (A is done), got {layers['b-task']}"
        ok("done-dep promotion")
    except Exception as exc:
        fail("done-dep promotion", exc)

    # (b) Isolated -> Z
    try:
        tasks = [
            {"slug": "iso-task", "id": 0, "title": "Isolated Task", "depends_on": [], "isolated": True, "deferred": False, "brief": "", "body": "", "status": None},
        ]
        layers = compute_layers(tasks)
        assert layers["iso-task"] == "Z", f"Isolated task should be Z, got {layers['iso-task']}"
        ok("isolated -> Z")
    except Exception as exc:
        fail("isolated -> Z", exc)

    # (c) Deferred -> __deferred__
    try:
        tasks = [
            {"slug": "deferred-task", "id": 0, "title": "Deferred Task", "depends_on": [], "isolated": False, "deferred": True, "brief": "", "body": "", "status": None},
        ]
        layers = compute_layers(tasks)
        assert layers["deferred-task"] == "__deferred__", f"Deferred task should be __deferred__, got {layers['deferred-task']}"
        ok("deferred -> __deferred__")
    except Exception as exc:
        fail("deferred -> __deferred__", exc)

    # (d) Precedence: done > deferred > isolated > topo
    try:
        tasks = [
            {"slug": "done-task", "id": 0, "title": "Done Task", "depends_on": [], "isolated": True, "deferred": True, "brief": "", "body": "", "status": "done"},
            {"slug": "deferred-iso", "id": 1, "title": "Deferred Iso", "depends_on": [], "isolated": True, "deferred": True, "brief": "", "body": "", "status": None},
            {"slug": "iso-only", "id": 2, "title": "Iso Only", "depends_on": [], "isolated": True, "deferred": False, "brief": "", "body": "", "status": None},
        ]
        layers = compute_layers(tasks)
        assert layers["done-task"] == "__done__", f"Done should win, got {layers['done-task']}"
        assert layers["deferred-iso"] == "__deferred__", f"Deferred should beat isolated, got {layers['deferred-iso']}"
        assert layers["iso-only"] == "Z", f"Isolated should give Z, got {layers['iso-only']}"
        ok("precedence done > deferred > isolated > topo")
    except Exception as exc:
        fail("precedence done > deferred > isolated > topo", exc)

    # (e) A..Y cap overflow raises
    try:
        tasks = []
        for i in range(26):
            slug = f"cap-{i}"
            deps = [] if i == 0 else [f"cap-{i-1}"]
            tasks.append({"slug": slug, "id": i, "title": f"Cap {i}", "depends_on": deps, "isolated": False, "deferred": False, "brief": "", "body": "", "status": None})
        try:
            compute_layers(tasks)
            fail("A..Y cap overflow raises", Exception("Should have raised ValueError"))
        except ValueError as e:
            if "cap" in str(e).lower() or "layer" in str(e).lower():
                ok("A..Y cap overflow raises")
            else:
                fail("A..Y cap overflow raises", Exception(f"Wrong error message: {e}"))
    except Exception as exc:
        fail("A..Y cap overflow raises", exc)

    # (f) Cycle raises
    try:
        tasks = [
            {"slug": "t1", "id": 0, "title": "T1", "depends_on": ["t2"], "isolated": False, "deferred": False, "brief": "", "body": "", "status": None},
            {"slug": "t2", "id": 1, "title": "T2", "depends_on": ["t1"], "isolated": False, "deferred": False, "brief": "", "body": "", "status": None},
        ]
        try:
            compute_layers(tasks)
            fail("cycle raises", Exception("Should have raised ValueError"))
        except ValueError as e:
            if "cycle" in str(e).lower() and "t1" in str(e) and "t2" in str(e):
                ok("cycle raises")
            else:
                fail("cycle raises", Exception(f"Wrong error message: {e}"))
    except Exception as exc:
        fail("cycle raises", exc)

    # (g) Dangling dep tolerated by compute_layers
    try:
        tasks = [
            {"slug": "dangle", "id": 0, "title": "Dangle Task", "depends_on": ["missing"], "isolated": False, "deferred": False, "brief": "", "body": "", "status": None},
        ]
        layers = compute_layers(tasks)
        assert layers["dangle"] == "A", f"Dangling dep should be tolerated, task gets A, got {layers['dangle']}"
        ok("dangling dep tolerated")
    except Exception as exc:
        fail("dangling dep tolerated", exc)

    # (h) render() dangling dep display
    try:
        tasks = [
            {"slug": "dangle-task", "id": 0, "title": "Dangle Task", "depends_on": ["missing"], "isolated": False, "deferred": False, "brief": "", "body": "", "status": None},
        ]
        result = render(tasks)
        home_content = result["Home.md"]
        assert "Depends on: #???: missing (missing)" in home_content, "Dangling dep should show as #???"
        ok("render() dangling dep display")
    except Exception as exc:
        fail("render() dangling dep display", exc)

    # (i) Render order A..Z -> Someday -> Done
    try:
        tasks = [
            {"slug": "layer-a", "id": 0, "title": "Layer A", "depends_on": [], "isolated": False, "deferred": False, "brief": "", "body": "", "status": None},
            {"slug": "someday", "id": 1, "title": "Someday", "depends_on": [], "isolated": False, "deferred": True, "brief": "", "body": "", "status": None},
            {"slug": "done", "id": 2, "title": "Done", "depends_on": [], "isolated": False, "deferred": False, "brief": "", "body": "", "status": "done"},
            {"slug": "layer-z", "id": 3, "title": "Layer Z", "depends_on": [], "isolated": True, "deferred": False, "brief": "", "body": "", "status": None},
        ]
        result = render(tasks)
        home_content = result["Home.md"]
        a_pos = home_content.find("# Layer A")
        z_pos = home_content.find("# Layer Z")
        someday_pos = home_content.find("# Someday")
        done_pos = home_content.find("# Done")
        assert a_pos < z_pos < someday_pos < done_pos, f"Order incorrect: A at {a_pos}, Z at {z_pos}, Someday at {someday_pos}, Done at {done_pos}"
        ok("render order A..Z -> Someday -> Done")
    except Exception as exc:
        fail("render order A..Z -> Someday -> Done", exc)

    # (j) # Unspecified not emitted
    try:
        tasks = [
            {"slug": "no-group", "id": 0, "title": "No Group", "depends_on": [], "isolated": False, "deferred": False, "brief": "", "body": "", "status": None},
        ]
        result = render(tasks)
        home_content = result["Home.md"]
        assert "# Unspecified" not in home_content, "Unspecified section should not be emitted"
        ok("# Unspecified not emitted")
    except Exception as exc:
        fail("# Unspecified not emitted", exc)

    # (k) Depends-on line shows numbers
    try:
        tasks = [
            {"slug": "a-task", "id": 10, "title": "A Task", "depends_on": [], "isolated": False, "deferred": False, "brief": "", "body": "", "status": None},
            {"slug": "b-task", "id": 20, "title": "B Task", "depends_on": ["a-task"], "isolated": False, "deferred": False, "brief": "", "body": "", "status": None},
        ]
        result = render(tasks)
        home_content = result["Home.md"]
        assert "Depends on: #010" in home_content, "B should show dependency on A (#010)"
        ok("depends-on line shows numbers")
    except Exception as exc:
        fail("depends-on line shows numbers", exc)

    # (l) Depends-on line omitted when empty
    try:
        tasks = [
            {"slug": "no-deps", "id": 0, "title": "No Deps", "depends_on": [], "isolated": False, "deferred": False, "brief": "", "body": "", "status": None},
        ]
        result = render(tasks)
        home_content = result["Home.md"]
        assert "Depends on:" not in home_content, "No Depends-on line should appear"
        ok("depends-on line omitted when empty")
    except Exception as exc:
        fail("depends-on line omitted when empty", exc)

    # (m) All-deps-done: Depends-on line still shown
    try:
        tasks = [
            {"slug": "a-task", "id": 0, "title": "A Task", "depends_on": [], "isolated": False, "deferred": False, "brief": "", "body": "", "status": "done"},
            {"slug": "b-task", "id": 1, "title": "B Task", "depends_on": ["a-task"], "isolated": False, "deferred": False, "brief": "", "body": "", "status": None},
        ]
        result = render(tasks)
        home_content = result["Home.md"]
        layers = compute_layers(tasks)
        assert layers["b-task"] == "A", "B should be promoted to A (A is done)"
        assert "Depends on: #000" in home_content, "B should still show Depends-on line even though A is done"
        ok("all-deps-done: depends-on line still shown")
    except Exception as exc:
        fail("all-deps-done: depends-on line still shown", exc)

    # (n) Done/deferred no letter suffix
    try:
        tasks = [
            {"slug": "active", "id": 0, "title": "Active", "depends_on": [], "isolated": False, "deferred": False, "brief": "", "body": "", "status": None},
            {"slug": "done", "id": 1, "title": "Done", "depends_on": [], "isolated": False, "deferred": False, "brief": "", "body": "", "status": "done"},
            {"slug": "deferred", "id": 2, "title": "Deferred", "depends_on": [], "isolated": False, "deferred": True, "brief": "", "body": "", "status": None},
        ]
        result = render(tasks)
        home_content = result["Home.md"]
        assert "## **#000:** Active [A]" in home_content, "Active should have [A]"
        assert "## **#001:** Done\n" in home_content, "Done should not have bracket"
        assert "## **#002:** Deferred\n" in home_content, "Deferred should not have bracket"
        ok("done/deferred no letter suffix")
    except Exception as exc:
        fail("done/deferred no letter suffix", exc)

    # (o) extended_title isolation
    try:
        active = {"title": "Active", "layer": "B", "status": None, "deferred": False}
        done = {"title": "Done", "layer": "A", "status": "done", "deferred": False}
        deferred = {"title": "Deferred", "layer": "C", "status": None, "deferred": True}
        assert extended_title(active) == "Active [B]", f"Active should have [B], got {extended_title(active)}"
        assert extended_title(done) == "Done", f"Done should have no suffix, got {extended_title(done)}"
        assert extended_title(deferred) == "Deferred", f"Deferred should have no suffix, got {extended_title(deferred)}"
        ok("extended_title isolation")
    except Exception as exc:
        fail("extended_title isolation", exc)

    # (p) render_order isolation
    try:
        tasks = [
            {"slug": "z-task", "id": 0, "title": "Z", "layer": "Z", "depends_on": [], "isolated": True, "deferred": False, "brief": "", "body": "", "status": None},
            {"slug": "a-task", "id": 1, "title": "A", "layer": "A", "depends_on": [], "isolated": False, "deferred": False, "brief": "", "body": "", "status": None},
            {"slug": "def-task", "id": 2, "title": "Def", "layer": "__deferred__", "depends_on": [], "isolated": False, "deferred": True, "brief": "", "body": "", "status": None},
            {"slug": "done-task", "id": 3, "title": "Done", "layer": "__done__", "depends_on": [], "isolated": False, "deferred": False, "brief": "", "body": "", "status": "done"},
        ]
        ordered = render_order(tasks)
        slugs = [t["slug"] for t in ordered]
        assert slugs == ["a-task", "z-task", "def-task", "done-task"], f"Order should be A, Z, deferred, done, got {slugs}"
        ok("render_order isolation")
    except Exception as exc:
        fail("render_order isolation", exc)

    # (q) Byte-identical double-render (already covered above in test 12, but reaffirm)
    try:
        tasks = [
            {"slug": "x", "id": 0, "title": "X", "depends_on": [], "isolated": False, "deferred": False, "brief": "Brief", "body": "", "status": None},
        ]
        r1 = render(tasks)
        r2 = render(tasks)
        assert r1 == r2, "Double render should produce identical output"
        ok("byte-identical double-render")
    except Exception as exc:
        fail("byte-identical double-render", exc)

    print("", file=sys.stderr)
    if failed:
        print(f"FAIL -- {failed} of {passed + failed}", file=sys.stderr)
        return 1
    print(f"PASS -- all {passed} tests", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
