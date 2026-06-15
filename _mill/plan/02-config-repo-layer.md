# Batch: config-repo-layer

```yaml
task: "Fix wiki push upstream, cleanliness gate, mojibake, container config, and stacked-branch finalize"
batch: "config-repo-layer"
number: 2
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-config.py
depends-on: []
```

## Batch Scope

Fixes GitHub issue #470: `_config.load_config` resolves the repo-layer
`mill-config.yaml` only at `<hub_root>/mill-config.yaml`. In container/`wts`
layout (hub is the container dir) that path does not exist, so per-repo
`roles.*` overrides are silently dropped and template defaults win. Broaden the
resolution to search the primary clone and the worktree, and emit a visible
note when no repo-layer config is found anywhere. Add tests for the
container-layout and total-absence cases.

## Cards

### Card 2: repo-layer config search in load_config

- **Context:**
  - `plugins/mill/scripts/_paths.py`
- **Edits:**
  - `plugins/mill/scripts/_config.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `_config.load_config`, replace the single repo-layer
  resolution (`mill_cfg_path = _paths.resolve_mill_config_path(hub_root)`
  followed by the `if mill_cfg_path.exists():` merge) with an ordered search
  that merges the first existing file from: (1)
  `_paths.resolve_mill_config_path(hub_root)`; (2)
  `_paths.resolve_main_worktree_root(worktree_root) / "mill-config.yaml"`; (3)
  `worktree_root / "mill-config.yaml"`. Do not hand-roll a `container / "wts" /
  repo` join — `resolve_main_worktree_root` already returns the primary-clone
  dir. Preserve the existing merge order (template -> repo layer -> local stub
  -> local real -> env overrides) and the `source_label` assignment. When none
  of the three candidates exists, emit a one-line ASCII note to stderr (e.g.
  `[_config] note: no repo-layer mill-config.yaml found ...`) so the layer is
  never silently dropped; do not raise. Do not change
  `_paths.resolve_mill_config_path`'s signature or contract.
- **Commit:** `fix(config): resolve repo-layer mill-config.yaml in container layout (#470)`

### Card 3: container-layout config tests

- **Context:**
  - `plugins/mill/scripts/_config.py`
  - `plugins/mill/scripts/_paths.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-config.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `test-config.py`, add a test that builds a container/`wts`
  tempdir layout where `hub_root` is the container dir (no `mill-config.yaml` at
  hub root) and the primary clone is a real `_git_init`'d repo at
  `<hub>/wts/<repo>/` (so `resolve_main_worktree_root(worktree_root)` resolves to
  that clone — candidate #2) carrying a
  `<hub>/wts/<repo>/mill-config.yaml` with a
  `roles.discussion-review.holistic.reviewer: opushigh` override; call
  `load_config(hub_root=<container>, worktree_root=<clone>)` and assert it
  returns `opushigh`, not the template default. `load_config` does not call
  `resolve_wiki_path`, so no wiki stub is needed; the clone must be a genuine git
  repo because `resolve_main_worktree_root` walks git. Add a second test for the
  total-absence case (no repo-layer config in any of the three search locations):
  assert the template default is returned and that the "no repo-layer" note is
  written to stderr. Reuse the existing helpers (`_git_init`, `_write_yaml`,
  `_setup_plugin_template`) and harness style.
- **Commit:** `test(config): cover container-layout repo-config resolution (#470)`

## Batch Tests

`verify:` runs `test-config.py` only. The change is confined to
`_config.load_config`; `test-config.py` already covers the merge layers and is
the right home for the new container-layout and absence cases.
