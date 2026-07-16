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

from _implementer_common import (  # noqa: E402
    _forward_output,
    _batch_completeness_stuck,
    _reclassify_verify_failure,
    _content_commit_count,
    emit_prepare,
    emit_prepare_no_dispatch,
    finalize_from_output,
    _is_formatter_drift_only,
    _commit_formatter_drift,
    _run_verify_gate,
    _run_verify_gates,
    _is_benign_windows_cleanup,
    _go_build_tag_retiering_stuck,
)
import _cleanliness  # noqa: E402
import _status  # noqa: E402
import _subprocess_util  # noqa: E402


def _capture_stdout(fn):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = fn()
    return rc, buf.getvalue()


def _go_gate_mock(build_returncode=0, build_stdout="", build_stderr=""):
    """Build a _subprocess_util.run side_effect that mocks 'go' invocations only.

    Every non-'go' argv (git, etc.) delegates to the real _subprocess_util.run so
    the git diff/status plumbing _go_build_tag_retiering_stuck depends on still
    works against the tempfile git fixture -- no real Go toolchain is invoked.

    Returns (side_effect, calls): side_effect is passed to
    unittest.mock.patch.object(_subprocess_util, "run", side_effect=...); calls
    accumulates every mocked 'go' argv for assertions.
    """
    real_run = _subprocess_util.run
    calls: list[list[str]] = []

    def _side_effect(argv, **kwargs):
        if argv and argv[0] == "go":
            calls.append(list(argv))
            return subprocess.CompletedProcess(
                argv, build_returncode, build_stdout, build_stderr
            )
        return real_run(argv, **kwargs)

    return _side_effect, calls


