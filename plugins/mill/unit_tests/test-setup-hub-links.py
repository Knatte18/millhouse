"""Unit tests for plugins/mill/scripts/_setup.py.

Uses safe_temp_dir() (junction-aware temp dir) and real disk operations for all
happy-path cases. A single selective mock covers the cross-volume hardlink
error path which cannot be triggered without multiple filesystem volumes.

Covers:
  - Token-scope filter: no <SLUG> in tokens -> .portals entry skipped; .wiki created
  - Mixed slug+non-slug entries: both .wiki and .portals created when SLUG present
  - Hardlink inode skip (idempotent re-run)
  - Hardlink inode-mismatch -> backup-and-recreate
  - Both empty config blocks -> empty result lists
  - Cross-volume hardlink -> ValueError with clear source/target in message
  - Portal-flow integration:
      - .wiki junction resolves to fixture wiki path
      - .portals junction resolves to wiki/active/<slug>/ dir
      - tasks.md hardlink shares an inode with wiki/Home.md
  - Graceful absence: missing hardlinks block -> empty hardlinks list
  - Graceful absence: hardlinks: null -> empty hardlinks list
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import yaml

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

from _setup import create_hub_links  # noqa: E402
from _test_helpers import safe_temp_dir  # noqa: E402


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _write_hub_config(hub_root: Path, cfg: dict) -> None:
    """Write cfg as YAML to hub_root/mill-config.yaml (where _junction.read_* looks)."""
    hub_root.mkdir(parents=True, exist_ok=True)
    (hub_root / "mill-config.yaml").write_text(
        yaml.dump(cfg, default_flow_style=False), encoding="utf-8"
    )


def _make_minimal_wiki(wiki_path: Path, hub_root: Path, cfg: dict) -> None:
    """Create wiki_path with Home.md and write cfg as hub_root/mill-config.yaml.

    The junctions/hardlinks blocks live at the hub (mill-config.yaml), not the
    wiki — _junction.read_junctions/read_hardlinks read from <hub_root>/mill-config.yaml.
    """
    wiki_path.mkdir(parents=True, exist_ok=True)
    (wiki_path / "Home.md").write_text("# Home\n", encoding="utf-8")
    _write_hub_config(hub_root, cfg)


# Config with the full new junctions block + one hardlink (used by most tests)
_FULL_CFG = {
    "junctions": {
        ".wiki": "<WIKI_PATH>",
        ".portals": "<WIKI_PATH>/active/<SLUG>/",
    },
    "hardlinks": {
        "tasks.md": "<WIKI_PATH>/Home.md",
    },
}

# Config where every entry requires <SLUG> — used to test that ALL entries
# are filtered when SLUG is absent, yielding empty result lists.
_ALL_SLUG_CFG = {
    "junctions": {
        ".portals": "<WIKI_PATH>/active/<SLUG>/",
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
        ".portals": "<WIKI_PATH>/active/<SLUG>/",  # filtered: needs SLUG
    },
    "hardlinks": {
        "tasks.md": "<WIKI_PATH>/Home.md",
    },
}


# ---------------------------------------------------------------------------
# Token-scope filter: no <SLUG> -> .active skipped
# ---------------------------------------------------------------------------


def test_token_scope_filter_no_slug() -> None:
    """When SLUG is absent from tokens, .portals entry is skipped; .wiki is created."""
    with safe_temp_dir() as tmp:
        container = tmp / "container"
        wiki_path = container / "wiki"
        target_root = container / "wts" / "my-repo"

        _make_minimal_wiki(wiki_path, target_root, _FULL_CFG)
        (wiki_path / "active").mkdir(parents=True)
        target_root.mkdir(parents=True, exist_ok=True)

        tokens = {
            "HUB_PATH": str(target_root),
            "CWD_PATH": str(target_root),
            "CONTAINER_PATH": str(container),
            "WIKI_PATH": str(wiki_path),
            "REPO": "my-repo",
            # deliberately omit SLUG
        }

        result = create_hub_links(target_root, wiki_path, tokens)

        # .wiki must be created
        wiki_link = target_root / ".wiki"
        if not (wiki_link.exists() or wiki_link.is_symlink()):
            raise AssertionError(f".wiki junction not created at {wiki_link}")

        # .portals must NOT be created (requires SLUG)
        portals_link = target_root / ".portals"
        if portals_link.exists() or portals_link.is_symlink():
            raise AssertionError(".portals should be skipped when SLUG absent")

        # Return value: 1 junction (.wiki), 1 hardlink (tasks.md)
        if len(result["junctions"]) != 1:
            raise AssertionError(
                f"expected 1 junction created, got {len(result['junctions'])}: "
                f"{result['junctions']}"
            )
        if len(result["hardlinks"]) != 1:
            raise AssertionError(
                f"expected 1 hardlink created, got {len(result['hardlinks'])}: "
                f"{result['hardlinks']}"
            )

    print("PASS: token-scope filter skips .portals when SLUG absent; .wiki created")


# ---------------------------------------------------------------------------
# Mixed slug+non-slug entries: all created when SLUG present
# ---------------------------------------------------------------------------


def test_token_scope_filter_with_slug() -> None:
    """When SLUG is present, both .wiki and .portals junctions and the hardlink are created."""
    with safe_temp_dir() as tmp:
        container = tmp / "container"
        wiki_path = container / "wiki"
        target_root = container / "wts" / "my-task"

        _make_minimal_wiki(wiki_path, target_root, _FULL_CFG)
        (wiki_path / "active" / "my-task").mkdir(parents=True)
        target_root.mkdir(parents=True, exist_ok=True)

        tokens = {
            "HUB_PATH": str(target_root),
            "CWD_PATH": str(target_root),
            "CONTAINER_PATH": str(container),
            "WIKI_PATH": str(wiki_path),
            "REPO": "my-repo",
            "SLUG": "my-task",
        }

        result = create_hub_links(target_root, wiki_path, tokens)

        wiki_link = target_root / ".wiki"
        portals_link = target_root / ".portals"

        if not (wiki_link.exists() or wiki_link.is_symlink()):
            raise AssertionError(f".wiki not created at {wiki_link}")
        if not (portals_link.exists() or portals_link.is_symlink()):
            raise AssertionError(f".portals not created at {portals_link}")

        tasks_md = target_root / "tasks.md"
        if not tasks_md.exists():
            raise AssertionError(f"tasks.md hardlink not created at {tasks_md}")

        if len(result["junctions"]) != 2:
            raise AssertionError(
                f"expected 2 junctions, got {len(result['junctions'])}: "
                f"{result['junctions']}"
            )
        if len(result["hardlinks"]) != 1:
            raise AssertionError(
                f"expected 1 hardlink, got {len(result['hardlinks'])}: "
                f"{result['hardlinks']}"
            )

    print("PASS: .wiki and .portals junctions and 1 hardlink created when SLUG present")


# ---------------------------------------------------------------------------
# Junction idempotency: skip on correct target
# ---------------------------------------------------------------------------


def test_junction_idempotent_skip_on_correct_target() -> None:
    """Second call with existing correct junctions returns empty junctions list.

    Uses _FULL_CFG with SLUG present so both .wiki and .portals are created on
    the first call. The second call detects they already point at the correct
    targets and silently skips them.
    """
    with safe_temp_dir() as tmp:
        container = tmp / "container"
        wiki_path = container / "wiki"
        target_root = container / "wts" / "my-task"

        _make_minimal_wiki(wiki_path, target_root, _FULL_CFG)
        (wiki_path / "active" / "my-task").mkdir(parents=True)
        target_root.mkdir(parents=True, exist_ok=True)

        tokens = {
            "HUB_PATH": str(target_root),
            "CWD_PATH": str(target_root),
            "CONTAINER_PATH": str(container),
            "WIKI_PATH": str(wiki_path),
            "REPO": "my-repo",
            "SLUG": "my-task",
        }

        result1 = create_hub_links(target_root, wiki_path, tokens)
        if len(result1["junctions"]) != 2:
            raise AssertionError(
                f"first call: expected 2 junctions, got {result1['junctions']}"
            )

        result2 = create_hub_links(target_root, wiki_path, tokens)
        if result2["junctions"] != []:
            raise AssertionError(
                f"second call: expected [] junctions (idempotent skip), got {result2['junctions']}"
            )

        # .wiki still traverses to wiki_path.
        probe_wiki = wiki_path / "wiki-probe-idempotent.txt"
        probe_wiki.write_text("wiki-ok", encoding="utf-8")
        via_wiki = target_root / ".wiki" / "wiki-probe-idempotent.txt"
        if not via_wiki.exists() or via_wiki.read_text(encoding="utf-8") != "wiki-ok":
            raise AssertionError(".wiki junction no longer traverses to wiki_path after idempotent run")
        probe_wiki.unlink()

        # .portals still traverses to wiki/active/my-task/.
        probe_portals = wiki_path / "active" / "my-task" / "portals-probe-idempotent.txt"
        probe_portals.write_text("portals-ok", encoding="utf-8")
        via_portals = target_root / ".portals" / "portals-probe-idempotent.txt"
        if not via_portals.exists() or via_portals.read_text(encoding="utf-8") != "portals-ok":
            raise AssertionError(".portals junction no longer traverses to wiki/active/my-task/ after idempotent run")
        probe_portals.unlink()

    print("PASS: junction idempotent skip — second call returns [] junctions, existing junctions preserved")


# ---------------------------------------------------------------------------
# Junction idempotency: recreate on drift
# ---------------------------------------------------------------------------


def test_junction_recreated_on_wrong_target() -> None:
    """A junction pointing at the wrong target is removed and recreated.

    Pre-creates .wiki pointing at wiki_b/ (wrong). Configures WIKI_PATH = wiki_a/.
    After create_hub_links, .wiki must point at wiki_a/ and wiki_b/ must survive.
    result["junctions"] must include .wiki (drift counts as created).
    """
    import _junction as junction_mod

    with safe_temp_dir() as tmp:
        container = tmp / "container"
        wiki_a = container / "wiki_a"
        wiki_b = container / "wiki_b"
        target_root = container / "wts" / "my-repo"

        _make_minimal_wiki(wiki_a, target_root, _FULL_CFG)
        wiki_b.mkdir(parents=True)
        (wiki_b / "config.yaml").write_text("junctions: {}\nhardlinks: {}\n", encoding="utf-8")
        (wiki_b / "sentinel.txt").write_text("wiki-b-content", encoding="utf-8")
        target_root.mkdir(parents=True, exist_ok=True)

        junction_mod.create(target=wiki_b, link_path=target_root / ".wiki")

        tokens = {
            "HUB_PATH": str(target_root),
            "CWD_PATH": str(target_root),
            "CONTAINER_PATH": str(container),
            "WIKI_PATH": str(wiki_a),
            "REPO": "my-repo",
        }

        result = create_hub_links(target_root, wiki_a, tokens)

        # .wiki must now resolve to wiki_a.
        probe_a = wiki_a / "drift-probe.txt"
        probe_a.write_text("wiki-a-content", encoding="utf-8")
        via_wiki = target_root / ".wiki" / "drift-probe.txt"
        if not via_wiki.exists() or via_wiki.read_text(encoding="utf-8") != "wiki-a-content":
            raise AssertionError(".wiki junction does not point at wiki_a after drift recreate")
        probe_a.unlink()

        # wiki_b/ must still exist as a real directory.
        if not wiki_b.is_dir():
            raise AssertionError(
                "wiki_b/ should still exist after junction drift recreate (only the junction was removed)"
            )

        # result["junctions"] must include .wiki (drift recreate appends).
        wiki_link = target_root / ".wiki"
        if wiki_link not in result["junctions"]:
            raise AssertionError(
                f".wiki should be in result['junctions'] after drift recreate, got {result['junctions']}"
            )

    print("PASS: junction recreated on wrong target — .wiki redirected to wiki_a, wiki_b/ survives")


# ---------------------------------------------------------------------------
# Junction idempotency: refuse on real directory
# ---------------------------------------------------------------------------


def test_junction_refuses_to_replace_real_directory() -> None:
    """create_hub_links raises ValueError when a real directory sits at link_path.

    Pre-creates target_root/.wiki as a REAL directory with a sentinel file.
    create_hub_links must propagate _junction.remove's ValueError rather than
    silently deleting the directory.
    """
    with safe_temp_dir() as tmp:
        container = tmp / "container"
        wiki_path = container / "wiki"
        target_root = container / "wts" / "my-repo"

        _make_minimal_wiki(wiki_path, target_root, _FULL_CFG)
        target_root.mkdir(parents=True, exist_ok=True)

        real_wiki_dir = target_root / ".wiki"
        real_wiki_dir.mkdir()
        sentinel = real_wiki_dir / "sentinel.txt"
        sentinel.write_text("do-not-delete", encoding="utf-8")

        tokens = {
            "HUB_PATH": str(target_root),
            "CWD_PATH": str(target_root),
            "CONTAINER_PATH": str(container),
            "WIKI_PATH": str(wiki_path),
            "REPO": "my-repo",
        }

        try:
            create_hub_links(target_root, wiki_path, tokens)
        except ValueError as exc:
            if "is not a junction or symlink" not in str(exc):
                raise AssertionError(
                    f"ValueError message should contain 'is not a junction or symlink', got: {exc!r}"
                )
        else:
            raise AssertionError("expected ValueError when a real directory is at link_path")

        if not real_wiki_dir.is_dir():
            raise AssertionError("real .wiki directory was deleted — should have been refused")
        if not sentinel.exists() or sentinel.read_text(encoding="utf-8") != "do-not-delete":
            raise AssertionError("sentinel file inside real .wiki directory was modified")

    print("PASS: create_hub_links raises ValueError on real directory at link_path; directory preserved")


# ---------------------------------------------------------------------------
# Hardlink inode skip (idempotent re-run)
# ---------------------------------------------------------------------------


def test_hardlink_inode_skip_idempotent() -> None:
    """Second call with same target/link is a no-op (returns empty hardlinks).

    Uses _HARDLINK_ONLY_CFG whose junction entry requires <SLUG> (so it is
    filtered when SLUG absent). Only the hardlink is created on the first call.
    The second call finds matching inodes and skips.
    """
    with safe_temp_dir() as tmp:
        container = tmp / "container"
        wiki_path = container / "wiki"
        target_root = container / "wts" / "my-repo"

        _make_minimal_wiki(wiki_path, target_root, _HARDLINK_ONLY_CFG)
        target_root.mkdir(parents=True, exist_ok=True)

        tokens = {
            "HUB_PATH": str(target_root),
            "CWD_PATH": str(target_root),
            "CONTAINER_PATH": str(container),
            "WIKI_PATH": str(wiki_path),
            "REPO": "my-repo",
            # deliberately omit SLUG -> junction entry is filtered
        }

        # First call: junction filtered -> 0 junctions; hardlink created -> 1
        result1 = create_hub_links(target_root, wiki_path, tokens)
        if len(result1["junctions"]) != 0:
            raise AssertionError(f"first call: expected 0 junctions, got {result1['junctions']}")
        if len(result1["hardlinks"]) != 1:
            raise AssertionError(f"first call: expected 1 hardlink, got {result1['hardlinks']}")

        tasks_md = target_root / "tasks.md"
        inode_first = tasks_md.stat().st_ino

        # Second call: hardlink inode matches -> skipped
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
# Hardlink inode mismatch -> backup-and-recreate
# ---------------------------------------------------------------------------


def test_hardlink_inode_mismatch_backup_and_recreate() -> None:
    """Pre-existing file at link_path with wrong inode is backed up and recreated."""
    with safe_temp_dir() as tmp:
        container = tmp / "container"
        wiki_path = container / "wiki"
        target_root = container / "wts" / "my-repo"

        _make_minimal_wiki(wiki_path, target_root, _FULL_CFG)
        target_root.mkdir(parents=True, exist_ok=True)

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
# Empty config blocks -> empty result lists
# ---------------------------------------------------------------------------


def test_all_entries_filtered_return_empty_lists() -> None:
    """When every config entry requires <SLUG> and SLUG is absent, both lists are empty.

    Uses _ALL_SLUG_CFG where the junction and hardlink both require <SLUG>.
    Without SLUG in the token map the token-scope filter skips them all.
    Note: read_junctions falls back to _JUNCTION_DEFAULTS for a truly empty
    junctions block; _ALL_SLUG_CFG avoids that by providing an explicit entry.
    """
    with safe_temp_dir() as tmp:
        wiki_path = tmp / "wiki"
        target_root = tmp / "worktree"

        _make_minimal_wiki(wiki_path, target_root, _ALL_SLUG_CFG)
        target_root.mkdir(exist_ok=True)

        tokens = {
            "HUB_PATH": str(target_root),
            "CWD_PATH": str(target_root),
            "CONTAINER_PATH": str(tmp),
            "WIKI_PATH": str(wiki_path),
            "REPO": "repo",
            # no SLUG -> every entry is filtered
        }

        result = create_hub_links(target_root, wiki_path, tokens)

        if result["junctions"] != []:
            raise AssertionError(f"expected empty junctions, got {result['junctions']}")
        if result["hardlinks"] != []:
            raise AssertionError(f"expected empty hardlinks, got {result['hardlinks']}")

    print("PASS: all-SLUG config with no SLUG token -> both result lists empty")


# ---------------------------------------------------------------------------
# Cross-volume hardlink -> ValueError with clear message
# ---------------------------------------------------------------------------


def test_cross_volume_hardlink_raises_clear_error() -> None:
    """OSError from hardlink_to (cross-volume) is re-raised as ValueError naming paths."""
    with safe_temp_dir() as tmp:
        wiki_path = tmp / "wiki"
        target_root = tmp / "worktree"
        _make_minimal_wiki(wiki_path, target_root, {"junctions": {}, "hardlinks": {"tasks.md": "<WIKI_PATH>/Home.md"}})
        target_root.mkdir(exist_ok=True)

        tokens = {
            "HUB_PATH": str(target_root),
            "CWD_PATH": str(target_root),
            "CONTAINER_PATH": str(tmp),
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
    """Full fixture with wiki/active structure asserts all links are correct.

    Fixture:
      container/
        wts/
          my-task/              <- target_root (new worktree)
        portals/
          my-task/              <- junction -> wiki/active/my-task/
        wiki/
          active/
            my-task/            <- wiki state dir (portal target)
          Home.md
          config.yaml

    Asserts:
      (a) .wiki junction inside target_root exists and resolves to wiki path
      (b) .portals junction inside target_root exists and resolves to wiki/active/my-task/
      (c) tasks.md hardlink shares an inode with wiki/Home.md
    """
    import _junction as junction_mod  # real junction helper

    with safe_temp_dir() as tmp:
        container = tmp / "container"
        wiki_path = container / "wiki"
        portals = container / "portals"
        target_root = container / "wts" / "my-task"

        _make_minimal_wiki(wiki_path, target_root, _FULL_CFG)
        (wiki_path / "active" / "my-task").mkdir(parents=True)
        portals.mkdir(parents=True)
        target_root.mkdir(parents=True, exist_ok=True)

        # Create portals/<slug> junction -> wiki/active/my-task/ (mirrors new mill-spawn)
        junction_mod.create(target=wiki_path / "active" / "my-task", link_path=portals / "my-task")

        tokens = {
            "HUB_PATH": str(target_root),
            "CWD_PATH": str(target_root),
            "CONTAINER_PATH": str(container),
            "WIKI_PATH": str(wiki_path),
            "REPO": "my-repo",
            "SLUG": "my-task",
        }

        result = create_hub_links(target_root, wiki_path, tokens)

        if len(result["junctions"]) != 2:
            raise AssertionError(
                f"expected 2 junctions from portal flow, got {len(result['junctions'])}: "
                f"{result['junctions']}"
            )
        if len(result["hardlinks"]) != 1:
            raise AssertionError(
                f"expected 1 hardlink from portal flow, got {len(result['hardlinks'])}: "
                f"{result['hardlinks']}"
            )

        # (a) .wiki junction exists and resolves to wiki path
        wiki_link = target_root / ".wiki"
        if not wiki_link.is_dir():
            raise AssertionError(f".wiki junction not a dir at {wiki_link}")
        probe_wiki = wiki_path / "wiki-probe.txt"
        probe_wiki.write_text("wiki-probe", encoding="utf-8")
        via_wiki_link = target_root / ".wiki" / "wiki-probe.txt"
        if not via_wiki_link.exists():
            raise AssertionError(f"wiki probe not accessible via junction at {via_wiki_link}")
        if via_wiki_link.read_text(encoding="utf-8") != "wiki-probe":
            raise AssertionError("wiki probe content mismatch via junction")
        probe_wiki.unlink()

        # (b) .portals junction exists and resolves to wiki/active/my-task/
        portals_link = target_root / ".portals"
        if not portals_link.is_dir():
            raise AssertionError(f".portals junction not a dir at {portals_link}")
        probe_active = wiki_path / "active" / "my-task" / "portals-probe.txt"
        probe_active.write_text("portals-probe", encoding="utf-8")
        via_portals = target_root / ".portals" / "portals-probe.txt"
        if not via_portals.exists():
            raise AssertionError(f"portals probe not accessible via .portals at {via_portals}")
        if via_portals.read_text(encoding="utf-8") != "portals-probe":
            raise AssertionError("portals probe content mismatch via .portals")
        probe_active.unlink()

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

    print("PASS: portal-flow integration — .wiki, .portals, and tasks.md hardlink created and traversable")


# ---------------------------------------------------------------------------
# Graceful absence: missing hardlinks block
# ---------------------------------------------------------------------------


def test_create_hub_links_handles_missing_hardlinks_block() -> None:
    """No hardlinks: block in config -> hardlinks result is empty, junctions created."""
    with safe_temp_dir() as tmp:
        container = tmp / "container"
        wiki_path = container / "wiki"
        target_root = container / "wts" / "my-repo"

        cfg_no_hardlinks = {
            "junctions": {
                ".wiki": "<WIKI_PATH>",
            },
            # deliberately no hardlinks key
        }
        _make_minimal_wiki(wiki_path, target_root, cfg_no_hardlinks)
        target_root.mkdir(parents=True, exist_ok=True)

        tokens = {
            "HUB_PATH": str(target_root),
            "CWD_PATH": str(target_root),
            "CONTAINER_PATH": str(container),
            "WIKI_PATH": str(wiki_path),
            "REPO": "my-repo",
        }

        result = create_hub_links(target_root, wiki_path, tokens)

        if result["hardlinks"] != []:
            raise AssertionError(
                f"expected empty hardlinks list, got {result['hardlinks']}"
            )
        if len(result["junctions"]) != 1:
            raise AssertionError(
                f"expected 1 junction, got {len(result['junctions'])}: {result['junctions']}"
            )

    print("PASS: missing hardlinks block -> empty hardlinks list, junction created normally")


def test_create_hub_links_handles_null_hardlinks_block() -> None:
    """hardlinks: null in config -> hardlinks result is empty, junctions created."""
    with safe_temp_dir() as tmp:
        container = tmp / "container"
        wiki_path = container / "wiki"
        target_root = container / "wts" / "my-repo"

        cfg_null_hardlinks = {
            "junctions": {
                ".wiki": "<WIKI_PATH>",
            },
            "hardlinks": None,  # explicit null -> yaml.safe_load yields None
        }
        _make_minimal_wiki(wiki_path, target_root, cfg_null_hardlinks)
        target_root.mkdir(parents=True, exist_ok=True)

        tokens = {
            "HUB_PATH": str(target_root),
            "CWD_PATH": str(target_root),
            "CONTAINER_PATH": str(container),
            "WIKI_PATH": str(wiki_path),
            "REPO": "my-repo",
        }

        result = create_hub_links(target_root, wiki_path, tokens)

        if result["hardlinks"] != []:
            raise AssertionError(
                f"expected empty hardlinks list for null block, got {result['hardlinks']}"
            )
        if len(result["junctions"]) != 1:
            raise AssertionError(
                f"expected 1 junction, got {len(result['junctions'])}: {result['junctions']}"
            )

    print("PASS: hardlinks: null -> empty hardlinks list, junction created normally")


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------


def main() -> int:
    tests = [
        test_token_scope_filter_no_slug,
        test_token_scope_filter_with_slug,
        test_junction_idempotent_skip_on_correct_target,
        test_junction_recreated_on_wrong_target,
        test_junction_refuses_to_replace_real_directory,
        test_hardlink_inode_skip_idempotent,
        test_hardlink_inode_mismatch_backup_and_recreate,
        test_all_entries_filtered_return_empty_lists,
        test_cross_volume_hardlink_raises_clear_error,
        test_portal_flow_integration,
        test_create_hub_links_handles_missing_hardlinks_block,
        test_create_hub_links_handles_null_hardlinks_block,
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
