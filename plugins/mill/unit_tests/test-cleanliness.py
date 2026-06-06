"""Unit tests for plugins/mill/scripts/_cleanliness.py."""
from __future__ import annotations

import io
import sys
import tempfile
import unittest.mock
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

from _cleanliness import capture_snapshot, compute_new_dirt, compute_scope_violations  # noqa: E402


def main() -> int:
    failures: list[str] = []

    # 1. compute_new_dirt: empty pre + empty post -> []
    try:
        with tempfile.TemporaryDirectory() as tmp:
            snapshot_path = Path(tmp) / "snapshot.txt"
            snapshot_path.write_text("", encoding="utf-8")
            with unittest.mock.patch("_cleanliness._pygit2_util.status_porcelain", return_value=[]):
                result = compute_new_dirt(Path(tmp), snapshot_path)
            assert result == [], f"expected [], got {result!r}"
        print("PASS: empty pre + empty post -> []")
    except AssertionError as exc:
        failures.append(f"FAIL: empty pre + empty post: {exc}")
    except Exception as exc:
        failures.append(f"FAIL: empty pre + empty post ({type(exc).__name__}): {exc}")

    # 2. compute_new_dirt: empty pre + dirty post -> all post lines sorted
    try:
        with tempfile.TemporaryDirectory() as tmp:
            snapshot_path = Path(tmp) / "snapshot.txt"
            snapshot_path.write_text("", encoding="utf-8")
            with unittest.mock.patch(
                "_cleanliness._pygit2_util.status_porcelain", return_value=[" M a.txt", " M b.txt"]
            ):
                result = compute_new_dirt(Path(tmp), snapshot_path)
            assert result == [" M a.txt", " M b.txt"], (
                f"expected sorted list, got {result!r}"
            )
        print("PASS: empty pre + dirty post -> all post lines sorted")
    except AssertionError as exc:
        failures.append(f"FAIL: empty pre + dirty post: {exc}")
    except Exception as exc:
        failures.append(f"FAIL: empty pre + dirty post ({type(exc).__name__}): {exc}")

    # 3. compute_new_dirt: dirty pre + identical post -> [] (the original repro)
    try:
        with tempfile.TemporaryDirectory() as tmp:
            snapshot_path = Path(tmp) / "snapshot.txt"
            snapshot_path.write_text(" M file.txt\n", encoding="utf-8")
            with unittest.mock.patch(
                "_cleanliness._pygit2_util.status_porcelain", return_value=[" M file.txt"]
            ):
                result = compute_new_dirt(Path(tmp), snapshot_path)
            assert result == [], f"expected [], got {result!r}"
        print("PASS: dirty pre + identical post -> [] (original repro)")
    except AssertionError as exc:
        failures.append(f"FAIL: dirty pre + identical post: {exc}")
    except Exception as exc:
        failures.append(f"FAIL: dirty pre + identical post ({type(exc).__name__}): {exc}")

    # 4. compute_new_dirt: dirty pre + post is a strict superset -> only extra lines flagged
    try:
        with tempfile.TemporaryDirectory() as tmp:
            snapshot_path = Path(tmp) / "snapshot.txt"
            snapshot_path.write_text(" M a.txt\n", encoding="utf-8")
            with unittest.mock.patch(
                "_cleanliness._pygit2_util.status_porcelain", return_value=[" M a.txt", " M b.txt"]
            ):
                result = compute_new_dirt(Path(tmp), snapshot_path)
            assert result == [" M b.txt"], f"expected [' M b.txt'], got {result!r}"
        print("PASS: dirty pre + post is a strict superset -> only extra lines flagged")
    except AssertionError as exc:
        failures.append(f"FAIL: dirty pre + post superset: {exc}")
    except Exception as exc:
        failures.append(f"FAIL: dirty pre + post superset ({type(exc).__name__}): {exc}")

    # 5. compute_new_dirt: dirty pre + post is a strict subset -> []
    try:
        with tempfile.TemporaryDirectory() as tmp:
            snapshot_path = Path(tmp) / "snapshot.txt"
            snapshot_path.write_text(" M a.txt\n M b.txt\n", encoding="utf-8")
            with unittest.mock.patch(
                "_cleanliness._pygit2_util.status_porcelain", return_value=[" M a.txt"]
            ):
                result = compute_new_dirt(Path(tmp), snapshot_path)
            assert result == [], f"expected [], got {result!r}"
        print("PASS: dirty pre + post is a strict subset -> []")
    except AssertionError as exc:
        failures.append(f"FAIL: dirty pre + post subset: {exc}")
    except Exception as exc:
        failures.append(f"FAIL: dirty pre + post subset ({type(exc).__name__}): {exc}")

    # 6. compute_new_dirt: status-code change M -> MM flagged
    try:
        with tempfile.TemporaryDirectory() as tmp:
            snapshot_path = Path(tmp) / "snapshot.txt"
            snapshot_path.write_text(" M file.txt\n", encoding="utf-8")
            with unittest.mock.patch(
                "_cleanliness._pygit2_util.status_porcelain", return_value=["MM file.txt"]
            ):
                result = compute_new_dirt(Path(tmp), snapshot_path)
            assert result == ["MM file.txt"], f"expected ['MM file.txt'], got {result!r}"
        print("PASS: status-code change M -> MM flagged")
    except AssertionError as exc:
        failures.append(f"FAIL: status-code change: {exc}")
    except Exception as exc:
        failures.append(f"FAIL: status-code change ({type(exc).__name__}): {exc}")

    # 7. compute_new_dirt: missing snapshot file -> returns post lines + [cleanliness] warning
    try:
        with tempfile.TemporaryDirectory() as tmp:
            snapshot_path = Path(tmp) / "missing.txt"
            with unittest.mock.patch(
                "_cleanliness._pygit2_util.status_porcelain", return_value=[" M a.txt"]
            ):
                with unittest.mock.patch("sys.stderr", new=io.StringIO()) as fake_err:
                    result = compute_new_dirt(Path(tmp), snapshot_path)
            assert result == [" M a.txt"], f"expected [' M a.txt'], got {result!r}"
            assert "[cleanliness]" in fake_err.getvalue(), (
                f"'[cleanliness]' not in stderr: {fake_err.getvalue()!r}"
            )
        print("PASS: missing snapshot file -> returns post lines + [cleanliness] warning to stderr")
    except AssertionError as exc:
        failures.append(f"FAIL: missing snapshot file: {exc}")
    except Exception as exc:
        failures.append(f"FAIL: missing snapshot file ({type(exc).__name__}): {exc}")

    # 8. compute_new_dirt: CRLF in snapshot, LF in subprocess stdout -> no false-positive
    try:
        with tempfile.TemporaryDirectory() as tmp:
            snapshot_path = Path(tmp) / "snapshot.txt"
            snapshot_path.write_bytes(b" M file.txt\r\n")
            with unittest.mock.patch(
                "_cleanliness._pygit2_util.status_porcelain", return_value=[" M file.txt"]
            ):
                result = compute_new_dirt(Path(tmp), snapshot_path)
            assert result == [], f"expected [], got {result!r}"
        print("PASS: CRLF in snapshot, LF in subprocess stdout -> no false-positive new dirt")
    except AssertionError as exc:
        failures.append(f"FAIL: CRLF/LF normalization: {exc}")
    except Exception as exc:
        failures.append(f"FAIL: CRLF/LF normalization ({type(exc).__name__}): {exc}")

    # 9. capture_snapshot: writes the exact git status --porcelain --untracked-files=no stdout
    try:
        with tempfile.TemporaryDirectory() as tmp:
            snapshot_path = Path(tmp) / "_mill" / ".cleanliness-snapshot-foo.txt"
            with unittest.mock.patch("_cleanliness._pygit2_util.status_porcelain", return_value=[" M file.txt"]):
                capture_snapshot(Path(tmp), snapshot_path)
            assert snapshot_path.exists(), "snapshot file not created"
            content = snapshot_path.read_text(encoding="utf-8")
            assert content == " M file.txt\n", f"content wrong: {content!r}"
        print("PASS: capture_snapshot writes exact git status stdout")
    except AssertionError as exc:
        failures.append(f"FAIL: capture_snapshot: {exc}")
    except Exception as exc:
        failures.append(f"FAIL: capture_snapshot ({type(exc).__name__}): {exc}")

    # CV-1. compute_scope_violations: clean worktree returns []
    try:
        with tempfile.TemporaryDirectory() as tmp:
            with unittest.mock.patch("_cleanliness._pygit2_util.status_porcelain", return_value=[]):
                result = compute_scope_violations(Path(tmp))
            assert result == [], f"expected [], got {result!r}"
        print("PASS: compute_scope_violations: clean worktree -> []")
    except AssertionError as exc:
        failures.append(f"FAIL: compute_scope_violations clean: {exc}")
    except Exception as exc:
        failures.append(f"FAIL: compute_scope_violations clean ({type(exc).__name__}): {exc}")

    # CV-2. compute_scope_violations: untracked file at root returned
    try:
        with tempfile.TemporaryDirectory() as tmp:
            with unittest.mock.patch("_cleanliness._pygit2_util.status_porcelain", return_value=["?? plugins_mill_scripts_foo.py"]):
                result = compute_scope_violations(Path(tmp))
            assert result == ["plugins_mill_scripts_foo.py"], f"expected ['plugins_mill_scripts_foo.py'], got {result!r}"
        print("PASS: compute_scope_violations: untracked at root -> path returned")
    except AssertionError as exc:
        failures.append(f"FAIL: compute_scope_violations untracked root: {exc}")
    except Exception as exc:
        failures.append(f"FAIL: compute_scope_violations untracked root ({type(exc).__name__}): {exc}")

    # CV-3. compute_scope_violations: untracked file under _mill/ filtered out
    try:
        with tempfile.TemporaryDirectory() as tmp:
            with unittest.mock.patch("_cleanliness._pygit2_util.status_porcelain", return_value=["?? _mill/some-scratch.txt"]):
                result = compute_scope_violations(Path(tmp))
            assert result == [], f"expected [], got {result!r}"
        print("PASS: compute_scope_violations: untracked under _mill/ -> filtered")
    except AssertionError as exc:
        failures.append(f"FAIL: compute_scope_violations _mill filter: {exc}")
    except Exception as exc:
        failures.append(f"FAIL: compute_scope_violations _mill filter ({type(exc).__name__}): {exc}")

    # CV-4. compute_scope_violations: untracked file in subdirectory outside _mill/ returned
    try:
        with tempfile.TemporaryDirectory() as tmp:
            with unittest.mock.patch("_cleanliness._pygit2_util.status_porcelain", return_value=["?? plugins/mill/scripts/new_file.py"]):
                result = compute_scope_violations(Path(tmp))
            assert result == ["plugins/mill/scripts/new_file.py"], f"expected ['plugins/mill/scripts/new_file.py'], got {result!r}"
        print("PASS: compute_scope_violations: untracked in subdir -> path returned")
    except AssertionError as exc:
        failures.append(f"FAIL: compute_scope_violations untracked subdir: {exc}")
    except Exception as exc:
        failures.append(f"FAIL: compute_scope_violations untracked subdir ({type(exc).__name__}): {exc}")

    # CV-5. compute_scope_violations: junctions (.wiki, .portals, .active, .others) filtered
    try:
        with tempfile.TemporaryDirectory() as tmp:
            with unittest.mock.patch(
                "_cleanliness._pygit2_util.status_porcelain",
                return_value=["?? .wiki", "?? .portals", "?? .active", "?? .others", "?? bad_file.py"]
            ):
                result = compute_scope_violations(Path(tmp))
            assert result == ["bad_file.py"], f"expected ['bad_file.py'], got {result!r}"
        print("PASS: compute_scope_violations: junctions filtered, genuine file returned")
    except AssertionError as exc:
        failures.append(f"FAIL: compute_scope_violations junction filter: {exc}")
    except Exception as exc:
        failures.append(f"FAIL: compute_scope_violations junction filter ({type(exc).__name__}): {exc}")

    # CV-6. compute_scope_violations: files under junction dirs filtered
    try:
        with tempfile.TemporaryDirectory() as tmp:
            with unittest.mock.patch(
                "_cleanliness._pygit2_util.status_porcelain",
                return_value=["?? .wiki/foo", "?? .portals/bar", "?? plugins/foo.py"]
            ):
                result = compute_scope_violations(Path(tmp))
            assert result == ["plugins/foo.py"], f"expected ['plugins/foo.py'], got {result!r}"
        print("PASS: compute_scope_violations: files under junctions filtered")
    except AssertionError as exc:
        failures.append(f"FAIL: compute_scope_violations files under junctions: {exc}")
    except Exception as exc:
        failures.append(f"FAIL: compute_scope_violations files under junctions ({type(exc).__name__}): {exc}")

    if failures:
        for msg in failures:
            print(msg, file=sys.stderr)
        return 1

    print("All _cleanliness unit tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
