# Batch: config-repo-layer

```yaml
task: "Fix wiki push upstream, cleanliness gate, mojibake, container config, and stacked-branch finalize"
batch: "config-repo-layer"
number: 2
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-config.py
depends-on: [1]
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

### Card 2: repo-layer config search in both load_config implementations

- **Context:**
  - `plugins/mill/scripts/_paths.py`
- **Edits:**
  - `plugins/mill/scripts/_config.py`
  - `plugins/mill/scripts/_review_common.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add a shared helper `resolve_repo_config_path(hub_root: Path,
  worktree_root: Path) -> Path | None` to `_config.py` that returns the first
  EXISTING file among: (1) `_paths.resolve_mill_config_path(hub_root)`; (2)
  `_paths.resolve_main_worktree_root(worktree_root) / "mill-config.yaml"`; (3)
  `worktree_root / "mill-config.yaml"`, or `None` when none exist. Do not
  hand-roll a `container / "wts" / repo` join — `resolve_main_worktree_root`
  already returns the primary-clone dir. Do not change
  `_paths.resolve_mill_config_path`'s signature or contract. Then rewire BOTH
  `load_config` implementations to use it:
  (a) In `_config.load_config`, replace the single
  `mill_cfg_path = _paths.resolve_mill_config_path(hub_root)` + `if
  mill_cfg_path.exists():` block with a call to `resolve_repo_config_path(hub_root,
  worktree_root)`; merge the returned file when non-None (preserving the existing
  merge order template -> repo layer -> local stub -> local real -> env
  overrides, and the `source_label` assignment); when None, emit a one-line ASCII
  note to stderr (e.g. `[_config] note: no repo-layer mill-config.yaml found ...`)
  so the layer is never silently dropped; do not raise.
  (b) In `_review_common.load_config` (the separate implementation around line
  1391, currently `mill_cfg_path = _paths.resolve_mill_config_path(hub_root)` at
  ~line 1419), replace that single-path resolution with the same
  `resolve_repo_config_path(hub_root, mill_dir)` call (import it from `_config`,
  which `_review_common` already imports from) so mill-go-driven reviewer/model
  selection honours container-layout repo overrides too. Preserve
  `_review_common.load_config`'s existing strict/lenient validation behaviour
  otherwise.
- **Commit:** `fix(config): resolve repo-layer mill-config.yaml in container layout (#470)`

### Card 3: container-layout config tests

- **Context:**
  - `plugins/mill/scripts/_config.py`
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-config.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `test-config.py`, add a test that builds a container/`wts`
  tempdir layout where `hub_root` is the container dir (no `mill-config.yaml` at
  hub root). The primary clone is a real `_git_init`'d repo at `<hub>/wts/<repo>/`
  carrying `<hub>/wts/<repo>/mill-config.yaml` with a
  `roles.discussion-review.holistic.reviewer: opushigh` override but NO
  `mill-config.yaml` in the task worktree itself. Add a LINKED worktree via `git
  -C <clone> worktree add <hub>/wts/<task-slug>` and pass that linked worktree as
  `worktree_root` so `resolve_main_worktree_root(worktree_root)` resolves to the
  primary clone (exercising candidate #2 distinctly from candidate #3, which
  would be the linked worktree's own absent config — this is the faithful #470
  task-worktree scenario). Call `load_config(hub_root=<container>,
  worktree_root=<linked-worktree>)` and assert it returns `opushigh`, not the
  template default. `load_config` does not call `resolve_wiki_path`, so no wiki
  stub is needed. Add a second test for the total-absence case (no repo-layer
  config in any of the three search locations): assert the template default is
  returned and that the "no repo-layer" note is written to stderr. Reuse the
  existing helpers (`_git_init`, `_write_yaml`, `_setup_plugin_template`) and
  harness style. Additionally add a parallel case asserting
  `_review_common.load_config(hub_root=<container>, mill_dir=<linked-worktree>)`
  resolves the same container-layout override (so the second implementation is
  covered too).
- **Commit:** `test(config): cover container-layout repo-config resolution (#470)`

## Batch Tests

`verify:` runs `test-config.py` only. The change is confined to
`_config.load_config`; `test-config.py` already covers the merge layers and is
the right home for the new container-layout and absence cases.
