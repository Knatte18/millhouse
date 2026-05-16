# Batch: wiki-helpers-post-migration

```yaml
task: 57 (A) -- Move config.yaml and agents.yaml from wiki to hub worktree
batch: wiki-helpers-post-migration
number: 5
cards: 2
verify: python plugins/mill/unit_tests/test-wiki.py
depends-on: [1, 2]
```

## Batch Scope

This batch retargets three `_wiki.py` helpers that read `wiki/config.yaml` directly so they keep working after migration removes that file. The three helpers are `_wiki.read_junctions`, `_wiki.read_hardlinks` (both used by mill-setup and mill-cleanup to enumerate the junction/hardlink set for safe worktree removal), and `_wiki.health_check` (called at the start of every mill-go batch and every holistic review round).

Without this batch the migration is a foot-gun: post-migration `_wiki.read_junctions(wiki_root)` returns `_JUNCTION_DEFAULTS = {".wiki": "<WIKI_PATH>"}` only -- silently dropping `.portals` and `.active`. CLAUDE.md issue #100 documents the consequence: `millpy-cleanup.py`'s long-path fallback (`rmdir /s /q`) follows the unstipped junctions into the real portals directory and sibling worktrees, wiping them. Separately, `_wiki.health_check` raises `WikiHealthError` whenever `wiki/config.yaml` is missing, so every mill-go batch on a migrated hub fails.

The batch reads YAML directly (no dependency on the refactored `load_config`), so it does not need batch 2's loader rewrites; however batch 2 also edits `millpy-cleanup.py`, so this batch depends on batch 2 to serialise the cleanup-file edits. The batch is independent of batch 3 (migration script and `mill-setup/SKILL.md` edits are not touched here) and of batch 4 (deletions).

Batch-local decisions:

- The three helpers gain a new signature that takes `hub_root: Path` as the primary argument and resolve the wiki via `_paths.resolve_wiki_path(hub_root)` internally for the legacy fallback. The old `wiki_root` parameter name is replaced with `hub_root`; callers are updated. This is preferable to keeping a parallel `(wiki_root, hub_root)` signature because it keeps the helper's primary input aligned with where the config now lives.
- `read_junctions` and `read_hardlinks` read the `junctions:` and `hardlinks:` blocks from `hub_root/mill-config.yaml` first. If that file is absent, they fall back to `_paths.resolve_wiki_path(hub_root)/config.yaml` (legacy hub during in-flight migration). If neither exists, they return the existing default empty/baseline dicts -- behaviour for unconfigured hubs is unchanged.
- `health_check` is renamed to verify "at least one valid config source exists" rather than insisting on `wiki/config.yaml` specifically. The check passes when `hub_root/mill-config.yaml` exists OR `_paths.resolve_wiki_path(hub_root)/config.yaml` exists. The `WikiHealthError` message names both searched paths so the operator can see which source they need to provide.
- mill-go SKILL.md call sites at lines ~120 and ~296 are updated to compute `hub_root = _paths.resolve_git_root()` instead of `wiki_path = _paths.resolve_wiki_path(...)` and pass that to `_wiki.health_check`. The exception class and overall control flow stay the same.

## Cards

### Card 23: Retarget `_wiki.read_junctions` and `_wiki.read_hardlinks` to hub `mill-config.yaml`

- **Context:**
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/templates/mill-config.yaml`
- **Edits:**
  - `plugins/mill/scripts/_wiki.py`
  - `plugins/mill/scripts/millpy-cleanup.py`
  - `plugins/mill/scripts/_setup.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `_wiki.py`, change both helpers' signatures from `(wiki_root: Path)` to `(hub_root: Path)`. Rewrite each body to:

  1. Build `mill_cfg_path = hub_root / "mill-config.yaml"`. If `mill_cfg_path.exists()`, load it via `yaml.safe_load(...)`.
  2. Else, try `_paths.resolve_wiki_path(hub_root)`; if that succeeds AND `<wiki>/config.yaml` exists, load it. Wrap the `resolve_wiki_path` call in `try: ... except SystemExit: wiki_cfg_path = None` to tolerate hubs with no configured wiki sibling.
  3. Else return the helper's existing default (`_JUNCTION_DEFAULTS` for `read_junctions`, empty dict for `read_hardlinks`).
  4. From the loaded yaml dict, extract the `junctions:` (or `hardlinks:`) block and return per the existing return-shape contract. Preserve the existing "missing block -> defaults" branch.

  Update each helper's docstring to reflect the new precedence (hub mill-config.yaml -> legacy wiki/config.yaml -> defaults).

  Update the two call sites:

  - `millpy-cleanup.py:611` -- replace `junctions_cfg = _wiki.read_junctions(wiki_path)` with `junctions_cfg = _wiki.read_junctions(git_root)`. `git_root` is already in scope at line ~592. If `wiki_path` becomes unused after this edit, leave its computation in place because other code in the file uses it (lines 593-610 etc.); do NOT remove `wiki_path`.
  - `_setup.py:83-84` -- inside `create_hub_links`, replace the two helper calls `_wiki.read_junctions(wiki_path)` and `_wiki.read_hardlinks(wiki_path)` with calls that pass the hub repo root. Derive it inside the function body: add `import _paths` to the file's imports if not present, then add `hub_root = _paths.resolve_git_root()` at the top of the `create_hub_links` body and pass `hub_root` to both helpers. This is correct in mill-setup's call context: Phase 4 invokes `create_hub_links` with cwd = hub_path, and `_paths.resolve_git_root()` returns the git toplevel of the cwd (the repo root, which is where `mill-config.yaml` lives). The existing `wiki_path` parameter on `create_hub_links` stays -- it is still used by callers and other internals. Do NOT edit `plugins/mill/skills/mill-setup/SKILL.md` in this card: the `create_hub_links` signature is unchanged from the caller's perspective. Re-grep `_wiki.read_junctions(` and `_wiki.read_hardlinks(` at the end -- the only references MUST be the function definitions plus the two updated call sites.
