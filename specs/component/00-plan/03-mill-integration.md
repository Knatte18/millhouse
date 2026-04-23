# Batch: mill-integration

```yaml
task: codeguide sibling-mode + unified sibling-path convention
batch: mill-integration
cards: 5
verify: python plugins/mill/integration_tests/test-spawn.py && python plugins/mill/integration_tests/test-merge.py
depends-on: [foundation]
```

## Batch Scope

Rewire `mill-spawn.py` and the `mill-setup` skill to call `_sibling.resolve_path` for their default sibling locations. Remove the token-template defaults from `wiki/config.yaml` so the helper is the single source of truth. Update the two integration-test fixtures (`test-spawn.py`, `test-merge.py`) to the new hub-form layout: test repo is named `hub/` so siblings become `worktrees/` and `wiki/` without the prefix.

Explicit `.millhouse/config.local.yaml` overrides (`spawn.worktrees_dir`, `wiki_path:`) continue to short-circuit the helper. Users with exotic setups keep their escape hatch.

**Important:** `mill-setup` is a skill (markdown prose), NOT a Python script. Its default wiki path lives inside the SKILL.md prose and must be fixed there — not in a non-existent `mill-setup.py`. Card 11 handles this.

## Cards

### Card 10: `mill-spawn.py` uses `_sibling.resolve_path("worktrees", ...)`

- **Reads:** `plugins/mill/scripts/mill-spawn.py`, `plugins/mill/scripts/_sibling.py` (post-Card-1), `plugins/mill/scripts/_worktree.py`, `wiki/config.yaml` (current `spawn.worktrees_dir` key).
- **Modifies:** `plugins/mill/scripts/mill-spawn.py`
- **Creates:** (none)
- **Requirements:**
  - Locate the existing worktrees-dir resolution logic. Currently it reads `cfg["spawn"]["worktrees_dir"]` as a token template (`<CONTAINER_PATH>/<REPO>.worktrees`) and substitutes. Preserve the override path: if `cfg["spawn"]` explicitly sets `worktrees_dir`, continue to use it as a token template (unchanged).
  - When the config key is ABSENT (new default path), call `_sibling.resolve_path("worktrees", git_toplevel)` from the imported `_sibling` module. Use the returned Path directly.
  - Import `_sibling` lazily inside the function body to keep existing import order stable.
  - Update the function's docstring to mention the helper and the hub-form rule.
  - No behaviour change for existing hub-form tests once Card 13 drops the seeded `worktrees_dir` key (test-spawn seeds `hub/` as repo; default helper returns `<container>/worktrees/`).
- **Commit:** `feat(mill-spawn): use _sibling.resolve_path for default worktrees path`

### Card 11: `mill-setup` SKILL.md uses `_sibling.py` CLI for default wiki path

- **Reads:** `plugins/mill/skills/mill-setup/SKILL.md`, `plugins/mill/scripts/_sibling.py` (post-Card-1), `plugins/mill/scripts/_wiki.py`, `plugins/mill/scripts/_junction.py`, `wiki/config.yaml` (the `<WIKI_PATH>` comment block and `junctions:` section).
- **Modifies:** `plugins/mill/skills/mill-setup/SKILL.md`
- **Creates:** (none)
- **Requirements:**
  - **The skill currently has internally-inconsistent wiki-path defaults.** Phase 3 reads: *"If `<container>/wiki/` does not exist: `git clone <wiki-url> <container>/wiki`"* — hardcoded hub-form. Phase 3.5 reads: *"`<WIKI_PATH>` — the wiki clone. Default: `<CONTAINER_PATH>/<REPO>.wiki/`"* — prefix-form. Both must become `_sibling.resolve_path("wiki", <hub-path>)`.
  - **Reconcile Phase 3:** Replace the hardcoded `<container>/wiki` with a computed path. Just before Phase 3, insert an explicit step: "Compute `<wiki-dir>` by invoking `python ${CLAUDE_PLUGIN_ROOT}/scripts/_sibling.py wiki <hub-path>`. Use the printed path as `<wiki-dir>` in Phases 3, 3.5, and 4."
  - **Reconcile Phase 3.5:** Update the `<WIKI_PATH>` bullet from *"Default: `<CONTAINER_PATH>/<REPO>.wiki/`"* to *"Default: the path computed by `_sibling.py wiki <hub-path>` above (hub-form → `<CONTAINER_PATH>/wiki/`; prefix-form → `<CONTAINER_PATH>/<REPO>.wiki/`). Override if `.millhouse/config.local.yaml` has a `wiki_path:` key."*
  - Preserve the existing `---` YAML frontmatter unchanged.
  - Preserve `wiki_path:` override semantics: if `.millhouse/config.local.yaml` sets it, that value wins over the helper's default.
  - Do NOT introduce any dependency on the mill scripts being importable from the skill (the skill is invoked where mill plugin IS installed, so `${CLAUDE_PLUGIN_ROOT}` is guaranteed).
