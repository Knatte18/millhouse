"""
Unit tests for _junction.strip_all_in_worktree FS-scan behaviour.

Covers the one-level filesystem scan that discovers and strips undeclared
junctions (legacy .active, etc.) in addition to declared ones, added for #385.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

import _junction  # noqa: E402
import _safe_rmtree  # noqa: E402


def main() -> int:
    passed = 0
    failed = 0

    def ok(name: str) -> None:
        nonlocal passed
        passed += 1
        print(f"PASS: {name}")

    def fail(name: str, exc: Exception) -> None:
        nonlocal failed
        failed += 1
        print(f"FAIL: {name}: {exc}", file=sys.stderr)

    # --- (a) strips-undeclared-junction case ---
    try:
        tmp = tempfile.mkdtemp()
        tmp_path = Path(tmp)
        try:
            target = tmp_path / "target"
            target.mkdir()
            wt = tmp_path / "wt"
            wt.mkdir()
            active_link = wt / ".active"

            _junction.create(target, active_link)

            stripped = _junction.strip_all_in_worktree(wt, junctions_cfg={})

            assert active_link in stripped, f".active not in stripped list: {stripped}"
            assert not active_link.exists(), ".active still exists after stripping"
            assert not _junction._is_junction_or_symlink(active_link), ".active is still a junction/symlink"
            assert target.exists(), "target directory was deleted (should not follow junction)"
            ok("strips-undeclared-junction case")
        finally:
            _safe_rmtree.safe_rmtree(tmp_path, allowed_root=tmp_path, ignore_errors=True)
    except Exception as exc:
        fail("strips-undeclared-junction case", exc)

    # --- (b) multiple-junctions case ---
    try:
        tmp = tempfile.mkdtemp()
        tmp_path = Path(tmp)
        try:
            wiki_target = tmp_path / "wiki_target"
            active_target = tmp_path / "active_target"
            portals_target = tmp_path / "portals_target"
            wiki_target.mkdir()
            active_target.mkdir()
            portals_target.mkdir()

            wt = tmp_path / "wt"
            wt.mkdir()

            wiki_link = wt / ".wiki"
            active_link = wt / ".active"
            portals_link = wt / ".portals"

            _junction.create(wiki_target, wiki_link)
            _junction.create(active_target, active_link)
            _junction.create(portals_target, portals_link)

            stripped = _junction.strip_all_in_worktree(wt, junctions_cfg={})

            assert wiki_link in stripped, ".wiki not in stripped list"
            assert active_link in stripped, ".active not in stripped list"
            assert portals_link in stripped, ".portals not in stripped list"
            assert not wiki_link.exists(), ".wiki still exists"
            assert not active_link.exists(), ".active still exists"
            assert not portals_link.exists(), ".portals still exists"
            ok("multiple-junctions case")
        finally:
            _safe_rmtree.safe_rmtree(tmp_path, allowed_root=tmp_path, ignore_errors=True)
    except Exception as exc:
        fail("multiple-junctions case", exc)

    # --- (c) non-junction-untouched case ---
    try:
        tmp = tempfile.mkdtemp()
        tmp_path = Path(tmp)
        try:
            target = tmp_path / "target"
            target.mkdir()

            wt = tmp_path / "wt"
            wt.mkdir()

            mill_dir = wt / "_mill"
            mill_dir.mkdir()

            claude_file = wt / "CLAUDE.md"
            claude_file.write_text("test", encoding="utf-8")

            wiki_link = wt / ".wiki"
            _junction.create(target, wiki_link)

            stripped = _junction.strip_all_in_worktree(wt, junctions_cfg={})

            assert wiki_link not in [p for p in stripped if p.name == ".wiki"] or not wiki_link.exists(), "junction should be removed"
            assert mill_dir.exists(), "_mill directory was removed (should not be touched)"
            assert claude_file.exists(), "CLAUDE.md file was removed (should not be touched)"
            ok("non-junction-untouched case")
        finally:
            _safe_rmtree.safe_rmtree(tmp_path, allowed_root=tmp_path, ignore_errors=True)
    except Exception as exc:
        fail("non-junction-untouched case", exc)

    # --- (d) missing-worktree case ---
    try:
        tmp = tempfile.mkdtemp()
        tmp_path = Path(tmp)
        try:
            missing = tmp_path / "does-not-exist"
            result = _junction.strip_all_in_worktree(missing, junctions_cfg={})
            assert result == [], f"expected empty list for missing worktree, got {result}"
            ok("missing-worktree case")
        finally:
            _safe_rmtree.safe_rmtree(tmp_path, allowed_root=tmp_path, ignore_errors=True)
    except Exception as exc:
        fail("missing-worktree case", exc)

    print(f"\n{passed} passed, {failed} failed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
