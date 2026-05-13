"""Unit tests for mill-fold helpers: _tasks_md additions (batch 1)."""
from __future__ import annotations

import sys
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

import _tasks_md  # noqa: E402

_HOME_MD_FIXTURE = (
    "# Tasks\n\n"
    "## Spawn Ready Task\n"
    "[spawn-ready] [s]\n"
    "\n"
    "This task is ready to spawn.\n"
    "\n"
    "## Active Task\n"
    "[active-task] [active]\n"
    "\n"
    "This task is currently active.\n"
    "\n"
    "## Done Task\n"
    "[done-task] [done]\n"
    "\n"
    "This task is already done.\n"
)


def main() -> int:
    # --- LOCKED_FOLD_PHASES constant ---
    try:
        assert _tasks_md.LOCKED_FOLD_PHASES == ("active", "ready-to-merge", "pr-pending"), (
            f"Got {_tasks_md.LOCKED_FOLD_PHASES!r}"
        )
        print("PASS: LOCKED_FOLD_PHASES has the correct value")
    except (AssertionError, Exception) as exc:
        print(f"FAIL: LOCKED_FOLD_PHASES constant: {exc}")
        return 1

    # --- append_to_body inserts before next heading ---
    try:
        result = _tasks_md.append_to_body(
            _HOME_MD_FIXTURE, "spawn-ready", "- Sources: #99 — example"
        )
        # Find the entry region for spawn-ready (up to ## Active Task)
        next_heading_pos = result.index("## Active Task")
        entry_text = result[:next_heading_pos]
        entry_lines = entry_text.rstrip("\n").splitlines()
        last_non_blank = next(line for line in reversed(entry_lines) if line.strip())
        assert last_non_blank == "- Sources: #99 — example", (
            f"Last non-blank line of entry body: {last_non_blank!r}"
        )
        # Substring from next heading onward must be unchanged
        orig_next_heading_pos = _HOME_MD_FIXTURE.index("## Active Task")
        assert result[next_heading_pos:] == _HOME_MD_FIXTURE[orig_next_heading_pos:], (
            "Substring from next heading onward was mutated"
        )
        print("PASS: append_to_body inserts before next heading with trailing blank line")
    except (AssertionError, Exception) as exc:
        print(f"FAIL: append_to_body inserts before next heading: {exc}")
        return 1

    # --- append_to_body EOF target ---
    try:
        result = _tasks_md.append_to_body(
            _HOME_MD_FIXTURE, "done-task", "- Sources: #100 — final"
        )
        bullet = "- Sources: #100 — final"
        bullet_pos = result.rindex(bullet)
        after_bullet = result[bullet_pos + len(bullet):]
        assert after_bullet == "\n", (
            f"Expected single trailing newline after bullet, got {after_bullet!r}"
        )
        assert "## " not in after_bullet
        print("PASS: append_to_body EOF target lands above single trailing newline")
    except (AssertionError, Exception) as exc:
        print(f"FAIL: append_to_body EOF target: {exc}")
        return 1

    # --- append_to_body empty body ---
    try:
        empty_fixture = "## Empty Task\n[empty-task]\n"
        result = _tasks_md.append_to_body(empty_fixture, "empty-task", "- note")
        expected = "## Empty Task\n[empty-task]\n\n- note\n"
        assert result == expected, (
            f"Empty-body result mismatch:\n  got:      {result!r}\n  expected: {expected!r}"
        )
        print("PASS: append_to_body empty body inserts blank line before bullet")
    except (AssertionError, Exception) as exc:
        print(f"FAIL: append_to_body empty body: {exc}")
        return 1

    # --- append_to_body missing slug ---
    try:
        raised = False
        try:
            _tasks_md.append_to_body(_HOME_MD_FIXTURE, "no-such-slug", "- note")
        except ValueError as exc:
            raised = True
            assert "'no-such-slug'" in str(exc), (
                f"Expected slug in repr form in error message, got: {exc}"
            )
        if not raised:
            raise AssertionError("Expected ValueError for missing slug; none was raised")
        print("PASS: append_to_body missing slug raises ValueError with slug in repr form")
    except (AssertionError, Exception) as exc:
        print(f"FAIL: append_to_body missing slug: {exc}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
