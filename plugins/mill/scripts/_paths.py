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
        wiki clone. Stub-aware: when a worktree carries a stub with
        ``hub_relative_path``, the ``paths.wiki:`` override is read from
        the real config at ``hub / .millhouse / config.local.yaml``; when
        no stub is present (or ``hub_relative_path == "."``) the stub itself
        is the real config. Falls back to ``resolve_path("wiki", main_root)``
        when no override is found. Does NOT check on-disk existence.

    resolve_main_worktree_root(git_root)
        Walk up from any worktree's ``git_root`` to the main worktree
        root using ``git rev-parse --git-common-dir``. From the main
        worktree the command returns ``".git"`` (relative); from a child
        worktree it returns the absolute path to the main worktree's
        ``.git`` directory. Both cases resolve to the main worktree root
        after ``.parent``. Raises ``SystemExit`` on non-zero exit.

    resolve_worktrees_dir(cfg, git_root)
        Return the worktrees container directory from config. When
        ``cfg["spawn"]["worktrees_dir"]`` is set, treat it as a
        ``<TOKEN>``-template and substitute path tokens derived from
        ``git_root`` (no slug — this returns the *container* dir, not a
        per-task subdir). Falls back to ``main_root.parent`` (the direct
        parent of the main worktree, which equals ``wts/`` in container-form).
        Prefix-form repos must set ``spawn.worktrees_dir:`` explicitly.

    resolve_container_path(git_root)
        Return the container directory for any worktree. In container-form
        (``main_root.parent.name == "wts"``) returns ``main_root.parent.parent``.
        In prefix-form returns ``main_root.parent``.

    resolve_hub_relative_path(worktree_root, hub_subpath)
        Translate the ``hub_relative_path`` value from
        ``.millhouse/config.local.yaml`` into an absolute path.
        ``"."`` returns ``worktree_root`` unchanged; any relative subpath
        returns ``worktree_root / hub_subpath`` (trailing slash normalised).
        Absolute values raise ``ValueError``.

    resolve_active_worktree(container_path, slug, *, cfg, git_root)
        Return the git checkout root for the active task with the given slug.
        Detection order: (1) in-place mode — when the current branch of
        ``git_root`` yields a slug (via ``_marker.slug_from_branch``) matching
        ``slug`` AND ``_inplace.is_inplace`` returns True, return ``git_root``;
        (2) worktree mode — when ``container_path / "wts" / slug`` exists and
        its current branch slug matches ``slug``, return that path.
        Raises ``ActiveWorktreeNotFound`` when neither mode applies.
        Raises ``ActiveWorktreeSlugMismatch`` when the worktree dir exists but
        its branch-derived slug differs.

    resolve_active_hub(container_path, slug, *, cfg, git_root)
        Return the hub directory (where ``.millhouse/`` and ``_mill/`` live)
        for the active task with the given slug. Calls
        ``resolve_active_worktree`` then resolves ``hub_relative_path`` with
        a two-tier lookup: (1) default from ``cfg.get("hub_relative_path",
        ".")``; (2) override from the resolved worktree's own
        ``.millhouse/config.local.yaml`` when it declares
        ``hub_relative_path:``. Propagates ``ActiveWorktreeNotFound`` and
        ``ActiveWorktreeSlugMismatch`` from the inner call.

    resolve_hub_path(cwd)
        Return the hub directory — assumes CC's cwd equals the hub when mill
        scripts run. Pass an explicit path for testing; omit for production use.

    status_path(worktree_root, cfg)
        Return the status.md path for ``worktree_root`` driven by
        ``cfg['paths']['status_md']``, with ``_mill/`` -> ``task/`` compat
        fallback via ``resolve_task_path``. Raises ``KeyError`` naming
        ``paths.status_md`` when the key is absent from ``cfg``.
