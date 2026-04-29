"""Unit tests for plugins/mill/scripts/_setup.py.

Uses tempfile.TemporaryDirectory() and real disk operations for all
happy-path cases. A single selective mock covers the cross-volume hardlink
error path which cannot be triggered without multiple filesystem volumes.

Covers:
  - Token-scope filter: no <SLUG> in tokens → .active entry skipped
  - Mixed slug+non-slug entries: all entries created when SLUG present
  - Hardlink inode skip (idempotent re-run)
  - Hardlink inode-mismatch → backup-and-recreate
  - Both empty config blocks → empty result lists
  - Cross-volume hardlink → ValueError with clear source/target in message
  - Portal-flow integration (Card 8):
      - .millhouse/wiki junction resolves to fixture wiki path
      - .others junction resolves to fixture portals dir
      - .active junction resolves to portals/<slug> junction
      - tasks.md hardlink shares an inode with wiki/Home.md
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import yaml

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

from _setup import create_hub_links  # noqa: E402


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _write_wiki_config(wiki_path: Path, cfg: dict) -> None:
    """Write cfg as YAML to wiki_path/config.yaml."""
    (wiki_path / "config.yaml").write_text(
        yaml.dump(cfg, default_flow_style=False), encoding="utf-8"
    )


def _make_minimal_wiki(wiki_path: Path, cfg: dict) -> None:
    """Create wiki_path with Home.md and config.yaml containing cfg."""
    wiki_path.mkdir(parents=True, exist_ok=True)
    (wiki_path / "Home.md").write_text("# Home\n", encoding="utf-8")
    _write_wiki_config(wiki_path, cfg)


# Config with the full new junctions block + one hardlink (used by most tests)
_FULL_CFG = {
    "junctions": {
        ".millhouse/wiki": "<WIKI_PATH>",
        ".others": "<CONTAINER_PATH>/portals/",
        ".active": "<CONTAINER_PATH>/portals/<SLUG>/",
    },
    "hardlinks": {
        "tasks.md": "<WIKI_PATH>/Home.md",
    },
}

# Config where every entry requires <SLUG> — used to test that ALL entries
# are filtered when SLUG is absent, yielding empty result lists.
_ALL_SLUG_CFG = {
    "junctions": {
        ".active": "<CONTAINER_PATH>/portals/<SLUG>/",
    },
    "hardlinks": {
        "task-status.md": "<WIKI_PATH>/active/<SLUG>/status.md",
    },
}

# Config with only a SLUG-requiring junction + a SLUG-free hardlink — used to
# test hardlink idempotency without also testing junction creation on a second
# call (which would fail because the junction already exists).
_HARDLINK_ONLY_CFG = {
    "junctions": {
        ".active": "<CONTAINER_PATH>/portals/<SLUG>/",  # filtered: needs SLUG
    },
    "hardlinks": {
        "tasks.md": "<WIKI_PATH>/Home.md",
    },
}


# ---------------------------------------------------------------------------
# Token-scope filter: no <SLUG> → .active skipped
# ---------------------------------------------------------------------------


def test_token_scope_filter_no_slug() -> None:
    """When SLUG is absent from tokens, entries requiring <SLUG> are skipped."""
    with tempfile.TemporaryDirectory() as tmp:
        container = Path(tmp) / "container"
        wiki_path = container / "wiki"
        portals = container / "portals"
        target_root = container / "wts" / "my-repo"

        _make_minimal_wiki(wiki_path, _FULL_CFG)
        portals.mkdir(parents=True)
        target_root.mkdir(parents=True)

        tokens = {
            "HUB_PATH": str(target_root),
            "CWD_PATH": str(target_root),
            "CONTAINER_PATH": str(container),
            "WIKI_PATH": str(wiki_path),
            "REPO": "my-repo",
            # deliberately omit SLUG
        }

        result = create_hub_links(target_root, wiki_path, tokens)

        # .millhouse/wiki and .others must be created
        wiki_link = target_root / ".millhouse" / "wiki"
        others_link = target_root / ".others"
        if not (wiki_link.exists() or wiki_link.is_symlink()):
            raise AssertionError(f".millhouse/wiki junction not created at {wiki_link}")
        if not (others_link.exists() or others_link.is_symlink()):
            raise AssertionError(f".others junction not created at {others_link}")

        # .active must NOT be created (requires SLUG)
        active_link = target_root / ".active"
        if active_link.exists() or active_link.is_symlink():
            raise AssertionError(".active should be skipped when SLUG absent")

        # Return value: 2 junctions, 1 hardlink (tasks.md)
        if len(result["junctions"]) != 2:
            raise AssertionError(
                f"expected 2 junctions created, got {len(result['junctions'])}: "
                f"{result['junctions']}"
            )
        if len(result["hardlinks"]) != 1:
            raise AssertionError(
                f"expected 1 hardlink created, got {len(result['hardlinks'])}: "
                f"{result['hardlinks']}"
            )

    print("PASS: token-scope filter skips .active when SLUG absent")


# ---------------------------------------------------------------------------
# Mixed slug+non-slug entries: all created when SLUG present
# ---------------------------------------------------------------------------


def test_token_scope_filter_with_slug() -> None:
    """When SLUG is present, all three junctions and the hardlink are created."""
    with tempfile.TemporaryDirectory() as tmp:
        container = Path(tmp) / "container"
        wiki_path = container / "wiki"
        portals = container / "portals"
        target_root = container / "wts" / "my-task"

        _make_minimal_wiki(wiki_path, _FULL_CFG)
        portals.mkdir(parents=True)
        target_root.mkdir(parents=True)

        tokens = {
            "HUB_PATH": str(target_root),
            "CWD_PATH": str(target_root),
            "CONTAINER_PATH": str(container),
            "WIKI_PATH": str(wiki_path),
            "REPO": "my-repo",
            "SLUG": "my-task",
        }

        result = create_hub_links(target_root, wiki_path, tokens)

        wiki_link = target_root / ".millhouse" / "wiki"
        others_link = target_root / ".others"
        active_link = target_root / ".active"

        if not (wiki_link.exists() or wiki_link.is_symlink()):
            raise AssertionError(f".millhouse/wiki not created at {wiki_link}")
        if not (others_link.exists() or others_link.is_symlink()):
            raise AssertionError(f".others not created at {others_link}")
        if not (active_link.exists() or active_link.is_symlink()):
            raise AssertionError(f".active not created at {active_link}")

        tasks_md = target_root / "tasks.md"
        if not tasks_md.exists():
            raise AssertionError(f"tasks.md hardlink not created at {tasks_md}")

        if len(result["junctions"]) != 3:
            raise AssertionError(
                f"expected 3 junctions, got {len(result['junctions'])}: "
                f"{result['junctions']}"
            )
        if len(result["hardlinks"]) != 1:
            raise AssertionError(
                f"expected 1 hardlink, got {len(result['hardlinks'])}: "
                f"{result['hardlinks']}"
            )

    print("PASS: all 3 junctions and 1 hardlink created when SLUG present")


# ---------------------------------------------------------------------------
# Hardlink inode skip (idempotent re-run)
# ---------------------------------------------------------------------------


def test_hardlink_inode_skip_idempotent() -> None:
    """Second call with same target/link is a no-op (returns empty hardlinks).

    Uses _HARDLINK_ONLY_CFG whose junction entry requires <SLUG> (so it is
    filtered when SLUG absent). Only the hardlink is created on the first call.
    The second call finds matching inodes and skips.
    """
    with tempfile.TemporaryDirectory() as tmp:
        container = Path(tmp) / "container"
        wiki_path = container / "wiki"
        target_root = container / "wts" / "my-repo"

        _make_minimal_wiki(wiki_path, _HARDLINK_ONLY_CFG)
        target_root.mkdir(parents=True)

        tokens = {
            "HUB_PATH": str(target_root),
            "CWD_PATH": str(target_root),
            "CONTAINER_PATH": str(container),
            "WIKI_PATH": str(wiki_path),
            "REPO": "my-repo",
            # deliberately omit SLUG → junction entry is filtered
        }

        # First call: junction filtered → 0 junctions; hardlink created → 1
        result1 = create_hub_links(target_root, wiki_path, tokens)
        if len(result1["junctions"]) != 0:
            raise AssertionError(f"first call: expected 0 junctions, got {result1['junctions']}")
        if len(result1["hardlinks"]) != 1:
            raise AssertionError(f"first call: expected 1 hardlink, got {result1['hardlinks']}")

        tasks_md = target_root / "tasks.md"
        inode_first = tasks_md.stat().st_ino

        # Second call: hardlink inode matches → skipped
        result2 = create_hub_links(target_root, wiki_path, tokens)
        if len(result2["hardlinks"]) != 0:
            raise AssertionError(
                f"second call should skip hardlink (same inode), got {result2['hardlinks']}"
            )

        # File still there with same inode.
        if tasks_md.stat().st_ino != inode_first:
            raise AssertionError("hardlink inode changed after idempotent re-run")

    print("PASS: hardlink idempotent re-run is a no-op (inode unchanged)")


# ---------------------------------------------------------------------------
# Hardlink inode mismatch → backup-and-recreate
# ---------------------------------------------------------------------------


def test_hardlink_inode_mismatch_backup_and_recreate() -> None:
    """Pre-existing file at link_path with wrong inode is backed up and recreated."""
    with tempfile.TemporaryDirectory() as tmp:
        container = Path(tmp) / "container"
        wiki_path = container / "wiki"
        portals = container / "portals"
        target_root = container / "wts" / "my-repo"

        _make_minimal_wiki(wiki_path, _FULL_CFG)
        portals.mkdir(parents=True)
        target_root.mkdir(parents=True)

        # Pre-create a tasks.md that is a regular file (different inode from Home.md)
        tasks_md = target_root / "tasks.md"
        tasks_md.write_text("old content", encoding="utf-8")
        old_inode = tasks_md.stat().st_ino

        tokens = {
            "HUB_PATH": str(target_root),
            "CWD_PATH": str(target_root),
            "CONTAINER_PATH": str(container),
            "WIKI_PATH": str(wiki_path),
            "REPO": "my-repo",
        }

        result = create_hub_links(target_root, wiki_path, tokens)

        # Verify a hardlink was created (listed in result)
        if len(result["hardlinks"]) != 1:
            raise AssertionError(
                f"expected 1 hardlink created on mismatch, got {result['hardlinks']}"
            )

        # tasks.md now shares inode with Home.md
        home_inode = (wiki_path / "Home.md").stat().st_ino
        new_inode = tasks_md.stat().st_ino
        if new_inode == old_inode:
            raise AssertionError("tasks.md inode should have changed after recreate")
        if new_inode != home_inode:
            raise AssertionError(
                f"tasks.md inode {new_inode} should match Home.md inode {home_inode}"
            )

        # Backup file must exist
        backup = target_root / "tasks.md.bak"
        if not backup.exists():
            raise AssertionError(f"backup file not found at {backup}")
        if backup.read_text(encoding="utf-8") != "old content":
            raise AssertionError("backup should contain the original content")

    print("PASS: inode mismatch triggers backup-and-recreate")


# ---------------------------------------------------------------------------
# Empty config blocks → empty result lists
# ---------------------------------------------------------------------------


def test_all_entries_filtered_return_empty_lists() -> None:
    """When every config entry requires <SLUG> and SLUG is absent, both lists are empty.

    Uses _ALL_SLUG_CFG where the junction and hardlink both require <SLUG>.
    Without SLUG in the token map the token-scope filter skips them all.
    Note: read_junctions falls back to _JUNCTION_DEFAULTS for a truly empty
    junctions block; _ALL_SLUG_CFG avoids that by providing an explicit entry.
    """
    with tempfile.TemporaryDirectory() as tmp:
        wiki_path = Path(tmp) / "wiki"
        target_root = Path(tmp) / "worktree"

        _make_minimal_wiki(wiki_path, _ALL_SLUG_CFG)
        target_root.mkdir()

        tokens = {
            "HUB_PATH": str(target_root),
            "CWD_PATH": str(target_root),
            "CONTAINER_PATH": str(Path(tmp)),
            "WIKI_PATH": str(wiki_path),
            "REPO": "repo",
            # no SLUG → every entry is filtered
        }

        result = create_hub_links(target_root, wiki_path, tokens)

        if result["junctions"] != []:
            raise AssertionError(f"expected empty junctions, got {result['junctions']}")
        if result["hardlinks"] != []:
            raise AssertionError(f"expected empty hardlinks, got {result['hardlinks']}")

    print("PASS: all-SLUG config with no SLUG token → both result lists empty")


# ---------------------------------------------------------------------------
# Cross-volume hardlink → ValueError with clear message
# ---------------------------------------------------------------------------


def test_cross_volume_hardlink_raises_clear_error() -> None:
    """OSError from hardlink_to (cross-volume) is re-raised as ValueError naming paths."""
    with tempfile.TemporaryDirectory() as tmp:
        wiki_path = Path(tmp) / "wiki"
        target_root = Path(tmp) / "worktree"
        _make_minimal_wiki(wiki_path, {"junctions": {}, "hardlinks": {"tasks.md": "<WIKI_PATH>/Home.md"}})
        target_root.mkdir()

        tokens = {
            "HUB_PATH": str(target_root),
            "CWD_PATH": str(target_root),
            "CONTAINER_PATH": str(Path(tmp)),
            "WIKI_PATH": str(wiki_path),
            "REPO": "repo",
        }

        cross_vol_error = OSError("cross-device link not permitted")
        with patch.object(Path, "hardlink_to", side_effect=cross_vol_error):
            try:
                create_hub_links(target_root, wiki_path, tokens)
            except ValueError as exc:
                msg = str(exc)
                if "Failed to create hardlink" not in msg:
                    raise AssertionError(
                        f"ValueError message should name the error, got: {msg!r}"
                    )
                # Both source and target paths must appear in the message.
                if "tasks.md" not in msg:
                    raise AssertionError(f"link path missing from error: {msg!r}")
                if "Home.md" not in msg:
                    raise AssertionError(f"target path missing from error: {msg!r}")
            else:
                raise AssertionError("expected ValueError for cross-volume hardlink")

    print("PASS: cross-volume OSError re-raised as ValueError naming source/target")


# ---------------------------------------------------------------------------
# Portal-flow integration (Card 8 assertions)
# ---------------------------------------------------------------------------


def test_portal_flow_integration() -> None:
    """Full fixture with portals structure asserts all four links are correct.

    Fixture:
      container/
        wts/
          my-task/        <- target_root (new worktree)
        portals/
          my-task/        <- junction → container/wts/my-task/
        wiki/
          Home.md
          config.yaml

    Asserts (from Card 6 requirements):
      (a) .others junction inside target_root exists and resolves to portals/
      (b) .active junction inside target_root exists and resolves to portals/<slug>
      (c) tasks.md hardlink shares an inode with wiki/Home.md
      (d) .millhouse/wiki junction exists and resolves to wiki path
    """
    import _junction as junction_mod  # real junction helper

    with tempfile.TemporaryDirectory() as tmp:
        container = Path(tmp) / "container"
        wiki_path = container / "wiki"
        portals = container / "portals"
        target_root = container / "wts" / "my-task"

        _make_minimal_wiki(wiki_path, _FULL_CFG)
        portals.mkdir(parents=True)
        target_root.mkdir(parents=True)

        # Create portals/<slug> junction → target_root (mirrors mill-spawn step 2)
        junction_mod.create(target=target_root, link_path=portals / "my-task")

        tokens = {
            "HUB_PATH": str(target_root),
            "CWD_PATH": str(target_root),
            "CONTAINER_PATH": str(container),
            "WIKI_PATH": str(wiki_path),
            "REPO": "my-repo",
            "SLUG": "my-task",
        }

        result = create_hub_links(target_root, wiki_path, tokens)

        if len(result["junctions"]) != 3:
            raise AssertionError(
                f"expected 3 junctions from portal flow, got {len(result['junctions'])}: "
                f"{result['junctions']}"
            )
        if len(result["hardlinks"]) != 1:
            raise AssertionError(
                f"expected 1 hardlink from portal flow, got {len(result['hardlinks'])}: "
                f"{result['hardlinks']}"
            )

        # (d) .millhouse/wiki exists and resolves to wiki path
        wiki_link = target_root / ".millhouse" / "wiki"
        if not wiki_link.is_dir():
            raise AssertionError(f".millhouse/wiki junction not a dir at {wiki_link}")
        # Write probe into wiki dir and verify via junction
        probe_wiki = wiki_path / "wiki-probe.txt"
        probe_wiki.write_text("wiki-probe", encoding="utf-8")
        via_wiki_link = target_root / ".millhouse" / "wiki" / "wiki-probe.txt"
        if not via_wiki_link.exists():
            raise AssertionError(f"wiki probe not accessible via junction at {via_wiki_link}")
        if via_wiki_link.read_text(encoding="utf-8") != "wiki-probe":
            raise AssertionError("wiki probe content mismatch via junction")
        probe_wiki.unlink()

        # (a) .others junction exists and resolves to portals/
        others_link = target_root / ".others"
        if not others_link.is_dir():
            raise AssertionError(f".others junction not a dir at {others_link}")
        # Write probe into portals dir and verify via .others
        probe_portals = portals / "portals-probe.txt"
        probe_portals.write_text("portals-probe", encoding="utf-8")
        via_others = target_root / ".others" / "portals-probe.txt"
        if not via_others.exists():
            raise AssertionError(f"portals probe not accessible via .others at {via_others}")
        if via_others.read_text(encoding="utf-8") != "portals-probe":
            raise AssertionError("portals probe content mismatch via .others")
        probe_portals.unlink()

        # (b) .active junction exists and resolves to portals/<slug>
        active_link = target_root / ".active"
        if not active_link.is_dir():
            raise AssertionError(f".active junction not a dir at {active_link}")
        # .active → portals/my-task (itself a junction → target_root)
        # Verify .active is traversable: portals/my-task contains the worktree contents.
        # Create a probe at portals level (accessible via .active which points there)
        # portals/my-task is a junction → target_root, so we write through target_root
        probe_in_target = target_root / "target-probe.txt"
        probe_in_target.write_text("target-probe", encoding="utf-8")
        # .active points to portals/my-task which points to target_root, so
        # .active/target-probe.txt should be accessible
        via_active = target_root / ".active" / "target-probe.txt"
        if not via_active.exists():
            raise AssertionError(f"target probe not accessible via .active at {via_active}")
        probe_in_target.unlink()

        # (c) tasks.md hardlink shares inode with wiki/Home.md
        tasks_md = target_root / "tasks.md"
        home_md = wiki_path / "Home.md"
        if not tasks_md.exists():
            raise AssertionError(f"tasks.md not created at {tasks_md}")
        if tasks_md.stat().st_ino != home_md.stat().st_ino:
            raise AssertionError(
                f"tasks.md inode {tasks_md.stat().st_ino} != Home.md inode "
                f"{home_md.stat().st_ino}"
            )

    print("PASS: portal-flow integration — all four links created and traversable")


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------


def main() -> int:
    tests = [
        test_token_scope_filter_no_slug,
        test_token_scope_filter_with_slug,
        test_hardlink_inode_skip_idempotent,
        test_hardlink_inode_mismatch_backup_and_recreate,
        test_all_entries_filtered_return_empty_lists,
        test_cross_volume_hardlink_raises_clear_error,
        test_portal_flow_integration,
    ]

    failures: list[str] = []
    for test_fn in tests:
        try:
            test_fn()
        except AssertionError as exc:
            print(f"FAIL [{test_fn.__name__}]: {exc}", file=sys.stderr)
            failures.append(test_fn.__name__)
        except Exception as exc:  # noqa: BLE001
            print(f"ERROR [{test_fn.__name__}]: {exc}", file=sys.stderr)
            failures.append(test_fn.__name__)

    print()
    if failures:
        print(f"FAIL -- {len(failures)} of {len(tests)} tests: {failures}", file=sys.stderr)
        return 1
    print(f"All {len(tests)} _setup hub-links unit tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
