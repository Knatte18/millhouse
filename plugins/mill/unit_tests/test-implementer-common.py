"""Unit tests for _implementer_common._forward_output inference paths."""
from __future__ import annotations

import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest.mock
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

from _implementer_common import _forward_output, emit_prepare, emit_prepare_no_dispatch, finalize_from_output, _is_formatter_drift_only, _commit_formatter_drift  # noqa: E402
import _cleanliness  # noqa: E402


def _capture_stdout(fn):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = fn()
    return rc, buf.getvalue()


def _setup_fixture(project_root: Path) -> str:
    """Init git repo with a README.md base commit; return base SHA."""
    subprocess.run(["git", "init", "-q", str(project_root)], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(project_root), "config", "user.email", "test@test.com"],
        check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(project_root), "config", "user.name", "Test"],
        check=True, capture_output=True,
    )
    (project_root / "README.md").write_text("seed", encoding="utf-8")
    subprocess.run(
        ["git", "-C", str(project_root), "add", "README.md"],
        check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(project_root), "commit", "-m", "initial"],
        check=True, capture_output=True,
    )
    return subprocess.run(
        ["git", "-C", str(project_root), "rev-parse", "HEAD"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()


def main() -> int:
    errors = 0

    # Case 1: inferred success — clean worktree + new commit
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        base_sha = _setup_fixture(project_root)
        snapshot_path = project_root / "_mill" / ".cleanliness-snapshot-test.txt"
        _cleanliness.capture_snapshot(project_root, snapshot_path)
        subprocess.run(
            ["git", "-C", str(project_root), "commit", "--allow-empty", "-m", "second"],
            check=True, capture_output=True,
        )
        new_head = subprocess.run(
            ["git", "-C", str(project_root), "rev-parse", "HEAD"],
            check=True, capture_output=True, text=True,
        ).stdout.strip()
        rc, captured = _capture_stdout(
            lambda: _forward_output(
                "garbage with no json",
                project_root,
                start_sha=base_sha,
                snapshot_path=snapshot_path,
            )
        )
        try:
            data = json.loads(captured.strip())
            assert data["status"] == "success", f"expected status=success, got {data}"
            assert data.get("inferred") is True, f"expected inferred=True, got {data}"
            assert data["commit_sha"] == new_head, f"expected commit_sha={new_head}, got {data}"
            print("PASS: inferred success - clean worktree + new commit -> success with inferred=True")
        except Exception as exc:
            print(f"FAIL: case 1 ({exc}) captured={captured!r}", file=sys.stderr)
            errors += 1

    # Case 2: no new commits -> no inference -> stuck/logic
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        base_sha = _setup_fixture(project_root)
        snapshot_path = project_root / "_mill" / ".cleanliness-snapshot-test.txt"
        _cleanliness.capture_snapshot(project_root, snapshot_path)
        # NO new commit — HEAD == start_sha
        rc, captured = _capture_stdout(
            lambda: _forward_output(
                "garbage",
                project_root,
                start_sha=base_sha,
                snapshot_path=snapshot_path,
            )
        )
        try:
            data = json.loads(captured.strip())
            assert data["status"] == "stuck", f"expected status=stuck, got {data}"
            assert data["stuck_type"] == "logic", f"expected stuck_type=logic, got {data}"
            print("PASS: no new commits -> stuck/logic (inference skipped: HEAD == start_sha)")
        except Exception as exc:
            print(f"FAIL: case 2 ({exc}) captured={captured!r}", file=sys.stderr)
            errors += 1

    # Case 3: dirty worktree -> no inference -> stuck/logic
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        base_sha = _setup_fixture(project_root)
        snapshot_path = project_root / "_mill" / ".cleanliness-snapshot-test.txt"
        _cleanliness.capture_snapshot(project_root, snapshot_path)
        # New commit so HEAD != start_sha
        subprocess.run(
            ["git", "-C", str(project_root), "commit", "--allow-empty", "-m", "second"],
            check=True, capture_output=True,
        )
        # Dirty already-tracked README.md without committing
        (project_root / "README.md").write_text("dirty", encoding="utf-8")
        rc, captured = _capture_stdout(
            lambda: _forward_output(
                "garbage",
                project_root,
                start_sha=base_sha,
                snapshot_path=snapshot_path,
            )
        )
        try:
            data = json.loads(captured.strip())
            assert data["status"] == "stuck", f"expected status=stuck, got {data}"
            assert data["stuck_type"] == "logic", f"expected stuck_type=logic, got {data}"
            print("PASS: dirty worktree -> stuck/logic (inference skipped: compute_new_dirt non-empty)")
        except Exception as exc:
            print(f"FAIL: case 3 ({exc}) captured={captured!r}", file=sys.stderr)
            errors += 1

    # Case 3b: pre-existing dirt survives in full-tree check -> stuck/logic
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        base_sha = _setup_fixture(project_root)
        snapshot_path = project_root / "_mill" / ".cleanliness-snapshot-test.txt"
        # Dirty README.md before snapshot — simulates pre-existing worktree dirt from a prior batch
        (project_root / "README.md").write_text("pre-existing dirty", encoding="utf-8")
        _cleanliness.capture_snapshot(project_root, snapshot_path)
        # New commit so HEAD != start_sha
        subprocess.run(
            ["git", "-C", str(project_root), "commit", "--allow-empty", "-m", "second"],
            check=True, capture_output=True,
        )
        new_head = subprocess.run(
            ["git", "-C", str(project_root), "rev-parse", "HEAD"],
            check=True, capture_output=True, text=True,
        ).stdout.strip()
        # README.md remains dirty (pre-existing) — implementer added no new dirt
        rc, captured = _capture_stdout(
            lambda: _forward_output(
                "garbage with no json",
                project_root,
                start_sha=base_sha,
                snapshot_path=snapshot_path,
            )
        )
        try:
            data = json.loads(captured.strip())
            assert data["status"] == "stuck", f"expected status=stuck, got {data}"
            assert data["stuck_type"] == "logic", f"expected stuck_type=logic, got {data}"
            print("PASS: pre-existing dirt in snapshot, no new dirt -> stuck/logic (inferred-success requires clean tree)")
        except Exception as exc:
            print(f"FAIL: case 3b ({exc}) captured={captured!r}", file=sys.stderr)
            errors += 1

    # Case 4: missing snapshot -> no inference -> stuck/logic
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        base_sha = _setup_fixture(project_root)
        # SKIP capture_snapshot — snapshot file does not exist
        snapshot_path = project_root / "_mill" / ".cleanliness-snapshot-nonexistent.txt"
        subprocess.run(
            ["git", "-C", str(project_root), "commit", "--allow-empty", "-m", "second"],
            check=True, capture_output=True,
        )
        rc, captured = _capture_stdout(
            lambda: _forward_output(
                "garbage",
                project_root,
                start_sha=base_sha,
                snapshot_path=snapshot_path,
            )
        )
        try:
            data = json.loads(captured.strip())
            assert data["status"] == "stuck", f"expected status=stuck, got {data}"
            assert data["stuck_type"] == "logic", f"expected stuck_type=logic, got {data}"
            print("PASS: missing snapshot -> stuck/logic (inference skipped: snapshot_path.exists() False)")
        except Exception as exc:
            print(f"FAIL: case 4 ({exc}) captured={captured!r}", file=sys.stderr)
            errors += 1

    # Case 5: inferred success — session_id plumbed through
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        base_sha = _setup_fixture(project_root)
        snapshot_path = project_root / "_mill" / ".cleanliness-snapshot-test.txt"
        _cleanliness.capture_snapshot(project_root, snapshot_path)
        subprocess.run(
            ["git", "-C", str(project_root), "commit", "--allow-empty", "-m", "second"],
            check=True, capture_output=True,
        )
        rc, captured = _capture_stdout(
            lambda: _forward_output(
                "garbage with no json",
                project_root,
                start_sha=base_sha,
                snapshot_path=snapshot_path,
                session_id="abc-uuid-xyz",
            )
        )
        try:
            data = json.loads(captured.strip())
            assert data["status"] == "success", f"expected status=success, got {data}"
            assert data.get("inferred") is True, f"expected inferred=True, got {data}"
            assert data["session_id"] == "abc-uuid-xyz", f"expected session_id=abc-uuid-xyz, got {data}"
            print("PASS: inferred success - session_id plumbed through (not 'unknown')")
        except Exception as exc:
            print(f"FAIL: case 5 ({exc}) captured={captured!r}", file=sys.stderr)
            errors += 1

    # Case 6: stuck/logic output + violations -> scope_violations in JSON
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        base_sha = _setup_fixture(project_root)
        snapshot_path = project_root / "_mill" / ".cleanliness-snapshot-test.txt"
        _cleanliness.capture_snapshot(project_root, snapshot_path)
        try:
            with unittest.mock.patch.object(
                _cleanliness, "compute_scope_violations", return_value=["plugins_mill_scripts_foo.py"]
            ):
                rc, captured = _capture_stdout(
                    lambda: _forward_output(
                        "garbage",
                        project_root,
                        start_sha=base_sha,
                        snapshot_path=snapshot_path,
                    )
                )
            data = json.loads(captured.strip())
            assert data["status"] == "stuck", f"expected status=stuck, got {data}"
            assert data["stuck_type"] == "logic", f"expected stuck_type=logic, got {data}"
            assert data.get("scope_violations") == ["plugins_mill_scripts_foo.py"], f"expected scope_violations, got {data}"
            print("PASS: stuck/logic + violations -> scope_violations in JSON")
        except Exception as exc:
            print(f"FAIL: case 6 ({exc}) captured={captured!r}", file=sys.stderr)
            errors += 1

    # Case 7: inferred-success scenario + violations -> status downgraded to stuck/logic
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        base_sha = _setup_fixture(project_root)
        snapshot_path = project_root / "_mill" / ".cleanliness-snapshot-test.txt"
        _cleanliness.capture_snapshot(project_root, snapshot_path)
        subprocess.run(
            ["git", "-C", str(project_root), "commit", "--allow-empty", "-m", "second"],
            check=True, capture_output=True,
        )
        try:
            with unittest.mock.patch.object(_cleanliness, "compute_scope_violations", return_value=["bad_file.py"]):
                rc, captured = _capture_stdout(
                    lambda: _forward_output(
                        "garbage",
                        project_root,
                        start_sha=base_sha,
                        snapshot_path=snapshot_path,
                    )
                )
            data = json.loads(captured.strip())
            assert data["status"] == "stuck", f"expected status=stuck, got {data}"
            assert data["stuck_type"] == "logic", f"expected stuck_type=logic, got {data}"
            assert data.get("inferred") is True, f"expected inferred=True, got {data}"
            assert data.get("scope_violations") == ["bad_file.py"], f"expected scope_violations, got {data}"
            print("PASS: inferred-success + violations -> stuck/logic with scope_violations")
        except Exception as exc:
            print(f"FAIL: case 7 ({exc}) captured={captured!r}", file=sys.stderr)
            errors += 1

    # Case 8: no violations -> output unchanged
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        base_sha = _setup_fixture(project_root)
        snapshot_path = project_root / "_mill" / ".cleanliness-snapshot-test.txt"
        _cleanliness.capture_snapshot(project_root, snapshot_path)
        subprocess.run(
            ["git", "-C", str(project_root), "commit", "--allow-empty", "-m", "second"],
            check=True, capture_output=True,
        )
        try:
            with unittest.mock.patch.object(_cleanliness, "compute_scope_violations", return_value=[]):
                rc, captured = _capture_stdout(
                    lambda: _forward_output(
                        "garbage",
                        project_root,
                        start_sha=base_sha,
                        snapshot_path=snapshot_path,
                    )
                )
            data = json.loads(captured.strip())
            assert data["status"] == "success", f"expected status=success, got {data}"
            assert data.get("inferred") is True, f"expected inferred=True, got {data}"
            assert "scope_violations" not in data, f"expected no scope_violations in {data}"
            print("PASS: inferred-success + no violations -> success unchanged")
        except Exception as exc:
            print(f"FAIL: case 8 ({exc}) captured={captured!r}", file=sys.stderr)
            errors += 1

    # Case 9: no-snapshot inferred success — HEAD advanced + clean tree
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        base_sha = _setup_fixture(project_root)
        subprocess.run(
            ["git", "-C", str(project_root), "commit", "--allow-empty", "-m", "second"],
            check=True, capture_output=True,
        )
        new_head = subprocess.run(
            ["git", "-C", str(project_root), "rev-parse", "HEAD"],
            check=True, capture_output=True, text=True,
        ).stdout.strip()
        rc, captured = _capture_stdout(
            lambda: _forward_output(
                "",
                project_root,
                start_sha=base_sha,
            )
        )
        try:
            data = json.loads(captured.strip())
            assert data["status"] == "success", f"expected status=success, got {data}"
            assert data.get("inferred") is True, f"expected inferred=True, got {data}"
            assert data["commit_sha"] == new_head, f"expected commit_sha={new_head}, got {data}"
            print("PASS: no-snapshot inferred success - HEAD advanced + clean tree -> success with inferred=True")
        except Exception as exc:
            print(f"FAIL: case 9 ({exc}) captured={captured!r}", file=sys.stderr)
            errors += 1

    # Case 10: no-snapshot, HEAD unchanged
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        base_sha = _setup_fixture(project_root)
        # NO new commit — HEAD == start_sha
        rc, captured = _capture_stdout(
            lambda: _forward_output(
                "",
                project_root,
                start_sha=base_sha,
            )
        )
        try:
            data = json.loads(captured.strip())
            assert data["status"] == "stuck", f"expected status=stuck, got {data}"
            assert data["stuck_type"] == "logic", f"expected stuck_type=logic, got {data}"
            print("PASS: no-snapshot, HEAD unchanged -> stuck/logic")
        except Exception as exc:
            print(f"FAIL: case 10 ({exc}) captured={captured!r}", file=sys.stderr)
            errors += 1

    # Case 11: no-snapshot, HEAD advanced but dirty tree
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        base_sha = _setup_fixture(project_root)
        subprocess.run(
            ["git", "-C", str(project_root), "commit", "--allow-empty", "-m", "second"],
            check=True, capture_output=True,
        )
        # Dirty already-tracked README.md without committing
        (project_root / "README.md").write_text("dirty", encoding="utf-8")
        rc, captured = _capture_stdout(
            lambda: _forward_output(
                "",
                project_root,
                start_sha=base_sha,
            )
        )
        try:
            data = json.loads(captured.strip())
            assert data["status"] == "stuck", f"expected status=stuck, got {data}"
            assert data["stuck_type"] == "logic", f"expected stuck_type=logic, got {data}"
            print("PASS: no-snapshot, HEAD advanced but dirty tree -> stuck/logic")
        except Exception as exc:
            print(f"FAIL: case 11 ({exc}) captured={captured!r}", file=sys.stderr)
            errors += 1

    # Case 12: emit_prepare writes brief and prints prepare JSON
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        briefs_dir = Path(tmpdir) / "briefs"
        prompt_text = "This is the prompt\n\ndetailed instructions"
        try:
            rc, captured = _capture_stdout(
                lambda: emit_prepare(
                    briefs_dir,
                    "implement",
                    "batch-1",
                    1,
                    prompt_text,
                    "sonnet",
                    "session-123",
                )
            )
            assert rc == 0, f"expected rc=0, got {rc}"
            brief_path = briefs_dir / "implement-batch-1-r1.md"
            assert brief_path.exists(), f"expected brief file at {brief_path}"
            assert brief_path.read_text(encoding="utf-8") == prompt_text, "brief content mismatch"
            data = json.loads(captured.strip())
            assert data["stage"] == "prepare", f"expected stage=prepare, got {data}"
            assert data["subagent_type"] == "mill:mill-implementer", f"expected mill:mill-implementer, got {data}"
            assert data["model"] == "sonnet", f"expected model=sonnet, got {data}"
            assert data["role"] == "implement", f"expected role=implement, got {data}"
            assert data["scope"] == "batch-1", f"expected scope=batch-1, got {data}"
            assert data["round"] == 1, f"expected round=1, got {data}"
            print("PASS: emit_prepare writes brief and prints prepare JSON")
        except Exception as exc:
            print(f"FAIL: case 12 ({exc}) captured={captured!r}", file=sys.stderr)
            errors += 1

    # Case 13: finalize_from_output reads agent output and delegates to _forward_output
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        base_sha = _setup_fixture(project_root)
        snapshot_path = project_root / "_mill" / ".cleanliness-snapshot-test.txt"
        _cleanliness.capture_snapshot(project_root, snapshot_path)
        subprocess.run(
            ["git", "-C", str(project_root), "commit", "--allow-empty", "-m", "second"],
            check=True, capture_output=True,
        )
        new_head = subprocess.run(
            ["git", "-C", str(project_root), "rev-parse", "HEAD"],
            check=True, capture_output=True, text=True,
        ).stdout.strip()
        agent_output_path = project_root / "_mill" / "agent-output.txt"
        agent_output_path.write_text("garbage output", encoding="utf-8")
        try:
            rc, captured = _capture_stdout(
                lambda: finalize_from_output(
                    agent_output_path,
                    project_root,
                    start_sha=base_sha,
                    snapshot_path=snapshot_path,
                    session_id="test-session",
                )
            )
            assert rc == 0, f"expected rc=0, got {rc}"
            data = json.loads(captured.strip())
            assert data["status"] == "success", f"expected status=success, got {data}"
            assert data["commit_sha"] == new_head, f"expected commit_sha={new_head}, got {data}"
            assert data["session_id"] == "test-session", f"expected session_id=test-session, got {data}"
            print("PASS: finalize_from_output reads agent output and produces success envelope")
        except Exception as exc:
            print(f"FAIL: case 13 ({exc}) captured={captured!r}", file=sys.stderr)
            errors += 1

    # Case 14: emit_prepare_no_dispatch prints prepare with dispatch_needed:false
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        _setup_fixture(project_root)
        try:
            rc, captured = _capture_stdout(
                lambda: emit_prepare_no_dispatch(
                    "haiku",
                    "session-456",
                    "merge",
                    "verify-fix",
                    1,
                    project_root,
                )
            )
            assert rc == 0, f"expected rc=0, got {rc}"
            data = json.loads(captured.strip())
            assert data["stage"] == "prepare", f"expected stage=prepare, got {data}"
            assert data["dispatch_needed"] is False, f"expected dispatch_needed=False, got {data}"
            assert data["subagent_type"] == "mill:mill-implementer", f"expected mill:mill-implementer, got {data}"
            assert data["role"] == "merge", f"expected role=merge, got {data}"
            assert data["scope"] == "verify-fix", f"expected scope=verify-fix, got {data}"
            assert "envelope" in data, f"expected envelope key in {data}"
            assert data["envelope"]["status"] == "success", f"expected envelope.status=success, got {data}"
            print("PASS: emit_prepare_no_dispatch prints prepare with dispatch_needed:false and embedded envelope")
        except Exception as exc:
            print(f"FAIL: case 14 ({exc}) captured={captured!r}", file=sys.stderr)
            errors += 1

    # Case 15: _is_formatter_drift_only - whitespace-only changes
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        _setup_fixture(project_root)
        # Stage and commit a file
        (project_root / "README.md").write_text("seed\n", encoding="utf-8")
        subprocess.run(
            ["git", "-C", str(project_root), "add", "README.md"],
            check=True, capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(project_root), "commit", "-m", "whitespace change"],
            check=True, capture_output=True,
        )
        # Make a whitespace-only change (add trailing spaces)
        (project_root / "README.md").write_text("seed   \n", encoding="utf-8")
        try:
            result = _is_formatter_drift_only(project_root)
            assert result is True, f"expected True (formatter drift detected), got {result}"
            print("PASS: _is_formatter_drift_only detects whitespace-only changes")
        except Exception as exc:
            print(f"FAIL: case 15 ({exc})", file=sys.stderr)
            errors += 1

    # Case 16: _is_formatter_drift_only - non-whitespace changes not detected as drift
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        _setup_fixture(project_root)
        # Stage and commit a file
        (project_root / "README.md").write_text("seed\n", encoding="utf-8")
        subprocess.run(
            ["git", "-C", str(project_root), "add", "README.md"],
            check=True, capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(project_root), "commit", "-m", "content change"],
            check=True, capture_output=True,
        )
        # Make a content change
        (project_root / "README.md").write_text("modified\n", encoding="utf-8")
        try:
            result = _is_formatter_drift_only(project_root)
            assert result is False, f"expected False (content changes, not drift), got {result}"
            print("PASS: _is_formatter_drift_only does not detect content changes as drift")
        except Exception as exc:
            print(f"FAIL: case 16 ({exc})", file=sys.stderr)
            errors += 1

    # Case 17: _is_formatter_drift_only - untracked files present not detected as drift
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        _setup_fixture(project_root)
        # Stage and commit a file
        (project_root / "README.md").write_text("seed\n", encoding="utf-8")
        subprocess.run(
            ["git", "-C", str(project_root), "add", "README.md"],
            check=True, capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(project_root), "commit", "-m", "first commit"],
            check=True, capture_output=True,
        )
        # Add untracked file and whitespace change
        (project_root / "untracked.py").write_text("code\n", encoding="utf-8")
        (project_root / "README.md").write_text("seed   \n", encoding="utf-8")
        try:
            result = _is_formatter_drift_only(project_root)
            assert result is False, f"expected False (untracked files present), got {result}"
            print("PASS: _is_formatter_drift_only returns False when untracked files exist")
        except Exception as exc:
            print(f"FAIL: case 17 ({exc})", file=sys.stderr)
            errors += 1

    # Case 18: _commit_formatter_drift auto-commits drift
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        _setup_fixture(project_root)
        # Stage and commit a file
        (project_root / "README.md").write_text("seed\n", encoding="utf-8")
        subprocess.run(
            ["git", "-C", str(project_root), "add", "README.md"],
            check=True, capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(project_root), "commit", "-m", "first"],
            check=True, capture_output=True,
        )
        # Make a whitespace change
        (project_root / "README.md").write_text("seed   \n", encoding="utf-8")
        try:
            result = _commit_formatter_drift(project_root)
            assert result is True, f"expected True (commit succeeded), got {result}"
            # Verify commit was made
            log_result = subprocess.run(
                ["git", "-C", str(project_root), "log", "-1", "--pretty=%s"],
                check=True, capture_output=True, text=True,
            )
            assert "chore(format)" in log_result.stdout, f"expected chore(format) in log, got {log_result.stdout}"
            # Verify tree is clean
            status_result = subprocess.run(
                ["git", "-C", str(project_root), "status", "--porcelain"],
                check=True, capture_output=True, text=True,
            )
            assert not status_result.stdout.strip(), f"expected clean tree, got {status_result.stdout}"
            print("PASS: _commit_formatter_drift commits drift and cleans tree")
        except Exception as exc:
            print(f"FAIL: case 18 ({exc})", file=sys.stderr)
            errors += 1

    # Case 19: verify_cmd provided, verify fails, parsed success -> demoted to stuck/verify
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        base_sha = _setup_fixture(project_root)
        snapshot_path = project_root / "_mill" / ".cleanliness-snapshot-test.txt"
        _cleanliness.capture_snapshot(project_root, snapshot_path)
        subprocess.run(
            ["git", "-C", str(project_root), "commit", "--allow-empty", "-m", "second"],
            check=True, capture_output=True,
        )
        new_head = subprocess.run(
            ["git", "-C", str(project_root), "rev-parse", "HEAD"],
            check=True, capture_output=True, text=True,
        ).stdout.strip()
        agent_output = '{"status":"success","commit_sha":"abc","session_id":"test-session"}\n'
        # Verify command that always fails
        verify_cmd = "exit 1"
        rc, captured = _capture_stdout(
            lambda: _forward_output(
                agent_output,
                project_root,
                start_sha=base_sha,
                snapshot_path=snapshot_path,
                verify_cmd=verify_cmd,
            )
        )
        try:
            data = json.loads(captured.strip())
            assert data["status"] == "stuck", f"expected status=stuck, got {data}"
            assert data["stuck_type"] == "verify", f"expected stuck_type=verify, got {data}"
            assert "reason" in data, f"expected reason key in {data}"
            assert "commit_sha" in data, f"expected commit_sha key in {data}"
            assert data["commit_sha"] == new_head, f"expected commit_sha={new_head}, got {data}"
            print("PASS: parsed success with failing verify_cmd -> stuck/verify with commit_sha")
        except Exception as exc:
            print(f"FAIL: case 19 ({exc}) captured={captured!r}", file=sys.stderr)
            errors += 1

    # Case 20: verify_cmd provided, verify passes, parsed success -> success preserved
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        base_sha = _setup_fixture(project_root)
        snapshot_path = project_root / "_mill" / ".cleanliness-snapshot-test.txt"
        _cleanliness.capture_snapshot(project_root, snapshot_path)
        subprocess.run(
            ["git", "-C", str(project_root), "commit", "--allow-empty", "-m", "second"],
            check=True, capture_output=True,
        )
        agent_output = '{"status":"success","commit_sha":"abc","session_id":"test-session"}\n'
        # Verify command that succeeds
        verify_cmd = "exit 0"
        rc, captured = _capture_stdout(
            lambda: _forward_output(
                agent_output,
                project_root,
                start_sha=base_sha,
                snapshot_path=snapshot_path,
                verify_cmd=verify_cmd,
            )
        )
        try:
            data = json.loads(captured.strip())
            assert data["status"] == "success", f"expected status=success, got {data}"
            assert "reason" not in data, f"expected no reason field in success output, got {data}"
            print("PASS: parsed success with passing verify_cmd -> success preserved")
        except Exception as exc:
            print(f"FAIL: case 20 ({exc}) captured={captured!r}", file=sys.stderr)
            errors += 1

    # Case 21: verify_cmd=None, parsed success -> success preserved (backward compat)
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        base_sha = _setup_fixture(project_root)
        snapshot_path = project_root / "_mill" / ".cleanliness-snapshot-test.txt"
        _cleanliness.capture_snapshot(project_root, snapshot_path)
        subprocess.run(
            ["git", "-C", str(project_root), "commit", "--allow-empty", "-m", "second"],
            check=True, capture_output=True,
        )
        agent_output = '{"status":"success","commit_sha":"abc","session_id":"test-session"}\n'
        rc, captured = _capture_stdout(
            lambda: _forward_output(
                agent_output,
                project_root,
                start_sha=base_sha,
                snapshot_path=snapshot_path,
                verify_cmd=None,
            )
        )
        try:
            data = json.loads(captured.strip())
            assert data["status"] == "success", f"expected status=success, got {data}"
            print("PASS: verify_cmd=None -> success preserved (backward compat)")
        except Exception as exc:
            print(f"FAIL: case 21 ({exc}) captured={captured!r}", file=sys.stderr)
            errors += 1

    # Case 22: inferred success, verify_cmd fails -> demoted to stuck/verify with commit_sha
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        base_sha = _setup_fixture(project_root)
        snapshot_path = project_root / "_mill" / ".cleanliness-snapshot-test.txt"
        _cleanliness.capture_snapshot(project_root, snapshot_path)
        subprocess.run(
            ["git", "-C", str(project_root), "commit", "--allow-empty", "-m", "second"],
            check=True, capture_output=True,
        )
        new_head = subprocess.run(
            ["git", "-C", str(project_root), "rev-parse", "HEAD"],
            check=True, capture_output=True, text=True,
        ).stdout.strip()
        # Inferred success path (no JSON in agent output)
        verify_cmd = "exit 1"
        rc, captured = _capture_stdout(
            lambda: _forward_output(
                "garbage output with no json",
                project_root,
                start_sha=base_sha,
                snapshot_path=snapshot_path,
                verify_cmd=verify_cmd,
            )
        )
        try:
            data = json.loads(captured.strip())
            assert data["status"] == "stuck", f"expected status=stuck, got {data}"
            assert data["stuck_type"] == "verify", f"expected stuck_type=verify, got {data}"
            assert "commit_sha" in data, f"expected commit_sha key in {data}"
            assert data["commit_sha"] == new_head, f"expected commit_sha={new_head}, got {data}"
            print("PASS: inferred success with failing verify_cmd -> stuck/verify with commit_sha")
        except Exception as exc:
            print(f"FAIL: case 22 ({exc}) captured={captured!r}", file=sys.stderr)
            errors += 1

    # Case 23: win32 + cleanup signature + no FAIL marker -> success (benign race)
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        base_sha = _setup_fixture(project_root)
        snapshot_path = project_root / "_mill" / ".cleanliness-snapshot-test.txt"
        _cleanliness.capture_snapshot(project_root, snapshot_path)
        subprocess.run(
            ["git", "-C", str(project_root), "commit", "--allow-empty", "-m", "second"],
            check=True, capture_output=True,
        )
        new_head = subprocess.run(
            ["git", "-C", str(project_root), "rev-parse", "HEAD"],
            check=True, capture_output=True, text=True,
        ).stdout.strip()
        # Verify command that outputs cleanup signature (unlinkat ... Access is denied) and fails
        verify_cmd = "echo 'error: unlinkat ...\\X.test.exe: Access is denied' && exit 1"
        agent_output = '{"status":"success","commit_sha":"abc","session_id":"test-session"}\n'
        # Monkeypatch sys.platform to win32
        original_platform = sys.platform
        try:
            sys.platform = "win32"
            rc, captured = _capture_stdout(
                lambda: _forward_output(
                    agent_output,
                    project_root,
                    start_sha=base_sha,
                    snapshot_path=snapshot_path,
                    verify_cmd=verify_cmd,
                )
            )
            data = json.loads(captured.strip())
            assert data["status"] == "success", f"expected status=success (benign cleanup on win32), got {data}"
            assert data["commit_sha"] == new_head, f"expected commit_sha={new_head}, got {data}"
            print("PASS: case 23 - win32 + cleanup signature + no FAIL -> success (benign race)")
        except Exception as exc:
            print(f"FAIL: case 23 ({exc}) captured={captured!r}", file=sys.stderr)
            errors += 1
        finally:
            sys.platform = original_platform

    # Case 24: win32 + cleanup signature BUT --- FAIL line present -> stays stuck/verify
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        base_sha = _setup_fixture(project_root)
        snapshot_path = project_root / "_mill" / ".cleanliness-snapshot-test.txt"
        _cleanliness.capture_snapshot(project_root, snapshot_path)
        subprocess.run(
            ["git", "-C", str(project_root), "commit", "--allow-empty", "-m", "second"],
            check=True, capture_output=True,
        )
        new_head = subprocess.run(
            ["git", "-C", str(project_root), "rev-parse", "HEAD"],
            check=True, capture_output=True, text=True,
        ).stdout.strip()
        # Verify command that outputs both cleanup signature AND --- FAIL
        verify_cmd = "echo 'error: unlinkat ...\\X.test.exe: Access is denied' && echo '--- FAIL: test_foo' && exit 1"
        agent_output = '{"status":"success","commit_sha":"abc","session_id":"test-session"}\n'
        original_platform = sys.platform
        try:
            sys.platform = "win32"
            rc, captured = _capture_stdout(
                lambda: _forward_output(
                    agent_output,
                    project_root,
                    start_sha=base_sha,
                    snapshot_path=snapshot_path,
                    verify_cmd=verify_cmd,
                )
            )
            data = json.loads(captured.strip())
            assert data["status"] == "stuck", f"expected status=stuck (real failure present), got {data}"
            assert data["stuck_type"] == "verify", f"expected stuck_type=verify, got {data}"
            print("PASS: case 24 - win32 + cleanup signature + --- FAIL present -> stuck/verify")
        except Exception as exc:
            print(f"FAIL: case 24 ({exc}) captured={captured!r}", file=sys.stderr)
            errors += 1
        finally:
            sys.platform = original_platform

    # Case 24b: win32 + cleanup signature BUT bare FAIL line present -> stays stuck/verify
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        base_sha = _setup_fixture(project_root)
        snapshot_path = project_root / "_mill" / ".cleanliness-snapshot-test.txt"
        _cleanliness.capture_snapshot(project_root, snapshot_path)
        subprocess.run(
            ["git", "-C", str(project_root), "commit", "--allow-empty", "-m", "second"],
            check=True, capture_output=True,
        )
        new_head = subprocess.run(
            ["git", "-C", str(project_root), "rev-parse", "HEAD"],
            check=True, capture_output=True, text=True,
        ).stdout.strip()
        # Verify command that outputs cleanup signature AND bare FAIL (as in go test output)
        verify_cmd = "echo 'error: unlinkat ...\\X.test.exe: Access is denied' && echo 'FAIL\tgithub.com/test/...' && exit 1"
        agent_output = '{"status":"success","commit_sha":"abc","session_id":"test-session"}\n'
        original_platform = sys.platform
        try:
            sys.platform = "win32"
            rc, captured = _capture_stdout(
                lambda: _forward_output(
                    agent_output,
                    project_root,
                    start_sha=base_sha,
                    snapshot_path=snapshot_path,
                    verify_cmd=verify_cmd,
                )
            )
            data = json.loads(captured.strip())
            assert data["status"] == "stuck", f"expected status=stuck (real failure present), got {data}"
            assert data["stuck_type"] == "verify", f"expected stuck_type=verify, got {data}"
            print("PASS: case 24b - win32 + cleanup signature + bare FAIL present -> stuck/verify")
        except Exception as exc:
            print(f"FAIL: case 24b ({exc}) captured={captured!r}", file=sys.stderr)
            errors += 1
        finally:
            sys.platform = original_platform

    # Case 25: win32 + ordinary non-zero (no cleanup signature) -> stuck/verify
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        base_sha = _setup_fixture(project_root)
        snapshot_path = project_root / "_mill" / ".cleanliness-snapshot-test.txt"
        _cleanliness.capture_snapshot(project_root, snapshot_path)
        subprocess.run(
            ["git", "-C", str(project_root), "commit", "--allow-empty", "-m", "second"],
            check=True, capture_output=True,
        )
        new_head = subprocess.run(
            ["git", "-C", str(project_root), "rev-parse", "HEAD"],
            check=True, capture_output=True, text=True,
        ).stdout.strip()
        # Verify command that fails with non-cleanup output
        verify_cmd = "echo 'something went wrong' && exit 1"
        agent_output = '{"status":"success","commit_sha":"abc","session_id":"test-session"}\n'
        original_platform = sys.platform
        try:
            sys.platform = "win32"
            rc, captured = _capture_stdout(
                lambda: _forward_output(
                    agent_output,
                    project_root,
                    start_sha=base_sha,
                    snapshot_path=snapshot_path,
                    verify_cmd=verify_cmd,
                )
            )
            data = json.loads(captured.strip())
            assert data["status"] == "stuck", f"expected status=stuck, got {data}"
            assert data["stuck_type"] == "verify", f"expected stuck_type=verify, got {data}"
            print("PASS: case 25 - win32 + ordinary non-zero (no signature) -> stuck/verify")
        except Exception as exc:
            print(f"FAIL: case 25 ({exc}) captured={captured!r}", file=sys.stderr)
            errors += 1
        finally:
            sys.platform = original_platform

    # Case 26: non-win32 + cleanup signature output -> stuck/verify (platform gate)
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        base_sha = _setup_fixture(project_root)
        snapshot_path = project_root / "_mill" / ".cleanliness-snapshot-test.txt"
        _cleanliness.capture_snapshot(project_root, snapshot_path)
        subprocess.run(
            ["git", "-C", str(project_root), "commit", "--allow-empty", "-m", "second"],
            check=True, capture_output=True,
        )
        # Verify command with cleanup signature
        verify_cmd = "echo 'error: unlinkat ...\\X.test.exe: Access is denied' && exit 1"
        agent_output = '{"status":"success","commit_sha":"abc","session_id":"test-session"}\n'
        original_platform = sys.platform
        try:
            # Force non-win32 (e.g., linux)
            sys.platform = "linux"
            rc, captured = _capture_stdout(
                lambda: _forward_output(
                    agent_output,
                    project_root,
                    start_sha=base_sha,
                    snapshot_path=snapshot_path,
                    verify_cmd=verify_cmd,
                )
            )
            data = json.loads(captured.strip())
            assert data["status"] == "stuck", f"expected status=stuck (non-win32 sees failure), got {data}"
            assert data["stuck_type"] == "verify", f"expected stuck_type=verify, got {data}"
            print("PASS: case 26 - non-win32 + cleanup signature -> stuck/verify (platform gate)")
        except Exception as exc:
            print(f"FAIL: case 26 ({exc}) captured={captured!r}", file=sys.stderr)
            errors += 1
        finally:
            sys.platform = original_platform

    # Case 27: #500 regression - parsed success but no content commit (HEAD == start_sha)
    # The verify gate must pass so we can test the no-commit guard independently
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        base_sha = _setup_fixture(project_root)
        snapshot_path = project_root / "_mill" / ".cleanliness-snapshot-test.txt"
        _cleanliness.capture_snapshot(project_root, snapshot_path)
        # IMPORTANT: Do NOT make a new commit - HEAD == start_sha
        # Verify must pass (so verify gate doesn't fire first)
        verify_cmd = "exit 0"
        agent_output = '{"status":"success","commit_sha":"abc","session_id":"test-session"}\n'
        rc, captured = _capture_stdout(
            lambda: _forward_output(
                agent_output,
                project_root,
                start_sha=base_sha,
                snapshot_path=snapshot_path,
                verify_cmd=verify_cmd,
            )
        )
        try:
            data = json.loads(captured.strip())
            assert data["status"] == "stuck", f"expected status=stuck, got {data}"
            assert data["stuck_type"] == "logic", f"expected stuck_type=logic, got {data}"
            assert "no content commit" in data.get("reason", "").lower(), f"expected 'no content commit' in reason, got {data}"
            print("PASS: #500 - parsed success with no content commit (HEAD == start_sha) -> stuck/logic")
        except Exception as exc:
            print(f"FAIL: case 27 ({exc}) captured={captured!r}", file=sys.stderr)
            errors += 1

    # Case 28: #499/#502 regression (a) - API error markers classified as transient
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        _setup_fixture(project_root)
        # Output contains API error but no parseable JSON
        rc, captured = _capture_stdout(
            lambda: _forward_output(
                "API Error: Internal server error occurred",
                project_root,
            )
        )
        try:
            data = json.loads(captured.strip())
            assert data["status"] == "stuck", f"expected status=stuck, got {data}"
            assert data["stuck_type"] == "transient", f"expected stuck_type=transient, got {data}"
            print("PASS: #499/#502 (a) - raw API error -> stuck/transient")
        except Exception as exc:
            print(f"FAIL: case 28 ({exc}) captured={captured!r}", file=sys.stderr)
            errors += 1

    # Case 29: #499/#502 regression (b) - plain garbage + HEAD == start_sha still yields logic
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        base_sha = _setup_fixture(project_root)
        snapshot_path = project_root / "_mill" / ".cleanliness-snapshot-test.txt"
        _cleanliness.capture_snapshot(project_root, snapshot_path)
        # NO new commit — HEAD == start_sha
        # Output contains no API error and no JSON
        rc, captured = _capture_stdout(
            lambda: _forward_output(
                "plain garbage output with no error markers",
                project_root,
                start_sha=base_sha,
                snapshot_path=snapshot_path,
            )
        )
        try:
            data = json.loads(captured.strip())
            assert data["status"] == "stuck", f"expected status=stuck, got {data}"
            assert data["stuck_type"] == "logic", f"expected stuck_type=logic, got {data}"
            print("PASS: #499/#502 (b) - plain garbage + HEAD == start_sha -> stuck/logic (not transient)")
        except Exception as exc:
            print(f"FAIL: case 29 ({exc}) captured={captured!r}", file=sys.stderr)
            errors += 1

    if errors:
        print(f"\n{errors} test(s) FAILED", file=sys.stderr)
        return 1
    print("All _implementer_common unit tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