- **Commit:** `feat(mill-setup): SKILL uses _sibling.py CLI for default wiki path`

### Card 12: drop `spawn.worktrees_dir` default from `wiki/config.yaml`

- **Reads:** `wiki/config.yaml`, `plugins/mill/scripts/mill-spawn.py` (post-Card-10).
- **Modifies:** `wiki/config.yaml`
- **Creates:** (none)
- **Requirements:**
  - Delete the line `worktrees_dir: <CONTAINER_PATH>/<REPO>.worktrees` from the `spawn:` block.
  - Update the preceding comment to describe the new behaviour: "`worktrees_dir` (optional) — absolute path or `<CONTAINER_PATH>/<REPO>.worktrees`-style template to override the default `_sibling.resolve_path('worktrees', repo_root)`. Omit to use the default (hub-form-aware)."
  - Leave `branch_prefix` unchanged.
  - Remove the obsolete `<WIKI_PATH>` documented default from the `junctions` block's header comment — replace with: "Default: `_sibling.resolve_path('wiki', repo_root)`."
- **Commit:** `config: drop worktrees_dir default; delegate to _sibling helper`

### Card 13: `test-spawn.py` aligns fixture to new layout

- **Reads:** `plugins/mill/integration_tests/test-spawn.py`, `plugins/mill/scripts/mill-spawn.py` (post-Card-10).
- **Modifies:** `plugins/mill/integration_tests/test-spawn.py`
- **Creates:** (none)
- **Requirements:**
  - The test's seeded wiki `config.yaml` currently includes `worktrees_dir: <CONTAINER_PATH>/<REPO>.worktrees`. After Card 12 this default is gone — the test either continues to seed it explicitly (to exercise the override path) or drops it (to exercise the new default).
  - **Chosen:** drop the `spawn.worktrees_dir` line from the seeded config. Test the new default behaviour.
  - Update the assertion that checks the worktree path: expect `<container>/worktrees/<slug>/` (not `<container>/hub.worktrees/<slug>/`).
  - Similarly update any variable named `worktrees_dir` in the test body. Search for `hub.worktrees` literal strings and replace.
  - Keep the remaining fixture + assertions untouched.
- **Commit:** `test(spawn): update fixture to hub-form default (worktrees/ not hub.worktrees/)`

### Card 14: `test-merge.py` aligns fixture to new layout

- **Reads:** `plugins/mill/integration_tests/test-merge.py`, `plugins/mill/scripts/mill-spawn.py` (post-Card-10), `plugins/mill/integration_tests/test-spawn.py` (post-Card-13).
- **Modifies:** `plugins/mill/integration_tests/test-merge.py`
- **Creates:** (none)
- **Requirements:**
  - Change `worktrees_dir = container / "hub.worktrees"` to `worktrees_dir = container / "worktrees"` in `_setup_trio`.
  - Update the hub-config seeded inside `_setup_trio` to drop the `spawn.worktrees_dir` line.
  - Update any assertion referencing the worktree path.
  - Everything else (Home.md flip, junction cleanup, merge lock) stays unchanged.
- **Commit:** `test(merge): update fixture to hub-form default`

## Batch Tests

Batch verify runs `test-spawn.py` and `test-merge.py` end-to-end. Both exercise the new path helper through real git ops. Pass criteria: both tests exit 0 with no assertion failures and no stray `hub.worktrees/` or `<repo>.worktrees/` paths in output.

Run order is sequential — `test-spawn.py` first (foundation for the layout), `test-merge.py` second (depends on spawn-style worktrees).

If either test fails, the implementer self-fixes up to `review.code.self_fix_rounds` attempts (2 per default config) before reporting stuck.
