"""
Integration test for hub_relative_path sub-project layout support.

Builds an isolated hub+wiki pair with a sub-project layout under ``.scratch/``
and exercises the path-resolution surface fixed in batches 1-3 against this
structure. The test:

1. Constructs a minimal sub-project fixture where the hub is a subfolder
   of the git repo root (e.g. ``<repo>/projects/sub/`` is the hub).
2. Runs ``millpy-spawn --dry-run`` from the hub subfolder to verify the
   path resolution works end-to-end.
3. Makes direct calls to ``_paths.resolve_active_hub`` and
   ``_review_common.resolve_ref_paths`` to assert the git_root fallback
   and hub_relative_path offset are applied correctly.

No LLM is invoked; no claude / sonnet subprocess fires. Git operations run
via subprocess against a real ``git`` in PATH.

Run from hub root:
    PYTHONPATH= uv run --project plugins/mill python plugins/mill/integration_tests/test-hub-relative-path.py

Exits 0 on PASS, 1 on any assertion failure (scratch dir preserved for post-mortem).
"""
from __future__ import annotations

import os
import subprocess
import sys
import uuid
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
SCRIPTS = HUB / "plugins" / "mill" / "scripts"
PLUGIN_ROOT = HUB / "plugins" / "mill"
SCRATCH = HUB / ".scratch"

sys.path.insert(0, str(SCRIPTS))

import _config  # noqa: E402
import _paths  # noqa: E402
import _review_common  # noqa: E402
import _safe_rmtree  # noqa: E402
from wiki import _client as wiki_client  # noqa: E402