"""
from __future__ import annotations

from pathlib import Path

import _subprocess_util
import _pygit2_util
from _sibling import resolve_path


__all__ = [
    "resolve_path",
    "resolve_git_root",
    "resolve_hub_path",
    "resolve_main_worktree_root",
    "resolve_wiki_path",
    "resolve_mill_config_path",
    "resolve_worktrees_dir",
    "resolve_short_name",
    "resolve_hub_relative_path",
    "resolve_active_worktree",
    "resolve_active_hub",
    "resolve_container_path",
    "ActiveWorktreeNotFound",
    "ActiveWorktreeSlugMismatch",
    "resolve_task_path",
    "status_path",
]


def resolve_git_root(start: Path | None = None) -> Path:
    """Return the git toplevel for ``start`` (default: current working directory)."""
    try:
        repo_root = _pygit2_util.discover_workdir(start)
    except _pygit2_util.GitOpsError as e:
        raise SystemExit(f"Not in a git repository: {e}")
    if repo_root.name == "wiki":
        raise SystemExit(
            f"cwd is inside wiki ({repo_root}) — scripts must run from a task worktree"
            " or the main repo, not the wiki. Wiki mutations go through"
            " git -C <wiki_path> or _wiki.write_commit_push."
        )
    try:
        wiki_path = resolve_wiki_path(repo_root)
    except (Exception, SystemExit):
        wiki_path = None
    if wiki_path is not None:
        try:
            same = repo_root.samefile(wiki_path)
        except OSError:
            same = repo_root.resolve() == wiki_path.resolve()
        if same:
            raise SystemExit(
                f"cwd is inside wiki ({wiki_path}) — scripts must run from a task worktree"
                " or the main repo, not the wiki. Wiki mutations go through"
                " git -C <wiki_path> or _wiki.write_commit_push."
            )
    return repo_root


def resolve_hub_path(cwd: Path | None = None) -> Path:
    """Return the hub directory — assumes CC's cwd equals the hub when mill scripts run."""
    return (cwd or Path.cwd()).resolve()


def resolve_main_worktree_root(git_root: Path) -> Path:
    """Return the main worktree root from any worktree (including main itself).

    Uses pygit2 to resolve the git common directory. From the main worktree
    this is the ``.git`` directory; from a child worktree it is the main
    worktree's ``.git`` directory. Both cases collapse to the main worktree
    root after ``.parent``.

    Args:
        git_root: Absolute path to any worktree's git checkout root.

    Returns:
        Absolute ``Path`` of the main worktree root.

    Raises:
        SystemExit: When unable to resolve the main worktree root.
    """
    try:
        return _pygit2_util.resolve_common_dir_parent(git_root)
    except _pygit2_util.GitOpsError as e:
        raise SystemExit(f"git rev-parse --git-common-dir failed for {git_root}: {e}")


def resolve_worktrees_dir(cfg: dict, git_root: Path) -> Path:
    """Return the worktrees container directory.

    When ``cfg["spawn"]["worktrees_dir"]`` is set explicitly, treat it as a
    ``<TOKEN>``-template and substitute path-level tokens derived from the
    main worktree root. The slug is intentionally absent — callers that need
    a per-task path append ``/ slug`` themselves.

    Falls back to ``main_root.parent`` (the direct parent of the main worktree)
    when the key is absent. In container-form this equals ``<container>/wts/``.
    Prefix-form repos must set ``spawn.worktrees_dir:`` explicitly — there is
    no automatic prefix-form fallback for the worktrees directory.

    Args:
        cfg: Deep-merged config dict (wiki config.yaml + config.local.yaml).
        git_root: Absolute path to any worktree git checkout root.

    Returns:
        Absolute ``Path`` of the worktrees container directory.
    """
    main_root = resolve_main_worktree_root(git_root)
    template = cfg.get("spawn", {}).get("worktrees_dir")
    if template is not None:
        import _junction

        container = (
            main_root.parent.parent if main_root.parent.name == "wts" else main_root.parent
        )
        tokens = {
            "HUB_PATH": str(main_root),
            "CWD_PATH": str(Path.cwd()),
            "CONTAINER_PATH": str(container),
            "REPO": main_root.name,
        }
        return Path(_junction.resolve_target(template, tokens))
    return main_root.parent


def resolve_container_path(git_root: Path) -> Path:
    """Return the container directory for any worktree.

    The canonical answer to "what is the container directory" for
    cross-worktree operations that need to resolve ``<container>/portals/``,
    ``<container>/wts/``, or ``<container>/wiki/``.

    In container-form (``main_root.parent.name == "wts"``) the container is
    the grandparent of the main worktree. In prefix-form the container is the
    direct parent of the main worktree.

    Args:
        git_root: Absolute path to any worktree's git checkout root.

    Returns:
        Absolute ``Path`` of the container directory.
    """
    main_root = resolve_main_worktree_root(git_root)
    if main_root.parent.name == "wts":
        return main_root.parent.parent
    return main_root.parent


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


