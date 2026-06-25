"""Unit tests for millpy-abandon.py logic.

Uses a trampoline subprocess that pre-patches sys.modules with mock _paths,
_marker, _review_common, and _subprocess_util modules so no real git or wiki
I/O occurs.
"""
from __future__ import annotations

import datetime
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
SCRIPTS = HUB / "plugins" / "mill" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import _builder_lock  # noqa: E402
import _status  # noqa: E402


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
    status_path = wt / "_mill" / "status.md"
    _make_status_md(status_path, phase)
    return wt, mill_dir, status_path


def _make_trampoline(tmp: Path, slug: str | None = "test-task") -> Path:
    """Write a subprocess trampoline that mocks _paths/_marker/_review_common/_subprocess_util."""
    abandon_src = (SCRIPTS / "millpy-abandon.py").as_posix()
    wt_posix = (tmp / "worktree").as_posix()
    wiki_posix = (tmp / "wiki").as_posix()
    tmp_posix = tmp.as_posix()
    cmds_posix = (tmp / "_git_cmds.json").as_posix()

    if slug is not None:
        marker_block = (
            "mm = types.ModuleType('_marker')\n"
            "mm.MarkerError = type('MarkerError', (RuntimeError,), {})\n"
            f"mm.slug_from_branch = lambda *a, **kw: {slug!r}\n"
            "sys.modules['_marker'] = mm\n"
        )
    else:
        marker_block = (
            "mm = types.ModuleType('_marker')\n"
            "mm.MarkerError = type('MarkerError', (RuntimeError,), {})\n"
            "def _marker_err(*a, **kw):\n"
            "    raise mm.MarkerError('not a worktree branch')\n"
            "mm.slug_from_branch = _marker_err\n"
            "sys.modules['_marker'] = mm\n"
        )

    trampoline = tmp / "_trampoline.py"
    trampoline.write_text(
        "import sys, types, importlib.util, json\n"
        "from pathlib import Path\n"
        "\n"
        "pm = types.ModuleType('_paths')\n"
        f"pm.resolve_git_root = lambda: Path(r'{tmp_posix}')\n"
        f"pm.resolve_wiki_path = lambda g: Path(r'{wiki_posix}')\n"
        f"pm.resolve_container_path = lambda p: Path(r'{tmp_posix}')\n"
        f"pm.resolve_hub_path = lambda: Path(r'{wt_posix}')\n"
        f"pm.resolve_active_hub = lambda container, slug, *, cfg, git_root: Path(r'{wt_posix}')\n"
        "def _rtp(wt, rel):\n"
        "    t = wt / rel\n"
        "    if t.exists(): return t\n"
        "    if '_mill/' in rel:\n"
        "        fb = wt / rel.replace('_mill/', 'task/', 1)\n"
        "        if fb.exists(): return fb\n"
        "    return t\n"
        "pm.resolve_task_path = _rtp\n"
        "pm.status_path = lambda wt, cfg: wt / '_mill' / 'status.md'\n"
        "sys.modules['_paths'] = pm\n"
        "\n"
        + marker_block +
        "\n"
        "rcm = types.ModuleType('_review_common')\n"
        "rcm.load_config = lambda wiki_root, mill_dir: {}\n"
        "sys.modules['_review_common'] = rcm\n"
        "\n"
        "_recorded = []\n"
        f"_cmds_file = Path(r'{cmds_posix}')\n"
        "\n"
        "class _FakeResult:\n"
        "    def __init__(self):\n"
        "        self.returncode = 0\n"
        "        self.stdout = ''\n"
        "        self.stderr = ''\n"
        "\n"
        "_sub = types.ModuleType('_subprocess_util')\n"
        "def _mock_run(argv, **kw):\n"
        "    _recorded.append(list(argv))\n"
        "    _cmds_file.write_text(json.dumps(_recorded), encoding='utf-8')\n"
        "    return _FakeResult()\n"
        "_sub.run = _mock_run\n"
        "sys.modules['_subprocess_util'] = _sub\n"
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


def _read_git_cmds(tmp: Path) -> list[list[str]]:
    p = tmp / "_git_cmds.json"
    if not p.exists():
        return []
    return json.loads(p.read_text(encoding="utf-8"))


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
            trampoline = _make_trampoline(tmp, slug=slug)
            result = _run(wt, trampoline, ["--force"])
            assert result.returncode == 0, f"exit={result.returncode} stderr={result.stderr}"
            assert slug in result.stdout, f"slug missing from stdout: {result.stdout!r}"
            assert "mill-cleanup" in result.stdout
            # status.md should have phase=abandoned
            info = _status.read_status(status_path)
            assert info["phase"] == "abandoned", f"phase={info['phase']!r}"
            # git commands should target the task branch (active_hub == wt for flat-hub)
            cmds = _read_git_cmds(tmp)
            wt_str = str(wt)
            assert ["git", "-C", wt_str, "add", "_mill/status.md"] in cmds, \
                f"add not in cmds: {cmds}"
            assert ["git", "-C", wt_str, "commit", "-m", f"task: abandon {slug}"] in cmds, \
                f"commit not in cmds: {cmds}"
            # The final git operation must be push origin --delete <branch>,
            # not a bare push -- we delete the remote branch instead of pushing
            # an abandon-marker commit.
            delete_cmds = [c for c in cmds if "push" in c and "--delete" in c]
            assert len(delete_cmds) == 1, \
                f"expected exactly one 'push origin --delete' command, got: {cmds}"
            assert "origin" in delete_cmds[0] and "--delete" in delete_cmds[0], \
                f"expected 'push origin --delete', got: {delete_cmds[0]}"
            # Confirm bare 'push' (old marker-push pattern) is not present.
            bare_push_cmds = [c for c in cmds if c == ["git", "-C", wt_str, "push"]]
            assert bare_push_cmds == [], \
                f"bare 'push' must not be present after refactor; got: {cmds}"
            ok("happy path --force: exits 0, status.md updated, push origin --delete issued")
    except Exception as exc:
        fail("happy path --force", exc)

    # --- (b) non-worktree: MarkerError -> refuse ---
    try:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            hub_root = tmp / "hub"
            hub_root.mkdir()
            trampoline = _make_trampoline(tmp, slug=None)
            result = _run(hub_root, trampoline, ["--force"])
            assert result.returncode != 0, f"expected non-zero from non-worktree, got {result.returncode}"
            combined = result.stdout + result.stderr
            assert "worktree" in combined, f"'worktree' not in output: {combined!r}"
            ok("non-worktree: MarkerError -> refuse with non-zero exit")
    except Exception as exc:
        fail("non-worktree MarkerError", exc)

    # --- (c) phase already abandoned -> refuse ---
    try:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            slug = "test-task"
            wt, mill_dir, status_path = _make_worktree(tmp, slug, "abandoned")
            trampoline = _make_trampoline(tmp, slug=slug)
            result = _run(wt, trampoline, ["--force"])
            assert result.returncode != 0, f"expected non-zero, got {result.returncode}"
            combined = result.stdout + result.stderr
            assert "already abandoned" in combined, "'already abandoned' not in output"
            ok("phase=abandoned -> refuse")
    except Exception as exc:
        fail("phase=abandoned refuse", exc)

    # --- (d) phase done -> refuse ---
    try:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            slug = "test-task"
            wt, mill_dir, status_path = _make_worktree(tmp, slug, "done")
            trampoline = _make_trampoline(tmp, slug=slug)
            result = _run(wt, trampoline, ["--force"])
            assert result.returncode != 0, f"expected non-zero, got {result.returncode}"
            combined = result.stdout + result.stderr
            assert "done" in combined, "'done' not in output"
            ok("phase=done -> refuse")
    except Exception as exc:
        fail("phase=done refuse", exc)

    # --- (e) non-stale builder lock -> refuse ---
    try:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            slug = "test-task"
            wt, mill_dir, status_path = _make_worktree(tmp, slug, "implementing")
            now_ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            (mill_dir / _builder_lock.LOCK_FILENAME).write_text(
                f"```yaml\nslug: other-task\ntimestamp: {now_ts}\n```\n", encoding="utf-8"
            )
            trampoline = _make_trampoline(tmp, slug=slug)
            result = _run(wt, trampoline)  # no --force
            assert result.returncode != 0, f"expected non-zero, got {result.returncode}"
            combined = result.stdout + result.stderr
            assert "builder lock" in combined, "'builder lock' not in output"
            ok("non-stale lock -> refuse without --force")
    except Exception as exc:
        fail("non-stale lock", exc)

    # --- (f) stale builder lock -> proceed ---
    try:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            slug = "test-task"
            wt, mill_dir, status_path = _make_worktree(tmp, slug, "implementing")
            (mill_dir / _builder_lock.LOCK_FILENAME).write_text(
                "```yaml\nslug: other-task\ntimestamp: 2000-01-01T00:00:00Z\n```\n",
                encoding="utf-8",
            )
            trampoline = _make_trampoline(tmp, slug=slug)
            result = _run(wt, trampoline, ["--force"])
            assert result.returncode == 0, f"exit={result.returncode} stderr={result.stderr}"
            cmds = _read_git_cmds(tmp)
            wt_str = str(wt)
            assert ["git", "-C", wt_str, "add", "_mill/status.md"] in cmds, \
                f"add not in cmds: {cmds}"
            ok("stale lock -> proceed with --force")
    except Exception as exc:
        fail("stale lock proceed", exc)

    # --- (g-push-delete) push origin --delete tolerates "remote ref does not exist" stderr ---
    # Verifies the Shared Decision: a non-zero exit whose stderr indicates the
    # remote ref does not exist is treated as success (idempotent teardown).
    try:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            slug = "test-task"
            wt, mill_dir, status_path = _make_worktree(tmp, slug, "implementing")
            # Build a trampoline where push origin --delete returns non-zero
            # with a "remote ref does not exist" message -- should succeed.
            abandon_src = (SCRIPTS / "millpy-abandon.py").as_posix()
            wt_posix = (tmp / "worktree").as_posix()
            wiki_posix = (tmp / "wiki").as_posix()
            tmp_posix = tmp.as_posix()
            cmds_posix = (tmp / "_git_cmds.json").as_posix()
            trampoline_rnd = tmp / "_trampoline_rnd.py"
            trampoline_rnd.write_text(
                "import sys, types, importlib.util, json\n"
                "from pathlib import Path\n"
                "\n"
                "pm = types.ModuleType('_paths')\n"
                f"pm.resolve_git_root = lambda: Path(r'{tmp_posix}')\n"
                f"pm.resolve_wiki_path = lambda g: Path(r'{wiki_posix}')\n"
                f"pm.resolve_container_path = lambda p: Path(r'{tmp_posix}')\n"
                f"pm.resolve_hub_path = lambda: Path(r'{wt_posix}')\n"
                f"pm.resolve_active_hub = lambda container, slug, *, cfg, git_root: Path(r'{wt_posix}')\n"
                "pm.status_path = lambda wt, cfg: wt / '_mill' / 'status.md'\n"
                "sys.modules['_paths'] = pm\n"
                "\n"
                "mm = types.ModuleType('_marker')\n"
                "mm.MarkerError = type('MarkerError', (RuntimeError,), {})\n"
                "mm.slug_from_branch = lambda *a, **kw: 'test-task'\n"
                "sys.modules['_marker'] = mm\n"
                "\n"
                "rcm = types.ModuleType('_review_common')\n"
                "rcm.load_config = lambda wiki_root, mill_dir: {}\n"
                "sys.modules['_review_common'] = rcm\n"
                "\n"
                "_recorded = []\n"
                f"_cmds_file = Path(r'{cmds_posix}')\n"
                "\n"
                "class _FakeResultOK:\n"
                "    returncode = 0\n"
                "    stdout = ''\n"
                "    stderr = ''\n"
                "\n"
                "class _FakeResultMissingRef:\n"
                "    returncode = 1\n"
                "    stdout = ''\n"
                "    stderr = 'error: unable to delete refs/heads/hanf/test-task: remote ref does not exist'\n"
                "\n"
                "_sub = types.ModuleType('_subprocess_util')\n"
                "def _mock_run(argv, **kw):\n"
                "    _recorded.append(list(argv))\n"
                "    _cmds_file.write_text(json.dumps(_recorded), encoding='utf-8')\n"
                "    # Simulate push origin --delete returning 'remote ref does not exist'\n"
                "    if '--delete' in argv:\n"
                "        return _FakeResultMissingRef()\n"
                "    return _FakeResultOK()\n"
                "_sub.run = _mock_run\n"
                "sys.modules['_subprocess_util'] = _sub\n"
                "\n"
                f"spec = importlib.util.spec_from_file_location('mill_abandon', r'{abandon_src}')\n"
                "mod = importlib.util.module_from_spec(spec)\n"
                "spec.loader.exec_module(mod)\n"
                "sys.exit(mod.main())\n",
                encoding="utf-8",
            )
            env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
            import subprocess as _subprocess
            result = _subprocess.run(
                [sys.executable, str(trampoline_rnd), "--force"],
                cwd=str(wt), input="",
                capture_output=True, text=True, encoding="utf-8", env=env,
            )
            assert result.returncode == 0, (
                f"expected exit 0 when 'remote ref does not exist', "
                f"got {result.returncode}; stderr={result.stderr!r}"
            )
            ok("push --delete tolerates 'remote ref does not exist' stderr (idempotent)")
    except Exception as exc:
        fail("push --delete tolerates missing remote ref", exc)

    # --- (g) missing status.md -> refuse ---
    try:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            slug = "test-task"
            wt = tmp / "worktree"
            wt.mkdir()
            mill_dir = wt / ".millhouse"
            mill_dir.mkdir()
            # status.md intentionally NOT created
            trampoline = _make_trampoline(tmp, slug=slug)
            result = _run(wt, trampoline, ["--force"])
            assert result.returncode != 0, f"expected non-zero, got {result.returncode}"
            combined = result.stdout + result.stderr
            assert "status.md" in combined, "'status.md' not in output"
            ok("missing status.md -> refuse")
    except Exception as exc:
        fail("missing status.md", exc)

    print(f"\n{passed} passed, {failed} failed.")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
