"""
Unit tests for _junction.strip_all_in_worktree FS-scan behaviour.

Covers the one-level filesystem scan that discovers and strips undeclared junctions (legacy .active,
etc.) in addition to declared ones, added for #385, plus vanished-entry TOCTOU races in the
recursive walk (GitHub issue #738).
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

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

            assert wiki_link in stripped, "junction should be in stripped list"
            assert not wiki_link.exists(), "junction should be removed"
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

    # --- (e) nested-junction case ---
    try:
        tmp = tempfile.mkdtemp()
        tmp_path = Path(tmp)
        try:
            # Create worktree with nested subdirectories.
            wt = tmp_path / "wt"
            nested_hub = wt / "src" / "hub"
            nested_hub.mkdir(parents=True)

            # Create junction targets.
            wiki_target = tmp_path / "wiki_target"
            portals_target = tmp_path / "portals_target"
            wiki_target.mkdir()
            portals_target.mkdir()

            # Create junctions at nested level.
            wiki_link = nested_hub / ".wiki"
            portals_link = nested_hub / ".portals"
            _junction.create(wiki_target, wiki_link)
            _junction.create(portals_target, portals_link)

            # Call strip_all_in_worktree from the root.
            stripped = _junction.strip_all_in_worktree(wt, junctions_cfg={})

            # Verify both junctions are stripped.
            assert wiki_link in stripped, ".wiki not in stripped list"
            assert portals_link in stripped, ".portals not in stripped list"
            assert not wiki_link.exists(), ".wiki still exists after stripping"
            assert not portals_link.exists(), ".portals still exists after stripping"
            # Verify the real parent directory still exists.
            assert (wt / "src" / "hub").exists(), "nested parent directory was removed (should not be touched)"
            # Verify the junction targets still exist.
            assert wiki_target.exists(), "wiki_target was deleted (junctions were stripped, targets untouched)"
            assert portals_target.exists(), "portals_target was deleted (junctions were stripped, targets untouched)"

            ok("(e) nested-junction case")
        finally:
            _safe_rmtree.safe_rmtree(tmp_path, allowed_root=tmp_path, ignore_errors=True)
    except Exception as exc:
        fail("(e) nested-junction case", exc)

    # --- (f) vanished file entry mid-walk: sibling still processed ---
    try:
        tmp = tempfile.mkdtemp()
        tmp_path = Path(tmp)
        try:
            wt = tmp_path / "wt"
            wt.mkdir()

            processed: list[str] = []
            entry_a = MagicMock()
            entry_a.path = str(wt / "a.txt")
            entry_a.is_symlink.side_effect = FileNotFoundError
            entry_b = MagicMock()
            entry_b.path = str(wt / "b.txt")
            entry_b.is_symlink.return_value = False
            entry_b.is_dir.side_effect = lambda *a, **k: processed.append("b") or False

            with patch("_junction.os.scandir", return_value=[entry_a, entry_b]):
                result = _junction.strip_all_in_worktree(wt, junctions_cfg={})

            assert processed == ["b"], f"surviving sibling must still be processed, got {processed}"
            assert result == [], f"vanished entry must not be counted as removed, got {result}"
            ok("(f) vanished file entry mid-walk case")
        finally:
            _safe_rmtree.safe_rmtree(tmp_path, allowed_root=tmp_path, ignore_errors=True)
    except Exception as exc:
        fail("(f) vanished file entry mid-walk case", exc)

    # --- (g) vanished subdirectory entry mid-walk: sibling still processed ---
    try:
        tmp = tempfile.mkdtemp()
        tmp_path = Path(tmp)
        try:
            wt = tmp_path / "wt"
            wt.mkdir()
            sub_path = wt / "sub"

            processed = []
            entry_sub = MagicMock()
            entry_sub.path = str(sub_path)
            entry_sub.is_symlink.return_value = False
            entry_sub.is_dir.return_value = True
            entry_sibling = MagicMock()
            entry_sibling.path = str(wt / "sibling.txt")
            entry_sibling.is_symlink.return_value = False
            entry_sibling.is_dir.side_effect = lambda *a, **k: processed.append("sibling") or False

            def fake_scandir(path: str):
                if str(path) == str(sub_path):
                    raise FileNotFoundError(f"vanished: {path}")
                if str(path) == str(wt):
                    return [entry_sub, entry_sibling]
                raise AssertionError(f"unexpected scandir call: {path}")

            with patch("_junction.os.scandir", side_effect=fake_scandir):
                result = _junction.strip_all_in_worktree(wt, junctions_cfg={})

            assert processed == ["sibling"], \
                f"sibling of vanished subdirectory must still be processed, got {processed}"
            assert result == [], f"vanished entry must not be counted as removed, got {result}"
            ok("(g) vanished subdirectory entry mid-walk case")
        finally:
            _safe_rmtree.safe_rmtree(tmp_path, allowed_root=tmp_path, ignore_errors=True)
    except Exception as exc:
        fail("(g) vanished subdirectory entry mid-walk case", exc)

    # --- (h) strip_all_in_worktree entry-point window: outermost scandir vanishes ---
    try:
        tmp = tempfile.mkdtemp()
        tmp_path = Path(tmp)
        try:
            wt = tmp_path / "wt"
            wt.mkdir()

            with patch("_junction.os.scandir", side_effect=FileNotFoundError):
                result = _junction.strip_all_in_worktree(wt, junctions_cfg={})

            assert result == [], f"expected empty list rather than a raised exception, got {result}"
            ok("(h) strip_all_in_worktree entry-point window case")
        finally:
            _safe_rmtree.safe_rmtree(tmp_path, allowed_root=tmp_path, ignore_errors=True)
    except Exception as exc:
        fail("(h) strip_all_in_worktree entry-point window case", exc)

    # --- (i) extended-path form is what _walk actually passes to os.scandir ---
    try:
        tmp = tempfile.mkdtemp()
        tmp_path = Path(tmp)
        try:
            wt = tmp_path / "wt"
            wt.mkdir()

            def fake_scandir(path: str):
                assert path == "LONGPATH-MARKER-SUCCESS", f"unexpected scandir arg: {path}"
                return []

            with patch("_junction._long_path.to_extended", MagicMock(return_value="LONGPATH-MARKER-SUCCESS")), \
                    patch("_junction.os.scandir", side_effect=fake_scandir):
                result = _junction.strip_all_in_worktree(wt, junctions_cfg={})

            assert result == [], f"expected empty list, got {result}"
            ok("(i) extended-path form passed to os.scandir case")
        finally:
            _safe_rmtree.safe_rmtree(tmp_path, allowed_root=tmp_path, ignore_errors=True)
    except Exception as exc:
        fail("(i) extended-path form passed to os.scandir case", exc)

    # --- (j) vanished-entry handling still fires when the extended-path call raises FileNotFoundError ---
    try:
        tmp = tempfile.mkdtemp()
        tmp_path = Path(tmp)
        try:
            wt = tmp_path / "wt"
            wt.mkdir()

            def fake_scandir(path: str):
                assert path == "LONGPATH-MARKER-VANISHED", f"unexpected scandir arg: {path}"
                raise FileNotFoundError("vanished")

            with patch("_junction._long_path.to_extended", MagicMock(return_value="LONGPATH-MARKER-VANISHED")), \
                    patch("_junction.os.scandir", side_effect=fake_scandir):
                result = _junction.strip_all_in_worktree(wt, junctions_cfg={})

            assert result == [], f"expected empty list rather than a raised exception, got {result}"
            ok("(j) vanished-entry handling via extended-path call case")
        finally:
            _safe_rmtree.safe_rmtree(tmp_path, allowed_root=tmp_path, ignore_errors=True)
    except Exception as exc:
        fail("(j) vanished-entry handling via extended-path call case", exc)

    # --- (k) _is_junction_or_symlink routes lexists/islink through _long_path.to_extended ---
    try:
        tmp = tempfile.mkdtemp()
        tmp_path = Path(tmp)
        try:
            target_file = tmp_path / "target_file"

            def fake_lexists(path: str) -> bool:
                assert path == "LONGPATH-MARKER-ISJUNCTION", f"unexpected lexists arg: {path}"
                return True

            def fake_islink(path: str) -> bool:
                assert path == "LONGPATH-MARKER-ISJUNCTION", f"unexpected islink arg: {path}"
                return False

            with patch("_junction._long_path.to_extended", MagicMock(return_value="LONGPATH-MARKER-ISJUNCTION")), \
                    patch("_junction.os.path.lexists", side_effect=fake_lexists), \
                    patch("_junction.os.path.islink", side_effect=fake_islink):
                result = _junction._is_junction_or_symlink(target_file)

            assert result is False, f"expected False, got {result}"
            ok("(k) _is_junction_or_symlink extended-path routing case")
        finally:
            _safe_rmtree.safe_rmtree(tmp_path, allowed_root=tmp_path, ignore_errors=True)
    except Exception as exc:
        fail("(k) _is_junction_or_symlink extended-path routing case", exc)

    # --- (l) remove() routes its os.unlink call through _long_path.to_extended ---
    try:
        tmp = tempfile.mkdtemp()
        tmp_path = Path(tmp)
        try:
            link_path = tmp_path / "a_symlink"

            with patch("_junction._long_path.to_extended", MagicMock(return_value="LONGPATH-MARKER-REMOVE")), \
                    patch("_junction.os.path.lexists", MagicMock(return_value=True)), \
                    patch("_junction.os.path.islink", MagicMock(return_value=True)), \
                    patch("_junction.os.unlink", MagicMock()) as mock_unlink:
                _junction.remove(link_path)

            assert mock_unlink.call_args[0][0] == "LONGPATH-MARKER-REMOVE", \
                f"expected extended-path marker passed to os.unlink, got {mock_unlink.call_args[0][0]}"
            ok("(l) remove() extended-path routing to os.unlink case")
        finally:
            _safe_rmtree.safe_rmtree(tmp_path, allowed_root=tmp_path, ignore_errors=True)
    except Exception as exc:
        fail("(l) remove() extended-path routing to os.unlink case", exc)

    print("", file=sys.stderr)
    if failed:
        print(f"FAIL -- {failed} of {passed + failed}", file=sys.stderr)
        return 1
    print(f"PASS -- all {passed} tests", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