def _run(cmd: list[str], *, cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    """Invoke ``cmd`` in ``cwd`` with UTF-8 output capture."""
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        check=check,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def _setup_subproject_pair(container: Path) -> tuple[Path, Path, Path, Path]:
    """
    Construct a minimal hub + wiki pair with sub-project layout under ``container``.

    Layout:
        <container>/wts/outer-repo/               — git repo root
        <container>/wts/outer-repo/lib/example.py — example file
        <container>/wts/outer-repo/projects/sub/  — hub subfolder
        <container>/wts/outer-repo/.millhouse/config.local.yaml — declares hub_relative_path
        <container>/wiki.git                      — bare "remote"
        <container>/wiki                          — working clone of the bare

    Returns ``(outer_repo, hub, wiki, worktrees_dir)``.
    """
    container.mkdir(parents=True, exist_ok=True)
    bare = container / "wiki.git"
    wiki = container / "wiki"
    outer_repo = container / "wts" / "outer-repo"
    hub = outer_repo / "projects" / "sub"
    worktrees_dir = container / "wts"

    # Bare wiki + clone.
    _run(["git", "init", "--bare", str(bare), "-b", "main"], cwd=container)
    _run(["git", "clone", str(bare), str(wiki)], cwd=container)
    _run(["git", "-C", str(wiki), "config", "user.email", "test@example.com"], cwd=container)
    _run(["git", "-C", str(wiki), "config", "user.name", "Test"], cwd=container)

    # Static wiki config (not task data — wiki._client.upsert_task seeds tasks.json + renders Home.md).
    (wiki / "config.yaml").write_text(
        "junctions:\n"
        "  .millhouse/wiki: <WIKI_PATH>\n"
        "  .active: <WIKI_PATH>/active/<SLUG>/\n"
        "\n"
        "spawn:\n"
        '  branch_prefix: "test/"\n',
        encoding="utf-8",
    )
    _run(["git", "-C", str(wiki), "add", "config.yaml"], cwd=container)
    _run(["git", "-C", str(wiki), "commit", "-m", "seed config"], cwd=container)
    _run(["git", "-C", str(wiki), "push", "origin", "main"], cwd=container)

    # Seed the spawn-ready task via the wiki client — daemon writes tasks.json,
    # renders Home.md, commits & pushes. status=None == spawn-ready ([s]).
    wiki_client.upsert_task(
        wiki,
        "subproj-fixture",
        title="Sub-project fixture",
        brief="Seed task for the hub-relative-path integration test.",
        body="# Sub-project fixture\n\nProposal for the hub-relative-path integration test.\n",
    )

    # Outer repo — git root with lib/example.py file.
    outer_repo.mkdir(parents=True, exist_ok=True)
    _run(["git", "init", str(outer_repo), "-b", "main"], cwd=container)
    _run(["git", "-C", str(outer_repo), "config", "user.email", "test@example.com"], cwd=container)
    _run(["git", "-C", str(outer_repo), "config", "user.name", "Test"], cwd=container)

    (outer_repo / "lib").mkdir(exist_ok=True)
    (outer_repo / "lib" / "example.py").write_text("def fn(): return 1\n", encoding="utf-8")
    (outer_repo / "README.md").write_text("sub-project test\n", encoding="utf-8")
    _run(["git", "-C", str(outer_repo), "add", "lib", "README.md"], cwd=container)
    _run(["git", "-C", str(outer_repo), "commit", "-m", "init"], cwd=container)

    # Hub subfolder with mill-config.yaml and config.local.yaml.
    hub.mkdir(parents=True, exist_ok=True)
    (hub / "mill-config.yaml").write_text(
        "spawn:\n"
        '  branch_prefix: "test/"\n'
        "paths:\n"
        "  status_md: _mill/status.md\n"
        "  discussion_file: _mill/discussion.md\n"
        "  reviews_dir: _mill/reviews\n",
        encoding="utf-8",
    )
    # Create .millhouse stub at hub with hub_relative_path so resolve_wiki_path works when running from the hub.
    (hub / ".millhouse").mkdir(exist_ok=True)
    (hub / ".millhouse" / "config.local.yaml").write_text(
        "hub_relative_path: projects/sub\n",
        encoding="utf-8",
    )
    _run(["git", "-C", str(outer_repo), "add", "projects/sub/mill-config.yaml", "projects/sub/.millhouse/config.local.yaml"], cwd=container)
    _run(["git", "-C", str(outer_repo), "commit", "-m", "add hub"], cwd=container)

    # .millhouse/ with wiki junction + config.local.yaml at outer-repo root.
    millhouse = outer_repo / ".millhouse"
    millhouse.mkdir()
    if sys.platform == "win32":
        subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(millhouse / "wiki"), str(wiki)],
            check=True,
            capture_output=True,
        )
    else:
        os.symlink(str(wiki), str(millhouse / "wiki"))
    (millhouse / "config.local.yaml").write_text(
        "hub_relative_path: projects/sub\n",
        encoding="utf-8",
    )
    # Also create the wiki junction at the hub subfolder so resolve_wiki_path can find it.
    hub_millhouse = hub / ".millhouse"
    hub_millhouse.mkdir(parents=True, exist_ok=True)
    if sys.platform == "win32":
        subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(hub_millhouse / "wiki"), str(wiki)],
            check=True,
            capture_output=True,
        )
    else:
        os.symlink(str(wiki), str(hub_millhouse / "wiki"))
    _run(["git", "-C", str(outer_repo), "add", ".millhouse"], cwd=container)
    _run(["git", "-C", str(outer_repo), "commit", "-m", "add millhouse config"], cwd=container)

    return outer_repo, hub, wiki, worktrees_dir


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def _run_spawn(hub: Path) -> subprocess.CompletedProcess:
    """Run mill-spawn --dry-run against ``hub`` subfolder."""
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(
        ["uv", "run", "--project", str(PLUGIN_ROOT), "python", str(SCRIPTS / "millpy-spawn.py"), "--dry-run", "--slug", "subproj-fixture"],
        cwd=str(hub),
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        check=False,
    )


