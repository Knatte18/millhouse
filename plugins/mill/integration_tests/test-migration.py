"""
Integration test for millpy-migrate-config.py.

Builds a hub+wiki fixture under .scratch/ with config.yaml and agents.yaml
and verifies the migration script handles: plain copy, skip-when-present,
identical agents deletion, different agents warning, and idempotency.

Run from hub root:
    python plugins/mill/integration_tests/test-migration.py

Exits 0 on PASS, 1 on any failure (scratch dir preserved for inspection).
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
SCRIPTS = HUB / "plugins" / "mill" / "scripts"
PLUGIN_ROOT = HUB / "plugins" / "mill"
SCRATCH = HUB / ".scratch"

sys.path.insert(0, str(SCRIPTS))
import _safe_rmtree  # noqa: E402


def _run(
    cmd: list[str], *, cwd: Path, check: bool = False, env_overrides: dict | None = None
) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    if env_overrides:
        env.update(env_overrides)
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        check=check,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )


def _git_init(repo: Path) -> None:
    _run(["git", "init", "-b", "main", str(repo)], cwd=repo.parent, check=True)
    _run(["git", "-C", str(repo), "config", "user.email", "test@example.com"], cwd=repo, check=True)
    _run(["git", "-C", str(repo), "config", "user.name", "Test"], cwd=repo, check=True)
    (repo / ".keep").write_text("", encoding="utf-8")
    _run(["git", "-C", str(repo), "add", ".keep"], cwd=repo, check=True)
    _run(["git", "-C", str(repo), "commit", "-m", "init"], cwd=repo, check=True)


def _make_hub_with_wiki(slug: str) -> tuple[Path, Path, Path]:
    """Create a test fixture with hub and wiki repos.

    Returns (hub_path, wiki_path, wiki_bare_path).
    """
    fixture_base = SCRATCH / "test-migration" / slug
    if fixture_base.exists():
        import shutil
        shutil.rmtree(fixture_base, ignore_errors=True)
    fixture_base.mkdir(parents=True, exist_ok=True)

    # Create wiki repo (will serve as the wiki clone)
    wiki_path = fixture_base / "wiki"
    _git_init(wiki_path)

    # Create bare remote for wiki (for push/pull testing)
    wiki_bare = fixture_base / "wiki.bare"
    _run(["git", "init", "--bare", str(wiki_bare)], cwd=fixture_base, check=True)
    (wiki_bare / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")

    # Add remote to wiki and push
    _run(["git", "-C", str(wiki_path), "remote", "add", "origin", str(wiki_bare)], cwd=fixture_base, check=True)
    _run(["git", "-C", str(wiki_path), "push", "-u", "origin", "main"], cwd=fixture_base, check=True)

    # Create hub
    hub_path = fixture_base / "hub"
    _git_init(hub_path)

    # Configure hub to point to wiki
    (hub_path / ".millhouse").mkdir(exist_ok=True)
    (hub_path / ".millhouse" / "config.local.yaml").write_text(
        f"paths:\n  wiki: {wiki_path.as_posix()}\n", encoding="utf-8"
    )

    return hub_path, wiki_path, wiki_bare


def test_config_migration_plain_copy() -> None:
    """Hub has no mill-config.yaml, wiki has config.yaml. Expect copy and wiki deletion."""
    hub, wiki, _ = _make_hub_with_wiki("plain-copy")
    fixture_base = wiki.parent

    # Create wiki/config.yaml with test content
    wiki_config = wiki / "config.yaml"
    wiki_config.write_text("key: from_wiki_yaml\n", encoding="utf-8")
    _run(["git", "-C", str(wiki), "add", "config.yaml"], cwd=wiki, check=True)
    _run(["git", "-C", str(wiki), "commit", "-m", "add config"], cwd=wiki, check=True)
    _run(["git", "-C", str(wiki), "push", "-u", "origin", "main"], cwd=fixture_base, check=True)

    # Run migration
    env = {"CLAUDE_PLUGIN_ROOT": str(PLUGIN_ROOT), "PYTHONPATH": str(SCRIPTS)}
    r = _run(
        [sys.executable, str(SCRIPTS / "millpy-migrate-config.py")],
        cwd=hub,
        env_overrides=env,
    )
    assert r.returncode == 0, f"migration failed: {r.stderr}"

    # Verify hub/mill-config.yaml exists and matches wiki's original
    hub_config = hub / "mill-config.yaml"
    assert hub_config.exists(), "mill-config.yaml not created"
    assert hub_config.read_text(encoding="utf-8") == "key: from_wiki_yaml\n", "content mismatch"

    # Verify it's staged
    r = _run(["git", "-C", str(hub), "diff", "--cached", "--name-only"], cwd=hub)
    assert "mill-config.yaml" in r.stdout, "mill-config.yaml not staged"

    # Verify wiki/config.yaml deleted
    assert not wiki_config.exists(), "wiki/config.yaml not deleted locally"

    # Verify wiki received the deletion
    r = _run(["git", "-C", str(wiki), "log", "--oneline", "config.yaml"], cwd=wiki)
    assert "remove wiki/config.yaml" in r.stdout or r.returncode != 0, "wiki deletion not committed"

    print("PASS: test_config_migration_plain_copy")


def test_config_migration_skip_copy_when_hub_already_has() -> None:
    """Hub already has mill-config.yaml. Expect wiki deletion but no copy."""
    hub, wiki, _ = _make_hub_with_wiki("skip-copy")
    fixture_base = wiki.parent

    # Create existing hub/mill-config.yaml with distinct content
    hub_config = hub / "mill-config.yaml"
    hub_config.write_text("key: from_hub_existing\n", encoding="utf-8")
    _run(["git", "-C", str(hub), "add", "mill-config.yaml"], cwd=hub, check=True)
    _run(["git", "-C", str(hub), "commit", "-m", "add config"], cwd=hub, check=True)

    # Create wiki/config.yaml
    wiki_config = wiki / "config.yaml"
    wiki_config.write_text("key: from_wiki_yaml\n", encoding="utf-8")
    _run(["git", "-C", str(wiki), "add", "config.yaml"], cwd=wiki, check=True)
    _run(["git", "-C", str(wiki), "commit", "-m", "add config"], cwd=wiki, check=True)
    _run(["git", "-C", str(wiki), "push", "-u", "origin", "main"], cwd=fixture_base, check=True)

    # Run migration
    env = {"CLAUDE_PLUGIN_ROOT": str(PLUGIN_ROOT), "PYTHONPATH": str(SCRIPTS)}
    r = _run(
        [sys.executable, str(SCRIPTS / "millpy-migrate-config.py")],
        cwd=hub,
        env_overrides=env,
    )
    assert r.returncode == 0, f"migration failed: {r.stderr}"

    # Verify hub config unchanged
    assert hub_config.read_text(encoding="utf-8") == "key: from_hub_existing\n", "hub config was overwritten"

    # Verify wiki/config.yaml deleted
    assert not wiki_config.exists(), "wiki/config.yaml not deleted"

    print("PASS: test_config_migration_skip_copy_when_hub_already_has")


def test_agents_migration_identical_deletes() -> None:
    """wiki/agents.yaml identical to plugin template. Expect deletion."""
    hub, wiki, _ = _make_hub_with_wiki("agents-identical")
    fixture_base = wiki.parent

    # Create wiki/agents.yaml with content identical to plugin template
    template_path = PLUGIN_ROOT / "templates" / "mill-agents.yaml"
    template_content = template_path.read_text(encoding="utf-8")
    wiki_agents = wiki / "agents.yaml"
    wiki_agents.write_text(template_content, encoding="utf-8")
    _run(["git", "-C", str(wiki), "add", "agents.yaml"], cwd=wiki, check=True)
    _run(["git", "-C", str(wiki), "commit", "-m", "add agents"], cwd=wiki, check=True)
    _run(["git", "-C", str(wiki), "push", "-u", "origin", "main"], cwd=fixture_base, check=True)

    # Run migration
    env = {"CLAUDE_PLUGIN_ROOT": str(PLUGIN_ROOT), "PYTHONPATH": str(SCRIPTS)}
    r = _run(
        [sys.executable, str(SCRIPTS / "millpy-migrate-config.py")],
        cwd=hub,
        env_overrides=env,
    )
    assert r.returncode == 0, f"migration failed: {r.stderr}"

    # Verify wiki/agents.yaml deleted
    assert not wiki_agents.exists(), "wiki/agents.yaml not deleted"

    # Verify no warnings on stderr
    assert "WARN" not in r.stderr, f"unexpected warning: {r.stderr}"

    print("PASS: test_agents_migration_identical_deletes")


def test_agents_migration_different_warns_and_skips() -> None:
    """wiki/agents.yaml has extra entry. Expect warning and skip."""
    hub, wiki, _ = _make_hub_with_wiki("agents-different")
    fixture_base = wiki.parent

    # Create wiki/agents.yaml with extra entry
    wiki_agents = wiki / "agents.yaml"
    wiki_agents.write_text("custom_agent:\n  model: custom\n  provider: custom\n  type: single\n", encoding="utf-8")
    _run(["git", "-C", str(wiki), "add", "agents.yaml"], cwd=wiki, check=True)
    _run(["git", "-C", str(wiki), "commit", "-m", "add agents"], cwd=wiki, check=True)
    _run(["git", "-C", str(wiki), "push", "-u", "origin", "main"], cwd=fixture_base, check=True)

    # Run migration
    env = {"CLAUDE_PLUGIN_ROOT": str(PLUGIN_ROOT), "PYTHONPATH": str(SCRIPTS)}
    r = _run(
        [sys.executable, str(SCRIPTS / "millpy-migrate-config.py")],
        cwd=hub,
        env_overrides=env,
    )
    assert r.returncode == 0, f"migration should not fail: {r.stderr}"

    # Verify wiki/agents.yaml NOT deleted
    assert wiki_agents.exists(), "wiki/agents.yaml should not be deleted when different"

    # Verify warnings on stderr
    assert "WARN" in r.stderr, "warning not printed for different agents"
    assert "custom_agent" in r.stderr, "custom entry name not mentioned in warning"

    print("PASS: test_agents_migration_different_warns_and_skips")


def test_idempotency() -> None:
    """Run migration twice. Second run should be a no-op."""
    hub, wiki, _ = _make_hub_with_wiki("idempotency")
    fixture_base = wiki.parent

    # Create wiki/config.yaml and agents.yaml (identical to template)
    wiki_config = wiki / "config.yaml"
    wiki_config.write_text("key: test\n", encoding="utf-8")
    template_path = PLUGIN_ROOT / "templates" / "mill-agents.yaml"
    template_content = template_path.read_text(encoding="utf-8")
    wiki_agents = wiki / "agents.yaml"
    wiki_agents.write_text(template_content, encoding="utf-8")
    _run(["git", "-C", str(wiki), "add", "."], cwd=wiki, check=True)
    _run(["git", "-C", str(wiki), "commit", "-m", "init"], cwd=wiki, check=True)
    _run(["git", "-C", str(wiki), "push", "-u", "origin", "main"], cwd=fixture_base, check=True)

    # First run
    env = {"CLAUDE_PLUGIN_ROOT": str(PLUGIN_ROOT), "PYTHONPATH": str(SCRIPTS)}
    r1 = _run(
        [sys.executable, str(SCRIPTS / "millpy-migrate-config.py")],
        cwd=hub,
        env_overrides=env,
    )
    assert r1.returncode == 0, f"first run failed: {r1.stderr}"

    # Get wiki commit count after first run
    r = _run(["git", "-C", str(wiki), "rev-list", "--count", "HEAD"], cwd=wiki)
    count_after_first = int(r.stdout.strip())

    # Second run
    r2 = _run(
        [sys.executable, str(SCRIPTS / "millpy-migrate-config.py")],
        cwd=hub,
        env_overrides=env,
    )
    assert r2.returncode == 0, f"second run failed: {r2.stderr}"

    # Verify no new commits in wiki
    r = _run(["git", "-C", str(wiki), "rev-list", "--count", "HEAD"], cwd=wiki)
    count_after_second = int(r.stdout.strip())
    assert count_after_second == count_after_first, "second run created new commits (should be idempotent)"

    print("PASS: test_idempotency")


def main() -> int:
    SCRATCH.mkdir(parents=True, exist_ok=True)
    failed = False

    test_cases = [
        test_config_migration_plain_copy,
        test_config_migration_skip_copy_when_hub_already_has,
        test_agents_migration_identical_deletes,
        test_agents_migration_different_warns_and_skips,
        test_idempotency,
    ]

    for test in test_cases:
        try:
            test()
        except AssertionError as exc:
            print(f"FAIL: {test.__name__}: {exc}", file=sys.stderr)
            failed = True
        except Exception as exc:
            print(f"FAIL: {test.__name__}: {exc}", file=sys.stderr)
            import traceback
            traceback.print_exc(file=sys.stderr)
            failed = True

    # Clean up on success
    if not failed:
        _safe_rmtree.safe_rmtree(SCRATCH / "test-migration", allowed_root=SCRATCH / "test-migration", ignore_errors=True)
        print("\nAll test-migration assertions passed.")
    else:
        print(f"\nFixture preserved at: {SCRATCH / 'test-migration'}", file=sys.stderr)

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
