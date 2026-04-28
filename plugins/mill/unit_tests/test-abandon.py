"""Unit tests for mill-abandon.py logic.

Uses a trampoline subprocess that pre-patches sys.modules with mock _paths
and _wiki modules so no real git or wiki I/O occurs.
"""
from __future__ import annotations

import datetime
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
SCRIPTS = HUB / "plugins" / "mill" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import _active
import _builder_lock
import _status


def _make_status_md(path: Path, phase: str = "implementing") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = _status.render_initial(
        task_title="Test task",
        task_description="A test.",
        timestamp="2026-04-24T10:00:00Z",
        parent_branch="main",
        slug="my-slug",
        branch="hanf/my-slug",
    )
    path.write_text(content, encoding="utf-8")
    if phase not in ("discussing",):
        _status.append_phase(path, phase, "2026-04-24T11:00:00Z")


def _make_worktree(tmp: Path, slug: str, phase: str = "implementing") -> tuple[Path, Path, Path]:
    """Return (worktree_root, mill_dir, status_path)."""
    wt = tmp / "worktree"
    wt.mkdir(exist_ok=True)
    mill_dir = wt / ".millhouse"
    mill_dir.mkdir(exist_ok=True)
    (mill_dir / "active.slug.md").write_text(f"slug: {slug}\n", encoding="utf-8")
    _active.write(mill_dir, slug=slug, task_title="Test task",
                  branch=f"impl/{slug}", spawned_at="2026-04-24T10:00:00Z")
    wiki = tmp / "wiki"
    status_path = wiki / "active" / slug / "status.md"
    _make_status_md(status_path, phase)
    return wt, mill_dir, status_path


def _make_trampoline(tmp: Path, wiki_path: Path) -> Path:
    """Write a subprocess trampoline that mocks _paths/_wiki before loading mill-abandon."""
    abandon_src = (SCRIPTS / "mill-abandon.py").as_posix()
    wiki_posix = wiki_path.as_posix()
    trampoline = tmp / "_trampoline.py"
    trampoline.write_text(
        "import sys, types, importlib.util\n"
        "from pathlib import Path\n"
        "\n"
        "pm = types.ModuleType('_paths')\n"
        f"pm.resolve_git_root = lambda: Path(r'{tmp.as_posix()}')\n"
        f"pm.resolve_wiki_path = lambda g: Path(r'{wiki_posix}')\n"
        "sys.modules['_paths'] = pm\n"
        "\n"
        "wm = types.ModuleType('_wiki')\n"
        "wm.acquire_lock = lambda *a, **k: None\n"
        "wm.release_lock = lambda *a, **k: None\n"
        "wm.write_commit_push = lambda *a, **k: None\n"
        "sys.modules['_wiki'] = wm\n"
        "\n"
        # Use 'mill_abandon' (not '__main__') so the if-__main__ block doesn't fire
        f"spec = importlib.util.spec_from_file_location('mill_abandon', r'{abandon_src}')\n"
        "mod = importlib.util.module_from_spec(spec)\n"
        "spec.loader.exec_module(mod)\n"
        "sys.exit(mod.main())\n",
        encoding="utf-8",
    )
    return trampoline


def _run(worktree: Path, trampoline: Path, extra_args: list[str] | None = None,
         stdin_input: str = "") -> subprocess.CompletedProcess:
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    cmd = [sys.executable, str(trampoline)] + (extra_args or [])
    return subprocess.run(
        cmd, cwd=str(worktree), input=stdin_input,
        capture_output=True, text=True, encoding="utf-8", env=env,
    )


