r"""
Scope-resolution for codeguide-update.

Scope-resolution chain
----------------------
1. **No-arg** (``args`` is empty): detect the parent branch via the
   three-step fallback below, then emit the union of ``<parent>..HEAD``
   (committed files) with the current diff (staged + unstaged).
2. **Time arg** (single token matching ``^\d+[hdw]$``, case-insensitive):
   use ``git log --since="N hour|day|week ago" --name-only --pretty=format:``
   and collect unique non-empty file paths.
3. **HEAD-rev arg** (single token starting with ``HEAD~``, matching
   ``^HEAD$``, or a 7–40 char hex SHA): use ``git diff --name-only
   <rev>..HEAD``.
4. **Explicit paths** (anything else): treat each token as a path, resolve
   relative to git toplevel, emit deduped absolute paths. No git invocation.

Parent detection
----------------
1. Try ``git symbolic-ref --short refs/remotes/origin/HEAD`` — strip the
   ``origin/`` prefix from the output (e.g. ``origin/main`` → ``main``).
2. On non-zero, try ``git rev-parse --verify origin/main`` → use ``main``.
3. On non-zero, try ``git rev-parse --verify origin/master`` → use ``master``.
4. On non-zero, ``base_branch = None``.

Public API
----------
CLI: ``python resolve_scope.py [<args>]``
    stdout  — newline-separated absolute paths (empty output is valid)
    stderr  — last non-empty line is a JSON summary
              ``{"mode", "parent", "base_branch", "included_committed",
                "included_diff"}``
    exit    — 0 unless not in a git repo

Function: ``enumerate_scope(args, cwd=None) -> (list[Path], dict)``
    ``args`` — the positional argument list (strings from ``$ARGUMENTS.split()``)
    ``cwd``  — working directory override for tests (defaults to ``os.getcwd()``)
    Returns  — ``(absolute_paths_deduped, summary_dict)``
"""

import argparse
import json
import os
import pathlib
import re
import subprocess
import sys

_TIME_RE = re.compile(r"^(\d+)([hdw])$", re.IGNORECASE)
_HEX_RE = re.compile(r"^[0-9a-f]{7,40}$", re.IGNORECASE)


def _git(toplevel: pathlib.Path, *args: str) -> tuple[int, str]:
    result = subprocess.run(
        ["git", "-C", str(toplevel), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.returncode, result.stdout


def _get_toplevel(cwd: pathlib.Path) -> pathlib.Path | None:
    result = subprocess.run(
        ["git", "-C", str(cwd), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if result.returncode != 0:
        return None
    return pathlib.Path(result.stdout.strip())


def _parse_paths(output: str, toplevel: pathlib.Path) -> list[pathlib.Path]:
    paths = []
    for line in output.splitlines():
        line = line.strip()
        if line:
            paths.append(toplevel / line)
    return paths


def _dedup(paths: list[pathlib.Path]) -> list[pathlib.Path]:
    seen: set[pathlib.Path] = set()
    result = []
    for p in paths:
        if p not in seen:
            seen.add(p)
            result.append(p)
    return result


def _detect_base_branch(toplevel: pathlib.Path) -> str | None:
    rc, out = _git(toplevel, "symbolic-ref", "--short", "refs/remotes/origin/HEAD")
    if rc == 0:
        name = out.strip()
        if name.startswith("origin/"):
            name = name[len("origin/"):]
        return name

    rc, _ = _git(toplevel, "rev-parse", "--verify", "origin/main")
    if rc == 0:
        return "main"

    rc, _ = _git(toplevel, "rev-parse", "--verify", "origin/master")
    if rc == 0:
        return "master"

    return None


def _no_arg_scope(toplevel: pathlib.Path) -> tuple[list[pathlib.Path], dict]:
    rc, out = _git(toplevel, "rev-parse", "--abbrev-ref", "HEAD")
    current_branch = out.strip() if rc == 0 else "HEAD"

    base_branch = _detect_base_branch(toplevel)
    parent: str | None = None
    committed: list[pathlib.Path] = []

    if base_branch is not None and current_branch != base_branch and current_branch != "HEAD":
        rc, out = _git(toplevel, "diff", "--name-only", f"{base_branch}..HEAD")
        if rc == 0:
            committed = _parse_paths(out, toplevel)
        parent = base_branch

    rc_u, out_u = _git(toplevel, "diff", "--name-only")
    unstaged = _parse_paths(out_u, toplevel) if rc_u == 0 else []

    rc_s, out_s = _git(toplevel, "diff", "--cached", "--name-only")
    staged = _parse_paths(out_s, toplevel) if rc_s == 0 else []

    diff_files = _dedup(unstaged + staged)
    paths = _dedup(committed + diff_files)

    summary = {
        "mode": "no-arg",
        "parent": parent,
        "base_branch": base_branch,
        "included_committed": len(committed),
        "included_diff": len(diff_files),
    }
    return paths, summary


def _time_scope(toplevel: pathlib.Path, token: str) -> tuple[list[pathlib.Path], dict]:
    m = _TIME_RE.match(token)
    n = m.group(1)
    unit = m.group(2).lower()
    unit_word = {"h": "hour", "d": "day", "w": "week"}[unit]
    since = f"{n} {unit_word} ago"
    rc, out = _git(toplevel, "log", f"--since={since}", "--name-only", "--pretty=format:")
    paths = _dedup(_parse_paths(out, toplevel)) if rc == 0 else []
    summary = {
        "mode": "time",
        "parent": None,
        "base_branch": None,
        "included_committed": len(paths),
        "included_diff": 0,
    }
    return paths, summary


def _head_rev_scope(toplevel: pathlib.Path, token: str) -> tuple[list[pathlib.Path], dict]:
    rc, out = _git(toplevel, "diff", "--name-only", f"{token}..HEAD")
    paths = _dedup(_parse_paths(out, toplevel)) if rc == 0 else []
    summary = {
        "mode": "head-rev",
        "parent": None,
        "base_branch": None,
        "included_committed": len(paths),
        "included_diff": 0,
    }
    return paths, summary


def _explicit_scope(toplevel: pathlib.Path, tokens: list[str]) -> tuple[list[pathlib.Path], dict]:
    paths = _dedup([toplevel / token for token in tokens])
    summary = {
        "mode": "explicit",
        "parent": None,
        "base_branch": None,
        "included_committed": 0,
        "included_diff": 0,
    }
    return paths, summary


def enumerate_scope(args: list[str], cwd: pathlib.Path | None = None) -> tuple[list[pathlib.Path], dict]:
    """Return (absolute_paths_deduped, summary_dict) for the given argument list."""
    cwd_path = pathlib.Path(cwd or os.getcwd()).resolve()
    toplevel = _get_toplevel(cwd_path)
    if toplevel is None:
        raise SystemExit("not in a git repository")

    if not args:
        return _no_arg_scope(toplevel)

    if len(args) == 1:
        token = args[0]
        if _TIME_RE.match(token):
            return _time_scope(toplevel, token)
        if token.startswith("HEAD~") or token == "HEAD" or _HEX_RE.match(token):
            return _head_rev_scope(toplevel, token)

    return _explicit_scope(toplevel, args)


def _cli(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="resolve_scope.py")
    parser.add_argument("args", nargs="*")
    parsed = parser.parse_args(argv[1:])

    try:
        paths, summary = enumerate_scope(parsed.args)
    except SystemExit as exc:
        if exc.args:
            print(str(exc.args[0]), file=sys.stderr)
        return 1

    for p in paths:
        print(p)
    print(json.dumps(summary), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv))
