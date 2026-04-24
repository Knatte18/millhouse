"""Unit tests for plugins/mill/scripts/_status.py."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

from _status import (  # noqa: E402
    append_phase,
    init_batches,
    read_batches,
    read_status,
    render_initial,
    set_batch_field,
    update_field,
)


def main() -> int:
    try:
        out = render_initial(
            task_title="Fix bug in widget handler",
            task_description="Widgets throw on empty input.",
            timestamp="2026-04-22T14:32:05Z",
            parent_branch="main",
        )
        assert out.startswith("# Status\n"), "Leading HTML comment should be stripped"
        assert "Fix bug in widget handler" in out
        assert "2026-04-22T14:32:05Z" in out
        assert "parent: main" in out
        assert "<TASK_TITLE>" not in out and "<TIMESTAMP>" not in out
        print("PASS: render_initial() substitutes tokens and strips header")

        with tempfile.TemporaryDirectory() as tmp:
            sp = Path(tmp) / "status.md"
            sp.write_text(out, encoding="utf-8")

            update_field(sp, "task", "Updated title")
            assert "task: Updated title" in sp.read_text(encoding="utf-8")
            print("PASS: update_field rewrites a scalar yaml row")

            append_phase(sp, "discussed", "2026-04-22T15:00:00Z")
            contents = sp.read_text(encoding="utf-8")
            assert "phase: discussed" in contents, "phase yaml row not updated"
            assert "discussed  2026-04-22T15:00:00Z" in contents, "timeline row not appended"
            print("PASS: append_phase updates phase yaml + appends timeline row")

            # Batches section
            assert read_batches(sp) == [], "no batches section yet"
            init_batches(sp, ["foundation", "reviewers"])
            batches = read_batches(sp)
            assert [b["name"] for b in batches] == ["foundation", "reviewers"]
            assert all(b["state"] == "pending" for b in batches)
            print("PASS: init_batches seeds pending entries")

            set_batch_field(sp, "foundation", "state", "running")
            set_batch_field(sp, "foundation", "implementer_session", "abc123")
            batches = read_batches(sp)
            foundation = next(b for b in batches if b["name"] == "foundation")
            assert foundation["state"] == "running"
            assert foundation["implementer_session"] == "abc123"
            print("PASS: set_batch_field updates state + implementer_session")

            try:
                set_batch_field(sp, "foundation", "nope", "x")
            except ValueError as exc:
                assert "Unknown batch field" in str(exc)
                print("PASS: set_batch_field rejects unknown key")

            try:
                set_batch_field(sp, "foundation", "state", "finished")
            except ValueError as exc:
                assert "Unknown batch state" in str(exc)
                print("PASS: set_batch_field rejects unknown state")

            try:
                set_batch_field(sp, "missing", "state", "running")
            except ValueError as exc:
                assert "not present" in str(exc)
                print("PASS: set_batch_field rejects unknown batch name")

            contents = sp.read_text(encoding="utf-8")
            assert "phase: discussed" in contents, "batches edit damaged top yaml"
            assert "discussed  2026-04-22T15:00:00Z" in contents, "batches edit damaged timeline"
            print("PASS: batches edits preserve top yaml + timeline")

        # --- read_status tests ---
        ts = "2026-04-22T14:32:05Z"

        # Case 1: freshly-rendered file
        with tempfile.TemporaryDirectory() as tmp:
            sp = Path(tmp) / "status.md"
            sp.write_text(
                render_initial("My task", "Desc.", ts, "main"), encoding="utf-8"
            )
            r = read_status(sp)
            assert r["phase"] == "discussing", f"expected discussing, got {r['phase']}"
            assert r["task"] == "My task", f"task mismatch: {r['task']}"
            assert r["last_timeline_entry"] is not None, "expected timeline entry"
            assert ts in r["last_timeline_entry"], "timestamp not in last_timeline_entry"
            assert r["current_batch"] is None
            assert r["blocked_reason"] is None
            print("PASS: read_status on fresh render_initial file")

        # Case 2: after append_phase
        with tempfile.TemporaryDirectory() as tmp:
            sp = Path(tmp) / "status.md"
            sp.write_text(render_initial("T", "D", ts, "main"), encoding="utf-8")
            ts2 = "2026-04-22T16:00:00Z"
            append_phase(sp, "discussed", ts2)
            r = read_status(sp)
            assert r["phase"] == "discussed", f"expected discussed, got {r['phase']}"
            assert r["last_timeline_entry"] == f"discussed  {ts2}", (
                f"unexpected last entry: {r['last_timeline_entry']!r}"
            )
            print("PASS: read_status after append_phase")

        # Case 3: current_batch from running batch
        with tempfile.TemporaryDirectory() as tmp:
            sp = Path(tmp) / "status.md"
            sp.write_text(render_initial("T", "D", ts, "main"), encoding="utf-8")
            init_batches(sp, ["b1", "b2"])
            set_batch_field(sp, "b1", "state", "running")
            r = read_status(sp)
            assert r["current_batch"] == "b1", f"expected b1, got {r['current_batch']}"
            print("PASS: read_status current_batch from running batch")

        # Case 4: ValueError on missing file
        try:
            read_status(Path("/nonexistent/status.md"))
            assert False, "expected ValueError"
        except ValueError:
            pass
        print("PASS: read_status raises ValueError on missing file")

        # Case 5: ValueError on file with no yaml block
        with tempfile.TemporaryDirectory() as tmp:
            sp = Path(tmp) / "status.md"
            sp.write_text("# Status\n\nNo fenced block here.\n", encoding="utf-8")
            try:
                read_status(sp)
                assert False, "expected ValueError"
            except ValueError:
                pass
        print("PASS: read_status raises ValueError on no yaml block")

        # Case 6: missing task: key — no exception, full shape check
        with tempfile.TemporaryDirectory() as tmp:
            sp = Path(tmp) / "status.md"
            minimal = "# Status\n\n```yaml\nphase: planning\n```\n"
            sp.write_text(minimal, encoding="utf-8")
            r = read_status(sp)
            assert r["task"] is None, f"task should be None, got {r['task']}"
            assert r["phase"] == "planning"
            assert r["current_batch"] is None
            assert r["blocked_reason"] is None
            assert r["last_timeline_entry"] is None
        print("PASS: read_status missing task: key returns None with full shape")

        # Case 7: malformed ## Batches section raises ValueError
        with tempfile.TemporaryDirectory() as tmp:
            sp = Path(tmp) / "status.md"
            sp.write_text(render_initial("T", "D", ts, "main"), encoding="utf-8")
            # Append a malformed Batches section (unclosed yaml fence)
            with open(sp, "a", encoding="utf-8") as f:
                f.write("\n## Batches\n\n```yaml\nbatches:\n  - name: b1\n")
            try:
                read_status(sp)
                assert False, "expected ValueError"
            except ValueError:
                pass
        print("PASS: read_status raises ValueError on malformed ## Batches")

        print("All _status unit tests passed.")
        return 0
    except AssertionError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
