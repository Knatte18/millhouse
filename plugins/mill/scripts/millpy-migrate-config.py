#!/usr/bin/env python3
"""Migrate wiki/config.yaml and wiki/agents.yaml to hub root and plugin template.

This script idempotently migrates existing hub config:
- Copies wiki/config.yaml to hub/mill-config.yaml (if needed).
- Removes the wiki copy and pushes the change.
- Checks wiki/agents.yaml against the plugin template.
  - If identical: deletes the wiki copy.
  - If different: warns and leaves it in place.

Standard invocation (cache form):
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-migrate-config.py"
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

import yaml

import _config
import _paths
import _subprocess_util
import _wiki


def main() -> int:
    try:
        # Step 1: Resolve paths. hub_root = CWD (where mill-setup was invoked).
        # git_root = git toplevel — used only for wiki-path resolution and git -C operations
        # on the wiki. mill-config.yaml belongs at hub_root, not git_root, so that
        # subdirectory-hub setups (hub_relative_path != ".") place it correctly.
        hub_root = Path.cwd().resolve()
        git_root = _paths.resolve_git_root()
        print(f"[migrate] hub root: {hub_root}")

        # Step 2: Resolve wiki_path
        try:
            wiki_path = _paths.resolve_wiki_path(git_root)
        except SystemExit:
            print("[migrate] no wiki configured -- nothing to migrate")
            return 0

        # Step 3: Resolve plugin template paths
        plugin_agents_template = _config.resolve_plugin_template_path("mill-agents.yaml")

        # Step 4: Config migration
        wiki_config = wiki_path / "config.yaml"
        hub_config = hub_root / "mill-config.yaml"
        try:
            config_rel = str(hub_config.relative_to(git_root))
        except ValueError:
            config_rel = "mill-config.yaml"

        if not wiki_config.exists():
            print("[migrate] no wiki/config.yaml -- config migration skipped")
        elif hub_config.exists():
            print("[migrate] mill-config.yaml already exists at hub root -- skipping copy")
        else:
            # Copy wiki/config.yaml to hub/mill-config.yaml
            shutil.copyfile(wiki_config, hub_config)
            _subprocess_util.run(["git", "-C", str(git_root), "add", config_rel])
            print(
                f"[migrate] mill-config.yaml staged at {hub_config}; commit it on the main branch to land the migration"
            )

        # Delete wiki/config.yaml if it exists (idempotently)
        if wiki_config.exists():
            with _wiki.wiki_lock(wiki_path, slug="migrate-config"):
                # Step 4a: git rm
                result = _subprocess_util.run(
                    ["git", "-C", str(wiki_path), "rm", "config.yaml"]
                )
                if result.returncode != 0:
                    print("[migrate] ERROR: git rm config.yaml failed", file=sys.stderr)
                    return 1

                # Step 4b: git commit
                result = _subprocess_util.run(
                    [
                        "git",
                        "-C",
                        str(wiki_path),
                        "commit",
                        "-m",
                        "chore(migrate): remove wiki/config.yaml (moved to hub/mill-config.yaml)",
                    ]
                )
                if result.returncode != 0:
                    if "nothing to commit" in result.stdout or "nothing to commit" in result.stderr:
                        pass  # Already deleted in prior run
                    else:
                        print(
                            f"[migrate] ERROR: git commit failed: {result.stderr.strip()}",
                            file=sys.stderr,
                        )
                        return 1

                # Step 4c: git push with rebase retry
                result = _subprocess_util.run(
                    ["git", "-C", str(wiki_path), "push"]
                )
                if result.returncode != 0:
                    if "non-fast-forward" in result.stderr or "rejected" in result.stderr:
                        # Retry with rebase
                        result = _subprocess_util.run(
                            ["git", "-C", str(wiki_path), "pull", "--rebase"]
                        )
                        if result.returncode != 0:
                            _subprocess_util.run(["git", "-C", str(wiki_path), "rebase", "--abort"])
                            print(
                                f"[migrate] ERROR: git pull --rebase failed: {result.stderr.strip()}",
                                file=sys.stderr,
                            )
                            return 1
                        # Retry push
                        result = _subprocess_util.run(
                            ["git", "-C", str(wiki_path), "push"]
                        )
                        if result.returncode != 0:
                            print(
                                f"[migrate] ERROR: git push failed after rebase: {result.stderr.strip()}",
                                file=sys.stderr,
                            )
                            return 1
                    else:
                        print(
                            f"[migrate] ERROR: git push failed: {result.stderr.strip()}",
                            file=sys.stderr,
                        )
                        return 1

            print("[migrate] wiki/config.yaml deleted and pushed")

        # Step 5: Agents migration
        wiki_agents = wiki_path / "agents.yaml"

        if not wiki_agents.exists():
            print("[migrate] no wiki/agents.yaml -- agents migration skipped")
        else:
            wiki_data = yaml.safe_load(wiki_agents.read_text(encoding="utf-8")) or {}
            template_text = plugin_agents_template.read_text(encoding="utf-8")
            template_data = yaml.safe_load(template_text) or {}

            if wiki_data == template_data:
                # Delete wiki/agents.yaml
                with _wiki.wiki_lock(wiki_path, slug="migrate-config"):
                    # git rm
                    result = _subprocess_util.run(
                        ["git", "-C", str(wiki_path), "rm", "agents.yaml"]
                    )
                    if result.returncode != 0:
                        print("[migrate] ERROR: git rm agents.yaml failed", file=sys.stderr)
                        return 1

                    # git commit
                    result = _subprocess_util.run(
                        [
                            "git",
                            "-C",
                            str(wiki_path),
                            "commit",
                            "-m",
                            "chore(migrate): remove wiki/agents.yaml (moved to plugin template)",
                        ]
                    )
                    if result.returncode != 0:
                        if "nothing to commit" not in result.stdout and "nothing to commit" not in result.stderr:
                            print(
                                f"[migrate] ERROR: git commit failed: {result.stderr.strip()}",
                                file=sys.stderr,
                            )
                            return 1

                    # git push with rebase retry
                    result = _subprocess_util.run(
                        ["git", "-C", str(wiki_path), "push"]
                    )
                    if result.returncode != 0:
                        if "non-fast-forward" in result.stderr or "rejected" in result.stderr:
                            result = _subprocess_util.run(
                                ["git", "-C", str(wiki_path), "pull", "--rebase"]
                            )
                            if result.returncode != 0:
                                _subprocess_util.run(["git", "-C", str(wiki_path), "rebase", "--abort"])
                                print(
                                    f"[migrate] ERROR: git pull --rebase failed: {result.stderr.strip()}",
                                    file=sys.stderr,
                                )
                                return 1
                            result = _subprocess_util.run(
                                ["git", "-C", str(wiki_path), "push"]
                            )
                            if result.returncode != 0:
                                print(
                                    f"[migrate] ERROR: git push failed after rebase: {result.stderr.strip()}",
                                    file=sys.stderr,
                                )
                                return 1
                        else:
                            print(
                                f"[migrate] ERROR: git push failed: {result.stderr.strip()}",
                                file=sys.stderr,
                            )
                            return 1

                print("[migrate] wiki/agents.yaml identical to plugin template -- deleted and pushed")
            else:
                # Agents differ - warn and skip
                for name in wiki_data:
                    if name not in template_data or wiki_data[name] != template_data.get(name):
                        print(
                            f"[migrate] WARN: wiki/agents.yaml differs from plugin template -- entry '{name}' is unique or modified",
                            file=sys.stderr,
                        )
                print(
                    "[migrate] WARN: wiki/agents.yaml NOT deleted -- copy unique entries above into .millhouse/agents.local.yaml and re-run mill-setup",
                    file=sys.stderr,
                )

        # Step 6: Machine-config-removal notice
        print(
            "[migrate] note: the per-machine config layer (~/.millhouse/config.machine.yaml) has been removed -- if you previously kept overrides there, move them into this hub's .millhouse/config.local.yaml",
            file=sys.stderr,
        )

        return 0

    except Exception as exc:
        print(f"[migrate] ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
