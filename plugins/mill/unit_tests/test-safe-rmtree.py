"""
Unit tests for plugins/mill/scripts/_safe_rmtree.py.

Covers: blacklist refusal, containment refusal, junction/symlink-strip before
rmtree (regression guard for the wiki-wipe incident), path-is-junction/symlink
refusal, missing-path no-op, ignore_errors semantics, and non-container
allowed_root handling.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

import _safe_rmtree  # noqa: E402
from _safe_rmtree import safe_rmtree  # noqa: E402
import _junction  # noqa: E402


def _make_container(tmp: Path) -> Path:
    """Build a fake millhouse container layout inside tmp."""
    container = tmp / "container"
    (container / "wiki").mkdir(parents=True)
    (container / "wiki" / "decoy.txt").write_text("wiki", encoding="utf-8")
    (container / "portals").mkdir(parents=True)
    (container / "portals" / "decoy.txt").write_text("portals", encoding="utf-8")
    (container / "wts" / "container").mkdir(parents=True)
    (container / "wts" / "container" / ".keep").write_text("", encoding="utf-8")
    slug = "myslug"
    (container / "wts" / slug).mkdir(parents=True)
    (container / "wts" / slug / ".keep").write_text("", encoding="utf-8")
    return container


def main() -> int:
    # --- refuses on path == container root ---
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        container = _make_container(tmp_path)
        raised = False
        with patch("_safe_rmtree._paths.resolve_container_path", return_value=container):
            try:
                safe_rmtree(container, allowed_root=container)
            except SystemExit:
                raised = True
        assert raised, "expected SystemExit for path == container root"
        print("PASS: refuses on path == container root")

    # --- refuses on path == container/wiki ---
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        container = _make_container(tmp_path)
        raised = False
        with patch("_safe_rmtree._paths.resolve_container_path", return_value=container):
            try:
                safe_rmtree(container / "wiki", allowed_root=container)
            except SystemExit:
                raised = True
        assert raised, "expected SystemExit for path == container/wiki"
        print("PASS: refuses on path == container/wiki")

    # --- refuses on path == container/portals ---
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        container = _make_container(tmp_path)
        raised = False
        with patch("_safe_rmtree._paths.resolve_container_path", return_value=container):
            try:
                safe_rmtree(container / "portals", allowed_root=container)
            except SystemExit:
                raised = True
        assert raised, "expected SystemExit for path == container/portals"
        print("PASS: refuses on path == container/portals")

    # --- refuses on path == container/wts/container ---
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        container = _make_container(tmp_path)
        raised = False
        with patch("_safe_rmtree._paths.resolve_container_path", return_value=container):
            try:
                safe_rmtree(container / "wts" / "container", allowed_root=container)
            except SystemExit:
                raised = True
        assert raised, "expected SystemExit for path == container/wts/container"
        print("PASS: refuses on path == container/wts/container")

    # --- refuses on path ancestor of blacklist ---
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        container = _make_container(tmp_path)
        raised = False
        with patch("_safe_rmtree._paths.resolve_container_path", return_value=container):
            try:
                safe_rmtree(tmp_path, allowed_root=tmp_path)
            except SystemExit:
                raised = True
        assert raised, "expected SystemExit when path is ancestor of blacklisted entry"
        print("PASS: refuses on path ancestor of blacklist")

    # --- refuses on path outside allowed_root ---
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        a = tmp_path / "a"
        b = tmp_path / "b"
        a.mkdir()
        b.mkdir()
        raised = False
        try:
            safe_rmtree(b, allowed_root=a)
        except SystemExit as exc:
            raised = True
            assert "path outside allowed_root" in str(exc), f"unexpected message: {exc}"
        assert raised, "expected SystemExit for path outside allowed_root"
        print("PASS: refuses on path outside allowed_root")

    # --- refuses when path is itself a symlink (POSIX-only) ---
    if os.name != "nt":
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            target = tmp_path / "target"
            target.mkdir()
            link = tmp_path / "link"
            os.symlink(str(target), str(link))
            raised = False
            try:
                safe_rmtree(link, allowed_root=tmp_path)
            except SystemExit as exc:
                raised = True
                assert "path is itself a symlink" in str(exc), f"unexpected message: {exc}"
            assert raised, "expected SystemExit for symlink path"
            assert target.exists(), "target must still exist after refused symlink rmtree"
            print("PASS: refuses when path is itself a symlink")
    else:
        print("SKIP: refuses when path is itself a symlink (POSIX-only)")

    # --- refuses when path is itself a junction (Windows-only) ---
    if os.name == "nt":
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            target = tmp_path / "target"
            target.mkdir()
            (target / "data.txt").write_text("DO NOT DELETE", encoding="utf-8")
            link = tmp_path / "link"
            _junction.create(target, link)
            raised = False
            try:
                safe_rmtree(link, allowed_root=tmp_path)
            except SystemExit as exc:
                raised = True
                assert "path is itself a junction" in str(exc), f"unexpected message: {exc}"
            assert raised, "expected SystemExit for junction path"
            assert (target / "data.txt").read_text(encoding="utf-8") == "DO NOT DELETE", \
                "target data must be intact after refused junction rmtree"
            print("PASS: refuses when path is itself a junction")
    else:
        print("SKIP: refuses when path is itself a junction (Windows-only)")

    # --- strips junction inside tree before rmtree (Windows-only) ---
    if os.name == "nt":
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            scratch = tmp_path / "scratch"
            sub = scratch / "sub"
            sub.mkdir(parents=True)
            shared_target = tmp_path / "shared_target"
            shared_target.mkdir()
            (shared_target / "data.txt").write_text("DO NOT DELETE", encoding="utf-8")
            _junction.create(shared_target, scratch / "sub" / "aliased")
            safe_rmtree(scratch, allowed_root=scratch)
            assert not scratch.exists(), "scratch must be gone after safe_rmtree"
            assert (shared_target / "data.txt").read_text(encoding="utf-8") == "DO NOT DELETE", \
                "shared_target/data.txt must be intact after safe_rmtree stripped its junction"
            print("PASS: strips junction inside tree before rmtree")
    else:
        print("SKIP: strips junction inside tree before rmtree (Windows-only)")

    # --- strips symlink inside tree before rmtree (POSIX-only) ---
    if os.name != "nt":
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            scratch = tmp_path / "scratch"
            sub = scratch / "sub"
            sub.mkdir(parents=True)
            shared_target = tmp_path / "shared_target"
            shared_target.mkdir()
            (shared_target / "data.txt").write_text("DO NOT DELETE", encoding="utf-8")
            os.symlink(str(shared_target), str(sub / "aliased"))
            safe_rmtree(scratch, allowed_root=scratch)
            assert not scratch.exists(), "scratch must be gone after safe_rmtree"
            assert (shared_target / "data.txt").read_text(encoding="utf-8") == "DO NOT DELETE", \
                "shared_target/data.txt must be intact after safe_rmtree stripped its symlink"
            print("PASS: strips symlink inside tree before rmtree")
    else:
        print("SKIP: strips symlink inside tree before rmtree (POSIX-only)")

    # --- strips multiple junctions at different depths (Windows-only) ---
    if os.name == "nt":
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            scratch = tmp_path / "scratch"
            d1 = scratch / "d1"
            d2 = d1 / "d2"
            d2.mkdir(parents=True)

            targets = []
            for i in range(3):
                t = tmp_path / f"target{i}"
                t.mkdir()
                (t / f"data{i}.txt").write_text(f"content{i}", encoding="utf-8")
                targets.append(t)

            _junction.create(targets[0], scratch / "j0")
            _junction.create(targets[1], d1 / "j1")
            _junction.create(targets[2], d2 / "j2")

            safe_rmtree(scratch, allowed_root=scratch)

            assert not scratch.exists(), "scratch must be gone"
            for i, t in enumerate(targets):
                assert (t / f"data{i}.txt").read_text(encoding="utf-8") == f"content{i}", \
                    f"target{i} data must be intact"
            print("PASS: strips multiple junctions at different depths")
    else:
        print("SKIP: strips multiple junctions at different depths (Windows-only)")

    # --- missing path is no-op ---
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        result = safe_rmtree(tmp_path / "does-not-exist", allowed_root=tmp_path)
        assert result is None
        # Also verify no exception with ignore_errors=False
        result2 = safe_rmtree(tmp_path / "does-not-exist", allowed_root=tmp_path, ignore_errors=False)
        assert result2 is None
        print("PASS: missing path is no-op")

    # --- ignore_errors=True swallows OSError from rmtree ---
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        scratch = tmp_path / "scratch"
        scratch.mkdir()
        with patch("_safe_rmtree.shutil.rmtree", side_effect=OSError("simulated")):
            # ignore_errors=True: no exception
            safe_rmtree(scratch, allowed_root=scratch, ignore_errors=True)
        # ignore_errors=False: OSError propagates
        scratch.mkdir(exist_ok=True)
        raised = False
        with patch("_safe_rmtree.shutil.rmtree", side_effect=OSError("simulated")):
            try:
                safe_rmtree(scratch, allowed_root=scratch, ignore_errors=False)
            except OSError:
                raised = True
        assert raised, "expected OSError to propagate when ignore_errors=False"
        print("PASS: ignore_errors=True swallows OSError from rmtree")

    # --- ignore_errors passes through to shutil.rmtree ---
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        scratch = tmp_path / "scratch"
        scratch.mkdir()
        mock = MagicMock()
        with patch("_safe_rmtree.shutil.rmtree", mock):
            safe_rmtree(scratch, allowed_root=scratch, ignore_errors=True)
        mock.assert_called_once()
        call_kwargs = mock.call_args[1]
        assert call_kwargs.get("ignore_errors") is True, \
            f"expected ignore_errors=True, got {call_kwargs}"

        scratch.mkdir(exist_ok=True)
        mock2 = MagicMock()
        with patch("_safe_rmtree.shutil.rmtree", mock2):
            safe_rmtree(scratch, allowed_root=scratch, ignore_errors=False)
        mock2.assert_called_once()
        call_kwargs2 = mock2.call_args[1]
        # ignore_errors=False path uses onexc=_onexc_chmod_retry (read-only retry)
        # instead of ignore_errors=False, so the kwarg should not be set to True.
        assert call_kwargs2.get("ignore_errors") is not True, \
            f"expected ignore_errors not True, got {call_kwargs2}"
        assert "onexc" in call_kwargs2, \
            f"expected onexc handler on ignore_errors=False path, got {call_kwargs2}"
        print("PASS: ignore_errors passes through to shutil.rmtree")

    # --- non-container allowed_root does not crash ---
    with tempfile.TemporaryDirectory() as tmp:
        non_container = Path(tmp)
        # _paths.resolve_container_path will raise SystemExit (non-git path);
        # the except (Exception, SystemExit) guard must catch it and yield empty blacklist.
        safe_rmtree(non_container, allowed_root=non_container)
        # Directory removed successfully; verify it's gone.
        assert not non_container.exists(), "non_container dir should be removed"
        print("PASS: non-container allowed_root does not crash")

    return 0


if __name__ == "__main__":
    sys.exit(main())
