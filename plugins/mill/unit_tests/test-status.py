"""Unit tests for plugins/mill/scripts/_status.py."""
from __future__ import annotations

import contextlib
import io
import re
import sys
import tempfile
from pathlib import Path

import yaml

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

from _status import (  # noqa: E402
    append_phase,
    init_batches,
    read_batches,
    read_branch,
    read_full,
    read_slug,
    read_status,
    render_initial,
    set_batch_field,
    set_batch_fields,
    set_blocked,
    update_field,
)
from _yaml_writer import quote_scalar  # noqa: E402


def main() -> int:
    try:
        out = render_initial(
            task_title="Fix bug in widget handler",
            task_description="Widgets throw on empty input.",
            timestamp="2026-04-22T14:32:05Z",
            parent_branch="main",
            slug="t-slug",
            branch="hanf/t-slug",
        )
        assert out.startswith("# Status\n"), "Leading HTML comment should be stripped"
        assert "Fix bug in widget handler" in out
        assert "2026-04-22T14:32:05Z" in out
        assert "parent: main" in out
        assert "<TASK_TITLE>" not in out and "<TIMESTAMP>" not in out
        print("PASS: render_initial() substitutes tokens and strips header")

        # Colon in task_title: YAML must parse cleanly.
        out_colon = render_initial(
            task_title="contains: colon",
            task_description="Desc.",
            timestamp="2026-04-22T14:32:05Z",
            parent_branch="main",
            slug="t-slug",
            branch="hanf/t-slug",
        )
        top_block_colon = "\n".join(
            out_colon.splitlines()[
                out_colon.splitlines().index("```yaml") + 1 :
                out_colon.splitlines().index("```", out_colon.splitlines().index("```yaml") + 1)
            ]
        )
        parsed_colon = yaml.safe_load(top_block_colon)
        assert parsed_colon["task"] == "contains: colon", (
            f"colon in task_title not round-tripped: {parsed_colon['task']!r}"
        )
        print("PASS: render_initial colon in task_title round-trips via yaml.safe_load")

        # task_description with colon stays correct via block scalar.
        out_desc = render_initial(
            task_title="plain title",
            task_description="single line with: colon",
            timestamp="2026-04-22T14:32:05Z",
            parent_branch="main",
            slug="t-slug",
            branch="hanf/t-slug",
        )
        top_block_desc = "\n".join(
            out_desc.splitlines()[
                out_desc.splitlines().index("```yaml") + 1 :
                out_desc.splitlines().index("```", out_desc.splitlines().index("```yaml") + 1)
            ]
        )
        parsed_desc = yaml.safe_load(top_block_desc)
        assert parsed_desc["task_description"].strip() == "single line with: colon", (
            f"block-scalar task_description colon not preserved: {parsed_desc['task_description']!r}"
        )
        print("PASS: render_initial block-scalar task_description preserves colon")

        # Safe input stability: plain title emits bare scalar (no extra quotes).
        out_plain = render_initial(
            task_title="plain title",
            task_description="Desc.",
            timestamp="2026-04-22T14:32:05Z",
            parent_branch="main",
            slug="t-slug",
            branch="hanf/t-slug",
        )
        assert "task: plain title" in out_plain, (
            f"safe input should emit bare scalar: {out_plain!r}"
        )
        print("PASS: render_initial plain title emits bare scalar (output stability)")

        with tempfile.TemporaryDirectory() as tmp:
            sp = Path(tmp) / "status.md"
            sp.write_text(out, encoding="utf-8")

            update_field(sp, "task", "Updated title")
            assert "task: Updated title" in sp.read_text(encoding="utf-8")
            print("PASS: update_field rewrites a scalar yaml row")

            update_field(sp, "task", "Updated: with colon")
            uf_block = "\n".join(
                sp.read_text(encoding="utf-8").splitlines()[
                    sp.read_text(encoding="utf-8").splitlines().index("```yaml") + 1 :
                    sp.read_text(encoding="utf-8").splitlines().index(
                        "```",
                        sp.read_text(encoding="utf-8").splitlines().index("```yaml") + 1,
                    )
                ]
            )
            assert yaml.safe_load(uf_block)["task"] == "Updated: with colon", (
                f"update_field colon round-trip failed: {yaml.safe_load(uf_block)['task']!r}"
            )
            print("PASS: update_field quotes a value with colon")

            append_phase(sp, "discussed", "2026-04-22T15:00:00Z")
            contents = sp.read_text(encoding="utf-8")
            assert "phase: discussed" in contents, "phase yaml row not updated"
            assert "discussed  '2026-04-22T15:00:00Z'" in contents, "timeline row not appended"
            print("PASS: append_phase updates phase yaml + appends timeline row")

        # Colon in phase round-trip — separate file to avoid contaminating shared sp.
        with tempfile.TemporaryDirectory() as tmp:
            sp_weird = Path(tmp) / "status.md"
            sp_weird.write_text(out, encoding="utf-8")
            append_phase(sp_weird, "weird: phase", "2026-04-22T16:00:00Z")
            data_weird = read_full(sp_weird)
            assert data_weird["yaml"]["phase"] == "weird: phase", (
                f"append_phase colon round-trip failed: {data_weird['yaml']['phase']!r}"
            )
            print("PASS: append_phase quotes phase with colon")

        # --- set_blocked tests ---

        # Test 1: set_blocked happy path on fresh status.
        with tempfile.TemporaryDirectory() as tmp:
            sp = Path(tmp) / "status.md"
            sp.write_text(
                render_initial("T", "D", "2026-05-12T00:00:00Z", "main", slug="t-slug", branch="hanf/t-slug"),
                encoding="utf-8",
            )
            set_blocked(sp, "auto: discussion review gaps unresolved after 2 rounds", timestamp="2026-05-12T01:00:00Z")
            r = read_status(sp)
            assert r["phase"] == "blocked", f"expected blocked, got {r['phase']!r}"
            assert r["blocked_reason"] == "auto: discussion review gaps unresolved after 2 rounds", (
                f"blocked_reason mismatch: {r['blocked_reason']!r}"
            )
            assert re.match(r"^blocked\s+'2026-05-12T01:00:00Z'$", r["last_timeline_entry"]), (
                f"unexpected last_timeline_entry: {r['last_timeline_entry']!r}"
            )
            print("PASS: set_blocked happy path on fresh status")

        # Test 2: set_blocked inserts blocked_reason directly after phase: when absent.
        with tempfile.TemporaryDirectory() as tmp:
            sp = Path(tmp) / "status.md"
            sp.write_text(
                render_initial("T", "D", "2026-05-12T00:00:00Z", "main", slug="t-slug", branch="hanf/t-slug"),
                encoding="utf-8",
            )
            set_blocked(sp, "auto: discussion review gaps unresolved after 2 rounds", timestamp="2026-05-12T01:00:00Z")
            file_text = sp.read_text(encoding="utf-8")
            text_lines = file_text.splitlines()
            phase_index = None
            for idx, line in enumerate(text_lines):
                if line.strip().startswith("phase:"):
                    phase_index = idx
                    break
            assert phase_index is not None, "phase: row not found in file"
            assert text_lines[phase_index + 1].startswith("blocked_reason:"), (
                f"expected blocked_reason: at index {phase_index + 1}, got {text_lines[phase_index + 1]!r}"
            )
            print("PASS: set_blocked inserts blocked_reason directly after phase:")

        # Test 3: set_blocked rewrites blocked_reason in place when already present.
        with tempfile.TemporaryDirectory() as tmp:
            sp = Path(tmp) / "status.md"
            content = render_initial("T", "D", "2026-05-12T00:00:00Z", "main", slug="t-slug", branch="hanf/t-slug")
            content = content.replace(
                "phase: discussing\n",
                f"phase: discussing\nblocked_reason: {quote_scalar('foo')}\n",
            )
            sp.write_text(content, encoding="utf-8")
            set_blocked(sp, "new reason", timestamp="2026-05-12T01:00:00Z")
            file_text = sp.read_text(encoding="utf-8")
            assert file_text.count("blocked_reason:") == 1, (
                f"expected exactly one blocked_reason: row, got {file_text.count('blocked_reason:')}"
            )
            expected_br = f"blocked_reason: {quote_scalar('new reason')}"
            assert expected_br in file_text, (
                f"rewritten blocked_reason not found; expected {expected_br!r}"
            )
            assert "foo" not in file_text, "old blocked_reason value 'foo' still present"
            print("PASS: set_blocked rewrites blocked_reason in place")

        # Test 4: append_phase quoting regression.
        with tempfile.TemporaryDirectory() as tmp:
            sp = Path(tmp) / "status.md"
            sp.write_text(
                render_initial("T", "D", "2026-05-12T00:00:00Z", "main", slug="t-slug", branch="hanf/t-slug"),
                encoding="utf-8",
            )
            append_phase(sp, "planning", "2026-05-12T02:00:00Z")
            file_text = sp.read_text(encoding="utf-8")
            lines_all = file_text.splitlines()
            in_tl = False
            tl_lines_content = []
            for line in lines_all:
                if line.strip() == "```text":
                    in_tl = True
                    continue
                if in_tl and line.strip() == "```":
                    break
                if in_tl and line.strip():
                    tl_lines_content.append(line.strip())
            last_tl = tl_lines_content[-1] if tl_lines_content else ""
            assert re.match(r"^planning\s+'2026-05-12T02:00:00Z'$", last_tl), (
                f"unexpected quoted timeline row: {last_tl!r}"
            )
            print("PASS: append_phase writes quoted timestamp in timeline row")

        with tempfile.TemporaryDirectory() as tmp:
            sp = Path(tmp) / "status.md"
            sp.write_text(out, encoding="utf-8")
            append_phase(sp, "discussed", "2026-04-22T15:00:00Z")

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
            assert "discussed  '2026-04-22T15:00:00Z'" in contents, "batches edit damaged timeline"
            print("PASS: batches edits preserve top yaml + timeline")

            set_batch_field(sp, "foundation", "blocked_reason", "missing key: foo")
            batches_colon = read_batches(sp)
            entry_colon = next(b for b in batches_colon if b["name"] == "foundation")
            assert entry_colon["blocked_reason"] == "missing key: foo", (
                f"blocked_reason colon not round-tripped: {entry_colon['blocked_reason']!r}"
            )
            print("PASS: _serialise_batches quotes str blocked_reason with colon")

            set_batch_field(sp, "foundation", "review_round", 3)
            batches_int = read_batches(sp)
            entry_int = next(b for b in batches_int if b["name"] == "foundation")
            assert entry_int["review_round"] == 3, (
                f"review_round should be int 3, got {entry_int['review_round']!r}"
            )
            print("PASS: _serialise_batches leaves int review_round unquoted")

        # --- read_status tests ---
        ts = "2026-04-22T14:32:05Z"

        # Case 1: freshly-rendered file
        with tempfile.TemporaryDirectory() as tmp:
            sp = Path(tmp) / "status.md"
            sp.write_text(
                render_initial("My task", "Desc.", ts, "main", slug="t-slug", branch="hanf/t-slug"), encoding="utf-8"
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
            sp.write_text(render_initial("T", "D", ts, "main", slug="t-slug", branch="hanf/t-slug"), encoding="utf-8")
            ts2 = "2026-04-22T16:00:00Z"
            append_phase(sp, "discussed", ts2)
            r = read_status(sp)
            assert r["phase"] == "discussed", f"expected discussed, got {r['phase']}"
            assert r["last_timeline_entry"] == f"discussed  '{ts2}'", (
                f"unexpected last entry: {r['last_timeline_entry']!r}"
            )
            print("PASS: read_status after append_phase")

        # Case 3: current_batch from running batch
        with tempfile.TemporaryDirectory() as tmp:
            sp = Path(tmp) / "status.md"
            sp.write_text(render_initial("T", "D", ts, "main", slug="t-slug", branch="hanf/t-slug"), encoding="utf-8")
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
            sp.write_text(render_initial("T", "D", ts, "main", slug="t-slug", branch="hanf/t-slug"), encoding="utf-8")
            # Append a malformed Batches section (unclosed yaml fence)
            with open(sp, "a", encoding="utf-8") as f:
                f.write("\n## Batches\n\n```yaml\nbatches:\n  - name: b1\n")
            try:
                read_status(sp)
                assert False, "expected ValueError"
            except ValueError:
                pass
        print("PASS: read_status raises ValueError on malformed ## Batches")

        # --- read_full tests ---
        ts_full = "2026-04-23T10:00:00Z"

        # Case F1: basic full read — yaml dict + timeline list
        with tempfile.TemporaryDirectory() as tmp:
            sp = Path(tmp) / "status.md"
            initial = render_initial("Full task", "Desc.", ts_full, "main", slug="t-slug", branch="hanf/t-slug")
            sp.write_text(initial, encoding="utf-8")
            append_phase(sp, "discussed", "2026-04-23T11:00:00Z")
            r = read_full(sp)
            assert isinstance(r["yaml"], dict), "yaml should be a dict"
            assert r["yaml"]["phase"] == "discussed", f"phase mismatch: {r['yaml']['phase']}"
            assert r["yaml"]["task"] == "Full task", f"task mismatch: {r['yaml']['task']}"
            assert "parent" in r["yaml"], "parent key should be present"
            assert isinstance(r["timeline"], list), "timeline should be a list"
            assert len(r["timeline"]) == 2, f"expected 2 timeline entries, got {len(r['timeline'])}"
            assert any("discussing" in line for line in r["timeline"]), "discussing entry missing"
            assert any("discussed" in line for line in r["timeline"]), "discussed entry missing"
        print("PASS: read_full basic yaml + timeline")

        # Case F2: empty timeline block
        with tempfile.TemporaryDirectory() as tmp:
            sp = Path(tmp) / "status.md"
            empty_tl = "# Status\n\n```yaml\nphase: planning\ntask: T\n```\n\n## Timeline\n\n```text\n```\n"
            sp.write_text(empty_tl, encoding="utf-8")
            r = read_full(sp)
            assert r["timeline"] == [], f"expected empty timeline, got {r['timeline']}"
        print("PASS: read_full empty timeline returns []")

        # Case F3: missing file raises ValueError
        try:
            read_full(Path("/nonexistent/status.md"))
            assert False, "expected ValueError"
        except ValueError:
            pass
        print("PASS: read_full raises ValueError on missing file")

        # --- render_initial new fields ---
        with tempfile.TemporaryDirectory() as tmp:
            rendered = render_initial(
                task_title="New Task",
                task_description="Desc.",
                timestamp="2026-04-28T10:00:00Z",
                parent_branch="main",
                slug="my-slug",
                branch="hanf/my-slug",
            )
            assert "slug: my-slug" in rendered, "slug row missing from rendered output"
            assert "branch: hanf/my-slug" in rendered, "branch row missing from rendered output"
            print("PASS: render_initial includes slug and branch rows")
            assert "<SLUG>" not in rendered and "<BRANCH>" not in rendered, (
                "unresolved SLUG/BRANCH tokens in render_initial output"
            )
            print("PASS: render_initial has no unresolved SLUG/BRANCH tokens")

            # plan: null pre-seed: update_field("plan", …) must not raise.
            sp_plan = Path(tmp) / "status-plan.md"
            sp_plan.write_text(rendered, encoding="utf-8")
            update_field(sp_plan, "plan", "active/yaml-colon-quoting/plan")
            data_plan = read_full(sp_plan)
            assert data_plan["yaml"]["plan"] == "active/yaml-colon-quoting/plan", (
                f"plan field not round-tripped: {data_plan['yaml']['plan']!r}"
            )
            print("PASS: status-discussing template seeds plan: null; update_field('plan', …) does not raise")

        # --- read_slug ---
        # Case A: slug: present in yaml block
        with tempfile.TemporaryDirectory() as tmp:
            sp = Path(tmp) / "status.md"
            content = render_initial(
                task_title="T",
                task_description="D",
                timestamp="2026-04-28T10:00:00Z",
                parent_branch="main",
                slug="foo",
                branch="hanf/foo",
            )
            sp.write_text(content, encoding="utf-8")
            assert read_slug(sp) == "foo", f"expected 'foo', got {read_slug(sp)!r}"
            print("PASS: read_slug returns slug from yaml block")

        # Case B: slug absent — falls back to parent dir name
        with tempfile.TemporaryDirectory() as tmp:
            slug_dir = Path(tmp) / "some-name"
            slug_dir.mkdir()
            sp = slug_dir / "status.md"
            sp.write_text(
                "# Status\n\n```yaml\nphase: discussing\n```\n\n## Timeline\n\n```text\n```\n",
                encoding="utf-8",
            )
            buf = io.StringIO()
            with contextlib.redirect_stderr(buf):
                result = read_slug(sp)
            assert result == "some-name", f"expected 'some-name', got {result!r}"
            assert buf.getvalue() == "", f"expected no stderr on slug fallback, got {buf.getvalue()!r}"
            print("PASS: read_slug falls back silently to parent dir name")

        # --- read_branch ---
        # Case A: branch: present in yaml block
        with tempfile.TemporaryDirectory() as tmp:
            sp = Path(tmp) / "status.md"
            content = render_initial(
                task_title="T",
                task_description="D",
                timestamp="2026-04-28T10:00:00Z",
                parent_branch="main",
                slug="foo",
                branch="hanf/foo",
            )
            sp.write_text(content, encoding="utf-8")
            buf = io.StringIO()
            with contextlib.redirect_stderr(buf):
                result = read_branch(sp, cfg={"spawn": {"branch_prefix": "hanf"}}, slug="foo")
            assert result == "hanf/foo", f"expected 'hanf/foo', got {result!r}"
            assert buf.getvalue() == "", f"expected no stderr when branch present, got {buf.getvalue()!r}"
            print("PASS: read_branch returns branch from yaml block, no warning")

        # Case B: branch absent — derived from prefix + slug
        with tempfile.TemporaryDirectory() as tmp:
            sp = Path(tmp) / "status.md"
            sp.write_text(
                "# Status\n\n```yaml\nphase: discussing\n```\n\n## Timeline\n\n```text\n```\n",
                encoding="utf-8",
            )
            buf = io.StringIO()
            with contextlib.redirect_stderr(buf):
                result = read_branch(sp, cfg={"spawn": {"branch_prefix": "hanf"}}, slug="foo")
            assert result == "hanf/foo", f"expected 'hanf/foo', got {result!r}"
            stderr_out = buf.getvalue()
            assert "[_status] warning" in stderr_out, f"expected warning in stderr, got {stderr_out!r}"
            assert "slug=foo" in stderr_out, f"expected slug=foo in warning, got {stderr_out!r}"
            print("PASS: read_branch derives from prefix+slug and emits warning")

        # Case C: empty branch_prefix — bare slug, warning still emitted
        with tempfile.TemporaryDirectory() as tmp:
            sp = Path(tmp) / "status.md"
            sp.write_text(
                "# Status\n\n```yaml\nphase: discussing\n```\n\n## Timeline\n\n```text\n```\n",
                encoding="utf-8",
            )
            buf = io.StringIO()
            with contextlib.redirect_stderr(buf):
                result = read_branch(sp, cfg={"spawn": {"branch_prefix": ""}}, slug="foo")
            assert result == "foo", f"expected 'foo', got {result!r}"
            assert "[_status] warning" in buf.getvalue(), "expected warning for empty prefix fallback"
            print("PASS: read_branch with empty prefix returns bare slug with warning")

        # --- set_batch_fields tests ---
        ts_sbf = "2026-04-22T14:32:05Z"
        _out_sbf = render_initial("T", "D", ts_sbf, "main", slug="t-slug", branch="hanf/t-slug")

        # Success path: multiple fields written atomically
        with tempfile.TemporaryDirectory() as tmp:
            sp = Path(tmp) / "status.md"
            sp.write_text(_out_sbf, encoding="utf-8")
            init_batches(sp, ["foundation", "reviewers"])
            set_batch_fields(sp, "foundation", {"state": "running", "implementer_session": "sess123", "start_sha": "abc"})
            entry = next(b for b in read_batches(sp) if b["name"] == "foundation")
            assert entry["state"] == "running", f"state mismatch: {entry['state']!r}"
            assert entry["implementer_session"] == "sess123", f"session mismatch: {entry['implementer_session']!r}"
            assert entry["start_sha"] == "abc", f"start_sha mismatch: {entry['start_sha']!r}"
        print("PASS: set_batch_fields writes multiple fields atomically")

        # Unknown key raises ValueError
        with tempfile.TemporaryDirectory() as tmp:
            sp = Path(tmp) / "status.md"
            sp.write_text(_out_sbf, encoding="utf-8")
            init_batches(sp, ["foundation"])
            try:
                set_batch_fields(sp, "foundation", {"nope": "x"})
                assert False, "expected ValueError"
            except ValueError:
                pass
        print("PASS: set_batch_fields rejects unknown key")

        # Unknown state raises ValueError
        with tempfile.TemporaryDirectory() as tmp:
            sp = Path(tmp) / "status.md"
            sp.write_text(_out_sbf, encoding="utf-8")
            init_batches(sp, ["foundation"])
            try:
                set_batch_fields(sp, "foundation", {"state": "finished"})
                assert False, "expected ValueError"
            except ValueError:
                pass
        print("PASS: set_batch_fields rejects unknown state")

        # Unknown batch name raises ValueError
        with tempfile.TemporaryDirectory() as tmp:
            sp = Path(tmp) / "status.md"
            sp.write_text(_out_sbf, encoding="utf-8")
            init_batches(sp, ["foundation"])
            try:
                set_batch_fields(sp, "missing", {"state": "running"})
                assert False, "expected ValueError"
            except ValueError:
                pass
        print("PASS: set_batch_fields rejects unknown batch name")

        print("All _status unit tests passed.")
        return 0
    except AssertionError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
