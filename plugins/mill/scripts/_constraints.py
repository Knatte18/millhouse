"""
Read ``CONSTRAINTS.md`` from the hub root, if present.

Some projects ship a top-level ``CONSTRAINTS.md`` listing invariants the
implementer must respect (e.g. "touch no files under ``vendored/``"). The
review pipeline and ``mill-start`` both want to inject that content into
prompts when it exists. Centralising the "find hub root + read file"
dance in one helper avoids divergent implementations.

Hub-root resolution uses ``git rev-parse --show-toplevel`` so the helper
works from any subfolder of the hub. Scripts invoked deep inside
``plugins/mill/scripts/`` get the same answer as scripts run from the
top level.

Public API:
    read_if_exists(cwd=None) -> str | None
        Return the text of ``<hub-root>/CONSTRAINTS.md`` or ``None``.
"""
from __future__ import annotations

from pathlib import Path

import _subprocess_util


def _hub_root(cwd: Path | None) -> Path | None:
    """Return the git toplevel of ``cwd`` (defaults to current working dir)."""
    args = ["git", "rev-parse", "--show-toplevel"]
    kwargs: dict = {}
    if cwd is not None:
        kwargs["cwd"] = str(cwd)
    result = _subprocess_util.run(args, **kwargs)
    if result.returncode != 0:
        return None
    return Path(result.stdout.strip())


def read_if_exists(cwd: Path | None = None) -> str | None:
    """
    Return the contents of ``CONSTRAINTS.md`` at the hub root, or None.

    ``cwd`` is the directory from which ``git rev-parse --show-toplevel``
    is run — defaults to the current working directory. Passing an
    explicit ``cwd`` is useful for tests that want to point at a scratch
    hub without chdir'ing the calling process.

    Args:
        cwd: Directory from which to resolve the git toplevel. If the
            directory is outside any git repo, returns ``None``.

    Returns:
        The file contents as a string, or ``None`` when either the
        directory isn't inside a git repo or ``CONSTRAINTS.md`` does not
        exist at its toplevel. Callers that want to distinguish "no
        repo" from "no file" should call ``_hub_root`` directly.
    """
    root = _hub_root(cwd)
    if root is None:
        return None
    path = root / "CONSTRAINTS.md"
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


if __name__ == "__main__":
    import tempfile
    import os

    # No CONSTRAINTS.md in a freshly-inited repo → None.
    with tempfile.TemporaryDirectory() as tmp:
        _subprocess_util.run(["git", "init", tmp, "-b", "main"])
        assert read_if_exists(Path(tmp)) is None
        print("PASS: read_if_exists returns None when CONSTRAINTS.md absent")

        (Path(tmp) / "CONSTRAINTS.md").write_text("hello\n", encoding="utf-8")
        assert read_if_exists(Path(tmp)) == "hello\n"
        print("PASS: read_if_exists returns file contents when present")

        # From a subfolder — exercises the subfolder-friendly resolution.
        sub = Path(tmp) / "sub" / "deeper"
        sub.mkdir(parents=True)
        assert read_if_exists(sub) == "hello\n"
        print("PASS: read_if_exists resolves from a subfolder")

    # Not inside a git repo at all → None.
    with tempfile.TemporaryDirectory() as tmp:
        # Make sure we're truly not inside any git repo: on Windows the
        # system temp dir can inherit parent git state; explicitly create
        # one that isn't a git repo.
        non_repo = Path(tmp)
        assert read_if_exists(non_repo) is None
        print("PASS: read_if_exists returns None outside a git repo")

    print("All _constraints smoke tests passed.")
