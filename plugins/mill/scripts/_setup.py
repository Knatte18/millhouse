"""
Shared hub-link creation and wiki-setup helpers.

Creates junctions and hardlinks in a worktree by reading the ``junctions:``
and ``hardlinks:`` blocks from ``mill-config.yaml``. A token-scope filter
silently skips any entry whose target template references a token absent from
the supplied ``tokens`` dict — this lets the same helper serve mill-setup
(no ``<SLUG>`` token → ``<SLUG>``-bearing entries skipped) and mill-spawn
(``<SLUG>`` present → all entries created).

Public API:
    create_hub_links(target_root, wiki_path, tokens) -> dict[str, list[Path]]
        Create junctions and hardlinks from mill-config.yaml in target_root.
        Returns a dict with keys "junctions" and "hardlinks", each a list of
        created link_path values.

    clone_or_init(url, branch, dest) -> dict
        Clone, init-orphan, or pull an existing wiki clone at dest.
        Returns a status dict with "action" and "branch_existed_on_remote".
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import _junction
import _paths
import _subprocess_util
import _wiki

_TOKEN_RE = re.compile(r"<([A-Za-z][A-Za-z0-9_]*)>")


class WikiSetupError(Exception):
    """Raised by clone_or_init on unrecoverable clone/init/mismatch failure."""


class WikiPushError(RuntimeError):
    """Raised by clone_or_init when git pull fails."""


def clone_or_init(url: str, branch: str | None, dest: Path) -> dict:
    """Clone, init-orphan, or pull an existing wiki clone at dest.

    Four code paths:

    Path A — dest exists and dest/.git exists:
        Verifies origin URL matches url; if branch is not None, verifies
        current branch matches branch; then runs git pull --ff-only.
        Returns {"action": "pulled", "branch_existed_on_remote": None}.

    Path B — dest exists but dest/.git is missing:
        Raises WikiSetupError (dest is not a git repo).

    Path C — dest does not exist, branch is None:
        Runs git clone <url> <dest> (remote HEAD).
        Returns {"action": "cloned", "branch_existed_on_remote": None}.

    Path D — dest does not exist, branch is not None:
        Checks remote branch existence via git ls-remote --heads.
        Branch exists  → git clone -b <branch> --single-branch <url> <dest>.
                         Returns {"action": "cloned", "branch_existed_on_remote": True}.
        Branch missing → git init <dest>, git remote add origin <url>,
                         git checkout --orphan <branch>, git config
                         branch.<branch>.remote/merge so the first
                         write_commit_push pushes upstream-cleanly.
                         Returns {"action": "initialized", "branch_existed_on_remote": False}.

    This helper does NOT log or print — the caller shapes all user-facing messages.
    All subprocess calls go through _subprocess_util.run; argv lists are explicit.

    Args:
        url:    Remote wiki URL.
        branch: Branch name to pin, or None to use the remote default.
        dest:   Filesystem path where the wiki clone should live.

    Returns:
        dict with keys:
          "action": "cloned" | "pulled" | "initialized"
          "branch_existed_on_remote": True | False | None

    Raises:
        WikiSetupError: Unrecoverable clone/init/mismatch failure.
        WikiPushError:  git pull --ff-only failed on an existing repo (Path A).
    """
    if dest.exists():
        if not (dest / ".git").exists():
            raise WikiSetupError(
                f"{dest} exists but is not a git repository; move or remove it and re-run"
            )
        # Path A — existing git repo
        get_url = _subprocess_util.run(
            ["git", "-C", str(dest), "remote", "get-url", "origin"]
        )
        if get_url.returncode != 0:
            raise WikiSetupError(
                f"git -C {dest} remote get-url origin failed: {get_url.stderr}"
            )
        actual_url = get_url.stdout.strip()
        if actual_url != url:
            raise WikiSetupError(
                f"wiki at {dest} has origin {actual_url!r}, expected {url!r};"
                " remove or fix the wiki dir manually"
            )
        if branch is not None:
            show = _subprocess_util.run(
                ["git", "-C", str(dest), "branch", "--show-current"]
            )
            if show.returncode != 0:
                raise WikiSetupError(
                    f"git -C {dest} branch --show-current failed: {show.stderr}"
                )
            actual_branch = show.stdout.strip()
            if actual_branch != branch:
                raise WikiSetupError(
                    f"wiki at {dest} is on branch {actual_branch!r}, expected {branch!r};"
                    " remove or fix the wiki dir manually"
                )
        pull = _subprocess_util.run(
            ["git", "-C", str(dest), "pull", "--ff-only"]
        )
        if pull.returncode != 0:
            raise WikiPushError(f"git pull --ff-only failed: {pull.stderr}")
        return {"action": "pulled", "branch_existed_on_remote": None}

    # dest does not exist
    if branch is None:
        # Path C — clone without branch
        result = _subprocess_util.run(["git", "clone", url, str(dest)])
        if result.returncode != 0:
            raise WikiSetupError(
                f"git clone {url} {dest} failed: {result.stderr}"
            )
        return {"action": "cloned", "branch_existed_on_remote": None}

    # Path D — dest missing, branch specified
    ls = _subprocess_util.run(["git", "ls-remote", "--heads", url, branch])
    if ls.returncode != 0:
        raise WikiSetupError(
            f"git ls-remote --heads {url} {branch} failed: {ls.stderr}"
        )
    if ls.stdout.strip():
        # branch exists on remote
        result = _subprocess_util.run(
            ["git", "clone", "-b", branch, "--single-branch", url, str(dest)]
        )
        if result.returncode != 0:
            raise WikiSetupError(
                f"git clone -b {branch} --single-branch {url} {dest} failed: {result.stderr}"
            )
        return {"action": "cloned", "branch_existed_on_remote": True}

    # branch missing — init orphan
    init = _subprocess_util.run(["git", "init", str(dest)])
    if init.returncode != 0:
        raise WikiSetupError(f"git init {dest} failed: {init.stderr}")

    remote = _subprocess_util.run(
        ["git", "-C", str(dest), "remote", "add", "origin", url]
    )
    if remote.returncode != 0:
        raise WikiSetupError(
            f"git -C {dest} remote add origin {url} failed: {remote.stderr}"
        )

    orphan = _subprocess_util.run(
        ["git", "-C", str(dest), "checkout", "--orphan", branch]
    )
    if orphan.returncode != 0:
        raise WikiSetupError(
            f"git -C {dest} checkout --orphan {branch} failed: {orphan.stderr}"
        )

    cfg_remote = _subprocess_util.run(
        ["git", "-C", str(dest), "config", f"branch.{branch}.remote", "origin"]
    )
    if cfg_remote.returncode != 0:
        raise WikiSetupError(
            f"git -C {dest} config branch.{branch}.remote failed: {cfg_remote.stderr}"
        )

    cfg_merge = _subprocess_util.run(
        ["git", "-C", str(dest), "config", f"branch.{branch}.merge", f"refs/heads/{branch}"]
    )
    if cfg_merge.returncode != 0:
        raise WikiSetupError(
            f"git -C {dest} config branch.{branch}.merge failed: {cfg_merge.stderr}"
        )

    return {"action": "initialized", "branch_existed_on_remote": False}


def _required_tokens(template: str) -> list[str]:
    """Return the list of all token names referenced in *template*."""
    return [m.group(1) for m in _TOKEN_RE.finditer(template)]


def create_hub_links(
    target_root: Path,
    wiki_path: Path,
    tokens: dict[str, str],
) -> dict[str, list[Path]]:
    """Create junctions and hardlinks from wiki/config.yaml in *target_root*.

    Iterates both the ``junctions:`` and ``hardlinks:`` blocks from
    ``wiki/config.yaml``. For each entry:

    * Scans the target template for ``<TOKEN>`` references.
    * Intersects with the supplied *tokens* dict.
    * Silently **skips** the entry if any required token is absent (token-scope
      filter). This is how mill-setup (no ``SLUG``) and mill-spawn (``SLUG``
      present) share one helper without separate config blocks.

    Junction creation:
        Calls ``_junction.resolve_target`` then ``_junction.create``. Ensures
        the resolved target directory exists first when the template carries
        ``<SLUG>`` (mimics the pre-existing mill-spawn behaviour). The strict
        ``ValueError`` from ``_junction.resolve_target`` on unknown tokens is
        preserved — filtering happens before the call so unknown tokens still
        raise.

    Hardlink creation (idempotent):
        * *link_path* absent → create directly via ``Path.hardlink_to``.
        * *link_path* present, inode matches target → skip (already correct).
        * *link_path* present, inode differs → back up to ``<name>.bak``,
          remove original, then create via ``Path.hardlink_to``.

    Args:
        target_root: Directory where junctions and hardlinks are created.
            Relative paths in the config are resolved against this root.
        wiki_path: Path to the wiki clone used to read ``config.yaml``.
        tokens: Token map passed to ``_junction.resolve_target``. Keys are
            token names (e.g. ``"HUB_PATH"``, ``"SLUG"``); values are
            concrete strings.

    Returns:
        ``{"junctions": [link_path, ...], "hardlinks": [link_path, ...]}``
        listing every link that was created or updated (skipped entries are
        not included).

    Raises:
        ValueError: Cross-volume hardlink failure (OSError re-raised with
            source and target paths named); or ``_junction.resolve_target``
            finding an unknown token after filtering (logic error in caller).
    """
    hub_root = target_root
    junctions_cfg = _wiki.read_junctions(hub_root, wiki_path=wiki_path)
    hardlinks_cfg = _wiki.read_hardlinks(hub_root, wiki_path=wiki_path)

    created_junctions: list[Path] = []
    created_hardlinks: list[Path] = []

    # ---------------------------------------------------------------------- #
    # Junctions                                                                #
    # ---------------------------------------------------------------------- #
    for junction_rel, target_template in junctions_cfg.items():
        required = _required_tokens(target_template)
        if any(tok not in tokens for tok in required):
            continue  # token-scope filter: skip when a required token is absent

        target = Path(_junction.resolve_target(target_template, tokens))
        link_path = target_root / junction_rel

        if _junction.has_slug_token(target_template):
            target.mkdir(parents=True, exist_ok=True)

        # Idempotency: skip on correct, recreate on drift, refuse on real directory.
        # Use os.path.lexists (does NOT follow links) so a broken NTFS junction —
        # whose target was deleted, making Path.exists() return False because it
        # follows the junction to a missing target, and Path.is_symlink() return
        # False because junctions are not Python symlinks — is still recognised
        # as present and routed through the drift branch. Mirrors the
        # lexists-based guard in _junction._is_junction_or_symlink.
        if os.path.lexists(str(link_path)):
            if _junction.points_to(link_path, target):
                continue
            # Drift: junction points elsewhere, is broken, or link_path is a
            # regular file/dir. _junction.remove raises ValueError on a real
            # directory — propagate unchanged.
            _junction.remove(link_path)

        _junction.create(target, link_path)
        created_junctions.append(link_path)
        print(f"[setup] junction created: {link_path} -> {target}", file=sys.stderr)

    # ---------------------------------------------------------------------- #
    # Hardlinks                                                                #
    # ---------------------------------------------------------------------- #
    for link_rel, target_template in hardlinks_cfg.items():
        required = _required_tokens(target_template)
        if any(tok not in tokens for tok in required):
            continue  # token-scope filter

        target = Path(_junction.resolve_target(target_template, tokens))
        link_path = target_root / link_rel

        if not link_path.exists() and not link_path.is_symlink():
            # First-run: no prior file at link_path — create directly.
            link_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                link_path.hardlink_to(target)
            except OSError as exc:
                raise ValueError(
                    f"Failed to create hardlink {link_path!r} -> {target!r}: {exc}"
                ) from exc
        else:
            # Inode equality check: skip when already the correct hardlink.
            link_inode = link_path.stat().st_ino
            try:
                target_inode = target.stat().st_ino
            except OSError:
                target_inode = None

            if target_inode is not None and link_inode == target_inode:
                continue  # already correct — idempotent skip

            # Inode mismatch: back up to <name>.bak and recreate.
            backup = link_path.parent / (link_path.name + ".bak")
            if backup.exists():
                backup.unlink()
            link_path.rename(backup)
            try:
                link_path.hardlink_to(target)
            except OSError as exc:
                raise ValueError(
                    f"Failed to create hardlink {link_path!r} -> {target!r}: {exc}"
                ) from exc

        created_hardlinks.append(link_path)
        print(f"[setup] hardlink created: {link_path} -> {target}", file=sys.stderr)

    return {"junctions": created_junctions, "hardlinks": created_hardlinks}
