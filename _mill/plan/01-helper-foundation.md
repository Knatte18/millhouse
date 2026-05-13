# Batch: helper-foundation

```yaml
task: (A) -- Add status_md to paths config + refactor 14 callsites
batch: helper-foundation
number: 1
cards: 3
verify: "uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py"
depends-on: []
```

## Batch Scope

This batch lays the foundation that every call site in batch 2 depends on: the new `paths.status_md` config key (in both the production wiki config and the template seed copied into new hubs), the `_paths.status_path` helper, and its unit-test surface. No call site is rewired in this batch -- the existing call sites continue to use `_paths.resolve_task_path(worktree, "_mill/status.md")` or local path arithmetic until batch 2 runs. That separation makes batch 1's diff small and reviewable (config + one helper + tests) and gives the reviewer a clear contract to validate before 14 call sites depend on it. The external interface batch 2 consumes is `_paths.status_path(worktree_root, cfg) -> Path` with the documented `KeyError` semantics.

The wiki/config.yaml mutation in card 1 is safe to ship mid-flight per the overview's `wiki-config-mutation-safety` shared decision: the new key has zero existing readers, every consumer is added in this same plan (batches 1 and 2), and stale plugin caches without the helper continue to hardcode their paths -- they do not read this key. The validator's `wiki-config-mutation` check will flag card 1; the validator-fix path in mill-plan's fix table allows proceeding with `--skip-check wiki-config-mutation` when a bootstrap card carrying the safety analysis is present, which card 1 is.

## Cards

### Card 1: Add `paths.status_md` to wiki/config.yaml and template

- **Context:** none
- **Edits:**
  - `wiki/config.yaml`
  - `plugins/mill/templates/wiki-config.yaml`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - In `wiki/config.yaml`, under the existing `paths:` block (currently containing `discussion_file`, `plan_dir`, `reviews_dir`), add a fourth row: `status_md: _mill/status.md`. Match the alignment of the surrounding rows (the value column is space-padded so values line up). Do not reorder existing rows.
  - In `plugins/mill/templates/wiki-config.yaml`, mirror the exact same addition under its `paths:` block. Both files must end up with the same four-key `paths:` block.
  - This is a bootstrap card per the overview's `wiki-config-mutation-safety` shared decision. The change is safe mid-flight because the key is purely additive: zero existing readers in `scripts/` or `skills/` reference `paths.status_md`, every consumer is added in this same plan (batches 1 and 2), and any stale plugin cache running pre-task code continues to hardcode the path -- nothing in the existing codebase reads this key. No backwards-compat-rollout layer is required.
- **Commit:** `paths: add status_md to wiki/config.yaml + template`

### Card 2: TDD unit tests for `_paths.status_path`

- **Context:**
  - `plugins/mill/unit_tests/test-paths.py`
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/unit_tests/run-all.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/unit_tests/test-paths-status.py`
- **Deletes:** none
- **Requirements:**
  - Create `plugins/mill/unit_tests/test-paths-status.py` mirroring the structure of `test-paths.py`: top-of-file `HUB = Path(__file__).resolve().parent.parent.parent.parent`, `SCRIPTS_DIR = HUB / "plugins" / "mill" / "scripts"`, `sys.path.insert(0, str(SCRIPTS_DIR))`, then `import _paths`. Define one function `test_status_path()` and call it from a `if __name__ == "__main__":` block at the bottom.
  - Inside `test_status_path()`, exercise five cases using `tempfile.TemporaryDirectory()` for the worktree fixture and a plain dict `cfg = {"paths": {"status_md": "_mill/status.md"}}` for the config (no `_config.load_config` call):
    1. Case 1: cfg has `paths.status_md` set, `<wt>/_mill/status.md` exists -> `_paths.status_path(wt, cfg)` returns `<wt>/_mill/status.md`. Capture stderr via `contextlib.redirect_stderr(io.StringIO())` and assert no `[compat]` substring.
    2. Case 2: cfg has `paths.status_md` set, `<wt>/_mill/status.md` missing, `<wt>/task/status.md` exists -> returns `<wt>/task/status.md` AND stderr contains `[compat]`.
    3. Case 3: cfg has `paths.status_md` set, neither file on disk -> returns `<wt>/_mill/status.md` (the configured target, even though it doesn't exist) AND stderr does not contain `[compat]`.
    4. Case 4: cfg is `{}` (no `paths` key) -> calling `_paths.status_path(wt, {})` raises `KeyError` whose `str()` contains `paths.status_md`.
    5. Case 5: cfg is `{"paths": {}}` (no `status_md` sub-key) -> raises `KeyError` whose `str()` contains `paths.status_md`.
  - Print `PASS status_path case <N>: <one-line description>` after each successful case, matching the cadence of `test_resolve_task_path` in `test-paths.py`.
  - The new file is automatically discovered by `plugins/mill/unit_tests/run-all.py` (which iterates `test-*.py`). No edit to `run-all.py` is required.
- **Commit:** `test(paths): add TDD cases for status_path helper`

### Card 3: Add `_paths.status_path` helper

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_paths.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - In `plugins/mill/scripts/_paths.py`, add a new public function `status_path(worktree_root: Path, cfg: dict) -> Path` immediately after the existing `resolve_task_path` function (which lives at lines 441-453 in the current file). The body reads `cfg["paths"]["status_md"]` and forwards: `return resolve_task_path(worktree_root, cfg["paths"]["status_md"])`. When the key is missing, raise `KeyError(f"paths.status_md missing from cfg; expected key under cfg['paths']")` -- catch both `cfg` lacking `"paths"` and `cfg["paths"]` lacking `"status_md"` by guarding with an explicit lookup that constructs the same message in either branch. Do not silently default to `_mill/status.md` -- the key is shipped by card 1.
  - Add a one-line docstring summarising the behaviour and pointing to `resolve_task_path` for the fallback semantics: `"""Return the status.md path for ``worktree_root`` driven by cfg['paths']['status_md'], with _mill/ -> task/ compat fallback via resolve_task_path."""`. ASCII-only per the overview's `ascii-only-log-strings` decision -- the docstring is exempt but no new operator-visible log lines should be added; the helper emits no stderr of its own.
  - Add `"status_path"` to the `__all__` list in the module (currently between `"resolve_active_hub"` and `"resolve_container_path"` -- the existing ordering groups by topic, so insert `"status_path"` near `"resolve_task_path"`).
  - Add an entry under the existing module-docstring's "Public API:" section (the header block above the `from __future__ import annotations` line) describing `status_path(worktree_root, cfg)`. Match the prose style of the surrounding entries (`resolve_task_path`, `resolve_hub_relative_path`).
  - Run `uv run --project plugins/mill python plugins/mill/unit_tests/test-paths-status.py` to confirm all five cases pass before commit.
- **Commit:** `feat(paths): add status_path helper driven by cfg['paths']['status_md']`

## Batch Tests

Verify command: `uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py`. The new test file `test-paths-status.py` exercises `_paths.status_path` directly (five cases per card 2). The existing `test-paths.py` still passes (no changes to `resolve_task_path`'s contract -- `status_path` is a wrapper that calls it). No other unit-test file imports `status_path` yet -- batch 2's call-site refactors are out of scope for this batch's verify.
