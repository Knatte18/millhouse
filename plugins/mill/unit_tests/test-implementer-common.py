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

from _implementer_common import _forward_output  # noqa: E402
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

    if errors:
        print(f"\n{errors} test(s) FAILED", file=sys.stderr)
        return 1
    print("All _implementer_common unit tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
