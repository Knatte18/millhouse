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

        print("All _status unit tests passed.")
        return 0
    except AssertionError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
