"""Unit tests for plugins/mill/scripts/_tasks_md.py."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

from _tasks_md import append_entry, claim, parse, remove_entry, set_phase, set_phase_at  # noqa: E402


def main() -> int:
    try:
        sample = (
            "# Tasks\n\n"
            "<!-- comment -->\n\n"
            "## First task\n"
            "[task-one]\n\n"
            "Summary for task-one.\n\n"
            "## Second task\n"
            "[[task-two]](proposal-task-two)\n\n"
            "Summary for task-two (with proposal).\n\n"
            "## Third task\n"
            "[task-three] [s]\n\n"
            "Summary for task-three, already spawn-ready.\n"
        )
        parsed = parse(sample)
        assert len(parsed) == 3, f"Expected 3 tasks, got {len(parsed)}"
        assert parsed[0].slug == "task-one" and parsed[0].phase is None
        assert parsed[1].slug == "task-two" and parsed[1].has_proposal
        assert parsed[2].phase == "s"
        print("PASS: parse() returns 3 tasks with correct slugs/phases/proposals")

        claimed = claim(sample, "task-one")
        reparsed = parse(claimed)
        assert reparsed[0].phase == "active", f"Expected active, got {reparsed[0].phase!r}"
        print("PASS: claim() sets [active] on the target heading")

        cleared = set_phase(claimed, "task-one", None)
        assert parse(cleared)[0].phase is None
        print("PASS: set_phase(..., None) strips the marker")

        try:
            claim(sample, "does-not-exist")
        except ValueError as exc:
            print(f"PASS: claim() raises on unknown slug ({exc})")
        else:
            raise AssertionError("Expected ValueError for unknown slug")

        # --- append_entry ---

        home = "# Tasks\n\n## Existing\n[existing]\n\nExisting body.\n"
        result = append_entry(home, "new-task", "New Task", "Task body.")
        tasks = parse(result)
        assert tasks[-1].slug == "new-task"
        assert "## New Task\n[new-task]\n\nTask body.\n" in result
        assert result.count("\n\n## New Task") == 1
        print("PASS: append_entry round-trip with non-empty body")

        result_empty_body = append_entry(home, "empty-body", "Empty Body", "")
        assert result_empty_body.endswith("## Empty Body\n[empty-body]\n")
        assert "## Empty Body\n[empty-body]\n\n" not in result_empty_body
        print("PASS: append_entry with empty body: heading + slug line + single newline")

        result_proposal = append_entry(home, "prop-task", "Prop Task", "Body.", has_proposal=True)
        assert "[[prop-task]](proposal-prop-task)" in result_proposal
        print("PASS: append_entry with has_proposal=True emits link form")

        try:
            append_entry(home, "Bad-Slug", "Bad", "")
        except ValueError as exc:
            assert "Bad-Slug" in str(exc)
            print("PASS: append_entry raises ValueError for invalid slug")
        else:
            raise AssertionError("Expected ValueError for invalid slug")

        empty_home = ""
        result_empty = append_entry(empty_home, "first", "First", "Body.")
        assert "## First\n[first]\n\nBody.\n" in result_empty
        print("PASS: append_entry into empty Home.md")

        # --- remove_entry ---

        multi = (
            "# Tasks\n\n"
            "## Alpha\n[alpha]\n\nAlpha body.\n\n"
            "## Beta\n[beta]\n\nBeta body.\n\n"
            "## Gamma\n[gamma]\n\nGamma body.\n"
        )
        after_remove_alpha = remove_entry(multi, "alpha")
        remaining = parse(after_remove_alpha)
        assert [t.slug for t in remaining] == ["beta", "gamma"]
        assert "Alpha" not in after_remove_alpha
        print("PASS: remove_entry round-trip removes target")

        after_remove_beta = remove_entry(multi, "beta")
        expected_middle = (
            "# Tasks\n\n"
            "## Alpha\n[alpha]\n\nAlpha body.\n\n"
            "## Gamma\n[gamma]\n\nGamma body.\n"
        )
        assert after_remove_beta == expected_middle, (
            f"remove middle byte-perfect FAIL:\n{repr(after_remove_beta)}\n!=\n{repr(expected_middle)}"
        )
        print("PASS: remove_entry middle entry preserves surrounding entries byte-perfect")

        after_remove_gamma = remove_entry(multi, "gamma")
        assert parse(after_remove_gamma)[-1].slug == "beta"
        assert after_remove_gamma.endswith("Beta body.\n")
        print("PASS: remove_entry last entry")

        only = "# Tasks\n\n## Only\n[only]\n\nOnly body.\n"
        after_only = remove_entry(only, "only")
        assert parse(after_only) == []
        assert after_only.endswith("\n")
        assert not after_only.endswith("\n\n")
        print("PASS: remove_entry only entry leaves clean file")

        try:
            remove_entry(multi, "does-not-exist")
        except ValueError as exc:
            assert "does-not-exist" in str(exc)
            print("PASS: remove_entry unknown slug raises ValueError")
        else:
            raise AssertionError("Expected ValueError for unknown slug")

        # remove-then-append round-trip
        after_remove = remove_entry(multi, "beta")
        after_append = append_entry(after_remove, "beta", "Beta", "Beta body.")
        slugs = [t.slug for t in parse(after_append)]
        assert "alpha" in slugs and "gamma" in slugs and "beta" in slugs
        print("PASS: remove-then-append round-trip")

        # --- set_phase_at ---

        home_text = (
            "# Tasks\n\n"
            "## My Task\n"
            "[my-task]\n\n"
            "Body.\n"
        )

        # (a) happy path: set_phase_at writes updated text back to path
        with tempfile.NamedTemporaryFile(
            "w", suffix=".md", delete=False, encoding="utf-8"
        ) as tmp:
            tmp.write(home_text)
            tmp_path = Path(tmp.name)
        try:
            set_phase_at(tmp_path, "my-task", "done")
            written = tmp_path.read_text(encoding="utf-8")
            assert "[done]" in written, f"expected [done] in {written!r}"
            assert parse(written)[0].phase == "done"
            print("PASS: set_phase_at happy path writes [done] back to file")

            # (d) round-trip with phase=None strips existing marker
            set_phase_at(tmp_path, "my-task", None)
            cleared = tmp_path.read_text(encoding="utf-8")
            assert "[done]" not in cleared
            assert parse(cleared)[0].phase is None
            print("PASS: set_phase_at phase=None strips existing marker")
        finally:
            tmp_path.unlink()

        # (b) unknown slug raises ValueError
        with tempfile.NamedTemporaryFile(
            "w", suffix=".md", delete=False, encoding="utf-8"
        ) as tmp:
            tmp.write(home_text)
            tmp_path = Path(tmp.name)
        try:
            try:
                set_phase_at(tmp_path, "no-such-slug", "done")
            except ValueError as exc:
                assert "no-such-slug" in str(exc)
                print(f"PASS: set_phase_at raises ValueError for unknown slug ({exc})")
            else:
                raise AssertionError("Expected ValueError for unknown slug")
        finally:
            tmp_path.unlink()

        # (c) invalid phase raises ValueError
        with tempfile.NamedTemporaryFile(
            "w", suffix=".md", delete=False, encoding="utf-8"
        ) as tmp:
            tmp.write(home_text)
            tmp_path = Path(tmp.name)
        try:
            try:
                set_phase_at(tmp_path, "my-task", "invalid-phase")
            except ValueError as exc:
                assert "invalid-phase" in str(exc) or "Invalid phase" in str(exc)
                print(f"PASS: set_phase_at raises ValueError for invalid phase ({exc})")
            else:
                raise AssertionError("Expected ValueError for invalid phase")
        finally:
            tmp_path.unlink()

        print("All _tasks_md unit tests passed.")
        return 0
    except AssertionError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
