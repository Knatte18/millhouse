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

        # Case 2: the blocked-phase grep is CRLF-piped too, and no bare
        # (un-piped-through-tr) grep of status_path exists anywhere.
        assert (
            "tr -d '\\r' < \"/tmp/status.md\" | grep -q \"^phase: blocked$\"" in cmd
        )
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

        # Case 5: exactly one of each echo/exit trio.
        assert cmd.count('echo "READY"') == 1
        assert "BLOCKED: " in cmd
        blocked_idx = cmd.index("BLOCKED: ")
        assert "${reason}" in cmd[blocked_idx : blocked_idx + len("BLOCKED: ${reason}") + 1]
        assert cmd.count("TIMEOUT after") == 1
        assert cmd.count("exit 0") == 1
        assert cmd.count("exit 1") == 1
        assert cmd.count("exit 2") == 1
        print("PASS: build_wait_command emits exactly one echo/exit pair per outcome")

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

        # Case 7: both grep patterns end with a trailing $ anchor.
        assert 'grep -q "^phase: planned$"' in cmd
        assert 'grep -q "^phase: blocked$"' in cmd
        print("PASS: build_wait_command anchors both grep patterns with a trailing $")

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

        # Case 13: CRLF end-to-end execution — regression for the Windows
        # grep-anchor bug caught in plan review round 1.
        with tempfile.TemporaryDirectory() as tmp:
            status_path = Path(tmp) / "status.md"
            # Raw bytes, bypassing Python's own newline translation, so the
            # on-disk file is byte-for-byte CRLF-terminated regardless of
            # the host platform running this test.
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

        # Case 14: matches_wait_trigger — the six widened Entry-gate
        # phase values mill-go/SKILL.md's "Mid-execution phase-gate
        # widening" subsection routes on.
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
        # Near-miss: no trailing "-{name}", must not full-match
        # "^approved-.*$".
        assert not matches_wait_trigger("approved", widened_exact, widened_regexes)
        print(
            "PASS: matches_wait_trigger rejects non-matching phases and the "
            "unsuffixed 'approved' near-miss against the widened set"
        )

        print("All _phase_wait unit tests passed.")
        return 0
    except AssertionError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
