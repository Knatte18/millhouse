r"""
Scope-resolution for codeguide-update.

Scope-resolution chain
----------------------
1. **No-arg** (``args`` is empty): detect the parent branch via the
   three-step fallback below (optionally overridden by ``--parent``/``parent=``),
   then emit the union of ``<parent>..HEAD`` (committed files) with the
   current diff (staged + unstaged).
2. **Time arg** (single token matching ``^\d+[hdw]$``, case-insensitive):
   use ``git log --since="N hour|day|week ago" --name-only --pretty=format:``
   and collect unique non-empty file paths.
3. **Single-token ref arg**: any single token that resolves as a git ref via
   ``git rev-parse --verify --quiet <token>^{commit}`` (a literal trailing
   ``..HEAD`` suffix is stripped before the check) uses ``git diff
   --name-only <resolved>..HEAD``. This subsumes hex SHAs, ``HEAD``,
   ``HEAD~N``, and branch/tag names.
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
CLI: ``python resolve_scope.py [--parent <ref>] [<args>]``
    stdout  — newline-separated absolute paths (empty output is valid)
    stderr  — last non-empty line is a JSON summary
              ``{"mode", "parent", "base_branch", "included_committed",
                "included_diff"}``
    exit    — 0 unless not in a git repo

Function: ``enumerate_scope(args, cwd=None, parent=None) -> (list[Path], dict)``
    ``args``   — the positional argument list (strings from ``$ARGUMENTS.split()``)
    ``cwd``    — working directory override for tests (defaults to ``os.getcwd()``)
    ``parent`` — optional base-branch override consulted only in no-arg mode;
                 falls back to git-native detection when it doesn't resolve
    Returns    — ``(absolute_paths_deduped, summary_dict)``
"""

import argparse
import json
import os
import pathlib
import re
import subprocess
import sys

_TIME_RE = re.compile(r"^(\d+)([hdw])$", re.IGNORECASE)


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


def _ref_resolves(toplevel: pathlib.Path, ref: str) -> bool:
    """
    Check whether a git reference resolves to a commit.

    Uses `git rev-parse --verify --quiet <ref>^{commit}` to determine
    if the ref can be resolved locally.

    Args:
        toplevel: The git repository root.
        ref: The reference string to check (can include ranges, branch names, SHAs, etc.).

    Returns:
        True if the ref resolves to a commit, False otherwise.
    """
    rc, _ = _git(toplevel, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")
    return rc == 0


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


def _no_arg_scope(toplevel: pathlib.Path, parent: str | None = None) -> tuple[list[pathlib.Path], dict]:
    rc, out = _git(toplevel, "rev-parse", "--abbrev-ref", "HEAD")
    current_branch = out.strip() if rc == 0 else "HEAD"

    # An explicit --parent override takes precedence over git-native detection,
    # but only when it actually resolves -- a stale/deleted parent ref falls
    # through to the origin/HEAD -> origin/main -> origin/master chain exactly
    # as if --parent had never been supplied.
    base_branch: str | None = None
    if parent is not None and _ref_resolves(toplevel, parent):
        base_branch = parent
    if base_branch is None:
        base_branch = _detect_base_branch(toplevel)

    resolved_parent: str | None = None
    committed: list[pathlib.Path] = []

    if base_branch is not None and current_branch != base_branch and current_branch != "HEAD":
        rc, out = _git(toplevel, "diff", "--name-only", f"{base_branch}..HEAD")
        if rc == 0:
            committed = _parse_paths(out, toplevel)
        resolved_parent = base_branch

    rc_u, out_u = _git(toplevel, "diff", "--name-only")
    unstaged = _parse_paths(out_u, toplevel) if rc_u == 0 else []

    rc_s, out_s = _git(toplevel, "diff", "--cached", "--name-only")
    staged = _parse_paths(out_s, toplevel) if rc_s == 0 else []

    diff_files = _dedup(unstaged + staged)
    paths = _dedup(committed + diff_files)

    summary = {
        "mode": "no-arg",
        "parent": resolved_parent,
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


def _resolve_ref_token(toplevel: pathlib.Path, token: str) -> str | None:
    """
    Determine whether a single scope-arg token names a git-resolvable ref.

    Strips a literal trailing ``..HEAD`` suffix (the shape mill-merge-in's
    checkpoint range produces) before checking, since git itself cannot
    resolve ``<ref>..HEAD`` as a single commit-ish. Any other token
    containing ``..`` (a genuine range) is passed through unstripped — it
    will simply fail the rev-parse check below, per the "literal ..HEAD
    suffix stripping only" design decision.

    Returns:
        The candidate ref string (with the ``..HEAD`` suffix already
        stripped, if present) when it resolves to a commit, else None.
    """
    suffix = "..HEAD"
    candidate = token[: -len(suffix)] if token.endswith(suffix) else token
    return candidate if _ref_resolves(toplevel, candidate) else None


def enumerate_scope(
    args: list[str], cwd: pathlib.Path | None = None, parent: str | None = None
) -> tuple[list[pathlib.Path], dict]:
    """Return (absolute_paths_deduped, summary_dict) for the given argument list."""
    cwd_path = pathlib.Path(cwd or os.getcwd()).resolve()
    toplevel = _get_toplevel(cwd_path)
    if toplevel is None:
        raise SystemExit("not in a git repository")

    if not args:
        return _no_arg_scope(toplevel, parent=parent)

    if len(args) == 1:
        token = args[0]
        # Time-form tokens (3d, 1h, ...) must never attempt ref resolution --
        # a token like "1h" could theoretically collide with a branch name,
        # so the time check stays first and short-circuits ref dispatch.
        if _TIME_RE.match(token):
            return _time_scope(toplevel, token)
        # Any token that git itself can resolve as a commit-ish (hex SHA,
        # HEAD, HEAD~N, or a plain branch/tag name, with an optional literal
        # ..HEAD suffix stripped first) routes through the head-rev path.
        resolved = _resolve_ref_token(toplevel, token)
        if resolved is not None:
            return _head_rev_scope(toplevel, resolved)

    return _explicit_scope(toplevel, args)


def _cli(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="resolve_scope.py")
    parser.add_argument("--parent", default=None)
    parser.add_argument("args", nargs="*")
    parsed = parser.parse_args(argv[1:])

    try:
        paths, summary = enumerate_scope(parsed.args, parent=parsed.parent)
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
