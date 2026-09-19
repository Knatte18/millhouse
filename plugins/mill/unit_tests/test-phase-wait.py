"""Unit tests for plugins/mill/scripts/_phase_wait.py."""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

from _phase_wait import build_wait_command, matches_wait_trigger  # noqa: E402


def main() -> int:
    try:
        cmd = build_wait_command(Path("/tmp/status.md"), "planned", 10, 7200)

        # Case 1: the ready-phase grep, CRLF-piped and trailing-anchored.
        assert (
            "tr -d '\\r' < \"/tmp/status.md\" | grep -q \"^phase: planned$\"" in cmd
        )
        print("PASS: build_wait_command contains the ready-phase grep pipeline")

        # Case 2: no bare (un-piped-through-tr) grep of status_path exists anywhere.
        for line in cmd.splitlines():
            if "grep" in line and "/tmp/status.md" in line:
                assert "tr -d '\\r' <" in line, (
                    f"found a grep reading status_path not preceded by tr -d '\\r': {line!r}"
                )
        print("PASS: build_wait_command pipes every status_path grep through tr -d '\\r'")

        # Case 3: the timeout comparison uses giveup_s verbatim.
        assert 'if [ "$elapsed" -ge 7200 ]; then' in cmd
        print("PASS: build_wait_command renders the giveup_s timeout comparison")

        # Case 4: sleep and elapsed-accumulation use poll_interval_s verbatim.
        assert "sleep 10" in cmd
        assert "elapsed=$((elapsed + 10))" in cmd
        print("PASS: build_wait_command renders the poll_interval_s sleep/accumulate lines")

        # Case 5: exactly one of each echo/exit pair, and no BLOCKED branch --
        # an upstream `blocked` phase is not terminal for this wait (it just keeps polling).
        assert cmd.count('echo "READY"') == 1
        assert "BLOCKED: " not in cmd
        assert "phase: blocked" not in cmd
        assert cmd.count("TIMEOUT after") == 1
        assert cmd.count("exit 0") == 1
        assert cmd.count("exit 2") == 1
        assert "exit 1" not in cmd
        print("PASS: build_wait_command emits exactly one echo/exit pair per outcome, no BLOCKED branch")

        # Case 6: a status_path containing a space stays double-quoted everywhere.
        spacey_cmd = build_wait_command(
            Path("/tmp/my status/status.md"), "planned", 10, 7200
        )
        assert '"/tmp/my status/status.md"' in spacey_cmd
        for line in spacey_cmd.splitlines():
            if "/tmp/my status/status.md" in line:
                assert '"/tmp/my status/status.md"' in line, (
                    f"unquoted status_path occurrence: {line!r}"
                )
        print("PASS: build_wait_command double-quotes a status_path containing spaces")

        # Case 7: the ready-phase grep pattern ends with a trailing $ anchor.
        assert 'grep -q "^phase: planned$"' in cmd
        print("PASS: build_wait_command anchors the ready-phase grep pattern with a trailing $")

        # Case 8: matches_wait_trigger — exact-set membership.
        assert matches_wait_trigger(
            "discussed",
            {"discussed", "discussing", "planning"},
            [r"^plan-review-r\d+$", r"^plan-fix-r\d+$"],
        )
        print("PASS: matches_wait_trigger matches an exact-set member")

        # Case 9: matches_wait_trigger — regex full-match.
        assert matches_wait_trigger(
            "plan-review-r1",
            {"discussed", "discussing", "planning"},
            [r"^plan-review-r\d+$", r"^plan-fix-r\d+$"],
        )
        assert matches_wait_trigger(
            "plan-fix-r12",
            {"discussed", "discussing", "planning"},
            [r"^plan-review-r\d+$", r"^plan-fix-r\d+$"],
        )
        print("PASS: matches_wait_trigger matches both regex patterns via full-match")

        # Case 10: matches_wait_trigger — non-matching phases return False.
        assert not matches_wait_trigger(
            "planned",
            {"discussed", "discussing", "planning"},
            [r"^plan-review-r\d+$", r"^plan-fix-r\d+$"],
        )
        assert not matches_wait_trigger(
            "implementing",
            {"discussed", "discussing", "planning"},
            [r"^plan-review-r\d+$", r"^plan-fix-r\d+$"],
        )
        print("PASS: matches_wait_trigger rejects non-matching phases")

        # Case 11: matches_wait_trigger — exact match with no regex patterns.
        assert matches_wait_trigger("discussing", {"discussing"}, [])
        print("PASS: matches_wait_trigger matches with an empty regex list")

        # Case 12: matches_wait_trigger — no accidental prefix widening.
        assert not matches_wait_trigger("planned", {"discussing"}, [])
        assert not matches_wait_trigger("discussion-fix-r1", {"discussing"}, [])
        print(
            "PASS: matches_wait_trigger does not accidentally match mill-start's "
            "mid-loop phase value against a narrower trigger set"
        )

        # Case 13: CRLF end-to-end execution — regression for the Windows grep-anchor bug caught in plan review round 1.
        with tempfile.TemporaryDirectory() as tmp:
            status_path = Path(tmp) / "status.md"
            # Raw bytes, bypassing Python's own newline translation, so the on-disk file is byte-for-byte CRLF-terminated regardless of the host platform running this test.
            with open(status_path, "wb") as fh:
                fh.write(b"phase: planned\r\n")

            crlf_cmd = build_wait_command(status_path, "planned", 1, 5)
            try:
                result = subprocess.run(
                    ["bash", "-c", crlf_cmd],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=False,
                )
            except FileNotFoundError:
                print(
                    "SKIP: bash not found on PATH, cannot exercise CRLF "
                    "end-to-end case"
                )
            else:
                assert result.returncode == 0, (
                    f"expected exit 0, got {result.returncode}; "
                    f"stdout={result.stdout!r} stderr={result.stderr!r}"
                )
                assert result.stdout.strip() == "READY"
                print(
                    "PASS: build_wait_command's tr -d '\\r' pipe makes the "
                    "trailing-$ anchor match a CRLF-terminated status.md line "
                    "end-to-end"
                )

        # Case 14: matches_wait_trigger — the six widened Entry-gate phase values mill-go-base/SKILL.md's "Mid-execution phase-gate widening" subsection routes on.
        widened_exact = {
            "implementing",
            "reviewing",
            "fixing",
            "self-resolved-verify-logic",
            "holistic-approved",
        }
        widened_regexes = [
            r"^approved-.*$",
            r"^reviewing-.*-r\d+$",
            r"^fixing-.*-r\d+$",
            r"^holistic-reviewing$",
        ]
        assert matches_wait_trigger("approved-foo", widened_exact, widened_regexes)
        assert matches_wait_trigger("reviewing-foo-r1", widened_exact, widened_regexes)
        assert matches_wait_trigger("fixing-foo-r3", widened_exact, widened_regexes)
        assert matches_wait_trigger("holistic-reviewing", widened_exact, widened_regexes)
        assert matches_wait_trigger(
            "self-resolved-verify-logic", widened_exact, widened_regexes
        )
        assert matches_wait_trigger("holistic-approved", widened_exact, widened_regexes)
        print(
            "PASS: matches_wait_trigger matches all six widened "
            "Entry-gate phase values"
        )

        assert not matches_wait_trigger("blocked", widened_exact, widened_regexes)
        assert not matches_wait_trigger("done", widened_exact, widened_regexes)
        # Near-miss: no trailing "-{name}", must not full-match "^approved-.*$".
        assert not matches_wait_trigger("approved", widened_exact, widened_regexes)
        print(
            "PASS: matches_wait_trigger rejects non-matching phases and the "
            "unsuffixed 'approved' near-miss against the widened set"
        )

        # Case 15: matches_wait_trigger — the Entry-gate wait's widened
        # discussion-fix-r{N} / discussion-gap-fix-r{N} patterns
        # (mill-go-base/SKILL.md's "Entry-gate wait for upstream mill-plan" section).
        entry_gate_exact = {"discussed", "discussing", "planning"}
        entry_gate_regexes = [
            r"^plan-review-r\d+$",
            r"^plan-fix-r\d+$",
            r"^discussion-fix-r\d+$",
            r"^discussion-gap-fix-r\d+$",
        ]
        assert matches_wait_trigger("discussion-fix-r3", entry_gate_exact, entry_gate_regexes)
        assert matches_wait_trigger(
            "discussion-gap-fix-r12", entry_gate_exact, entry_gate_regexes
        )
        # Near-miss: "discussion-fixed-r3" must not accidentally match "^discussion-fix-r\d+$".
        assert not matches_wait_trigger(
            "discussion-fixed-r3", entry_gate_exact, entry_gate_regexes
        )
        print(
            "PASS: matches_wait_trigger matches the Entry-gate wait's widened "
            "discussion-fix-rN/discussion-gap-fix-rN patterns without accidentally "
            "matching a near-miss string"
        )

        # Case 16: matches_wait_trigger — mill-plan's own (now-widened) 2-pattern
        # Entry-gate wait trigger list.
        mill_plan_exact = {"discussing"}
        mill_plan_regexes = [r"^discussion-fix-r\d+$", r"^discussion-gap-fix-r\d+$"]
        assert matches_wait_trigger("discussion-gap-fix-r12", mill_plan_exact, mill_plan_regexes)
        assert matches_wait_trigger("discussion-fix-r3", mill_plan_exact, mill_plan_regexes)
        assert not matches_wait_trigger("discussion-fixed-r3", mill_plan_exact, mill_plan_regexes)
        print(
            "PASS: matches_wait_trigger matches mill-plan's widened "
            "discussion-fix-rN/discussion-gap-fix-rN trigger list"
        )

        # Case 17: build_wait_command regression -- omitting the two new keyword
        # arguments reproduces today's exact output, byte-for-byte, against a
        # fixed golden string (not merely two identical live calls against
        # each other).
        expected = (
            "elapsed=0\n"
            "while true; do\n"
            "  if tr -d '\\r' < \"/tmp/status.md\" | grep -q \"^phase: planned$\"; then\n"
            "    echo \"READY\"\n"
            "    exit 0\n"
            "  fi\n"
            "  if [ \"$elapsed\" -ge 7200 ]; then\n"
            "    echo \"TIMEOUT after ${elapsed}s waiting for phase: planned\"\n"
            "    exit 2\n"
            "  fi\n"
            "  sleep 10\n"
            "  elapsed=$((elapsed + 10))\n"
            "done\n"
        )
        assert cmd == expected
        print("PASS: build_wait_command's default output matches the golden baseline byte-for-byte")

        # Case 18: build_wait_command with clean_tree_root/clean_tree_paths supplied
        # wraps the READY echo in a git-status-porcelain guard.
        clean_tree_cmd = build_wait_command(
            Path("/tmp/status.md"),
            "planned",
            10,
            7200,
            clean_tree_root=Path("/tmp/repo"),
            clean_tree_paths=[Path("/tmp/status.md"), Path("/tmp/discussion.md")],
        )
        git_status_line = 'git -C "/tmp/repo" status --porcelain -- "/tmp/status.md" "/tmp/discussion.md"'
        assert git_status_line in clean_tree_cmd
        lines = clean_tree_cmd.splitlines()
        git_status_line_idx = next(i for i, line in enumerate(lines) if git_status_line in line)
        ready_line_idx = next(i for i, line in enumerate(lines) if 'echo "READY"' in line)
        assert git_status_line_idx < ready_line_idx
        assert git_status_line in lines[git_status_line_idx]
        assert "if" in lines[git_status_line_idx]
        print(
            "PASS: build_wait_command nests echo \"READY\" inside the "
            "clean-tree git-status guard when clean_tree_root/clean_tree_paths are supplied"
        )

        # Case 19: build_wait_command raises ValueError when exactly one of
        # clean_tree_root/clean_tree_paths is supplied.
        try:
            build_wait_command(
                Path("/tmp/status.md"),
                "planned",
                10,
                7200,
                clean_tree_root=Path("/tmp/repo"),
            )
            raise AssertionError("expected ValueError for clean_tree_root without clean_tree_paths")
        except ValueError as exc:
            assert "must both be provided together" in str(exc)
        try:
            build_wait_command(
                Path("/tmp/status.md"),
                "planned",
                10,
                7200,
                clean_tree_paths=[Path("/tmp/status.md")],
            )
            raise AssertionError("expected ValueError for clean_tree_paths without clean_tree_root")
        except ValueError as exc:
            assert "must both be provided together" in str(exc)
        print(
            "PASS: build_wait_command raises ValueError when exactly one of "
            "clean_tree_root/clean_tree_paths is supplied"
        )

        # Case 20: end-to-end dirty-then-clean execution -- READY must never
        # fire while the tree is dirty, and must fire once it is clean.
        try:
            with tempfile.TemporaryDirectory() as tmp:
                subprocess.run(
                    ["git", "init", tmp],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=True,
                )
                subprocess.run(
                    ["git", "-C", tmp, "config", "user.email", "test@example.com"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=True,
                )
                subprocess.run(
                    ["git", "-C", tmp, "config", "user.name", "Test"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=True,
                )
                status_path = Path(tmp) / "status.md"
                status_path.write_text("phase: planned\n")
                subprocess.run(
                    ["git", "-C", tmp, "add", "status.md"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=True,
                )
                subprocess.run(
                    ["git", "-C", tmp, "commit", "-m", "initial commit"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=True,
                )

                dirty_cmd = build_wait_command(
                    status_path, "planned", 1, 5, clean_tree_root=Path(tmp), clean_tree_paths=[status_path]
                )

                # Make the tree dirty -- an uncommitted change to status.md, still phase: planned.
                status_path.write_text("phase: planned\n# uncommitted change\n")
                result = subprocess.run(
                    ["bash", "-c", dirty_cmd],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=False,
                )
                assert result.returncode == 2, (
                    f"expected timeout (exit 2) while tree is dirty, got {result.returncode}; "
                    f"stdout={result.stdout!r} stderr={result.stderr!r}"
                )

                # Clean the tree -- commit the pending change.
                subprocess.run(
                    ["git", "-C", tmp, "add", "status.md"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=True,
                )
                subprocess.run(
                    ["git", "-C", tmp, "commit", "-m", "clean the tree"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=True,
                )
                result = subprocess.run(
                    ["bash", "-c", dirty_cmd],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=False,
                )
                assert result.returncode == 0, (
                    f"expected READY (exit 0) once tree is clean, got {result.returncode}; "
                    f"stdout={result.stdout!r} stderr={result.stderr!r}"
                )
                assert result.stdout.strip() == "READY"
                print(
                    "PASS: build_wait_command withholds READY while the clean-tree "
                    "gate paths are dirty and fires once they are committed clean"
                )
        except FileNotFoundError:
            print(
                "SKIP: git/bash not found on PATH, cannot exercise dirty-then-clean "
                "end-to-end case"
            )

        print("All _phase_wait unit tests passed.")
        return 0
    except AssertionError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
