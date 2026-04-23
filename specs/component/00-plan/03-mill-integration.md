# Batch: mill-integration

```yaml
task: codeguide sibling-mode + unified sibling-path convention
batch: mill-integration
cards: 5
verify: python plugins/mill/integration_tests/test-spawn.py && python plugins/mill/integration_tests/test-merge.py
depends-on: [foundation]
```

## Batch Scope

Rewire `mill-spawn` and `mill-setup` to call `_sibling.resolve_path` for their default sibling locations. Remove the token-template defaults from `wiki/config.yaml` (`<REPO>.worktrees`, `<REPO>.wiki/` documented default) so the helper is the single source of truth. Update the two integration-test fixtures (`test-spawn.py`, `test-merge.py`) to the new hub-form layout: test repo is named `hub/` so siblings become `worktrees/` and `wiki/` without the prefix.

Explicit `.millhouse/config.local.yaml` overrides (`spawn.worktrees_dir`, `wiki_path:`) continue to short-circuit the helper. Users with exotic setups keep their escape hatch.

## Cards

### Card 8: `mill-spawn.py` uses `_sibling.resolve_path("worktrees", ...)`

- **Reads:** `plugins/mill/scripts/mill-spawn.py`, `plugins/mill/scripts/_sibling.py` (post-Card-1), `plugins/mill/scripts/_worktree.py`.
- **Modifies:** `plugins/mill/scripts/mill-spawn.py`
- **Creates:** (none)
- **Requirements:**
  - Locate the current `_resolve_worktrees_dir` (or equivalent) function. Replace the `<REPO>.worktrees` token-template default with a direct call to `_sibling.resolve_path("worktrees", git_toplevel)`.
  - If `.millhouse/config.local.yaml` or wiki `config.yaml` explicitly sets `spawn.worktrees_dir`, that string continues to be token-substituted as today. Helper is only the FALLBACK default.
  - Import `_sibling` lazily inside the function body to keep existing import order stable.
  - Update the function's docstring to mention the helper and the hub-form rule.
  - No behaviour change for existing hub-form tests (test-spawn.py seeds `hub/` as repo; default helper returns `<container>/worktrees/`).
- **Commit:** `feat(mill-spawn): use _sibling.resolve_path for default worktrees path`

### Card 9: `mill-setup.py` uses `_sibling.resolve_path("wiki", ...)`

- **Reads:** `plugins/mill/scripts/mill-setup.py`, `plugins/mill/scripts/_sibling.py`, `plugins/mill/scripts/_wiki.py`.
- **Modifies:** `plugins/mill/scripts/mill-setup.py`
- **Creates:** (none)
- **Requirements:**
  - Find the current logic that defaults `wiki_path:` to `<CONTAINER_PATH>/<REPO>.wiki/`. Replace with `_sibling.resolve_path("wiki", git_toplevel)` when the key is absent in `.millhouse/config.local.yaml`.
  - Explicit `wiki_path:` overrides the helper — unchanged.
  - Docstring update.
  - If mill-setup's implementation does NOT currently carry a wiki_path default (only reads from config), this card is a no-op: document that the helper is available and leave behaviour unchanged.
- **Commit:** `feat(mill-setup): use _sibling.resolve_path for default wiki path`

### Card 10: drop `spawn.worktrees_dir` default from `wiki/config.yaml`

- **Reads:** `wiki/config.yaml`, `plugins/mill/scripts/mill-spawn.py` (post-Card-8).
- **Modifies:** `wiki/config.yaml`
- **Creates:** (none)
- **Requirements:**
  - Delete the line `worktrees_dir: <CONTAINER_PATH>/<REPO>.worktrees` from the `spawn:` block.
  - Update the preceding comment to describe the new behaviour: "`worktrees_dir` (optional) — absolute path or `<CONTAINER_PATH>/<REPO>.worktrees`-style template to override the default `_sibling.resolve_path('worktrees', repo_root)`. Omit to use the default (hub-form-aware)."
  - Leave `branch_prefix` unchanged.
  - Remove the obsolete `<WIKI_PATH>` documented default from the `junctions` block's header comment — replace with: "Default: `_sibling.resolve_path('wiki', repo_root)`."
- **Commit:** `config: drop worktrees_dir default; delegate to _sibling helper`

### Card 11: `test-spawn.py` aligns fixture to new layout

- **Reads:** `plugins/mill/integration_tests/test-spawn.py`, `plugins/mill/scripts/mill-spawn.py` (post-Card-8).
- **Modifies:** `plugins/mill/integration_tests/test-spawn.py`
- **Creates:** (none)
- **Requirements:**
  - The test's seeded wiki `config.yaml` currently includes `worktrees_dir: <CONTAINER_PATH>/<REPO>.worktrees`. After Card 10 this default is gone — the test must either continue to seed it explicitly (if we want to test the override path) or drop it (if we want to test the new default).
  - **Chosen:** drop the `spawn.worktrees_dir` line from the seeded config. Test the new default behaviour.
  - Update the assertion that checks the worktree path: expect `<container>/worktrees/<slug>/` (not `<container>/hub.worktrees/<slug>/`).
  - Similarly update any variable named `worktrees_dir` in the test body. Search for `hub.worktrees` literal strings and replace.
  - Keep the remaining fixture + assertions untouched.
- **Commit:** `test(spawn): update fixture to hub-form default (worktrees/ not hub.worktrees/)`

### Card 12: `test-merge.py` aligns fixture to new layout

- **Reads:** `plugins/mill/integration_tests/test-merge.py`, `plugins/mill/scripts/mill-spawn.py` (post-Card-8), `plugins/mill/integration_tests/test-spawn.py` (post-Card-11).
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
