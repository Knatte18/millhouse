"""
Single home for path resolution in the mill plugin.

Collects helpers that turn (git context, config) into concrete paths.
Scripts MUST use these helpers instead of reaching for ``.millhouse/wiki``
or other junctions directly — junctions are IDE/terminal convenience, not
a code contract. See CLAUDE.md ``## Path invariants``.

Public API:
    resolve_path(role, repo_root)
        Re-exported from ``_sibling`` — canonical (role, repo_root) →
        sibling directory. Hub-form vs prefix-form detection lives there.

    resolve_git_root()
        Thin wrapper around ``git rev-parse --show-toplevel``. Raises
        ``SystemExit`` with a user-facing message on non-zero exit.

    resolve_wiki_path(git_toplevel)
        Local-override-first, sibling-default-second resolution for the
        wiki clone. Reads ``.millhouse/config.local.yaml`` ``paths.wiki:``
        at ``<git-toplevel>`` if present; otherwise delegates to
        ``resolve_path("wiki", git_toplevel)``. Does NOT check on-disk
        existence — callers that need the path to exist surface their
        own error (mill-setup's Phase 3 is the one that creates it).

    resolve_worktrees_dir(cfg, git_root)
        Return the worktrees container directory from config. When
        ``cfg["spawn"]["worktrees_dir"]`` is set, treat it as a
        ``<TOKEN>``-template and substitute path tokens derived from
        ``git_root`` (no slug — this returns the *container* dir, not a
        per-task subdir). Falls back to ``resolve_path("worktrees",
        git_root)`` when the key is absent.
"""
from __future__ import annotations

from pathlib import Path

import _subprocess_util
from _sibling import resolve_path


__all__ = ["resolve_path", "resolve_git_root", "resolve_wiki_path", "resolve_worktrees_dir", "resolve_short_name"]


def resolve_git_root() -> Path:
    """Return the git toplevel of the current working directory."""
    result = _subprocess_util.run(["git", "rev-parse", "--show-toplevel"])
    if result.returncode != 0:
        raise SystemExit(f"Not in a git repository: {result.stderr.strip()!r}")
    return Path(result.stdout.strip())


def resolve_worktrees_dir(cfg: dict, git_root: Path) -> Path:
    """Return the worktrees container directory.

    When ``cfg["spawn"]["worktrees_dir"]`` is set explicitly, treat it as a
    ``<TOKEN>``-template and substitute path-level tokens derived from
    ``git_root``. The slug is intentionally absent — callers that need a
    per-task path append ``/ slug`` themselves. Falls back to
    ``resolve_path("worktrees", git_root)`` when the key is absent.

    Args:
        cfg: Deep-merged config dict (wiki config.yaml + config.local.yaml).
        git_root: Absolute path to the hub git checkout.

    Returns:
        Absolute ``Path`` of the worktrees container directory.
    """
    template = cfg.get("spawn", {}).get("worktrees_dir")
    if template is not None:
        import _junction

        tokens = {
            "HUB_PATH": str(git_root),
            "CWD_PATH": str(Path.cwd()),
            "CONTAINER_PATH": str(git_root.parent),
            "REPO": git_root.name,
        }
        return Path(_junction.resolve_target(template, tokens))
    return resolve_path("worktrees", git_root)


def resolve_short_name(cfg: dict, repo_name: str) -> str:
    """Return the repository short name from config or derive a default.

    Returns ``cfg["repo"]["short_name"]`` when set to a non-empty string.
    Falls back to ``repo_name[:2].upper()`` when the ``repo:`` block is
    absent, ``short_name`` key is missing, or the value is an empty string.

    Args:
        cfg: Deep-merged config dict (wiki config.yaml + config.local.yaml).
        repo_name: Repository directory name (e.g. ``"millhouse"``).

    Returns:
        Short name string (e.g. ``"MH"``).
    """
    short = cfg.get("repo", {}).get("short_name", "")
    if short:
        return short
    return repo_name[:2].upper() if len(repo_name) >= 2 else repo_name.upper()


def resolve_wiki_path(git_toplevel: Path) -> Path:
    """Return the wiki clone path: local override first, sibling default second.

    Resolution order:
    1. ``<git-toplevel>/.millhouse/config.local.yaml`` ``paths.wiki:`` override.
       Absolute paths returned as-is; relative paths resolved against
       ``git_toplevel``.
    2. ``resolve_path("wiki", git_toplevel)`` — the sibling-path default.

    The ``.millhouse/wiki`` junction is never consulted. Junctions are
    IDE/terminal convenience; the real wiki path is computed from the
    repo's own git-toplevel.
    """
    local_cfg = git_toplevel / ".millhouse" / "config.local.yaml"
    if local_cfg.exists():
        import yaml

        cfg = yaml.safe_load(local_cfg.read_text(encoding="utf-8")) or {}
        paths = cfg.get("paths") or {}
        override = paths.get("wiki")
        if override:
            override_path = Path(override)
            if override_path.is_absolute():
                return override_path
            return (git_toplevel / override_path).resolve()
    return resolve_path("wiki", git_toplevel)
