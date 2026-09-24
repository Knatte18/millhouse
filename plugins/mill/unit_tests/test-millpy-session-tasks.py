"""Unit tests for plugins/mill/scripts/millpy-session-tasks.py."""
from __future__ import annotations

import contextlib
import importlib.util
import io
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

# Load the hyphenated module name via importlib (a bare `import` cannot handle the hyphen).
_SCRIPT = HUB / "plugins" / "mill" / "scripts" / "millpy-session-tasks.py"
_spec = importlib.util.spec_from_file_location("mill_session_tasks", _SCRIPT)
mill_session_tasks = importlib.util.module_from_spec(_spec)
sys.modules["mill_session_tasks"] = mill_session_tasks  # register so patch() can resolve it
_spec.loader.exec_module(mill_session_tasks)

_MARKER_ERROR = mill_session_tasks._marker.MarkerError


def _run(
    repo: Path,
    cfg: dict,
    slug_effect,
    *,
    short: str | None = "HUBSHORT",
    main_root: Path | None = None,
) -> tuple[int, str, str]:
    """
    Run main() with patched path/config/marker functions; return (rc, stdout, stderr).

    ``short`` patches ``resolve_short_name`` (``None`` runs the real function);
    ``main_root`` is the patched main worktree root (default ``repo``).
    """
    out, err = io.StringIO(), io.StringIO()
    short_patch = (
        contextlib.nullcontext()
        if short is None
        else patch("mill_session_tasks.resolve_short_name", return_value=short)
    )
    with (
        patch("mill_session_tasks.resolve_git_root", return_value=repo),
        patch("mill_session_tasks.resolve_hub_path", return_value=repo),
        patch("mill_session_tasks.resolve_wiki_path", return_value=repo / "wiki"),
        patch("mill_session_tasks._load_config", return_value=cfg),
        patch("mill_session_tasks.resolve_main_worktree_root", return_value=main_root or repo),
        short_patch,
        patch("mill_session_tasks._marker.slug_from_branch", side_effect=slug_effect),
        contextlib.redirect_stdout(out),
        contextlib.redirect_stderr(err),
    ):
        rc = mill_session_tasks.main([])
    return rc, out.getvalue(), err.getvalue()


def _check(condition: bool, label: str) -> int:
    if condition:
        print(f"PASS: {label}")
        return 0
    print(f"FAIL: {label}", file=sys.stderr)
    return 1


def _slug_returns(slug: str):
    return lambda *args, **kwargs: slug


def _slug_raises(exc: BaseException):
    def _raise(*args, **kwargs):
        raise exc
    return _raise


def main() -> int:
    errors = 0

    # Task worktree: slug names the sessions.
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = Path(tmpdir)
        (repo / ".vscode").mkdir()
        rc, out, _ = _run(repo, {}, _slug_returns("my-task"))
        target = repo / ".vscode" / "tasks.json"
        text = target.read_text(encoding="utf-8") if target.exists() else ""
        errors += _check(rc == 0 and "hubshort:my-task:start" in text and "mill: orch" not in text,
        "task worktree renders prefixed slug names",
    )
        errors += _check(out.startswith("tasks: created "), "task worktree prints created status")

    # Hub worktree: MarkerError selects the short name.
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = Path(tmpdir)
        (repo / ".vscode").mkdir()
        rc, _, _ = _run(repo, {}, _slug_raises(_MARKER_ERROR("no slug")))
        text = (repo / ".vscode" / "tasks.json").read_text(encoding="utf-8")
        errors += _check(
            rc == 0 and "hubshort:start" in text and "mill: orch" in text and "hubshort:orch" in text,
            "hub worktree renders short name and orch task",
        )

    # Fallback short name comes from the main worktree directory, with one warning.
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = Path(tmpdir) / "session-name-short-prefix"
        (repo / ".vscode").mkdir(parents=True)
        main_root = Path(tmpdir) / "millhouse"
        rc, _, err = _run(repo, {}, _slug_returns("session-name-short-prefix"), short=None, main_root=main_root)
        text = (repo / ".vscode" / "tasks.json").read_text(encoding="utf-8")
        warnings = [line for line in err.splitlines() if "repo.short_name is not set" in line]
        errors += _check(
            rc == 0
            and "mi:session-name-short-prefix:start" in text
            and "se:" not in text
            and len(warnings) == 1
            and "'MI'" in warnings[0],
            "worktree fallback derives short name from main worktree and warns once",
        )

    # A configured short name renders without a warning.
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = Path(tmpdir)
        (repo / ".vscode").mkdir()
        rc, _, err = _run(repo, {"repo": {"short_name": "MH"}}, _slug_returns("my-task"), short=None)
        text = (repo / ".vscode" / "tasks.json").read_text(encoding="utf-8")
        errors += _check(
            rc == 0 and "mh:my-task:start" in text and "repo.short_name is not set" not in err,
            "configured short name renders without warning",
        )

    # Changing spawn.sessions updates the existing file; an unchanged config leaves it alone.
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = Path(tmpdir)
        (repo / ".vscode").mkdir()
        target = repo / ".vscode" / "tasks.json"
        _run(repo, {}, _slug_returns("t"))
        cfg = {"spawn": {"sessions": {"go": {"model": "haiku", "effort": "low"}}}}
        rc, out, _ = _run(repo, cfg, _slug_returns("t"))
        text = target.read_text(encoding="utf-8")
        errors += _check(
            rc == 0 and "--model haiku --effort low" in text and out.startswith("tasks: updated "),
            "changed spawn.sessions updates model and effort",
        )
        before_bytes = target.read_bytes()
        before_mtime = target.stat().st_mtime_ns
        rc, out, _ = _run(repo, cfg, _slug_returns("t"))
        errors += _check(
            rc == 0
            and out.startswith("tasks: unchanged ")
            and target.read_bytes() == before_bytes
            and target.stat().st_mtime_ns == before_mtime,
            "unchanged config leaves file byte-identical",
        )

    # Missing .vscode directory.
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = Path(tmpdir)
        rc, _, err = _run(repo, {}, _slug_returns("t"))
        errors += _check(
            rc == 1
            and not (repo / ".vscode").exists()
            and len(err.strip().splitlines()) == 1
            and err.isascii(),
            "missing .vscode returns 1, writes nothing, one ASCII stderr line",
        )

    # Non-MarkerError marker failures.
    for label, exc in (("SystemExit", SystemExit(2)), ("RuntimeError", RuntimeError("wiki down"))):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            (repo / ".vscode").mkdir()
            rc, _, err = _run(repo, {}, _slug_raises(exc))
            errors += _check(
                rc == 1
                and not (repo / ".vscode" / "tasks.json").exists()
                and err.startswith("[mill-session-tasks]"),
                f"{label} from slug_from_branch returns 1 and writes nothing",
            )

    # Invalid configured model leaves an existing file untouched.
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = Path(tmpdir)
        (repo / ".vscode").mkdir()
        target = repo / ".vscode" / "tasks.json"
        _run(repo, {}, _slug_returns("t"))
        before = target.read_bytes()
        bad_cfg = {"spawn": {"sessions": {"go": {"model": "bad model;"}}}}
        rc, _, err = _run(repo, bad_cfg, _slug_returns("t"))
        errors += _check(
            rc == 1 and target.read_bytes() == before and err.startswith("[mill-session-tasks]"),
            "invalid model value returns 1 and leaves existing file untouched",
        )

    if errors:
        print(f"\n{errors} test(s) FAILED", file=sys.stderr)
        return 1
    print("All mill-session-tasks unit tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