def main() -> int:
    passed = 0
    failed = 0

    def ok(name: str) -> None:
        nonlocal passed
        passed += 1
        msg = f"PASS: {name}\n"
        sys.stdout.buffer.write(msg.encode("utf-8", errors="backslashreplace"))
        sys.stdout.buffer.flush()

    def fail(name: str, exc: Exception) -> None:
        nonlocal failed
        failed += 1
        msg = f"FAIL: {name}: {exc}\n"
        sys.stderr.buffer.write(msg.encode("utf-8", errors="backslashreplace"))
        sys.stderr.buffer.flush()

    # --- (a) happy path ---
    try:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            slug = "test-task"
            wt, mill_dir, status_path = _make_worktree(tmp, slug, "implementing")
            trampoline = _make_trampoline(tmp, tmp / "wiki")
            result = _run(wt, trampoline, ["--force"])
            assert result.returncode == 0, f"exit={result.returncode} stderr={result.stderr}"
            assert slug in result.stdout, f"slug missing from stdout: {result.stdout!r}"
            assert "mill-cleanup" in result.stdout
            # status.md should have phase=abandoned
            info = _status.read_status(status_path)
            assert info["phase"] == "abandoned", f"phase={info['phase']!r}"
            ok("happy path --force: exits 0, status.md updated")
    except Exception as exc:
        fail("happy path --force", exc)

    # --- (b) hub check: no active.slug.md ---
    try:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            hub_root = tmp / "hub"
            hub_root.mkdir()
            trampoline = _make_trampoline(tmp, tmp / "wiki")
            result = _run(hub_root, trampoline, ["--force"])
            assert result.returncode != 0, f"expected non-zero from hub, got {result.returncode}"
            ok("hub check: exits non-zero when active.slug.md absent")
    except Exception as exc:
        fail("hub check", exc)

    # --- (c) phase already abandoned → refuse ---
    try:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            slug = "test-task"
            wt, mill_dir, status_path = _make_worktree(tmp, slug, "abandoned")
            trampoline = _make_trampoline(tmp, tmp / "wiki")
            result = _run(wt, trampoline, ["--force"])
            assert result.returncode != 0, f"expected non-zero, got {result.returncode}"
            combined = result.stdout + result.stderr
            assert "already abandoned" in combined, f"'already abandoned' not in output"
            ok("phase=abandoned → refuse")
    except Exception as exc:
        fail("phase=abandoned refuse", exc)

    # --- (d) phase done → refuse ---
    try:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            slug = "test-task"
            wt, mill_dir, status_path = _make_worktree(tmp, slug, "done")
            trampoline = _make_trampoline(tmp, tmp / "wiki")
            result = _run(wt, trampoline, ["--force"])
            assert result.returncode != 0, f"expected non-zero, got {result.returncode}"
            combined = result.stdout + result.stderr
            assert "done" in combined, "'done' not in output"
            ok("phase=done → refuse")
    except Exception as exc:
        fail("phase=done refuse", exc)

    # --- (e) non-stale builder lock → refuse ---
    try:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            slug = "test-task"
            wt, mill_dir, status_path = _make_worktree(tmp, slug, "implementing")
            now_ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            (mill_dir / _builder_lock.LOCK_FILENAME).write_text(
                f"```yaml\nslug: other-task\ntimestamp: {now_ts}\n```\n", encoding="utf-8"
            )
            trampoline = _make_trampoline(tmp, tmp / "wiki")
            result = _run(wt, trampoline)  # no --force
            assert result.returncode != 0, f"expected non-zero, got {result.returncode}"
            combined = result.stdout + result.stderr
            assert "builder lock" in combined, "'builder lock' not in output"
            ok("non-stale lock → refuse without --force")
    except Exception as exc:
        fail("non-stale lock", exc)

    # --- (f) stale builder lock → proceed ---
    try:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            slug = "test-task"
            wt, mill_dir, status_path = _make_worktree(tmp, slug, "implementing")
            (mill_dir / _builder_lock.LOCK_FILENAME).write_text(
                "```yaml\nslug: other-task\ntimestamp: 2000-01-01T00:00:00Z\n```\n",
                encoding="utf-8",
            )
            trampoline = _make_trampoline(tmp, tmp / "wiki")
            result = _run(wt, trampoline, ["--force"])
            assert result.returncode == 0, f"exit={result.returncode} stderr={result.stderr}"
            ok("stale lock → proceed with --force")
    except Exception as exc:
        fail("stale lock proceed", exc)

    # --- (g) missing status.md → refuse ---
    try:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            slug = "test-task"
            wt = tmp / "worktree"
            wt.mkdir()
            mill_dir = wt / ".millhouse"
            mill_dir.mkdir()
            (mill_dir / "active.slug.md").write_text(f"slug: {slug}\n", encoding="utf-8")
            _active.write(mill_dir, slug=slug, task_title="Test task",
                          branch=f"impl/{slug}", spawned_at="2026-04-24T10:00:00Z")
            # status.md intentionally NOT created
            trampoline = _make_trampoline(tmp, tmp / "wiki")
            result = _run(wt, trampoline, ["--force"])
            assert result.returncode != 0, f"expected non-zero, got {result.returncode}"
            combined = result.stdout + result.stderr
            assert "status.md" in combined, "'status.md' not in output"
            ok("missing status.md → refuse")
    except Exception as exc:
        fail("missing status.md", exc)

    print(f"\n{passed} passed, {failed} failed.")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