def main() -> int:
    SCRATCH.mkdir(parents=True, exist_ok=True)
    container = SCRATCH / f"test-hub-relative-path-{uuid.uuid4().hex[:8]}"
    failed = False
    try:
        outer_repo, hub, wiki, worktrees_dir = _setup_subproject_pair(container)
        print(f"[test-hub-relative-path] container: {container}", file=sys.stderr)

        # === Step 1: Run mill-spawn dry-run and verify status path ===
        _assert(
            (outer_repo / "lib" / "example.py").exists(),
            f"example.py not found at {outer_repo / 'lib' / 'example.py'}",
        )
        _assert(
            (hub / "mill-config.yaml").exists(),
            f"mill-config.yaml not found at {hub / 'mill-config.yaml'}",
        )
        _assert(
            (wiki / "Home.md").exists(),
            f"Home.md not found at {wiki / 'Home.md'}",
        )

        # Run mill-spawn dry-run from hub subfolder.
        spawn_result = _run_spawn(hub)
        _assert(
            spawn_result.returncode == 0,
            f"mill-spawn dry-run failed with exit code {spawn_result.returncode}: {spawn_result.stderr}",
        )

        # Parse dry-run output to find the Status: line.
        status_line = None
        for line in spawn_result.stdout.split("\n"):
            if "[DryRun] Status:" in line:
                status_line = line
                break
        _assert(
            status_line is not None,
            f"No [DryRun] Status: line in spawn output:\n{spawn_result.stdout}",
        )

        # Extract path from "Status: /path/to/status.md" format.
        status_path_str = status_line.split("[DryRun] Status:")[-1].strip()
        status_path_obj = Path(status_path_str)

        # Verify the status path is under the hub subfolder, not the worktree root.
        # Expected: <worktrees_dir>/subproj-fixture/projects/sub/_mill/status.md
        expected_hub_in_path = worktrees_dir / "subproj-fixture" / "projects" / "sub"
        expected_status_path = expected_hub_in_path / "_mill" / "status.md"
        _assert(
            status_path_obj == expected_status_path,
            f"Status path {status_path_obj} does not match expected {expected_status_path}",
        )

        # === Step 2: Load config and resolve_active_hub ===
        cfg = _config.load_config(hub, hub)
        container_path = _paths.resolve_container_path(outer_repo)

        # Create stub worktree directory for resolve_active_hub call.
        # Use git worktree add to properly link it to the outer-repo.
        stub_wt = worktrees_dir / "subproj-fixture"
        _run(
            ["git", "-C", str(outer_repo), "worktree", "add", str(stub_wt), "-b", "test/subproj-fixture"],
            cwd=container,
        )
        # Add the stub config at the worktree root with hub_relative_path.
        (stub_wt / ".millhouse").mkdir(exist_ok=True)
        (stub_wt / ".millhouse" / "config.local.yaml").write_text(
            "hub_relative_path: projects/sub\n",
            encoding="utf-8",
        )

        # Call resolve_active_hub and assert it returns the hub subfolder within the worktree.
        expected_hub = stub_wt / "projects" / "sub"
        resolved_hub = _paths.resolve_active_hub(container_path, "subproj-fixture", cfg=cfg, git_root=outer_repo)
        _assert(
            resolved_hub == expected_hub,
            f"resolve_active_hub returned {resolved_hub}, expected {expected_hub}",
        )

        # === Step 3: Test resolve_ref_paths with git_root fallback ===
        raw_paths = ["lib/example.py"]
        resolved = _review_common.resolve_ref_paths(
            raw_paths,
            project_root=hub,
            root=None,
            git_root=outer_repo,
        )
        _assert(
            len(resolved) == 1,
            f"resolve_ref_paths returned {len(resolved)} paths, expected 1",
        )
        _assert(
            resolved[0].suffix == ".py" and "example.py" in str(resolved[0]),
            f"resolved path does not match: {resolved[0]}",
        )
        _assert(
            resolved[0] == outer_repo / "lib" / "example.py",
            f"resolved path {resolved[0]} != expected {outer_repo / 'lib' / 'example.py'}",
        )

        # Test that without git_root it raises ReviewError (fallback is required for sub-project).
        try:
            _review_common.resolve_ref_paths(
                raw_paths,
                project_root=hub,
                root=None,
                git_root=None,
            )
            _assert(False, "resolve_ref_paths should have raised ReviewError without git_root")
        except _review_common.ReviewError:
            pass  # Expected.

        print("PASS", file=sys.stderr)
        return 0

    except AssertionError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        failed = True
        return 1
    except Exception as exc:  # noqa: BLE001 — want full surface on unexpected
        print(f"FAIL (unexpected): {type(exc).__name__}: {exc}", file=sys.stderr)
        failed = True
        return 1
    finally:
        if failed:
            print(
                f"Scratch dir preserved for inspection: {container}",
                file=sys.stderr,
            )
        else:
            _safe_rmtree.safe_rmtree(container, allowed_root=container, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