- **Commit:** `refactor(wiki): read junctions/hardlinks from hub mill-config.yaml`

### Card 24: Retarget `_wiki.health_check` to accept either config source; add `test-wiki.py`

- **Context:**
  - `plugins/mill/scripts/_paths.py`
- **Edits:**
  - `plugins/mill/scripts/_wiki.py`
  - `plugins/mill/skills/mill-go/SKILL.md`
  - `plugins/mill/unit_tests/test-wiki.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `_wiki.py`, change `health_check`'s signature from `(wiki_path: Path)` to `(hub_root: Path)`. Rewrite the body to verify that at least one config source exists:

  1. Compute `mill_cfg = hub_root / "mill-config.yaml"`.
  2. Try `wiki_root = _paths.resolve_wiki_path(hub_root)` inside `try: ... except SystemExit: wiki_root = None`; if `wiki_root` is not None, compute `wiki_cfg = wiki_root / "config.yaml"`, else `wiki_cfg = None`.
  3. If `not hub_root.exists()`, raise `WikiHealthError(hub_root, f"hub directory does not exist at {hub_root}")` -- preserve the "hub-must-exist" gate (rename the error's first arg accordingly; the `WikiHealthError` class itself stays unchanged, only the constructed message reflects the new precedence).
  4. If `mill_cfg.exists()`, return None (success).
  5. Elif `wiki_cfg is not None and wiki_cfg.exists()`, return None (success, legacy hub).
  6. Else raise `WikiHealthError(hub_root, f"no config source found: searched {mill_cfg} and {wiki_cfg}")`. ASCII only.

  Update the docstring: drop the "`wiki/config.yaml` missing ..." raise-list line; add a new raise-list line documenting the "no config source" message and the two paths searched. The `Args` block documents `hub_root` (was `wiki_path`).

  Update mill-go SKILL.md at the two call sites (approximately lines 115-124 and 290-300 in the current file). Each call site currently does `wiki_path = _paths.resolve_wiki_path(_paths.resolve_git_root())` then `_wiki.health_check(wiki_path)`. Replace with `hub_root = _paths.resolve_git_root()` then `_wiki.health_check(hub_root)`. The `_wiki.WikiHealthError` exception handling stays unchanged. The error message printed by the script handler ("wiki health check failed") may stay -- the operator-facing string is informational. The HALT recovery message at line ~302 ("re-run mill-setup to restore it") still applies; no change required.

  After all edits, re-grep `_wiki.health_check(` across `plugins/` -- the only references MUST be the function definition and the two mill-go SKILL.md call sites.

  **IMPORTANT -- existing file:** `plugins/mill/unit_tests/test-wiki.py` already exists with ~426 lines covering `wiki_lock`, re-entrancy, stale-self-lock, `sync_pull`, `write_commit_push`, `clone_or_init` (8 scenarios), and `health_check`. Do NOT create a new file or overwrite it. Read the existing file first to understand the test framework and runner pattern, then APPEND the following new test functions to the existing file (add them to the `main()` test list too):

  - `test_read_junctions_from_mill_config` -- create `tmp_hub / "mill-config.yaml"` with a `junctions:` block (e.g. `{".wiki": "<WIKI_PATH>", ".portals": "../portals"}`); call `_wiki.read_junctions(tmp_hub)`; assert the returned dict contains both junction entries.
  - `test_read_junctions_falls_back_to_wiki` -- monkeypatch `_paths.resolve_wiki_path` to return a sibling tmp dir; write `<wiki>/config.yaml` with a `junctions:` block; ensure no `mill-config.yaml` at hub root; call `_wiki.read_junctions(tmp_hub)`; assert the wiki-sourced block is returned.
  - `test_health_check_passes_when_mill_config_present` -- create `tmp_hub / "mill-config.yaml"` (touch, no content needed); call `_wiki.health_check(tmp_hub)`; assert no exception.
  - `test_health_check_passes_when_wiki_config_present` -- no `mill-config.yaml` at hub root; monkeypatch `_paths.resolve_wiki_path` to return a sibling tmp dir; write `<wiki>/config.yaml` (touch); call `_wiki.health_check(tmp_hub)`; assert no exception.
  - `test_health_check_raises_when_neither_present` -- no `mill-config.yaml`, monkeypatch `_paths.resolve_wiki_path` to raise `SystemExit`; call `_wiki.health_check(tmp_hub)`; assert `WikiHealthError` is raised.

  Match the monkeypatching style already used in the existing file (the existing tests patch `_subprocess_util.run` via `unittest.mock.patch`; use the same mechanism to patch `_paths.resolve_wiki_path`). All five appended tests use `tempfile.TemporaryDirectory` for fixtures; no real git, no real wiki. Keep the appended section under 100 lines.
- **Commit:** `refactor(wiki): health_check accepts hub_root with mill-config.yaml or wiki fallback`

## Batch Tests

The `verify:` runs `test-wiki.py` if it exists in the unit-tests dir; if not, the verify command should be relaxed to `python plugins/mill/unit_tests/run-all.py` so the change is covered by adjacent tests of callers (`test-cleanup.py`, `test-setup.py`, etc.) plus the integration tests. The implementer should add minimal new test cases in `test-wiki.py` if the file exists OR create it with three tests covering: (a) `read_junctions` returns hub-config junctions when `mill-config.yaml` exists; (b) `read_junctions` falls back to wiki when only legacy file exists; (c) `health_check` succeeds when either source exists and raises when neither does. Keep the new test file under 100 lines.