def resolve_hub_relative_path(worktree_root: Path, hub_subpath: str) -> Path:
    """Return the hub directory path within a worktree.

    Translates the ``hub_relative_path`` value from ``.millhouse/config.local.yaml``
    into an absolute path. The caller reads the config; this function only performs
    path arithmetic.

    Args:
        worktree_root: Absolute path to the worktree's git checkout root.
        hub_subpath: Relative subpath from ``config.local.yaml`` ``hub_relative_path:``.
            Use ``"."`` when the hub is the worktree root itself (the typical case).
            Trailing slashes are normalised away.

    Returns:
        Absolute ``Path`` of the hub directory inside ``worktree_root``.

    Raises:
        ValueError: When ``hub_subpath`` is an absolute path.
    """
    sub = Path(hub_subpath)
    # Check for absolute paths. Path.is_absolute() handles Windows drive-letter paths
    # (e.g. "C:\foo"); the additional startswith("/") check catches Unix-rooted paths
    # on Windows where pathlib considers them only drive-relative.
    if sub.is_absolute() or hub_subpath.startswith("/"):
        raise ValueError(
            f"hub_subpath must be a relative path or '.', got: {hub_subpath!r}"
        )
    if str(sub) == ".":
        return worktree_root
    return worktree_root / sub


class ActiveWorktreeNotFound(RuntimeError):
    """Raised when the expected worktree directory does not exist."""


class ActiveWorktreeSlugMismatch(RuntimeError):
    """Raised when a worktree directory exists but its marker slug differs from the requested slug."""


def resolve_active_worktree(
    container_path: Path,
    slug: str,
    *,
    cfg: dict,
    git_root: Path,
) -> Path:
    """Return the git checkout root for the active task with the given slug.

    Detection order:
    1. In-place mode: when the current branch of ``git_root`` yields slug
       (via ``_marker.slug_from_branch``) matching ``slug`` AND
       ``_inplace.is_inplace`` returns True, return ``git_root``.
    2. Worktree mode: when ``container_path / "wts" / slug`` exists and its
       current branch-derived slug matches ``slug``, return that path.

    Raises:
        ActiveWorktreeNotFound: neither mode applies.
        ActiveWorktreeSlugMismatch: worktree-dir exists but branch-derived slug differs.
    """
    import _inplace
    import _marker

    try:
        _wiki = resolve_wiki_path(git_root)
        marker_slug = _marker.slug_from_branch(git_root, _wiki, cfg)
    except (_marker.MarkerError, SystemExit):
        marker_slug = None
    if marker_slug == slug and _inplace.is_inplace(slug, git_root, cfg):
        return git_root

    worktree = container_path / "wts" / slug
    if not worktree.is_dir():
        raise ActiveWorktreeNotFound(
            f"No worktree directory at {worktree} for slug {slug!r}"
        )
    branch_result = _subprocess_util.run(
        ["git", "-C", str(worktree), "branch", "--show-current"]
    )
    branch = branch_result.stdout.strip()
    dir_slug = branch.removeprefix(cfg.get("spawn", {}).get("branch_prefix", ""))
    if dir_slug != slug:
        raise ActiveWorktreeSlugMismatch(
            f"Worktree at {worktree} has slug {dir_slug!r}, expected {slug!r}"
        )
    return worktree


def resolve_active_hub(
    container_path: Path,
    slug: str,
    *,
    cfg: dict,
    git_root: Path,
) -> Path:
    """Return the hub directory (where ``.millhouse/`` and ``_mill/`` live) for the slug.

    Calls ``resolve_active_worktree`` then resolves ``hub_relative_path``.
    Resolution order:
    1. Default from the caller's cfg: ``cfg.get("hub_relative_path", ".")``.
    2. Override from the resolved worktree's own ``.millhouse/config.local.yaml``
       when that file exists and declares ``hub_relative_path:``.

    The two-tier resolution covers both cases:
    - In-place mode (mill-claim): mill-claim writes the stub only at the hub
      (``<git_root>/<hub_rel>/.millhouse/``), never at ``<git_root>/.millhouse/``.
      So the worktree-root stub is absent for M2+sub and the caller's cfg is the
      authoritative source.
    - Worktree mode (mill-spawn): mill-spawn bootstraps a stub at
      ``<wt>/.millhouse/config.local.yaml`` carrying ``hub_relative_path:`` so
      cross-worktree consumers (cleanup, status) that have no cfg about the
      target can still resolve correctly.

    Propagates ``ActiveWorktreeNotFound`` and ``ActiveWorktreeSlugMismatch``
    from the inner call.
    """
    import yaml

    wt = resolve_active_worktree(container_path, slug, cfg=cfg, git_root=git_root)
    hub_subpath = cfg.get("hub_relative_path", ".")
    stub_path = wt / ".millhouse" / "config.local.yaml"
    if stub_path.exists():
        try:
            stub_data = yaml.safe_load(stub_path.read_text(encoding="utf-8")) or {}
            stub_value = stub_data.get("hub_relative_path")
            if stub_value is not None:
                hub_subpath = stub_value
        except Exception:  # noqa: BLE001
            pass
    return resolve_hub_relative_path(wt, hub_subpath)