def _setup_fixture(project_root: Path) -> str:
    """Init git repo with a README.md base commit; return base SHA."""
    subprocess.run(
        ["git", "init", "-q", str(project_root)], check=True, capture_output=True
    )
    subprocess.run(
        ["git", "-C", str(project_root), "config", "user.email", "test@test.com"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(project_root), "config", "user.name", "Test"],
        check=True,
        capture_output=True,
    )
    (project_root / "README.md").write_text("seed", encoding="utf-8")
    subprocess.run(
        ["git", "-C", str(project_root), "add", "README.md"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(project_root), "commit", "-m", "initial"],
        check=True,
        capture_output=True,
    )
    return subprocess.run(
        ["git", "-C", str(project_root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
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
            check=True,
            capture_output=True,
        )
        new_head = subprocess.run(
            ["git", "-C", str(project_root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
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
            assert data["commit_sha"] == new_head, (
                f"expected commit_sha={new_head}, got {data}"
            )
            print(
                "PASS: inferred success - clean worktree + new commit -> success with inferred=True"
            )
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
            assert data["stuck_type"] == "logic", (
                f"expected stuck_type=logic, got {data}"
            )
            print(
                "PASS: no new commits -> stuck/logic (inference skipped: HEAD == start_sha)"
            )
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
            check=True,
            capture_output=True,
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
            assert data["stuck_type"] == "logic", (
                f"expected stuck_type=logic, got {data}"
            )
            print(
                "PASS: dirty worktree -> stuck/logic (inference skipped: compute_new_dirt non-empty)"
            )
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
            check=True,
            capture_output=True,
        )
        new_head = subprocess.run(
            ["git", "-C", str(project_root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
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
            assert data["stuck_type"] == "logic", (
                f"expected stuck_type=logic, got {data}"
            )
            print(
                "PASS: pre-existing dirt in snapshot, no new dirt -> stuck/logic (inferred-success requires clean tree)"
            )
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
            check=True,
            capture_output=True,
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
            assert data["stuck_type"] == "logic", (
                f"expected stuck_type=logic, got {data}"
            )
            print(
                "PASS: missing snapshot -> stuck/logic (inference skipped: snapshot_path.exists() False)"
            )
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
            check=True,
            capture_output=True,
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
            assert data["session_id"] == "abc-uuid-xyz", (
                f"expected session_id=abc-uuid-xyz, got {data}"
            )
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
                _cleanliness,
                "compute_scope_violations",
                return_value=["plugins_mill_scripts_foo.py"],
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
            assert data["stuck_type"] == "logic", (
                f"expected stuck_type=logic, got {data}"
            )
            assert data.get("scope_violations") == ["plugins_mill_scripts_foo.py"], (
                f"expected scope_violations, got {data}"
            )
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
            check=True,
            capture_output=True,
        )
        try:
            with unittest.mock.patch.object(
                _cleanliness, "compute_scope_violations", return_value=["bad_file.py"]
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
            assert data["stuck_type"] == "logic", (
                f"expected stuck_type=logic, got {data}"
            )
            assert data.get("inferred") is True, f"expected inferred=True, got {data}"
            assert data.get("scope_violations") == ["bad_file.py"], (
                f"expected scope_violations, got {data}"
            )
            print(
                "PASS: inferred-success + violations -> stuck/logic with scope_violations"
            )
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
            check=True,
            capture_output=True,
        )
        try:
            with unittest.mock.patch.object(
                _cleanliness, "compute_scope_violations", return_value=[]
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
            assert data["status"] == "success", f"expected status=success, got {data}"
            assert data.get("inferred") is True, f"expected inferred=True, got {data}"
            assert "scope_violations" not in data, (
                f"expected no scope_violations in {data}"
            )
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
            check=True,
            capture_output=True,
        )
        new_head = subprocess.run(
            ["git", "-C", str(project_root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
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
            assert data["commit_sha"] == new_head, (
                f"expected commit_sha={new_head}, got {data}"
            )
            print(
                "PASS: no-snapshot inferred success - HEAD advanced + clean tree -> success with inferred=True"
            )
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
            assert data["stuck_type"] == "logic", (
                f"expected stuck_type=logic, got {data}"
            )
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
            check=True,
            capture_output=True,
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
            assert data["stuck_type"] == "logic", (
                f"expected stuck_type=logic, got {data}"
            )
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
            assert brief_path.read_text(encoding="utf-8") == prompt_text, (
                "brief content mismatch"
            )
            data = json.loads(captured.strip())
            assert data["stage"] == "prepare", f"expected stage=prepare, got {data}"
            assert data["subagent_type"] == "mill:mill-implementer", (
                f"expected mill:mill-implementer, got {data}"
            )
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
            check=True,
            capture_output=True,
        )
        new_head = subprocess.run(
            ["git", "-C", str(project_root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
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
            assert data["commit_sha"] == new_head, (
                f"expected commit_sha={new_head}, got {data}"
            )
            assert data["session_id"] == "test-session", (
                f"expected session_id=test-session, got {data}"
            )
            print(
                "PASS: finalize_from_output reads agent output and produces success envelope"
            )
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
            assert data["dispatch_needed"] is False, (
                f"expected dispatch_needed=False, got {data}"
            )
            assert data["subagent_type"] == "mill:mill-implementer", (
                f"expected mill:mill-implementer, got {data}"
            )
            assert data["role"] == "merge", f"expected role=merge, got {data}"
            assert data["scope"] == "verify-fix", (
                f"expected scope=verify-fix, got {data}"
            )
            assert "envelope" in data, f"expected envelope key in {data}"
            assert data["envelope"]["status"] == "success", (
                f"expected envelope.status=success, got {data}"
            )
            print(
                "PASS: emit_prepare_no_dispatch prints prepare with dispatch_needed:false and embedded envelope"
            )
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
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(project_root), "commit", "-m", "whitespace change"],
            check=True,
            capture_output=True,
        )
        # Make a whitespace-only change (add trailing spaces)
        (project_root / "README.md").write_text("seed   \n", encoding="utf-8")
        try:
            result = _is_formatter_drift_only(project_root)
            assert result is True, (
                f"expected True (formatter drift detected), got {result}"
            )
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
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(project_root), "commit", "-m", "content change"],
            check=True,
            capture_output=True,
        )
        # Make a content change
        (project_root / "README.md").write_text("modified\n", encoding="utf-8")
        try:
            result = _is_formatter_drift_only(project_root)
            assert result is False, (
                f"expected False (content changes, not drift), got {result}"
            )
            print(
                "PASS: _is_formatter_drift_only does not detect content changes as drift"
            )
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
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(project_root), "commit", "-m", "first commit"],
            check=True,
            capture_output=True,
        )
        # Add untracked file and whitespace change
        (project_root / "untracked.py").write_text("code\n", encoding="utf-8")
        (project_root / "README.md").write_text("seed   \n", encoding="utf-8")
        try:
            result = _is_formatter_drift_only(project_root)
            assert result is False, (
                f"expected False (untracked files present), got {result}"
            )
            print(
                "PASS: _is_formatter_drift_only returns False when untracked files exist"
            )
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
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(project_root), "commit", "-m", "first"],
            check=True,
            capture_output=True,
        )
        # Make a whitespace change
        (project_root / "README.md").write_text("seed   \n", encoding="utf-8")
        try:
            result = _commit_formatter_drift(project_root)
            assert result is True, f"expected True (commit succeeded), got {result}"
            # Verify commit was made
            log_result = subprocess.run(
                ["git", "-C", str(project_root), "log", "-1", "--pretty=%s"],
                check=True,
                capture_output=True,
                text=True,
            )
            assert "chore(format)" in log_result.stdout, (
                f"expected chore(format) in log, got {log_result.stdout}"
            )
            # Verify tree is clean
            status_result = subprocess.run(
                ["git", "-C", str(project_root), "status", "--porcelain"],
                check=True,
                capture_output=True,
                text=True,
            )
            assert not status_result.stdout.strip(), (
                f"expected clean tree, got {status_result.stdout}"
            )
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
            check=True,
            capture_output=True,
        )
        new_head = subprocess.run(
            ["git", "-C", str(project_root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        agent_output = (
            '{"status":"success","commit_sha":"abc","session_id":"test-session"}\n'
        )
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
            assert data["stuck_type"] == "verify", (
                f"expected stuck_type=verify, got {data}"
            )
            assert "reason" in data, f"expected reason key in {data}"
            assert "commit_sha" in data, f"expected commit_sha key in {data}"
            assert data["commit_sha"] == new_head, (
                f"expected commit_sha={new_head}, got {data}"
            )
            print(
                "PASS: parsed success with failing verify_cmd -> stuck/verify with commit_sha"
            )
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
            check=True,
            capture_output=True,
        )
        agent_output = (
            '{"status":"success","commit_sha":"abc","session_id":"test-session"}\n'
        )
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
            assert "reason" not in data, (
                f"expected no reason field in success output, got {data}"
            )
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
            check=True,
            capture_output=True,
        )
        agent_output = (
            '{"status":"success","commit_sha":"abc","session_id":"test-session"}\n'
        )
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
            check=True,
            capture_output=True,
        )
        new_head = subprocess.run(
            ["git", "-C", str(project_root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
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
            assert data["stuck_type"] == "verify", (
                f"expected stuck_type=verify, got {data}"
            )
            assert "commit_sha" in data, f"expected commit_sha key in {data}"
            assert data["commit_sha"] == new_head, (
                f"expected commit_sha={new_head}, got {data}"
            )
            print(
                "PASS: inferred success with failing verify_cmd -> stuck/verify with commit_sha"
            )
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
            check=True,
            capture_output=True,
        )
        new_head = subprocess.run(
            ["git", "-C", str(project_root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        # Verify command that outputs cleanup signature (unlinkat ... Access is denied) and fails
        verify_cmd = (
            "echo 'error: unlinkat ...\\X.test.exe: Access is denied' && exit 1"
        )
        agent_output = (
            '{"status":"success","commit_sha":"abc","session_id":"test-session"}\n'
        )
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
            assert data["status"] == "success", (
                f"expected status=success (benign cleanup on win32), got {data}"
            )
            assert data["commit_sha"] == new_head, (
                f"expected commit_sha={new_head}, got {data}"
            )
            print(
                "PASS: case 23 - win32 + cleanup signature + no FAIL -> success (benign race)"
            )
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
            check=True,
            capture_output=True,
        )
        new_head = subprocess.run(
            ["git", "-C", str(project_root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        # Verify command that outputs both cleanup signature AND --- FAIL
        verify_cmd = "echo 'error: unlinkat ...\\X.test.exe: Access is denied' && echo '--- FAIL: test_foo' && exit 1"
        agent_output = (
            '{"status":"success","commit_sha":"abc","session_id":"test-session"}\n'
        )
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
            assert data["status"] == "stuck", (
                f"expected status=stuck (real failure present), got {data}"
            )
            assert data["stuck_type"] == "verify", (
                f"expected stuck_type=verify, got {data}"
            )
            print(
                "PASS: case 24 - win32 + cleanup signature + --- FAIL present -> stuck/verify"
            )
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
            check=True,
            capture_output=True,
        )
        new_head = subprocess.run(
            ["git", "-C", str(project_root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        # Verify command that outputs cleanup signature AND bare FAIL (as in go test output)
        verify_cmd = "echo 'error: unlinkat ...\\X.test.exe: Access is denied' && echo 'FAIL\tgithub.com/test/...' && exit 1"
        agent_output = (
            '{"status":"success","commit_sha":"abc","session_id":"test-session"}\n'
        )
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
            assert data["status"] == "stuck", (
                f"expected status=stuck (real failure present), got {data}"
            )
            assert data["stuck_type"] == "verify", (
                f"expected stuck_type=verify, got {data}"
            )
            print(
                "PASS: case 24b - win32 + cleanup signature + bare FAIL present -> stuck/verify"
            )
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
            check=True,
            capture_output=True,
        )
        new_head = subprocess.run(
            ["git", "-C", str(project_root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        # Verify command that fails with non-cleanup output
        verify_cmd = "echo 'something went wrong' && exit 1"
        agent_output = (
            '{"status":"success","commit_sha":"abc","session_id":"test-session"}\n'
        )
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
            assert data["stuck_type"] == "verify", (
                f"expected stuck_type=verify, got {data}"
            )
            print(
                "PASS: case 25 - win32 + ordinary non-zero (no signature) -> stuck/verify"
            )
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
            check=True,
            capture_output=True,
        )
        # Verify command with cleanup signature
        verify_cmd = (
            "echo 'error: unlinkat ...\\X.test.exe: Access is denied' && exit 1"
        )
        agent_output = (
            '{"status":"success","commit_sha":"abc","session_id":"test-session"}\n'
        )
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
            assert data["status"] == "stuck", (
                f"expected status=stuck (non-win32 sees failure), got {data}"
            )
            assert data["stuck_type"] == "verify", (
                f"expected stuck_type=verify, got {data}"
            )
            print(
                "PASS: case 26 - non-win32 + cleanup signature -> stuck/verify (platform gate)"
            )
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
        agent_output = (
            '{"status":"success","commit_sha":"abc","session_id":"test-session"}\n'
        )
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
            assert data["stuck_type"] == "logic", (
                f"expected stuck_type=logic, got {data}"
            )
            assert "no content commit" in data.get("reason", "").lower(), (
                f"expected 'no content commit' in reason, got {data}"
            )
            print(
                "PASS: #500 - parsed success with no content commit (HEAD == start_sha) -> stuck/logic"
            )
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
            assert data["stuck_type"] == "transient", (
                f"expected stuck_type=transient, got {data}"
            )
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
            assert data["stuck_type"] == "logic", (
                f"expected stuck_type=logic, got {data}"
            )
            print(
                "PASS: #499/#502 (b) - plain garbage + HEAD == start_sha -> stuck/logic (not transient)"
            )
        except Exception as exc:
            print(f"FAIL: case 29 ({exc}) captured={captured!r}", file=sys.stderr)
            errors += 1

    # Case 27: completeness gate (a) -- fewer commits than cards -> stuck/transient
    # card_ids={1,2} but only 1 commit since start_sha; self-reported success is demoted.
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        base_sha = _setup_fixture(project_root)
        # Make exactly 1 content commit since base_sha
        subprocess.run(
            ["git", "-C", str(project_root), "commit", "--allow-empty", "-m", "card-1"],
            check=True,
            capture_output=True,
        )
        # Use verify_cmd=None so the verify gate does not interfere
        agent_output = '{"status":"success","commit_sha":"abc","session_id":"s1"}\n'
        rc, captured = _capture_stdout(
            lambda: _forward_output(
                agent_output,
                project_root,
                start_sha=base_sha,
                verify_cmd=None,
                card_ids={1, 2},
            )
        )
        try:
            data = json.loads(captured.strip())
            assert data["status"] == "stuck", f"case 27a: expected stuck, got {data}"
            assert data["stuck_type"] == "incomplete", (
                f"case 27a: expected incomplete, got {data}"
            )
            assert "batch incomplete" in data.get("reason", ""), (
                f"case 27a: expected 'batch incomplete' in reason, got {data}"
            )
            print(
                "PASS: case 27a - completeness gate: fewer commits than cards -> stuck/incomplete"
            )
        except Exception as exc:
            print(f"FAIL: case 27a ({exc}) captured={captured!r}", file=sys.stderr)
            errors += 1

    # Case 27b: completeness gate (b) -- commit count >= len(card_ids) -> success preserved
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        base_sha = _setup_fixture(project_root)
        # Make exactly 2 content commits since base_sha (matching card_ids={1,2})
        subprocess.run(
            ["git", "-C", str(project_root), "commit", "--allow-empty", "-m", "card-1"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(project_root), "commit", "--allow-empty", "-m", "card-2"],
            check=True,
            capture_output=True,
        )
        agent_output = '{"status":"success","commit_sha":"abc","session_id":"s2"}\n'
        rc, captured = _capture_stdout(
            lambda: _forward_output(
                agent_output,
                project_root,
                start_sha=base_sha,
                verify_cmd=None,
                card_ids={1, 2},
            )
        )
        try:
            data = json.loads(captured.strip())
            assert data["status"] == "success", (
                f"case 27b: expected success, got {data}"
            )
            print(
                "PASS: case 27b - completeness gate: commit count == len(card_ids) -> success preserved"
            )
        except Exception as exc:
            print(f"FAIL: case 27b ({exc}) captured={captured!r}", file=sys.stderr)
            errors += 1

    # Case 28: dirty-tree gate (c) -- uncommitted in-scope tracked file -> stuck/logic
    # Set up a real git repo with a parent branch and a task branch.
    # README.md is committed on the task branch (owned by this task via parent-diff),
    # then dirtied again without committing. compute_terminal_dirt must detect it as
    # in-scope and dirty.
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        base_sha = _setup_fixture(project_root)
        # _setup_fixture commits on the default branch; treat that as the parent.
        branch_result = subprocess.run(
            ["git", "-C", str(project_root), "branch", "--show-current"],
            check=True,
            capture_output=True,
            text=True,
        )
        parent_branch_name = branch_result.stdout.strip()
        # Create a task branch off of base_sha.
        subprocess.run(
            ["git", "-C", str(project_root), "checkout", "-b", "task-branch"],
            check=True,
            capture_output=True,
        )
        # Make a commit on the task branch that modifies README.md (puts it in owned_paths).
        (project_root / "README.md").write_text("task change", encoding="utf-8")
        subprocess.run(
            ["git", "-C", str(project_root), "add", "README.md"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(project_root), "commit", "-m", "card-1-modify-readme"],
            check=True,
            capture_output=True,
        )
        # Dirty README.md again without committing -- it is in owned_paths, so in-scope.
        (project_root / "README.md").write_text("dirty in-scope", encoding="utf-8")
        # task_dir = _mill subdir.
        task_dir = project_root / "_mill"
        agent_output = '{"status":"success","commit_sha":"abc","session_id":"s3"}\n'
        rc, captured = _capture_stdout(
            lambda: _forward_output(
                agent_output,
                project_root,
                # Use base_sha (the initial commit) as start_sha so HEAD != start_sha
                # (the card-1 commit advanced HEAD), passing the no-content-commit check.
                start_sha=base_sha,
                verify_cmd=None,
                task_dir=task_dir,
                parent_branch=parent_branch_name,
            )
        )
        try:
            data = json.loads(captured.strip())
            assert data["status"] == "stuck", f"case 28c: expected stuck, got {data}"
            assert data["stuck_type"] == "logic", (
                f"case 28c: expected logic, got {data}"
            )
            assert "in-scope working tree dirty" in data.get("reason", ""), (
                f"case 28c: expected dirty reason, got {data}"
            )
            print(
                "PASS: case 28c - dirty-tree gate: uncommitted in-scope file -> stuck/logic"
            )
        except Exception as exc:
            print(f"FAIL: case 28c ({exc}) captured={captured!r}", file=sys.stderr)
            errors += 1

    # Case 28d: dirty-tree gate (d) -- clean in-scope tree -> success preserved
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        base_sha = _setup_fixture(project_root)
        subprocess.run(
            ["git", "-C", str(project_root), "commit", "--allow-empty", "-m", "card-1"],
            check=True,
            capture_output=True,
        )
        branch_result = subprocess.run(
            ["git", "-C", str(project_root), "branch", "--show-current"],
            check=True,
            capture_output=True,
            text=True,
        )
        current_branch = branch_result.stdout.strip()
        # Tree is clean -- no unstaged changes
        task_dir = project_root / "_mill"
        agent_output = '{"status":"success","commit_sha":"abc","session_id":"s4"}\n'
        rc, captured = _capture_stdout(
            lambda: _forward_output(
                agent_output,
                project_root,
                start_sha=base_sha,
                verify_cmd=None,
                task_dir=task_dir,
                parent_branch=current_branch,
            )
        )
        try:
            data = json.loads(captured.strip())
            assert data["status"] == "success", (
                f"case 28d: expected success, got {data}"
            )
            print(
                "PASS: case 28d - dirty-tree gate: clean in-scope tree -> success preserved"
            )
        except Exception as exc:
            print(f"FAIL: case 28d ({exc}) captured={captured!r}", file=sys.stderr)
            errors += 1

    # Case 29: backward compatibility (e) -- all new kwargs omitted -> no demotion
    # Verifies that existing callers that do not pass card_ids/task_dir/parent_branch
    # still get success when the report is valid and HEAD != start_sha.
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        base_sha = _setup_fixture(project_root)
        subprocess.run(
            ["git", "-C", str(project_root), "commit", "--allow-empty", "-m", "card-1"],
            check=True,
            capture_output=True,
        )
        agent_output = '{"status":"success","commit_sha":"abc","session_id":"s5"}\n'
        # Call without card_ids, task_dir, parent_branch -- all default to None
        rc, captured = _capture_stdout(
            lambda: _forward_output(
                agent_output,
                project_root,
                start_sha=base_sha,
                verify_cmd=None,
            )
        )
        try:
            data = json.loads(captured.strip())
            assert data["status"] == "success", (
                f"case 29e: expected success, got {data}"
            )
            print(
                "PASS: case 29e - backward compat: omitted new kwargs -> no demotion, success preserved"
            )
        except Exception as exc:
            print(f"FAIL: case 29e ({exc}) captured={captured!r}", file=sys.stderr)
            errors += 1

    # Case 30: two-gate sequence -- batch passes, module-wide fails -> stuck/verify
    # with "[module-wide verify]" prefix in reason.
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        base_sha = _setup_fixture(project_root)
        snapshot_path = project_root / "_mill" / ".cleanliness-snapshot-test.txt"
        _cleanliness.capture_snapshot(project_root, snapshot_path)
        subprocess.run(
            ["git", "-C", str(project_root), "commit", "--allow-empty", "-m", "second"],
            check=True,
            capture_output=True,
        )
        new_head = subprocess.run(
            ["git", "-C", str(project_root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        agent_output = (
            '{"status":"success","commit_sha":"abc","session_id":"test-session"}\n'
        )
        # Batch gate passes (exit 0), module-wide gate fails (exit 1)
        rc, captured = _capture_stdout(
            lambda: _forward_output(
                agent_output,
                project_root,
                start_sha=base_sha,
                snapshot_path=snapshot_path,
                verify_cmd="exit 0",
                module_wide_verify_cmd="exit 1",
            )
        )
        try:
            data = json.loads(captured.strip())
            assert data["status"] == "stuck", f"case 30: expected stuck, got {data}"
            assert data["stuck_type"] == "verify", (
                f"case 30: expected stuck_type=verify, got {data}"
            )
            assert "[module-wide verify]" in data.get("reason", ""), (
                f"case 30: expected '[module-wide verify]' prefix in reason, got {data}"
            )
            assert data.get("commit_sha") == new_head, (
                f"case 30: expected commit_sha={new_head}, got {data}"
            )
            print(
                "PASS: case 30 - two-gate: batch passes + module-wide fails -> stuck/verify with prefix"
            )
        except Exception as exc:
            print(f"FAIL: case 30 ({exc}) captured={captured!r}", file=sys.stderr)
            errors += 1

    # Case 31: module_wide_verify_cmd=None runs only the batch gate (backward compat)
    # Verify that _run_verify_gates with None module_wide behaves identically to
    # _run_verify_gate for both the pass and fail cases.
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        _setup_fixture(project_root)
        try:
            # Batch gate passes, module-wide is None -> no stuck result
            result = _run_verify_gates(project_root, "exit 0", None)
            assert result is None, f"case 31a: expected None (both pass), got {result}"
            # Batch gate fails, module-wide is None -> stuck dict (batch reason, no prefix)
            result = _run_verify_gates(project_root, "exit 1", None)
            assert result is not None, f"case 31b: expected stuck dict, got {result}"
            assert result["stuck_type"] == "verify", (
                f"case 31b: expected stuck_type=verify, got {result}"
            )
            assert "[module-wide verify]" not in result.get("reason", ""), (
                f"case 31b: expected no module-wide prefix in batch failure reason, got {result}"
            )
            print(
                "PASS: case 31 - module_wide_verify_cmd=None: only batch gate runs (backward compat)"
            )
        except Exception as exc:
            print(f"FAIL: case 31 ({exc})", file=sys.stderr)
            errors += 1

    # Case 32: module-wide gate is reached from the inferred-success path (no snapshot)
    # Verifies that the no-snapshot inferred-success code path also invokes the module-wide gate.
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        base_sha = _setup_fixture(project_root)
        # Make a new commit so inferred-success fires (HEAD != start_sha, clean tree)
        subprocess.run(
            ["git", "-C", str(project_root), "commit", "--allow-empty", "-m", "second"],
            check=True,
            capture_output=True,
        )
        new_head = subprocess.run(
            ["git", "-C", str(project_root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        # No JSON in output so the inferred-success path fires (no snapshot provided)
        rc, captured = _capture_stdout(
            lambda: _forward_output(
                "garbage output with no json",
                project_root,
                start_sha=base_sha,
                # No snapshot_path -> no-snapshot branch
                verify_cmd="exit 0",
                module_wide_verify_cmd="exit 1",
            )
        )
        try:
            data = json.loads(captured.strip())
            assert data["status"] == "stuck", f"case 32: expected stuck, got {data}"
            assert data["stuck_type"] == "verify", (
                f"case 32: expected stuck_type=verify, got {data}"
            )
            assert "[module-wide verify]" in data.get("reason", ""), (
                f"case 32: expected '[module-wide verify]' prefix in reason, got {data}"
            )
            print(
                "PASS: case 32 - module-wide gate reached from no-snapshot inferred-success path"
            )
        except Exception as exc:
            print(f"FAIL: case 32 ({exc}) captured={captured!r}", file=sys.stderr)
            errors += 1

    # Case 33: benign Go output -- cleanup race with "fail" only inside an ok-line path
    # Regression for the bare-"fail"-substring over-match: before the fix, output like
    # "ok  \tpkg/failover\t0.1s" was classified as a real failure because "fail" appeared
    # as a substring. After the fix, line-anchored matching is used, so only lines that
    # start with "fail" (for the package-summary) or contain "--- fail" (for per-test)
    # trigger the failure marker -- a passing "ok" line with "failover" in the path does not.
    try:
        # Output has a Windows cleanup-race signature (unlinkat / Access is denied) and
        # Go test output whose only "fail" substring is inside an ok-line package path.
        # The real TAB character is used in the ok-line (as produced by go test).
        benign_go_output = (
            "error: unlinkat ...\\X.test.exe: Access is denied\n"
            "ok  \tpkg/failover\t0.1s\n"
            "ok  \tpkg/other\t0.2s\n"
        )
        result = _is_benign_windows_cleanup(benign_go_output)
        assert result is True, (
            f"case 33: expected True (benign -- fail only in ok-line path), got {result}"
        )
        print(
            "PASS: case 33 - benign Go output: cleanup race + fail only in ok-line path -> True"
        )
    except Exception as exc:
        print(f"FAIL: case 33 ({exc})", file=sys.stderr)
        errors += 1

    # Case 34: real Go test failure -- cleanup race + "--- FAIL:" per-test line -> False
    # Verifies that a real per-test failure line still triggers the failure marker even
    # after the line-anchoring change.
    try:
        real_fail_per_test_output = (
            "error: unlinkat ...\\X.test.exe: Access is denied\n"
            "ok  \tpkg/failover\t0.1s\n"
            "--- FAIL: TestSomething (0.01s)\n"
        )
        result = _is_benign_windows_cleanup(real_fail_per_test_output)
        assert result is False, (
            f"case 34: expected False (real --- FAIL: line present), got {result}"
        )
        print("PASS: case 34 - real Go failure: cleanup race + --- FAIL: line -> False")
    except Exception as exc:
        print(f"FAIL: case 34 ({exc})", file=sys.stderr)
        errors += 1

    # Case 35: real Go package failure -- cleanup race + "FAIL\tpkg" summary line -> False
    # Verifies that the package-summary line "FAIL\tgithub.com/..." (with a real TAB
    # after FAIL at the start of the line) still triggers the failure marker.
    try:
        real_fail_pkg_output = (
            "error: unlinkat ...\\X.test.exe: Access is denied\n"
            "ok  \tpkg/failover\t0.1s\n"
            "FAIL\tgithub.com/test/pkg\t0.05s\n"
        )
        result = _is_benign_windows_cleanup(real_fail_pkg_output)
        assert result is False, (
            f"case 35: expected False (real FAIL\\tpkg summary line present), got {result}"
        )
        print(
            "PASS: case 35 - real Go failure: cleanup race + FAIL\\tpkg summary line -> False"
        )
    except Exception as exc:
        print(f"FAIL: case 35 ({exc})", file=sys.stderr)
        errors += 1

    # Test A: git_root kwarg selects cwd for the verify subprocess (#554)
    # Mock subprocess.run so the cwd kwarg is observable without executing real commands.
    with tempfile.TemporaryDirectory() as tmpdir:
        hub_dir = Path(tmpdir) / "hub"
        repo_dir = Path(tmpdir) / "repo"
        hub_dir.mkdir()
        repo_dir.mkdir()
        try:
            with unittest.mock.patch("_implementer_common.subprocess.run") as mock_run:
                # Configure mock to return a passing result (returncode=0)
                mock_result = unittest.mock.MagicMock()
                mock_result.returncode = 0
                mock_result.stdout = ""
                mock_result.stderr = ""
                mock_run.return_value = mock_result

                # Call with git_root; the verify subprocess cwd must equal git_root.
                result = _run_verify_gate(hub_dir, "echo ok", git_root=repo_dir)
                assert result is None, f"Test A: expected None (pass), got {result}"
                # Confirm cwd passed to subprocess.run equals repo_dir (git_root)
                call_kwargs = mock_run.call_args[1]
                assert call_kwargs.get("cwd") == repo_dir, (
                    f"Test A: expected cwd=repo_dir, got {call_kwargs.get('cwd')}"
                )

                # Call without git_root; the verify subprocess cwd must equal hub_dir (project_root).
                mock_run.reset_mock()
                result = _run_verify_gate(hub_dir, "echo ok")
                assert result is None, (
                    f"Test A (no git_root): expected None (pass), got {result}"
                )
                call_kwargs_no_root = mock_run.call_args[1]
                assert call_kwargs_no_root.get("cwd") == hub_dir, (
                    f"Test A (no git_root): expected cwd=hub_dir, got {call_kwargs_no_root.get('cwd')}"
                )

            print("PASS: Test A - git_root kwarg selects verify subprocess cwd (#554)")
        except Exception as exc:
            print(f"FAIL: Test A ({exc})", file=sys.stderr)
            errors += 1

    # Test B: git_root=None falls back to project_root as the verify subprocess cwd (#554)
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        try:
            with unittest.mock.patch("_implementer_common.subprocess.run") as mock_run:
                mock_result = unittest.mock.MagicMock()
                mock_result.returncode = 0
                mock_result.stdout = ""
                mock_result.stderr = ""
                mock_run.return_value = mock_result

                # Explicitly pass git_root=None; cwd must fall back to project_root.
                result = _run_verify_gate(project_root, "echo ok", git_root=None)
                assert result is None, f"Test B: expected None (pass), got {result}"
                call_kwargs = mock_run.call_args[1]
                assert call_kwargs.get("cwd") == project_root, (
                    f"Test B: expected cwd=project_root, got {call_kwargs.get('cwd')}"
                )

            print(
                "PASS: Test B - git_root=None falls back to project_root as verify cwd (#554)"
            )
        except Exception as exc:
            print(f"FAIL: Test B ({exc})", file=sys.stderr)
            errors += 1

    # Test B2: cwd_override takes precedence over both git_root and project_root (#604)
    # A synthetic cwd_override Path must win as the verify subprocess's cwd even when
    # both git_root and project_root are also supplied.
    with tempfile.TemporaryDirectory() as tmpdir:
        hub_dir = Path(tmpdir) / "hub"
        repo_dir = Path(tmpdir) / "repo"
        override_dir = Path(tmpdir) / "override"
        hub_dir.mkdir()
        repo_dir.mkdir()
        override_dir.mkdir()
        try:
            with unittest.mock.patch("_implementer_common.subprocess.run") as mock_run:
                mock_result = unittest.mock.MagicMock()
                mock_result.returncode = 0
                mock_result.stdout = ""
                mock_result.stderr = ""
                mock_run.return_value = mock_result

                # Both git_root and cwd_override supplied; cwd_override must win.
                result = _run_verify_gate(
                    hub_dir, "echo ok", git_root=repo_dir, cwd_override=override_dir
                )
                assert result is None, f"Test B2: expected None (pass), got {result}"
                call_kwargs = mock_run.call_args[1]
                assert call_kwargs.get("cwd") == override_dir, (
                    f"Test B2: expected cwd=override_dir, got {call_kwargs.get('cwd')}"
                )

            print(
                "PASS: Test B2 - cwd_override takes precedence over git_root and project_root (#604)"
            )
        except Exception as exc:
            print(f"FAIL: Test B2 ({exc})", file=sys.stderr)
            errors += 1

    # Test C: dotnet build-server shutdown fires regardless of verify exit code (#556)
    # Sub-case C1: verify exits 0 (success) -> cleanup still fires.
    # Sub-case C2: verify exits 1 (failure) -> cleanup still fires.
    # Also asserts cleanup does NOT fire when the command does not contain "dotnet".
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        try:
            dotnet_cmd = "dotnet test MyProject.csproj"
            non_dotnet_cmd = "pytest tests/ -q"

            # Sub-case C1: verify succeeds (returncode=0); dotnet cleanup must still fire.
            with (
                unittest.mock.patch("sys.platform", "win32"),
                unittest.mock.patch("_implementer_common.subprocess.run") as mock_run,
            ):
                # First call is the verify subprocess; second is the dotnet shutdown call.
                passing_result = unittest.mock.MagicMock()
                passing_result.returncode = 0
                passing_result.stdout = ""
                passing_result.stderr = ""
                # The dotnet shutdown call also needs a mock result (ignored by caller).
                shutdown_result = unittest.mock.MagicMock()
                mock_run.side_effect = [passing_result, shutdown_result]

                result = _run_verify_gate(project_root, dotnet_cmd)
                assert result is None, f"Test C1: expected None (pass), got {result}"

                # Confirm dotnet build-server shutdown was called.
                all_calls = mock_run.call_args_list
                shutdown_calls = [
                    c
                    for c in all_calls
                    if c.args and c.args[0] == ["dotnet", "build-server", "shutdown"]
                ]
                assert len(shutdown_calls) == 1, (
                    f"Test C1: expected 1 dotnet shutdown call on success, got {shutdown_calls}"
                )

            print("PASS: Test C1 - dotnet cleanup fires on verify success (#556)")

            # Sub-case C2: verify fails (returncode=1); dotnet cleanup must still fire.
            with (
                unittest.mock.patch("sys.platform", "win32"),
                unittest.mock.patch("_implementer_common.subprocess.run") as mock_run,
            ):
                failing_result = unittest.mock.MagicMock()
                failing_result.returncode = 1
                # Provide explicit string attrs so error-handling string ops do not raise on MagicMock.
                failing_result.stdout = ""
                failing_result.stderr = ""
                shutdown_result = unittest.mock.MagicMock()
                mock_run.side_effect = [failing_result, shutdown_result]

                result = _run_verify_gate(project_root, dotnet_cmd)
                # Verify gate returns a stuck dict on failure.
                assert result is not None, (
                    "Test C2: expected stuck dict on verify failure"
                )
                assert result["stuck_type"] == "verify", (
                    f"Test C2: expected stuck_type=verify, got {result}"
                )

                # Confirm dotnet build-server shutdown was called even on failure.
                all_calls = mock_run.call_args_list
                shutdown_calls = [
                    c
                    for c in all_calls
                    if c.args and c.args[0] == ["dotnet", "build-server", "shutdown"]
                ]
                assert len(shutdown_calls) == 1, (
                    f"Test C2: expected 1 dotnet shutdown call on failure, got {shutdown_calls}"
                )

            print("PASS: Test C2 - dotnet cleanup fires on verify failure (#556)")

            # Non-dotnet command: cleanup must NOT fire.
            with (
                unittest.mock.patch("sys.platform", "win32"),
                unittest.mock.patch("_implementer_common.subprocess.run") as mock_run,
            ):
                non_dotnet_result = unittest.mock.MagicMock()
                non_dotnet_result.returncode = 0
                non_dotnet_result.stdout = ""
                non_dotnet_result.stderr = ""
                mock_run.return_value = non_dotnet_result

                result = _run_verify_gate(project_root, non_dotnet_cmd)
                assert result is None, (
                    f"Test C non-dotnet: expected None (pass), got {result}"
                )

                all_calls = mock_run.call_args_list
                shutdown_calls = [
                    c
                    for c in all_calls
                    if c.args and c.args[0] == ["dotnet", "build-server", "shutdown"]
                ]
                assert len(shutdown_calls) == 0, (
                    f"Test C non-dotnet: expected 0 dotnet shutdown calls, got {shutdown_calls}"
                )

            print(
                "PASS: Test C non-dotnet - dotnet cleanup skipped for non-dotnet commands (#556)"
            )

        except Exception as exc:
            print(f"FAIL: Test C ({exc})", file=sys.stderr)
            errors += 1

    # Case 36 -- Bug #557 (parsed success, start-batch commit only -> stuck/logic)
    # Verifies that when the only commit since start_sha is a "mill-go: start batch" commit,
    # the parsed-success path emits stuck/logic rather than success.
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        pre_start_sha = _setup_fixture(project_root)
        # Simulate the prepare-stage housekeeping commit.
        subprocess.run(
            [
                "git",
                "-C",
                str(project_root),
                "commit",
                "--allow-empty",
                "-m",
                "mill-go: start batch test-batch",
            ],
            check=True,
            capture_output=True,
        )
        head_sha = subprocess.run(
            ["git", "-C", str(project_root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        agent_output = (
            f'{{"status":"success","commit_sha":"{head_sha}","session_id":"test"}}'
        )
        rc, captured = _capture_stdout(
            lambda: _forward_output(
                agent_output,
                project_root,
                start_sha=pre_start_sha,
                card_ids={1},
                session_id="test",
            )
        )
        try:
            data = json.loads(captured.strip())
            assert data["status"] == "stuck", f"case 36: expected stuck, got {data}"
            assert data["stuck_type"] == "logic", (
                f"case 36: expected stuck_type=logic, got {data}"
            )
            assert "no content commit" in data.get("reason", ""), (
                f"case 36: expected 'no content commit' in reason, got {data}"
            )
            print(
                "PASS: case 36 - Bug #557 parsed success with start-batch commit only -> stuck/logic"
            )
        except Exception as exc:
            print(f"FAIL: case 36 ({exc}) captured={captured!r}", file=sys.stderr)
            errors += 1

    # Case 37 -- Bug #557 (start commit + code commit -> success, guard does not fire)
    # When the implementer adds a real code commit after the start-batch commit, the guard
    # must NOT fire and the result must be success.
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        pre_start_sha = _setup_fixture(project_root)
        # Simulate the prepare-stage housekeeping commit.
        subprocess.run(
            [
                "git",
                "-C",
                str(project_root),
                "commit",
                "--allow-empty",
                "-m",
                "mill-go: start batch test-batch",
            ],
            check=True,
            capture_output=True,
        )
        # Add a real code commit so two commits exist since pre_start_sha.
        subprocess.run(
            [
                "git",
                "-C",
                str(project_root),
                "commit",
                "--allow-empty",
                "-m",
                "fix(foo): real code change",
            ],
            check=True,
            capture_output=True,
        )
        head_sha = subprocess.run(
            ["git", "-C", str(project_root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        agent_output = (
            f'{{"status":"success","commit_sha":"{head_sha}","session_id":"test"}}'
        )
        rc, captured = _capture_stdout(
            lambda: _forward_output(
                agent_output,
                project_root,
                start_sha=pre_start_sha,
                card_ids={1},
                session_id="test",
            )
        )
        try:
            data = json.loads(captured.strip())
            assert data["status"] == "success", f"case 37: expected success, got {data}"
            print(
                "PASS: case 37 - Bug #557 start commit + code commit -> success, guard does not fire"
            )
        except Exception as exc:
            print(f"FAIL: case 37 ({exc}) captured={captured!r}", file=sys.stderr)
            errors += 1

    # Case 38 -- Bug #557 (retry scenario: start_sha = start-batch commit, one code commit -> success)
    # In a retry, skip_start_commit already ran, so start_sha points at the housekeeping commit.
    # With a real code commit after it, there is exactly one commit since start_sha and its
    # message does NOT start with "mill-go: start batch", so the guard must NOT fire.
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        _setup_fixture(project_root)
        # Simulate the prepare-stage housekeeping commit; capture its SHA as start_sha.
        subprocess.run(
            [
                "git",
                "-C",
                str(project_root),
                "commit",
                "--allow-empty",
                "-m",
                "mill-go: start batch test-batch",
            ],
            check=True,
            capture_output=True,
        )
        # start_sha points at the housekeeping commit (retry scenario).
        start_sha_retry = subprocess.run(
            ["git", "-C", str(project_root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        # Add the real code commit (the one the implementer made on the retry).
        subprocess.run(
            [
                "git",
                "-C",
                str(project_root),
                "commit",
                "--allow-empty",
                "-m",
                "fix(foo): card-1 implementation",
            ],
            check=True,
            capture_output=True,
        )
        head_sha = subprocess.run(
            ["git", "-C", str(project_root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        agent_output = (
            f'{{"status":"success","commit_sha":"{head_sha}","session_id":"test"}}'
        )
        rc, captured = _capture_stdout(
            lambda: _forward_output(
                agent_output,
                project_root,
                start_sha=start_sha_retry,
                card_ids={1},
                session_id="test",
            )
        )
        try:
            data = json.loads(captured.strip())
            assert data["status"] == "success", f"case 38: expected success, got {data}"
            print(
                "PASS: case 38 - Bug #557 retry scenario: start_sha at start-batch commit + code commit -> success"
            )
        except Exception as exc:
            print(f"FAIL: case 38 ({exc}) captured={captured!r}", file=sys.stderr)
            errors += 1

    # Case 39 -- Bug #557 (inference path, start-batch commit only, snapshot present -> stuck/logic)
    # Exercises the snapshot-present clean-tree inference emit path (~line 851). When the only
    # commit since pre_start_sha is the prepare housekeeping commit and the tree is clean,
    # the guard must fire and emit stuck/logic before the success is printed.
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        pre_start_sha = _setup_fixture(project_root)
        # Capture a snapshot of the clean repo before the prepare commit.
        snapshot_path = project_root / "_mill" / ".cleanliness-snapshot-test.txt"
        _cleanliness.capture_snapshot(project_root, snapshot_path)
        # Simulate the prepare-stage housekeeping commit.
        subprocess.run(
            [
                "git",
                "-C",
                str(project_root),
                "commit",
                "--allow-empty",
                "-m",
                "mill-go: start batch test-batch",
            ],
            check=True,
            capture_output=True,
        )
        # Leave tree clean; no code commits made.
        rc, captured = _capture_stdout(
            lambda: _forward_output(
                "no json here",
                project_root,
                start_sha=pre_start_sha,
                snapshot_path=snapshot_path,
                session_id="test",
            )
        )
        try:
            data = json.loads(captured.strip())
            assert data["status"] == "stuck", f"case 39: expected stuck, got {data}"
            assert data["stuck_type"] == "logic", (
                f"case 39: expected stuck_type=logic, got {data}"
            )
            assert "batch-start commit" in data.get("reason", ""), (
                f"case 39: expected 'batch-start commit' in reason, got {data}"
            )
            print(
                "PASS: case 39 - Bug #557 inference path (snapshot present, start-batch commit only) -> stuck/logic"
            )
        except Exception as exc:
            print(f"FAIL: case 39 ({exc}) captured={captured!r}", file=sys.stderr)
            errors += 1

    # Case 40 -- Bug #548 (completeness gate disabled when verify_cmd is not None)
    # Calls _batch_completeness_stuck directly with verify_cmd set to a non-None value.
    # Even though card_ids={1,2} and only one commit was made (which would normally fire),
    # the gate must return None because verify_cmd is present.
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        start_sha_40 = _setup_fixture(project_root)
        # Make one commit (card_ids will be {1,2}, so 1 < 2 would normally fire).
        subprocess.run(
            [
                "git",
                "-C",
                str(project_root),
                "commit",
                "--allow-empty",
                "-m",
                "card-1 only",
            ],
            check=True,
            capture_output=True,
        )
        try:
            result = _batch_completeness_stuck(
                project_root,
                start_sha_40,
                card_ids={1, 2},
                session_id="test",
                verify_cmd="should-not-be-called",
            )
            assert result is None, (
                f"case 40: expected None (gate disabled by verify_cmd), got {result}"
            )
            print(
                "PASS: case 40 - Bug #548 completeness gate disabled when verify_cmd is not None"
            )
        except Exception as exc:
            print(f"FAIL: case 40 ({exc})", file=sys.stderr)
            errors += 1

    # Case 41 -- Bug #548 (regression guard: gate fires when verify_cmd is None)
    # Same setup as Case 40 but verify_cmd=None. Confirms the gate still fires on the
    # same commit count so the fix in Case 40 did not accidentally disable it permanently.
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        start_sha_41 = _setup_fixture(project_root)
        subprocess.run(
            [
                "git",
                "-C",
                str(project_root),
                "commit",
                "--allow-empty",
                "-m",
                "card-1 only",
            ],
            check=True,
            capture_output=True,
        )
        try:
            result = _batch_completeness_stuck(
                project_root,
                start_sha_41,
                card_ids={1, 2},
                session_id="test",
                verify_cmd=None,
            )
            assert result is not None, (
                f"case 41: expected stuck dict (gate fires), got {result}"
            )
            assert result["status"] == "stuck", (
                f"case 41: expected status=stuck, got {result}"
            )
            assert result["stuck_type"] == "incomplete", (
                f"case 41: expected stuck_type=incomplete, got {result}"
            )
            print(
                "PASS: case 41 - Bug #548 regression: gate fires when verify_cmd is None -> incomplete"
            )
        except Exception as exc:
            print(f"FAIL: case 41 ({exc})", file=sys.stderr)
            errors += 1

    # Case 42 -- Bug #545/#560 (commits_made: 2 in stuck dict)
    # Verifies that the commits_made field reflects the actual commit count.
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        start_sha_42 = _setup_fixture(project_root)
        # Make exactly two commits since start_sha (card_ids={1,2,3} so 2 < 3 fires).
        for msg in ("card-1", "card-2"):
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(project_root),
                    "commit",
                    "--allow-empty",
                    "-m",
                    msg,
                ],
                check=True,
                capture_output=True,
            )
        try:
            result = _batch_completeness_stuck(
                project_root,
                start_sha_42,
                card_ids={1, 2, 3},
                session_id="test",
            )
            assert result is not None, f"case 42: expected stuck dict, got {result}"
            assert result.get("commits_made") == 2, (
                f"case 42: expected commits_made=2, got {result}"
            )
            print("PASS: case 42 - Bug #545/#560 commits_made=2 in stuck dict")
        except Exception as exc:
            print(f"FAIL: case 42 ({exc})", file=sys.stderr)
            errors += 1

    # Case 43 -- Bug #545/#560 (commits_made: 0 when no commits since start_sha)
    # Verifies that commits_made=0 appears when the implementer made no commits at all.
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        start_sha_43 = _setup_fixture(project_root)
        # No commits made after capturing start_sha.
        try:
            result = _batch_completeness_stuck(
                project_root,
                start_sha_43,
                card_ids={1, 2, 3},
                session_id="test",
            )
            assert result is not None, f"case 43: expected stuck dict, got {result}"
            assert result["status"] == "stuck", (
                f"case 43: expected status=stuck, got {result}"
            )
            assert result["stuck_type"] == "incomplete", (
                f"case 43: expected stuck_type=incomplete, got {result}"
            )
            assert result.get("commits_made") == 0, (
                f"case 43: expected commits_made=0, got {result}"
            )
            print(
                "PASS: case 43 - Bug #545/#560 commits_made=0 when no commits since start_sha -> incomplete"
            )
        except Exception as exc:
            print(f"FAIL: case 43 ({exc})", file=sys.stderr)
            errors += 1

    # Case 44a -- #570 partial-batch reclassify: inferred no-snapshot path, verify fails,
    # k=1 content commit + 1 housekeeping commit (raw range=2) -> stuck_type:incomplete
    # with commits_made=1 (content count, not raw count).
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        base_sha = _setup_fixture(project_root)
        # Housekeeping commit that prepare always inserts before the implementer runs.
        subprocess.run(
            ["git", "-C", str(project_root), "commit", "--allow-empty",
             "-m", "mill-go: start batch test-batch"],
            check=True, capture_output=True,
        )
        # k=1 content commit; raw range from base_sha = 2.
        subprocess.run(
            ["git", "-C", str(project_root), "commit", "--allow-empty", "-m", "card-1 done"],
            check=True, capture_output=True,
        )
        # card_ids={1,2,3} so content=1 satisfies 0<1<3 -> reclassify to incomplete.
        rc, captured = _capture_stdout(
            lambda: _forward_output(
                "garbage output with no json",
                project_root,
                start_sha=base_sha,
                verify_cmd="exit 1",
                card_ids={1, 2, 3},
                session_id="test-a",
            )
        )
        try:
            data = json.loads(captured.strip())
            assert data["status"] == "stuck", f"case 44a: expected stuck, got {data}"
            assert data["stuck_type"] == "incomplete", (
                f"case 44a: expected incomplete (not verify), got {data}"
            )
            assert data.get("commits_made") == 1, (
                f"case 44a: expected commits_made=1 (content, not 2 raw), got {data}"
            )
            assert "batch incomplete" in data.get("reason", ""), (
                f"case 44a: expected 'batch incomplete' in reason, got {data}"
            )
            print(
                "PASS: case 44a - partial-batch reclassify:"
                " inferred path k=1 content N=3 -> incomplete commits_made=1"
            )
        except Exception as exc:
            print(f"FAIL: case 44a ({exc}) captured={captured!r}", file=sys.stderr)
            errors += 1

    # Case 45b -- #570 partial-batch reclassify: complete batch (content>=N), verify fails
    # -> stuck_type:verify preserved (not reclassified to transient).
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        base_sha = _setup_fixture(project_root)
        subprocess.run(
            ["git", "-C", str(project_root), "commit", "--allow-empty",
             "-m", "mill-go: start batch test-batch"],
            check=True, capture_output=True,
        )
        # 3 content commits matching card_ids={1,2,3} -> content=3>=3 -> no reclassification.
        for msg in ("card-1", "card-2", "card-3"):
            subprocess.run(
                ["git", "-C", str(project_root), "commit", "--allow-empty", "-m", msg],
                check=True, capture_output=True,
            )
        rc, captured = _capture_stdout(
            lambda: _forward_output(
                "garbage output with no json",
                project_root,
                start_sha=base_sha,
                verify_cmd="exit 1",
                card_ids={1, 2, 3},
            )
        )
        try:
            data = json.loads(captured.strip())
            assert data["status"] == "stuck", f"case 45b: expected stuck, got {data}"
            assert data["stuck_type"] == "verify", (
                f"case 45b: expected verify (full batch, no reclassify), got {data}"
            )
            print(
                "PASS: case 45b - partial-batch reclassify:"
                " complete batch, verify fails -> still stuck/verify"
            )
        except Exception as exc:
            print(f"FAIL: case 45b ({exc}) captured={captured!r}", file=sys.stderr)
            errors += 1

    # Case 46c -- #570 partial-batch reclassify: zero content commits (only housekeeping),
    # verify fails -> stuck_type:logic "no content commit".
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        base_sha = _setup_fixture(project_root)
        subprocess.run(
            ["git", "-C", str(project_root), "commit", "--allow-empty",
             "-m", "mill-go: start batch test-batch"],
            check=True, capture_output=True,
        )
        # No content commits -- content=0 after housekeeping subtraction.
        rc, captured = _capture_stdout(
            lambda: _forward_output(
                "garbage output with no json",
                project_root,
                start_sha=base_sha,
                verify_cmd="exit 1",
                card_ids={1, 2, 3},
                session_id="test-c",
            )
        )
        try:
            data = json.loads(captured.strip())
            assert data["status"] == "stuck", f"case 46c: expected stuck, got {data}"
            assert data["stuck_type"] == "logic", (
                f"case 46c: expected logic (zero content), got {data}"
            )
            assert "no content commit" in data.get("reason", ""), (
                f"case 46c: expected 'no content commit' in reason, got {data}"
            )
            print(
                "PASS: case 46c - partial-batch reclassify:"
                " zero content commits, verify fails -> stuck/logic"
            )
        except Exception as exc:
            print(f"FAIL: case 46c ({exc}) captured={captured!r}", file=sys.stderr)
            errors += 1

    # Case 47d -- #570 partial-batch reclassify: complete batch, verify passes -> success.
    # When verify passes the reclassify helper does not run (verify-pass-is-conclusive).
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        base_sha = _setup_fixture(project_root)
        subprocess.run(
            ["git", "-C", str(project_root), "commit", "--allow-empty",
             "-m", "mill-go: start batch test-batch"],
            check=True, capture_output=True,
        )
        for msg in ("card-1", "card-2", "card-3"):
            subprocess.run(
                ["git", "-C", str(project_root), "commit", "--allow-empty", "-m", msg],
                check=True, capture_output=True,
            )
        rc, captured = _capture_stdout(
            lambda: _forward_output(
                "garbage output with no json",
                project_root,
                start_sha=base_sha,
                verify_cmd="exit 0",
                card_ids={1, 2, 3},
            )
        )
        try:
            data = json.loads(captured.strip())
            assert data["status"] == "success", (
                f"case 47d: expected success (verify passes), got {data}"
            )
            print(
                "PASS: case 47d - partial-batch reclassify:"
                " complete batch, verify passes -> success"
            )
        except Exception as exc:
            print(f"FAIL: case 47d ({exc}) captured={captured!r}", file=sys.stderr)
            errors += 1

    # Case 48e -- #570 canonical case: parsed-success path, verify fails, 0<content<N.
    # Exercises the _gate_session_id hoist in _forward_output; the inferred-path cases
    # (44a-47d) do not cover this code path.
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        base_sha = _setup_fixture(project_root)
        subprocess.run(
            ["git", "-C", str(project_root), "commit", "--allow-empty",
             "-m", "mill-go: start batch test-batch"],
            check=True, capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(project_root), "commit", "--allow-empty", "-m", "card-1 done"],
            check=True, capture_output=True,
        )
        # Agent output contains a success JSON -- exercises the parsed-success reclassify site.
        agent_output = (
            '{"status":"success","commit_sha":"abc","session_id":"parsed-session"}\n'
        )
        rc, captured = _capture_stdout(
            lambda: _forward_output(
                agent_output,
                project_root,
                start_sha=base_sha,
                verify_cmd="exit 1",
                card_ids={1, 2, 3},
                session_id="caller-session",
            )
        )
        try:
            data = json.loads(captured.strip())
            assert data["status"] == "stuck", f"case 48e: expected stuck, got {data}"
            assert data["stuck_type"] == "incomplete", (
                f"case 48e: expected incomplete (not verify), got {data}"
            )
            assert data.get("commits_made") == 1, (
                f"case 48e: expected commits_made=1 (content), got {data}"
            )
            print(
                "PASS: case 48e - parsed-success path: partial-batch verify failure"
                " -> incomplete (gate_session_id hoist exercised)"
            )
        except Exception as exc:
            print(f"FAIL: case 48e ({exc}) captured={captured!r}", file=sys.stderr)
            errors += 1

    # Case 49f -- _batch_completeness_stuck with housekeeping commit: commits_made reflects
    # content count (1), not raw range count (2).
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        base_sha = _setup_fixture(project_root)
        subprocess.run(
            ["git", "-C", str(project_root), "commit", "--allow-empty",
             "-m", "mill-go: start batch test-batch"],
            check=True, capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(project_root), "commit", "--allow-empty", "-m", "card-1"],
            check=True, capture_output=True,
        )
        # raw range = 2, content = 1 (housekeeping subtracted); card_ids={1,2} -> 1<2 -> stuck.
        try:
            result = _batch_completeness_stuck(
                project_root,
                base_sha,
                card_ids={1, 2},
                session_id="test",
            )
            assert result is not None, f"case 49f: expected stuck dict, got {result}"
            assert result["stuck_type"] == "incomplete", (
                f"case 49f: expected incomplete, got {result}"
            )
            assert result.get("commits_made") == 1, (
                f"case 49f: expected commits_made=1 (content not 2 raw), got {result}"
            )
            print(
                "PASS: case 49f - _batch_completeness_stuck with housekeeping:"
                " commits_made=1 (content, not 2 raw) -> incomplete"
            )
        except Exception as exc:
            print(f"FAIL: case 49f ({exc})", file=sys.stderr)
            errors += 1

    # Case 50g -- one-card-short with housekeeping commit: content==N-1 now flags incomplete.
    # Without the housekeeping exclusion, raw_count==N==len(card_ids) would NOT fire the gate.
    # With exclusion, content==N-1<N fires it -> stuck_type:incomplete, commits_made=N-1.
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        base_sha = _setup_fixture(project_root)
        subprocess.run(
            ["git", "-C", str(project_root), "commit", "--allow-empty",
             "-m", "mill-go: start batch test-batch"],
            check=True, capture_output=True,
        )
        # N=3, N-1=2 content commits; raw_count = 3 == len(card_ids), content = 2 < len(card_ids).
        for msg in ("card-1", "card-2"):
            subprocess.run(
                ["git", "-C", str(project_root), "commit", "--allow-empty", "-m", msg],
                check=True, capture_output=True,
            )
        try:
            result = _batch_completeness_stuck(
                project_root,
                base_sha,
                card_ids={1, 2, 3},
                session_id="test",
            )
            assert result is not None, (
                f"case 50g: expected stuck dict (raw==N but content==N-1), got {result}"
            )
            assert result["stuck_type"] == "incomplete", (
                f"case 50g: expected incomplete, got {result}"
            )
            assert result.get("commits_made") == 2, (
                f"case 50g: expected commits_made=2 (N-1 content), got {result}"
            )
            print(
                "PASS: case 50g - one-card-short with housekeeping:"
                " raw==N but content==N-1 -> stuck/incomplete commits_made=2"
            )
        except Exception as exc:
            print(f"FAIL: case 50g ({exc})", file=sys.stderr)
            errors += 1

    # Case 51: #574 regression -- no-JSON inference path, verify_cmd set and PASSES,
    # content-commits < len(card_ids) -> stuck/incomplete with commits_made and commit_sha.
    # Before the fix, _batch_completeness_stuck was disabled when verify_cmd was set,
    # so a partial batch on the no-JSON path would slip through as inferred success.
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        base_sha = _setup_fixture(project_root)
        # Housekeeping commit (prepare stage).
        subprocess.run(
            ["git", "-C", str(project_root), "commit", "--allow-empty",
             "-m", "mill-go: start batch my-batch"],
            check=True, capture_output=True,
        )
        # One content commit (card_ids={1,2,3}, so content=1 < 3 -> partial batch).
        subprocess.run(
            ["git", "-C", str(project_root), "commit", "--allow-empty", "-m", "card-1"],
            check=True, capture_output=True,
        )
        new_head_51 = subprocess.run(
            ["git", "-C", str(project_root), "rev-parse", "HEAD"],
            check=True, capture_output=True, text=True,
        ).stdout.strip()
        rc, captured = _capture_stdout(
            lambda: _forward_output(
                "garbage output no json",
                project_root,
                start_sha=base_sha,
                verify_cmd="exit 0",
                card_ids={1, 2, 3},
                session_id="s51",
            )
        )
        try:
            data = json.loads(captured.strip())
            assert data["status"] == "stuck", f"case 51: expected stuck, got {data}"
            assert data["stuck_type"] == "incomplete", (
                f"case 51: expected incomplete (#574 fix), got {data}"
            )
            assert data.get("commits_made") == 1, (
                f"case 51: expected commits_made=1 (content), got {data}"
            )
            assert "commit_sha" in data, f"case 51: expected commit_sha in envelope, got {data}"
            assert data["commit_sha"] == new_head_51, (
                f"case 51: expected commit_sha={new_head_51}, got {data}"
            )
            print(
                "PASS: case 51 - #574 regression: no-JSON inference, verify passes,"
                " partial batch -> stuck/incomplete with commits_made and commit_sha"
            )
        except Exception as exc:
            print(f"FAIL: case 51 ({exc}) captured={captured!r}", file=sys.stderr)
            errors += 1

    # Case 52: explicit status:success JSON + verify passes + content < len(card_ids) -> success
    # preserved (not false incomplete). The explicit-success completeness gate is disabled
    # when verify_cmd is set (ignore_verify stays False on that path).
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        base_sha = _setup_fixture(project_root)
        # One commit since base_sha; card_ids={1,2} (fewer commits than cards), but verify passes.
        subprocess.run(
            ["git", "-C", str(project_root), "commit", "--allow-empty", "-m", "card-1"],
            check=True, capture_output=True,
        )
        agent_output_52 = (
            '{"status":"success","commit_sha":"abc","session_id":"s52"}\n'
        )
        rc, captured = _capture_stdout(
            lambda: _forward_output(
                agent_output_52,
                project_root,
                start_sha=base_sha,
                verify_cmd="exit 0",
                card_ids={1, 2},
                session_id="s52",
            )
        )
        try:
            data = json.loads(captured.strip())
            assert data["status"] == "success", (
                f"case 52: expected success (explicit+verify conclusive), got {data}"
            )
            print(
                "PASS: case 52 - explicit status:success + verify passes + content<cards"
                " -> success preserved (no false incomplete)"
            )
        except Exception as exc:
            print(f"FAIL: case 52 ({exc}) captured={captured!r}", file=sys.stderr)
            errors += 1

    # Case 53: _forward_output normalizes implementer-emitted status:incomplete report.
    # A bare {"status":"incomplete","cards_done":1,"cards_remaining":2,"session_id":"s"}
    # must be normalized to the stuck/incomplete envelope with commits_made and commit_sha.
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        base_sha = _setup_fixture(project_root)
        # One content commit so HEAD != base_sha (enables commit_sha attachment).
        subprocess.run(
            ["git", "-C", str(project_root), "commit", "--allow-empty", "-m", "card-1"],
            check=True, capture_output=True,
        )
        new_head_53 = subprocess.run(
            ["git", "-C", str(project_root), "rev-parse", "HEAD"],
            check=True, capture_output=True, text=True,
        ).stdout.strip()
        incomplete_report = (
            '{"status":"incomplete","cards_done":1,"cards_remaining":2,"session_id":"impl-s"}'
        )
        rc, captured = _capture_stdout(
            lambda: _forward_output(
                incomplete_report,
                project_root,
                start_sha=base_sha,
                session_id="caller-s",
            )
        )
        try:
            data = json.loads(captured.strip())
            assert data["status"] == "stuck", f"case 53: expected stuck, got {data}"
            assert data["stuck_type"] == "incomplete", (
                f"case 53: expected incomplete, got {data}"
            )
            # session_id: caller-supplied takes precedence over implementer's.
            assert data.get("session_id") == "caller-s", (
                f"case 53: expected session_id=caller-s, got {data}"
            )
            # commits_made from _content_commit_count (1 real commit since base_sha).
            assert data.get("commits_made") == 1, (
                f"case 53: expected commits_made=1, got {data}"
            )
            assert "commit_sha" in data, f"case 53: expected commit_sha in envelope, got {data}"
            assert data["commit_sha"] == new_head_53, (
                f"case 53: expected commit_sha={new_head_53}, got {data}"
            )
            print(
                "PASS: case 53 - implementer status:incomplete normalized to stuck/incomplete"
                " with commits_made and commit_sha"
            )
        except Exception as exc:
            print(f"FAIL: case 53 ({exc}) captured={captured!r}", file=sys.stderr)
            errors += 1

    # Case 54: _content_commit_count with two "mill-go: start batch" commits returns N
    # (subtract-all). Verifies Card 1 fix: previously only the oldest was subtracted.
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        base_sha = _setup_fixture(project_root)
        # Two housekeeping commits (e.g. original prepare + retry prepare).
        subprocess.run(
            ["git", "-C", str(project_root), "commit", "--allow-empty",
             "-m", "mill-go: start batch batch-a"],
            check=True, capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(project_root), "commit", "--allow-empty",
             "-m", "mill-go: start batch batch-a (retry)"],
            check=True, capture_output=True,
        )
        # Two content commits; with both housekeeping commits subtracted -> count = 2.
        subprocess.run(
            ["git", "-C", str(project_root), "commit", "--allow-empty", "-m", "card-1"],
            check=True, capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(project_root), "commit", "--allow-empty", "-m", "card-2"],
            check=True, capture_output=True,
        )
        try:
            count = _content_commit_count(project_root, base_sha)
            assert count == 2, (
                f"case 54: expected 2 (2 content commits, 2 housekeeping subtracted), got {count}"
            )
            print(
                "PASS: case 54 - _content_commit_count: two start-batch commits both subtracted"
                " -> 2 content commits"
            )
        except Exception as exc:
            print(f"FAIL: case 54 ({exc})", file=sys.stderr)
            errors += 1

    # Case 55: reclassified incomplete envelope carries commit_sha (membership guard includes
    # "incomplete"). Exercises the parsed-success -> verify-fail -> reclassify -> incomplete
    # path and confirms commit_sha was attached by the membership guard.
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        base_sha = _setup_fixture(project_root)
        # Housekeeping commit + one content commit -> content=1, card_ids={1,2,3} -> partial.
        subprocess.run(
            ["git", "-C", str(project_root), "commit", "--allow-empty",
             "-m", "mill-go: start batch test-batch"],
            check=True, capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(project_root), "commit", "--allow-empty", "-m", "card-1 done"],
            check=True, capture_output=True,
        )
        new_head_55 = subprocess.run(
            ["git", "-C", str(project_root), "rev-parse", "HEAD"],
            check=True, capture_output=True, text=True,
        ).stdout.strip()
        agent_output_55 = (
            '{"status":"success","commit_sha":"old","session_id":"s55"}\n'
        )
        rc, captured = _capture_stdout(
            lambda: _forward_output(
                agent_output_55,
                project_root,
                start_sha=base_sha,
                verify_cmd="exit 1",
                card_ids={1, 2, 3},
                session_id="s55",
            )
        )
        try:
            data = json.loads(captured.strip())
            assert data["status"] == "stuck", f"case 55: expected stuck, got {data}"
            assert data["stuck_type"] == "incomplete", (
                f"case 55: expected incomplete (reclassified from verify), got {data}"
            )
            assert "commit_sha" in data, (
                f"case 55: expected commit_sha in incomplete envelope, got {data}"
            )
            assert data["commit_sha"] == new_head_55, (
                f"case 55: expected commit_sha={new_head_55}, got {data}"
            )
            print(
                "PASS: case 55 - reclassified incomplete envelope carries commit_sha"
                " (membership guard includes incomplete)"
            )
        except Exception as exc:
            print(f"FAIL: case 55 ({exc}) captured={captured!r}", file=sys.stderr)
            errors += 1

    # Case 56: #582 regression - nits-only zero-commit pushback -> success (not stuck/logic).
    # A --nits-only pass that legitimately pushes back on every NIT finding (per the
    # mill-receiving-review decision tree) is expected to make zero content commits;
    # this must be reported as success with the nits-fixed marker written, not demoted
    # by the no-content-commit gate (HEAD == start_sha).
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        base_sha = _setup_fixture(project_root)
        snapshot_path = project_root / "_mill" / ".cleanliness-snapshot-test.txt"
        _cleanliness.capture_snapshot(project_root, snapshot_path)
        status_path = project_root / "_mill" / "status.md"
        status_path.write_text(
            _status.render_initial(
                task_title="t",
                task_description="d",
                timestamp="2026-06-30T00:00:00Z",
                parent_branch="main",
                slug="test-slug",
                branch="test-branch",
            ),
            encoding="utf-8",
        )
        # IMPORTANT: Do NOT make a new commit -- HEAD == base_sha (all-pushback, zero-commit).
        verify_cmd = "exit 0"
        agent_output = (
            '{"status":"success","commit_sha":"abc","session_id":"test-session"}\n'
        )
        rc, captured = _capture_stdout(
            lambda: _forward_output(
                agent_output,
                project_root,
                start_sha=base_sha,
                snapshot_path=snapshot_path,
                verify_cmd=verify_cmd,
                nits_only=True,
                status_path=status_path,
                nits_scope="holistic",
            )
        )
        try:
            data = json.loads(captured.strip())
            assert data["status"] == "success", (
                f"case 56: expected success, got {data}"
            )
            assert data.get("nits_applied") is True, (
                f"case 56: expected nits_applied=True, got {data}"
            )
            full = _status.read_full(status_path)
            assert any(
                e.startswith("nits-fixed-holistic") for e in full["timeline"]
            ), (
                f"case 56: expected nits-fixed-holistic in timeline, got {full['timeline']}"
            )
            print(
                "PASS: case 56 - #582 nits-only zero-commit pushback -> success with marker"
            )
        except Exception as exc:
            print(f"FAIL: case 56 ({exc}) captured={captured!r}", file=sys.stderr)
            errors += 1

    # Case 57: #582 regression - nits-only with an in-scope dirty tracked file still hits
    # the dirty-tree gate (stuck/logic), proving the gate's own logic is unaffected by the
    # Card 5 change to the no-content-commit gate. task_dir/parent_branch are the inputs
    # _in_scope_dirty_stuck() needs to run at all; millpy-fix.py's CLI never supplies them
    # today (see Batch Scope), so this exercises the gate directly via _forward_output.
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        base_sha = _setup_fixture(project_root)
        branch_result = subprocess.run(
            ["git", "-C", str(project_root), "branch", "--show-current"],
            check=True,
            capture_output=True,
            text=True,
        )
        parent_branch_name = branch_result.stdout.strip()
        subprocess.run(
            ["git", "-C", str(project_root), "checkout", "-b", "task-branch"],
            check=True,
            capture_output=True,
        )
        # Commit a README.md change on the task branch (puts it in owned_paths).
        (project_root / "README.md").write_text("task change", encoding="utf-8")
        subprocess.run(
            ["git", "-C", str(project_root), "add", "README.md"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(project_root), "commit", "-m", "card-1-modify-readme"],
            check=True,
            capture_output=True,
        )
        # Dirty README.md again without committing -- in-scope and dirty.
        (project_root / "README.md").write_text("dirty in-scope", encoding="utf-8")
        task_dir = project_root / "_mill"
        task_dir.mkdir(parents=True, exist_ok=True)
        status_path = task_dir / "status.md"
        status_path.write_text(
            _status.render_initial(
                task_title="t",
                task_description="d",
                timestamp="2026-06-30T00:00:00Z",
                parent_branch=parent_branch_name,
                slug="test-slug",
                branch="task-branch",
            ),
            encoding="utf-8",
        )
        agent_output = '{"status":"success","commit_sha":"abc","session_id":"s57"}\n'
        rc, captured = _capture_stdout(
            lambda: _forward_output(
                agent_output,
                project_root,
                start_sha=base_sha,
                verify_cmd=None,
                task_dir=task_dir,
                parent_branch=parent_branch_name,
                nits_only=True,
                status_path=status_path,
                nits_scope="holistic",
            )
        )
        try:
            data = json.loads(captured.strip())
            assert data["status"] == "stuck", f"case 57: expected stuck, got {data}"
            assert data["stuck_type"] == "logic", (
                f"case 57: expected logic (dirty-tree gate), got {data}"
            )
            assert "in-scope working tree dirty" in data.get("reason", ""), (
                f"case 57: expected dirty reason, got {data}"
            )
            print(
                "PASS: case 57 - nits-only with dirty in-scope file still hits"
                " dirty-tree gate -> stuck/logic"
            )
        except Exception as exc:
            print(f"FAIL: case 57 ({exc}) captured={captured!r}", file=sys.stderr)
            errors += 1

    # Case 58: regression guard -- nits_only=False (default) with the same zero-commit
    # setup as case 56 still demotes to stuck/logic "no content commit". Proves the
    # Card 5 "not nits_only" condition does not affect the non-nits-only path.
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        base_sha = _setup_fixture(project_root)
        snapshot_path = project_root / "_mill" / ".cleanliness-snapshot-test.txt"
        _cleanliness.capture_snapshot(project_root, snapshot_path)
        # IMPORTANT: Do NOT make a new commit -- HEAD == base_sha.
        verify_cmd = "exit 0"
        agent_output = (
            '{"status":"success","commit_sha":"abc","session_id":"test-session"}\n'
        )
        rc, captured = _capture_stdout(
            lambda: _forward_output(
                agent_output,
                project_root,
                start_sha=base_sha,
                snapshot_path=snapshot_path,
                verify_cmd=verify_cmd,
                nits_only=False,
            )
        )
        try:
            data = json.loads(captured.strip())
            assert data["status"] == "stuck", f"case 58: expected stuck, got {data}"
            assert data["stuck_type"] == "logic", (
                f"case 58: expected stuck_type=logic, got {data}"
            )
            assert "no content commit" in data.get("reason", "").lower(), (
                f"case 58: expected 'no content commit' in reason, got {data}"
            )
            print(
                "PASS: case 58 - nits_only=False zero-commit success still"
                " demotes to stuck/logic (regression guard)"
            )
        except Exception as exc:
            print(f"FAIL: case 58 ({exc}) captured={captured!r}", file=sys.stderr)
            errors += 1

    # Case 59: module_verify_baseline="pre-existing-failures" with a failing
    # module_wide_verify_cmd -- the module-wide gate is skipped entirely (never
    # invoked), the batch gate's own pass/fail is unaffected, and the overall
    # result is success, not stuck/verify. subprocess.run is spied on (real
    # calls still execute via side_effect, so git plumbing inside
    # _forward_output keeps working) so we can assert the module-wide command
    # string never appears in any recorded call.
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        base_sha = _setup_fixture(project_root)
        snapshot_path = project_root / "_mill" / ".cleanliness-snapshot-test.txt"
        _cleanliness.capture_snapshot(project_root, snapshot_path)
        subprocess.run(
            ["git", "-C", str(project_root), "commit", "--allow-empty", "-m", "second"],
            check=True,
            capture_output=True,
        )
        agent_output = (
            '{"status":"success","commit_sha":"abc","session_id":"test-session"}\n'
        )
        real_run = subprocess.run
        with unittest.mock.patch(
            "_implementer_common.subprocess.run", side_effect=real_run
        ) as mock_run:
            rc, captured = _capture_stdout(
                lambda: _forward_output(
                    agent_output,
                    project_root,
                    start_sha=base_sha,
                    snapshot_path=snapshot_path,
                    verify_cmd="exit 0",
                    module_wide_verify_cmd="exit 1",
                    module_verify_baseline="pre-existing-failures",
                )
            )
        try:
            data = json.loads(captured.strip())
            assert data["status"] == "success", (
                f"case 59: expected success, got {data}"
            )
            # Confirm the module-wide command ("exit 1") was never handed to
            # subprocess.run -- only git plumbing and the batch gate's "exit 0"
            # should appear in the recorded call history.
            for call in mock_run.call_args_list:
                call_args = call.args[0] if call.args else []
                flattened = (
                    call_args if isinstance(call_args, str) else " ".join(call_args)
                )
                assert "exit 1" not in flattened, (
                    f"case 59: module-wide command invoked unexpectedly: {flattened!r}"
                )
            print(
                "PASS: case 59 - pre-existing-failures baseline skips module-wide"
                " gate entirely (never invoked), overall success"
            )
        except Exception as exc:
            print(f"FAIL: case 59 ({exc}) captured={captured!r}", file=sys.stderr)
            errors += 1

    # Case 60: module_verify_baseline="clean" -- the module-wide gate runs exactly
    # as it did before this parameter existed. Mirrors Case 30 (batch passes,
    # module-wide fails -> stuck/verify with "[module-wide verify]" prefix) and
    # Case 31 (module-wide passes -> overall success/None).
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        base_sha = _setup_fixture(project_root)
        snapshot_path = project_root / "_mill" / ".cleanliness-snapshot-test.txt"
        _cleanliness.capture_snapshot(project_root, snapshot_path)
        subprocess.run(
            ["git", "-C", str(project_root), "commit", "--allow-empty", "-m", "second"],
            check=True,
            capture_output=True,
        )
        new_head = subprocess.run(
            ["git", "-C", str(project_root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        agent_output = (
            '{"status":"success","commit_sha":"abc","session_id":"test-session"}\n'
        )
        # Case 30 mirror: batch gate passes, module-wide gate fails.
        rc, captured = _capture_stdout(
            lambda: _forward_output(
                agent_output,
                project_root,
                start_sha=base_sha,
                snapshot_path=snapshot_path,
                verify_cmd="exit 0",
                module_wide_verify_cmd="exit 1",
                module_verify_baseline="clean",
            )
        )
        try:
            data = json.loads(captured.strip())
            assert data["status"] == "stuck", f"case 60a: expected stuck, got {data}"
            assert data["stuck_type"] == "verify", (
                f"case 60a: expected stuck_type=verify, got {data}"
            )
            assert "[module-wide verify]" in data.get("reason", ""), (
                f"case 60a: expected '[module-wide verify]' prefix in reason, got {data}"
            )
            assert data.get("commit_sha") == new_head, (
                f"case 60a: expected commit_sha={new_head}, got {data}"
            )
            print(
                "PASS: case 60a - clean baseline: module-wide gate still runs and"
                " fails -> stuck/verify with prefix (matches Case 30)"
            )
        except Exception as exc:
            print(f"FAIL: case 60a ({exc}) captured={captured!r}", file=sys.stderr)
            errors += 1
        # Case 31 mirror: both gates pass -> no demotion.
        try:
            result = _run_verify_gates(
                project_root, "exit 0", "exit 0", module_verify_baseline="clean"
            )
            assert result is None, f"case 60b: expected None (both pass), got {result}"
            print(
                "PASS: case 60b - clean baseline: module-wide gate runs and passes"
                " -> overall success (matches Case 31)"
            )
        except Exception as exc:
            print(f"FAIL: case 60b ({exc})", file=sys.stderr)
            errors += 1

    # Case 61: module_verify_baseline=None (the default, not yet computed) --
    # identical behavior to Case 60 ("clean"): the module-wide gate still runs
    # strictly. This is the fail-safe-toward-strict default.
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        _setup_fixture(project_root)
        try:
            # Batch passes, module-wide fails -> stuck/verify with prefix.
            result = _run_verify_gates(
                project_root, "exit 0", "exit 1", module_verify_baseline=None
            )
            assert result is not None, f"case 61a: expected stuck dict, got {result}"
            assert result["stuck_type"] == "verify", (
                f"case 61a: expected stuck_type=verify, got {result}"
            )
            assert "[module-wide verify]" in result.get("reason", ""), (
                f"case 61a: expected '[module-wide verify]' prefix in reason, got {result}"
            )
            # Batch passes, module-wide also passes -> no demotion.
            result = _run_verify_gates(
                project_root, "exit 0", "exit 0", module_verify_baseline=None
            )
            assert result is None, f"case 61b: expected None (both pass), got {result}"
            print(
                "PASS: case 61 - module_verify_baseline=None (default) behaves"
                " identically to 'clean' -- strict fail-safe default"
            )
        except Exception as exc:
            print(f"FAIL: case 61 ({exc})", file=sys.stderr)
            errors += 1

    # Case 62: backward-compatibility guard -- calling _forward_output without
    # passing module_verify_baseline at all (kwarg omitted) behaves identically
    # to Case 61 (defaults to None, module-wide gate runs strictly). Confirms no
    # existing caller (e.g. millpy-fix.py) changes behavior from this batch alone.
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        base_sha = _setup_fixture(project_root)
        snapshot_path = project_root / "_mill" / ".cleanliness-snapshot-test.txt"
        _cleanliness.capture_snapshot(project_root, snapshot_path)
        subprocess.run(
            ["git", "-C", str(project_root), "commit", "--allow-empty", "-m", "second"],
            check=True,
            capture_output=True,
        )
        agent_output = (
            '{"status":"success","commit_sha":"abc","session_id":"test-session"}\n'
        )
        # module_verify_baseline intentionally omitted -- exercises the default.
        rc, captured = _capture_stdout(
            lambda: _forward_output(
                agent_output,
                project_root,
                start_sha=base_sha,
                snapshot_path=snapshot_path,
                verify_cmd="exit 0",
                module_wide_verify_cmd="exit 1",
            )
        )
        try:
            data = json.loads(captured.strip())
            assert data["status"] == "stuck", f"case 62: expected stuck, got {data}"
            assert data["stuck_type"] == "verify", (
                f"case 62: expected stuck_type=verify, got {data}"
            )
            assert "[module-wide verify]" in data.get("reason", ""), (
                f"case 62: expected '[module-wide verify]' prefix in reason, got {data}"
            )
            print(
                "PASS: case 62 - module_verify_baseline omitted entirely (existing"
                " caller shape) -> module-wide gate still runs strictly"
            )
        except Exception as exc:
            print(f"FAIL: case 62 ({exc}) captured={captured!r}", file=sys.stderr)
            errors += 1

    # Case 63: #605 regression -- finalize_from_output unescapes HTML entities in the
    # agent-output file before delegating to _forward_output. The harness HTML-escapes
    # the <task-notification> payload uniformly before delivery, so the raw file on disk
    # may contain entities like "&amp;", "&lt;", "&gt;". Patch _forward_output to capture
    # its first positional argument (the "output" string) so we can assert the captured
    # text is the fully-unescaped original rather than exercising the real gate logic.
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        base_sha = _setup_fixture(project_root)
        snapshot_path = project_root / "_mill" / ".cleanliness-snapshot-test.txt"
        _cleanliness.capture_snapshot(project_root, snapshot_path)
        subprocess.run(
            ["git", "-C", str(project_root), "commit", "--allow-empty", "-m", "second"],
            check=True,
            capture_output=True,
        )
        agent_output_path = project_root / "_mill" / "agent-output.txt"
        escaped_text = "Q&amp;A send &lt;guid&gt; Cards 20 &amp; 21"
        agent_output_path.write_text(escaped_text, encoding="utf-8")
        captured_args = {}

        def _fake_forward_output(output, *args, **kwargs):
            captured_args["output"] = output
            return 0

        try:
            with unittest.mock.patch(
                "_implementer_common._forward_output",
                side_effect=_fake_forward_output,
            ):
                finalize_from_output(
                    agent_output_path,
                    project_root,
                    start_sha=base_sha,
                    snapshot_path=snapshot_path,
                    session_id="test-session",
                )
            assert captured_args.get("output") == "Q&A send <guid> Cards 20 & 21", (
                f"case 63: expected fully-unescaped text, got {captured_args.get('output')!r}"
            )
            print(
                "PASS: case 63 - #605 finalize_from_output unescapes HTML entities"
                " in agent-output read"
            )
        except Exception as exc:
            print(f"FAIL: case 63 ({exc})", file=sys.stderr)
            errors += 1

    # Case 64: #619 - emit_prepare threads nits_only through the prepare envelope.
    # nits_only=True must add "nits_only": true; the default (omitted) must leave
    # the key entirely absent from the envelope, mirroring the start_sha pattern.
    with tempfile.TemporaryDirectory() as tmpdir:
        briefs_dir = Path(tmpdir) / "briefs"
        try:
            rc, captured = _capture_stdout(
                lambda: emit_prepare(
                    briefs_dir,
                    "fix",
                    "test-batch",
                    1,
                    "prompt text",
                    "haiku",
                    "session-abc",
                    nits_only=True,
                )
            )
            assert rc == 0, f"expected rc=0, got {rc}"
            data = json.loads(captured.strip())
            assert data["nits_only"] is True, (
                f"expected nits_only=True in envelope, got {data}"
            )

            rc, captured = _capture_stdout(
                lambda: emit_prepare(
                    briefs_dir,
                    "fix",
                    "test-batch",
                    2,
                    "prompt text",
                    "haiku",
                    "session-abc",
                )
            )
            assert rc == 0, f"expected rc=0, got {rc}"
            data = json.loads(captured.strip())
            assert "nits_only" not in data, (
                f"expected nits_only key absent when omitted, got {data}"
            )
            print("PASS: case 64 - emit_prepare threads nits_only through envelope")
        except Exception as exc:
            print(f"FAIL: case 64 ({exc}) captured={captured!r}", file=sys.stderr)
            errors += 1

    # Case 65: #628/#633 - emit_prepare threads effort through the prepare envelope.
    # effort="high" must add "effort": "high"; the default (omitted) must leave
    # the key entirely absent from the envelope, mirroring the start_sha pattern.
    with tempfile.TemporaryDirectory() as tmpdir:
        briefs_dir = Path(tmpdir) / "briefs"
        try:
            rc, captured = _capture_stdout(
                lambda: emit_prepare(
                    briefs_dir,
                    "fix",
                    "test-batch",
                    1,
                    "prompt text",
                    "haiku",
                    "session-abc",
                    effort="high",
                )
            )
            assert rc == 0, f"expected rc=0, got {rc}"
            data = json.loads(captured.strip())
            assert data["effort"] == "high", (
                f"expected effort='high' in envelope, got {data}"
            )

            rc, captured = _capture_stdout(
                lambda: emit_prepare(
                    briefs_dir,
                    "fix",
                    "test-batch",
                    2,
                    "prompt text",
                    "haiku",
                    "session-abc",
                )
            )
            assert rc == 0, f"expected rc=0, got {rc}"
            data = json.loads(captured.strip())
            assert "effort" not in data, (
                f"expected effort key absent when omitted, got {data}"
            )
            print("PASS: case 65 - emit_prepare threads effort through envelope")
        except Exception as exc:
            print(f"FAIL: case 65 ({exc}) captured={captured!r}", file=sys.stderr)
            errors += 1

    # Case 65a -- cards_done covers all card_ids despite content < len(card_ids) -> no-stuck.
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        base_sha = _setup_fixture(project_root)
        # Only 1 content commit even though 3 cards are declared -- would fail the old
        # raw-count heuristic, but cards_done self-reports all three as done (e.g. two
        # cards were folded into this single commit per the "one combined commit" rule).
        subprocess.run(
            ["git", "-C", str(project_root), "commit", "--allow-empty", "-m", "cards 1-3 combined"],
            check=True, capture_output=True,
        )
        try:
            result = _batch_completeness_stuck(
                project_root,
                base_sha,
                card_ids={1, 2, 3},
                session_id="test",
                cards_done=[1, 2, 3],
            )
            assert result is None, (
                f"case 65a: expected None (cards_done covers all declared cards), got {result}"
            )
            print(
                "PASS: case 65a - cards_done covers all card_ids despite fewer commits"
                " than cards -> no-stuck"
            )
        except Exception as exc:
            print(f"FAIL: case 65a ({exc})", file=sys.stderr)
            errors += 1

    # Case 65b -- cards_done present but missing entries from card_ids -> stuck/incomplete
    # with the missing card IDs named in the reason.
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        base_sha = _setup_fixture(project_root)
        subprocess.run(
            ["git", "-C", str(project_root), "commit", "--allow-empty", "-m", "card-1,2"],
            check=True, capture_output=True,
        )
        try:
            result = _batch_completeness_stuck(
                project_root,
                base_sha,
                card_ids={1, 2, 3},
                session_id="test",
                cards_done=[1, 2],
            )
            assert result is not None, f"case 65b: expected stuck dict, got {result}"
            assert result["stuck_type"] == "incomplete", (
                f"case 65b: expected incomplete, got {result}"
            )
            assert "3" in result.get("reason", ""), (
                f"case 65b: expected missing card 3 named in reason, got {result}"
            )
            print(
                "PASS: case 65b - cards_done missing declared card -> stuck/incomplete"
                " with missing card named"
            )
        except Exception as exc:
            print(f"FAIL: case 65b ({exc})", file=sys.stderr)
            errors += 1

    # Case 65c -- cards_done absent (None) with a batch that would pass the old count
    # check -> no-stuck (absent-field fallback, passing case).
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        base_sha = _setup_fixture(project_root)
        for msg in ("card-1", "card-2"):
            subprocess.run(
                ["git", "-C", str(project_root), "commit", "--allow-empty", "-m", msg],
                check=True, capture_output=True,
            )
        try:
            result = _batch_completeness_stuck(
                project_root,
                base_sha,
                card_ids={1, 2},
                session_id="test",
                cards_done=None,
            )
            assert result is None, (
                f"case 65c: expected None (2 commits >= 2 cards, old count check passes), got {result}"
            )
            print(
                "PASS: case 65c - cards_done absent, commit count satisfies old check"
                " -> no-stuck (fallback)"
            )
        except Exception as exc:
            print(f"FAIL: case 65c ({exc})", file=sys.stderr)
            errors += 1

    # Case 65d -- cards_done absent with a batch that would fail the old count check
    # -> stuck/incomplete (fallback path, failing case).
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        base_sha = _setup_fixture(project_root)
        subprocess.run(
            ["git", "-C", str(project_root), "commit", "--allow-empty", "-m", "card-1"],
            check=True, capture_output=True,
        )
        try:
            result = _batch_completeness_stuck(
                project_root,
                base_sha,
                card_ids={1, 2, 3},
                session_id="test",
                cards_done=None,
            )
            assert result is not None, f"case 65d: expected stuck dict, got {result}"
            assert result["stuck_type"] == "incomplete", (
                f"case 65d: expected incomplete, got {result}"
            )
            print(
                "PASS: case 65d - cards_done absent, commit count fails old check"
                " -> stuck/incomplete (fallback)"
            )
        except Exception as exc:
            print(f"FAIL: case 65d ({exc})", file=sys.stderr)
            errors += 1

    # Case 65e -- cards_done as JSON string card numbers (e.g. ["7","8"]) matching
    # integer card_ids (e.g. {7,8}) -> coerces and passes.
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        base_sha = _setup_fixture(project_root)
        # Only 1 commit for 2 declared cards -- would fail the raw-count check, but the
        # string-coerced cards_done confirms both are done.
        subprocess.run(
            ["git", "-C", str(project_root), "commit", "--allow-empty", "-m", "cards 7,8 combined"],
            check=True, capture_output=True,
        )
        try:
            result = _batch_completeness_stuck(
                project_root,
                base_sha,
                card_ids={7, 8},
                session_id="test",
                cards_done=["7", "8"],
            )
            assert result is None, (
                f"case 65e: expected None (string card numbers coerce and match), got {result}"
            )
            print(
                "PASS: case 65e - cards_done as JSON string numbers coerces to int"
                " and matches card_ids -> no-stuck"
            )
        except Exception as exc:
            print(f"FAIL: case 65e ({exc})", file=sys.stderr)
            errors += 1

    # Case 65f -- cards_done with one malformed non-numeric entry -> falls back to the
    # count check rather than crashing.
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        base_sha = _setup_fixture(project_root)
        subprocess.run(
            ["git", "-C", str(project_root), "commit", "--allow-empty", "-m", "card-7"],
            check=True, capture_output=True,
        )
        try:
            result = _batch_completeness_stuck(
                project_root,
                base_sha,
                card_ids={7, 8},
                session_id="test",
                cards_done=["7", "abc"],
            )
            assert result is not None, (
                f"case 65f: expected stuck dict (fallback to count check: 1<2), got {result}"
            )
            assert result["stuck_type"] == "incomplete", (
                f"case 65f: expected incomplete, got {result}"
            )
            print(
                "PASS: case 65f - cards_done with malformed entry falls back to count"
                " check, not a crash"
            )
        except Exception as exc:
            print(f"FAIL: case 65f ({exc})", file=sys.stderr)
            errors += 1

    # Case 65g -- verify_cmd set and ignore_verify=False -> _batch_completeness_stuck
    # still returns None regardless of cards_done/card_ids (verify-present short-circuit
    # preserved).
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        base_sha = _setup_fixture(project_root)
        subprocess.run(
            ["git", "-C", str(project_root), "commit", "--allow-empty", "-m", "card-1"],
            check=True, capture_output=True,
        )
        try:
            result = _batch_completeness_stuck(
                project_root,
                base_sha,
                card_ids={1, 2, 3},
                session_id="test",
                verify_cmd="should-not-be-called",
                cards_done=[1],
            )
            assert result is None, (
                f"case 65g: expected None (verify-present short-circuit), got {result}"
            )
            print(
                "PASS: case 65g - verify_cmd present -> gate disabled regardless of"
                " cards_done/card_ids"
            )
        except Exception as exc:
            print(f"FAIL: case 65g ({exc})", file=sys.stderr)
            errors += 1

    # Case 65h -- already_complete=True short-circuits the gate to pass regardless of
    # every other argument.
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        base_sha = _setup_fixture(project_root)
        # Deliberately contradictory inputs: only 1 commit for 3 cards, cards_done
        # missing entries -- would fire the gate on every other check.
        subprocess.run(
            ["git", "-C", str(project_root), "commit", "--allow-empty", "-m", "card-1"],
            check=True, capture_output=True,
        )
        try:
            result = _batch_completeness_stuck(
                project_root,
                base_sha,
                card_ids={1, 2, 3},
                session_id="test",
                cards_done=[1],
                already_complete=True,
            )
            assert result is None, (
                f"case 65h: expected None (already_complete short-circuits), got {result}"
            )
            print(
                "PASS: case 65h - already_complete=True short-circuits the gate"
                " regardless of every other argument"
            )
        except Exception as exc:
            print(f"FAIL: case 65h ({exc})", file=sys.stderr)
            errors += 1

    # Case 65i -- _reclassify_verify_failure's content==0 branch is unaffected by any
    # cards_done value; still reclassifies to stuck_type:logic "no content commit".
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        base_sha = _setup_fixture(project_root)
        # No content commits at all since base_sha.
        verify_stuck = {"status": "stuck", "stuck_type": "verify", "reason": "tests failed"}
        try:
            result = _reclassify_verify_failure(
                verify_stuck,
                project_root,
                base_sha,
                card_ids={1, 2, 3},
                session_id="test",
                cards_done=[1, 2, 3],
            )
            assert result["status"] == "stuck", f"case 65i: expected stuck, got {result}"
            assert result["stuck_type"] == "logic", (
                f"case 65i: expected logic (zero content, unaffected by cards_done), got {result}"
            )
            assert "no content commit" in result.get("reason", ""), (
                f"case 65i: expected 'no content commit' in reason, got {result}"
            )
            print(
                "PASS: case 65i - _reclassify_verify_failure content==0 branch"
                " unaffected by cards_done -> stuck/logic"
            )
        except Exception as exc:
            print(f"FAIL: case 65i ({exc})", file=sys.stderr)
            errors += 1

    # Case 65j -- _reclassify_verify_failure mirrors cases (a) and (b) above on its own
    # 0<content<len(card_ids)-equivalent trigger path.
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        base_sha = _setup_fixture(project_root)
        subprocess.run(
            ["git", "-C", str(project_root), "commit", "--allow-empty", "-m", "cards 1-3 combined"],
            check=True, capture_output=True,
        )
        verify_stuck = {"status": "stuck", "stuck_type": "verify", "reason": "tests failed"}
        try:
            # Mirrors (a): cards_done covers all declared cards -> verify_stuck returned
            # unchanged (not reclassified to incomplete).
            result_a = _reclassify_verify_failure(
                verify_stuck,
                project_root,
                base_sha,
                card_ids={1, 2, 3},
                session_id="test",
                cards_done=[1, 2, 3],
            )
            assert result_a is verify_stuck, (
                f"case 65j-a: expected verify_stuck unchanged, got {result_a}"
            )
            # Mirrors (b): cards_done missing an entry -> reclassified to incomplete.
            result_b = _reclassify_verify_failure(
                verify_stuck,
                project_root,
                base_sha,
                card_ids={1, 2, 3},
                session_id="test",
                cards_done=[1, 2],
            )
            assert result_b["status"] == "stuck", (
                f"case 65j-b: expected stuck, got {result_b}"
            )
            assert result_b["stuck_type"] == "incomplete", (
                f"case 65j-b: expected incomplete, got {result_b}"
            )
            assert "3" in result_b.get("reason", ""), (
                f"case 65j-b: expected missing card 3 named in reason, got {result_b}"
            )
            print(
                "PASS: case 65j - _reclassify_verify_failure mirrors (a)/(b) on its"
                " own trigger path"
            )
        except Exception as exc:
            print(f"FAIL: case 65j ({exc})", file=sys.stderr)
            errors += 1

    # Case 66a -- _go_build_tag_retiering_stuck: added-tag transition (file exits
    # the default build) -> gate invokes (mocked) `go build ./<dir>/...`.
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        _setup_fixture(project_root)
        pkg_dir = project_root / "pkg"
        pkg_dir.mkdir()
        (pkg_dir / "foo.go").write_text("package pkg\n\nfunc Foo() {}\n", encoding="utf-8")
        subprocess.run(
            ["git", "-C", str(project_root), "add", "pkg/foo.go"],
            check=True, capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(project_root), "commit", "-m", "add untagged foo.go"],
            check=True, capture_output=True,
        )
        start_sha = subprocess.run(
            ["git", "-C", str(project_root), "rev-parse", "HEAD"],
            check=True, capture_output=True, text=True,
        ).stdout.strip()
        # Transition: add a //go:build constraint -- file now exits the default build.
        (pkg_dir / "foo.go").write_text(
            "//go:build integration\n\npackage pkg\n\nfunc Foo() {}\n", encoding="utf-8"
        )
        subprocess.run(
            ["git", "-C", str(project_root), "commit", "-am", "tag foo.go integration"],
            check=True, capture_output=True,
        )
        side_effect, calls = _go_gate_mock(build_returncode=0)
        try:
            with unittest.mock.patch.object(_subprocess_util, "run", side_effect=side_effect):
                result = _go_build_tag_retiering_stuck(project_root, start_sha, "sess-a")
            assert result is None, f"case 66a: expected None (compile passed), got {result}"
            assert len(calls) == 1, f"case 66a: expected exactly one go build call, got {calls}"
            assert calls[0] == ["go", "build", "./pkg/..."], (
                f"case 66a: expected untagged build of ./pkg/..., got {calls[0]}"
            )
            print(
                "PASS: case 66a - added-tag transition invokes go build ./<dir>/... for the directory"
            )
        except Exception as exc:
            print(f"FAIL: case 66a ({exc})", file=sys.stderr)
            errors += 1

    # Case 66b -- removed-tag transition (single custom tag) -> gate invokes
    # (mocked) `go build -tags <tag> ./<dir>/...`.
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        _setup_fixture(project_root)
        pkg_dir = project_root / "pkg"
        pkg_dir.mkdir()
        (pkg_dir / "bar.go").write_text(
            "//go:build integration\n\npackage pkg\n\nfunc Bar() {}\n", encoding="utf-8"
        )
        subprocess.run(
            ["git", "-C", str(project_root), "add", "pkg/bar.go"],
            check=True, capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(project_root), "commit", "-m", "add tagged bar.go"],
            check=True, capture_output=True,
        )
        start_sha = subprocess.run(
            ["git", "-C", str(project_root), "rev-parse", "HEAD"],
            check=True, capture_output=True, text=True,
        ).stdout.strip()
        # Transition: remove the //go:build constraint -- file now enters the default build.
        (pkg_dir / "bar.go").write_text("package pkg\n\nfunc Bar() {}\n", encoding="utf-8")
        subprocess.run(
            ["git", "-C", str(project_root), "commit", "-am", "untag bar.go"],
            check=True, capture_output=True,
        )
        side_effect, calls = _go_gate_mock(build_returncode=0)
        try:
            with unittest.mock.patch.object(_subprocess_util, "run", side_effect=side_effect):
                result = _go_build_tag_retiering_stuck(project_root, start_sha, "sess-b")
            assert result is None, f"case 66b: expected None (compile passed), got {result}"
            assert len(calls) == 1, f"case 66b: expected exactly one go build call, got {calls}"
            assert calls[0] == ["go", "build", "-tags", "integration", "./pkg/..."], (
                f"case 66b: expected tagged build of ./pkg/..., got {calls[0]}"
            )
            print(
                "PASS: case 66b - removed-tag transition invokes go build -tags <tag> ./<dir>/..."
            )
        except Exception as exc:
            print(f"FAIL: case 66b ({exc})", file=sys.stderr)
            errors += 1

    # Case 66c -- removed compound/negated/GOOS-only constraints are logged and
    # skipped, never translated to a -tags compile check.
    for _label, _constraint in (
        ("compound", "a && b"),
        ("negated", "!a"),
        ("GOOS-only", "linux"),
    ):
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            _setup_fixture(project_root)
            pkg_dir = project_root / "pkg"
            pkg_dir.mkdir()
            (pkg_dir / "qux.go").write_text(
                f"//go:build {_constraint}\n\npackage pkg\n\nfunc Qux() {{}}\n",
                encoding="utf-8",
            )
            subprocess.run(
                ["git", "-C", str(project_root), "add", "pkg/qux.go"],
                check=True, capture_output=True,
            )
            subprocess.run(
                ["git", "-C", str(project_root), "commit", "-m", "add tagged qux.go"],
                check=True, capture_output=True,
            )
            start_sha = subprocess.run(
                ["git", "-C", str(project_root), "rev-parse", "HEAD"],
                check=True, capture_output=True, text=True,
            ).stdout.strip()
            (pkg_dir / "qux.go").write_text(
                "package pkg\n\nfunc Qux() {}\n", encoding="utf-8"
            )
            subprocess.run(
                ["git", "-C", str(project_root), "commit", "-am", "untag qux.go"],
                check=True, capture_output=True,
            )
            side_effect, calls = _go_gate_mock(build_returncode=0)
            stderr_buf = io.StringIO()
            try:
                with unittest.mock.patch.object(_subprocess_util, "run", side_effect=side_effect):
                    with contextlib.redirect_stderr(stderr_buf):
                        result = _go_build_tag_retiering_stuck(
                            project_root, start_sha, "sess-c"
                        )
                assert result is None, (
                    f"case 66c ({_label}): expected None (no compile check run), got {result}"
                )
                assert calls == [], (
                    f"case 66c ({_label}): expected no go build call, got {calls}"
                )
                assert "skip" in stderr_buf.getvalue().lower(), (
                    f"case 66c ({_label}): expected a skip log line,"
                    f" got {stderr_buf.getvalue()!r}"
                )
                print(
                    f"PASS: case 66c ({_label}) - unparseable removed constraint"
                    " is logged and skipped"
                )
            except Exception as exc:
                print(f"FAIL: case 66c ({_label}) ({exc})", file=sys.stderr)
                errors += 1

    # Case 66d -- a //go:build line whose value changes but is present both before
    # and after (value-only edit) -> gate does not fire (not a membership transition).
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        _setup_fixture(project_root)
        pkg_dir = project_root / "pkg"
        pkg_dir.mkdir()
        (pkg_dir / "value.go").write_text(
            "//go:build alpha\n\npackage pkg\n\nfunc Value() {}\n", encoding="utf-8"
        )
        subprocess.run(
            ["git", "-C", str(project_root), "add", "pkg/value.go"],
            check=True, capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(project_root), "commit", "-m", "add value.go (alpha)"],
            check=True, capture_output=True,
        )
        start_sha = subprocess.run(
            ["git", "-C", str(project_root), "rev-parse", "HEAD"],
            check=True, capture_output=True, text=True,
        ).stdout.strip()
        (pkg_dir / "value.go").write_text(
            "//go:build beta\n\npackage pkg\n\nfunc Value() {}\n", encoding="utf-8"
        )
        subprocess.run(
            ["git", "-C", str(project_root), "commit", "-am", "retag value.go (beta)"],
            check=True, capture_output=True,
        )
        side_effect, calls = _go_gate_mock(build_returncode=0)
        try:
            with unittest.mock.patch.object(_subprocess_util, "run", side_effect=side_effect):
                result = _go_build_tag_retiering_stuck(project_root, start_sha, "sess-d")
            assert result is None, f"case 66d: expected None (value-only edit), got {result}"
            assert calls == [], f"case 66d: expected no go build call, got {calls}"
            print("PASS: case 66d - value-only //go:build edit is not a membership transition")
        except Exception as exc:
            print(f"FAIL: case 66d ({exc})", file=sys.stderr)
            errors += 1

    # Case 66e -- no .go files changed, or a .go file changed with no //go:build
    # lines touched -> gate returns None silently (no compile check, no log line).
    # (i) no .go files changed at all.
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        base_sha = _setup_fixture(project_root)
        (project_root / "README.md").write_text("seed v2", encoding="utf-8")
        subprocess.run(
            ["git", "-C", str(project_root), "commit", "-am", "readme only"],
            check=True, capture_output=True,
        )
        side_effect, calls = _go_gate_mock(build_returncode=0)
        try:
            with unittest.mock.patch.object(_subprocess_util, "run", side_effect=side_effect):
                result = _go_build_tag_retiering_stuck(project_root, base_sha, "sess-e1")
            assert result is None, f"case 66e-i: expected None (no .go changes), got {result}"
            assert calls == [], f"case 66e-i: expected no go build call, got {calls}"
            print("PASS: case 66e (i) - no .go files changed -> gate is a silent no-op")
        except Exception as exc:
            print(f"FAIL: case 66e (i) ({exc})", file=sys.stderr)
            errors += 1

    # (ii) a .go file changed but no //go:build lines were touched.
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        _setup_fixture(project_root)
        pkg_dir = project_root / "pkg"
        pkg_dir.mkdir()
        (pkg_dir / "plain.go").write_text(
            "package pkg\n\nfunc Plain() int { return 1 }\n", encoding="utf-8"
        )
        subprocess.run(
            ["git", "-C", str(project_root), "add", "pkg/plain.go"],
            check=True, capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(project_root), "commit", "-m", "add plain.go"],
            check=True, capture_output=True,
        )
        start_sha = subprocess.run(
            ["git", "-C", str(project_root), "rev-parse", "HEAD"],
            check=True, capture_output=True, text=True,
        ).stdout.strip()
        (pkg_dir / "plain.go").write_text(
            "package pkg\n\nfunc Plain() int { return 2 }\n", encoding="utf-8"
        )
        subprocess.run(
            ["git", "-C", str(project_root), "commit", "-am", "change plain.go body"],
            check=True, capture_output=True,
        )
        side_effect, calls = _go_gate_mock(build_returncode=0)
        try:
            with unittest.mock.patch.object(_subprocess_util, "run", side_effect=side_effect):
                result = _go_build_tag_retiering_stuck(project_root, start_sha, "sess-e2")
            assert result is None, (
                f"case 66e-ii: expected None (no build-tag lines touched), got {result}"
            )
            assert calls == [], f"case 66e-ii: expected no go build call, got {calls}"
            print(
                "PASS: case 66e (ii) - .go file changed with no //go:build delta"
                " -> gate is a no-op"
            )
        except Exception as exc:
            print(f"FAIL: case 66e (ii) ({exc})", file=sys.stderr)
            errors += 1

    # Case 66f -- mocked compile-check failure (non-zero exit) -> gate returns a
    # stuck_type=verify dict naming the directory and transition direction.
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        _setup_fixture(project_root)
        pkg_dir = project_root / "pkg"
        pkg_dir.mkdir()
        (pkg_dir / "broken.go").write_text(
            "package pkg\n\nfunc Broken() {}\n", encoding="utf-8"
        )
        subprocess.run(
            ["git", "-C", str(project_root), "add", "pkg/broken.go"],
            check=True, capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(project_root), "commit", "-m", "add untagged broken.go"],
            check=True, capture_output=True,
        )
        start_sha = subprocess.run(
            ["git", "-C", str(project_root), "rev-parse", "HEAD"],
            check=True, capture_output=True, text=True,
        ).stdout.strip()
        (pkg_dir / "broken.go").write_text(
            "//go:build integration\n\npackage pkg\n\nfunc Broken() {}\n", encoding="utf-8"
        )
        subprocess.run(
            ["git", "-C", str(project_root), "commit", "-am", "tag broken.go integration"],
            check=True, capture_output=True,
        )
        side_effect, calls = _go_gate_mock(
            build_returncode=1, build_stdout="", build_stderr="pkg/broken.go:1: syntax error"
        )
        try:
            with unittest.mock.patch.object(_subprocess_util, "run", side_effect=side_effect):
                result = _go_build_tag_retiering_stuck(project_root, start_sha, "sess-f")
            assert result is not None, "case 66f: expected a stuck dict, got None"
            assert result["status"] == "stuck", f"case 66f: expected stuck, got {result}"
            assert result["stuck_type"] == "verify", (
                f"case 66f: expected stuck_type=verify, got {result}"
            )
            assert "pkg" in result.get("reason", ""), (
                f"case 66f: expected directory 'pkg' named in reason, got {result}"
            )
            assert "added-tag transition" in result.get("reason", ""), (
                f"case 66f: expected 'added-tag transition' in reason, got {result}"
            )
            assert "syntax error" in result.get("reason", ""), (
                f"case 66f: expected captured output tail in reason, got {result}"
            )
            assert result["session_id"] == "sess-f", (
                f"case 66f: expected session_id passthrough, got {result}"
            )
            print(
                "PASS: case 66f - mocked compile failure -> stuck/verify naming dir + transition"
            )
        except Exception as exc:
            print(f"FAIL: case 66f ({exc})", file=sys.stderr)
            errors += 1

    # Case 66g -- case 66f's scenario reached via the no-snapshot no-JSON inference
    # path in _forward_output (not the explicit-success path) -- confirms the gate
    # is wired into all four call sites (Card 9), not just the explicit-success one.
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        _setup_fixture(project_root)
        pkg_dir = project_root / "pkg"
        pkg_dir.mkdir()
        (pkg_dir / "baz.go").write_text("package pkg\n\nfunc Baz() {}\n", encoding="utf-8")
        subprocess.run(
            ["git", "-C", str(project_root), "add", "pkg/baz.go"],
            check=True, capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(project_root), "commit", "-m", "add untagged baz.go"],
            check=True, capture_output=True,
        )
        start_sha = subprocess.run(
            ["git", "-C", str(project_root), "rev-parse", "HEAD"],
            check=True, capture_output=True, text=True,
        ).stdout.strip()
        (pkg_dir / "baz.go").write_text(
            "//go:build integration\n\npackage pkg\n\nfunc Baz() {}\n", encoding="utf-8"
        )
        subprocess.run(
            ["git", "-C", str(project_root), "commit", "-am", "tag baz.go integration"],
            check=True, capture_output=True,
        )
        side_effect, calls = _go_gate_mock(
            build_returncode=1, build_stdout="", build_stderr="pkg/baz.go:1: syntax error"
        )
        captured = ""
        try:
            with unittest.mock.patch.object(_subprocess_util, "run", side_effect=side_effect):
                rc, captured = _capture_stdout(
                    lambda: _forward_output(
                        "garbage output with no json",
                        project_root,
                        start_sha=start_sha,
                        # No snapshot_path -> exercises the no-snapshot inference path.
                        session_id="sess-g",
                    )
                )
            data = json.loads(captured.strip())
            assert data["status"] == "stuck", f"case 66g: expected stuck, got {data}"
            assert data["stuck_type"] == "verify", (
                f"case 66g: expected stuck_type=verify, got {data}"
            )
            assert "go build-tag retiering check failed" in data.get("reason", ""), (
                f"case 66g: expected retiering-gate reason, got {data}"
            )
            assert "commit_sha" in data, f"case 66g: expected commit_sha attached, got {data}"
            print(
                "PASS: case 66g - retiering-gate failure reached via the no-snapshot"
                " no-JSON inference path (Card 9 all-four-paths wiring)"
            )
        except Exception as exc:
            print(f"FAIL: case 66g ({exc}) captured={captured!r}", file=sys.stderr)
            errors += 1

    if errors:
        print(f"\n{errors} test(s) FAILED", file=sys.stderr)
        return 1
    print("All _implementer_common unit tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