def resolve_wiki_path(git_toplevel: Path) -> Path:
    """Return the wiki clone path: local override first, sibling default second.

    Resolution order:
    1. ``<git-toplevel>/.millhouse/config.local.yaml`` ``paths.wiki:`` override.
       Absolute paths returned as-is; relative paths resolved against the
       main worktree root (not ``git_toplevel``, which may be a child worktree).
    2. ``resolve_path("wiki", main_root)`` — the sibling-path default.

    The local config read is stub-aware: when a worktree carries a stub with
    ``hub_relative_path``, the ``paths.wiki:`` override is read from the real
    config at ``hub / .millhouse / config.local.yaml``.

    The ``.millhouse/wiki`` junction is never consulted. Junctions are
    IDE/terminal convenience; the real wiki path is computed from the
    repo's own git-toplevel.
    """
    if Path(git_toplevel).name == "wiki":
        raise SystemExit(
            f"cwd is inside wiki ({git_toplevel}) — scripts must run from a task worktree"
            " or the main repo, not the wiki. Wiki mutations go through"
            " git -C <wiki_path> or _wiki.write_commit_push."
        )
    import yaml

    main_root = resolve_main_worktree_root(git_toplevel)

    stub_path = git_toplevel / ".millhouse" / "config.local.yaml"
    hub_subpath = "."
    stub_cfg: dict = {}
    if stub_path.exists():
        stub_cfg = yaml.safe_load(stub_path.read_text(encoding="utf-8")) or {}
        hub_subpath = stub_cfg.get("hub_relative_path", ".")

    hub = git_toplevel if hub_subpath == "." else git_toplevel / hub_subpath

    if hub != git_toplevel:
        real_cfg_path = hub / ".millhouse" / "config.local.yaml"
        if real_cfg_path.exists():
            cfg = yaml.safe_load(real_cfg_path.read_text(encoding="utf-8")) or {}
        else:
            cfg = {}
    else:
        cfg = stub_cfg

    paths = cfg.get("paths") or {}
    override = paths.get("wiki")
    if override:
        override_path = Path(override)
        if override_path.is_absolute():
            return override_path
        return (main_root / override_path).resolve()
    return resolve_path("wiki", main_root)


def resolve_mill_config_path(repo_root: Path) -> Path:
    """Return the hub-root mill-config.yaml path.

    Args:
        repo_root: Absolute path to the hub directory (worktree root or repo root).

    Returns:
        Absolute ``Path`` of the mill-config.yaml file.
    """
    return repo_root / "mill-config.yaml"


def resolve_task_path(worktree_root: Path, cfg_relative_path: str) -> Path:
    """Resolve config-relative path with _mill/->task/ fallback for in-flight worktrees."""
    target = worktree_root / cfg_relative_path
    if target.exists():
        if not (target.is_dir() and not any(target.iterdir())):
            return target
    if "_mill/" in cfg_relative_path:
        fallback_rel = cfg_relative_path.replace("_mill/", "task/", 1)
        fallback = worktree_root / fallback_rel
        if fallback.exists():
            import sys
            print(f"[compat] falling back to task/ for {cfg_relative_path!r}", file=sys.stderr)
            return fallback
    return target


def status_path(worktree_root: Path, cfg: dict) -> Path:
    """Return the status.md path for ``worktree_root`` driven by cfg['paths']['status_md'], with _mill/ -> task/ compat fallback via resolve_task_path."""
    _msg = "paths.status_md missing from cfg; expected key under cfg['paths']"
    if "paths" not in cfg:
        raise KeyError(_msg)
    if "status_md" not in cfg["paths"]:
        raise KeyError(_msg)
    return resolve_task_path(worktree_root, cfg["paths"]["status_md"])
