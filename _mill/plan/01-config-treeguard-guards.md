# Batch: config-treeguard-guards

```yaml
task: '_config.py / _treeguard.py: silently-ignored config keys and unguarded str-vs-Path args'
batch: config-treeguard-guards
number: 1
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-config.py test-treeguard.py
depends-on: []
```

## Batch Scope

This batch delivers both bug fixes from `_mill/discussion.md` in full: `_config.py`'s legacy-key warning gets a corrective hint (card 1), and `_treeguard.py`'s `check_and_restore` gets an argument-type guard (card 2). The two fixes are independent (different source files, no shared runtime code path) but small enough, and part of the same two-issue task, to implement as one batch. There is no external interface either card exposes to a later batch — this is the only batch in the plan.

## Cards

### Card 1: `_config.py` — name the correct key in the legacy-key warning

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_config.py`
  - `plugins/mill/unit_tests/test-config.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Add a new module-level constant `RENAMED_KEY_HINTS: dict[str, str]` in `_config.py`, placed immediately after the existing `ENV_REGISTRY` dict (the module-level table it follows as a placement precedent — this is a distinct dict, not an addition to `ENV_REGISTRY` itself):
  ```python
  RENAMED_KEY_HINTS = {
      "pipeline.max_review_rounds": "round caps now live at roles.<role>.<scope>.rounds, e.g. roles.plan-review.holistic.rounds -- this key has no effect",
      "pipeline.max_discussion_review_rounds": "round caps now live at roles.<role>.<scope>.rounds, e.g. roles.discussion-review.holistic.rounds -- this key has no effect",
  }
  ```
  Add `"RENAMED_KEY_HINTS"` to the module's existing `__all__` list, alongside `"ENV_REGISTRY"`.

  In `warn_unknown_keys`, change the loop body so an unknown path that is a key in `RENAMED_KEY_HINTS` gets the hint appended to its warning line, while every other unknown path (including anything in `deprecated_keys`) keeps exactly today's behavior. Replace:
  ```python
    unknown = walk_unknown_keys(actual, template)
    for path in unknown:
        if path not in deprecated_keys:
            print(f"[config] unknown key: {path} (in {source_label})", file=sys.stderr)
  ```
  with:
  ```python
      unknown = walk_unknown_keys(actual, template)
      for path in unknown:
          if path in deprecated_keys:
              continue
          hint = RENAMED_KEY_HINTS.get(path)
          if hint:
              print(f"[config] unknown key: {path} (in {source_label}) -- {hint}", file=sys.stderr)
          else:
              print(f"[config] unknown key: {path} (in {source_label})", file=sys.stderr)
  ```
  This is a behavior-preserving refactor of the `if path not in deprecated_keys:` guard into `if path in deprecated_keys: continue`, plus the new hint branch — no change to the `deprecated_keys` frozenset or to `walk_unknown_keys`.

  In `plugins/mill/unit_tests/test-config.py`, add two new test functions following the existing `test_unknown_key_warning_emitted` fixture shape (tempdir + `_git_init` + `patch("sys.stderr", new=io.StringIO())` + `_config.load_config(wt_root, wt_root)`), **but do NOT reuse `_setup_plugin_template`**: `_config.walk_unknown_keys` (lines 88-109) only descends into a nested dict when the key is present in `template` AND is itself a dict there — `_setup_plugin_template`'s fixture template has no `pipeline:` key at all, so an actual-config `pipeline.max_review_rounds` would surface as the single top-level unknown path `"pipeline"`, never the dotted `"pipeline.max_review_rounds"` the `RENAMED_KEY_HINTS` lookup needs, and both new tests would fail their hint assertions. Instead, each new test writes its own local plugin template containing a `pipeline: {}` key (an explicit empty mapping, so `isinstance(template.get("pipeline"), dict)` is `True` and `walk_unknown_keys` recurses into it) alongside the same `spawn:`/`git:`/`roles:` keys `_setup_plugin_template` already writes, and patches `_config.resolve_plugin_template_path` to return that local template's path — mirroring `test_worktree_template_augments_template_cfg`'s local-template-write pattern (lines 867-931), not `_setup_plugin_template`.
  - `test_renamed_key_hints_named_in_warning`: write both `pipeline.max_review_rounds` and `pipeline.max_discussion_review_rounds` into `.millhouse/config.local.yaml`, call `load_config`, and assert the captured stderr contains `"roles.plan-review.holistic.rounds"` (from the first key's hint) and `"roles.discussion-review.holistic.rounds"` (from the second key's hint).
  - `test_unrelated_unknown_key_no_hint_bleed`: write `pipeline.max_review_rounds` together with an unrelated unknown key under the same `pipeline:` block (e.g. `pipeline.some_unrecognized_key: true`, matching `test_unknown_key_warning_emitted`'s existing fixture key) into the same `config.local.yaml`, call `load_config`, split the captured stderr into lines, and assert: the line naming `pipeline.max_review_rounds` contains `"roles."`; the line naming `pipeline.some_unrecognized_key` does NOT contain `"roles."` (proving the hint is scoped to exactly the two named legacy keys and does not bleed onto an unrelated unknown key's message).

  Add both new test function names to the `tests` list inside `test-config.py`'s own `main()` function (the file's test-registration list, currently ending with `test_load_config_stub_misuse_no_warning_git_root_override_only,`), so `run-all.py`/direct invocation actually executes them.
- **Commit:** `fix(config): name the correct roles.<role>.<scope>.rounds key in the legacy pipeline.max_review_rounds/max_discussion_review_rounds unknown-key warning`

### Card 2: `_treeguard.py` — guard `check_and_restore`'s `worktree`/`git_root` arguments

- **Context:**
  - `plugins/mill/scripts/_status.py`
- **Edits:**
  - `plugins/mill/scripts/_treeguard.py`
  - `plugins/mill/unit_tests/test-treeguard.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `_treeguard.py`'s `check_and_restore(worktree: Path, tracked_root: str = "_mill", *, git_root: Path | None = None) -> dict`, add two `isinstance` guards as the function's first statements, before the existing `lines = _pygit2_util.status_porcelain(worktree, include_untracked=False)` line:
  ```python
      if not isinstance(worktree, Path):
          raise TypeError(f"check_and_restore: worktree must be a pathlib.Path, got {type(worktree).__name__}")
      if git_root is not None and not isinstance(git_root, Path):
          raise TypeError(f"check_and_restore: git_root must be a pathlib.Path, got {type(git_root).__name__}")
  ```
  `tracked_root` is unaffected — it is declared `str`, not `Path`, and is out of scope for this fix. The message format (`"{fn}: {arg} must be a pathlib.Path, got {type}"`) matches `_status.py`'s existing `_require_path` helper's message shape; do not import `_require_path` (private to `_status.py`) or add a new shared helper module — the two checks are written inline in `_treeguard.py`, matching this file's own existing convention of reimplementing a private helper locally rather than importing another module's underscore-prefixed internal (see `_rebase_onto_hub`'s docstring in this same file for the established precedent). `Path` is already imported at the top of `_treeguard.py` — no new import needed.

  In `plugins/mill/unit_tests/test-treeguard.py`, add two new scenarios inside `main()`, following the existing scenarios' shape (each a fenced `# --- Scenario N: ... ---` comment block followed by a `try`/`except`/`else` around the `check_and_restore` call, an `assert` on the message content, and a `print("PASS: ...")` line), placed after the last existing scenario and before the final `print("All _treeguard unit tests passed.")` line:
  - One scenario calling `check_and_restore("/some/str/path", "_mill")` (plain `str` in place of `worktree`) inside a `try`/`except TypeError as exc`/`else: raise AssertionError(...)` block, asserting `"worktree"` and `"pathlib.Path"` are both present in `str(exc)`.
  - One scenario calling `check_and_restore(Path("/some/worktree"), "_mill", git_root="/some/str/path")` (plain `str` for `git_root`, with a `Path` for `worktree` so the first guard passes and the second guard is what actually fires) inside the same `try`/`except TypeError as exc`/`else: raise AssertionError(...)` shape, asserting `"git_root"` and `"pathlib.Path"` are both present in `str(exc)`.
  Neither scenario needs `_seed_repo` — the guard raises before any git/filesystem access, so a non-existent `Path` literal is sufficient.
- **Commit:** `fix(treeguard): raise a clear TypeError on str worktree/git_root instead of a raw AttributeError deep in check_and_restore`

## Batch Tests

`verify:` runs `plugins/mill/unit_tests/run-all.py --only test-config.py test-treeguard.py` — the exact two files both cards touch. This exercises every existing test in both files (regression coverage for the surrounding `load_config`/`warn_unknown_keys`/`check_and_restore` behavior) plus the four new tests/scenarios this batch adds (two in `test-config.py`, two in `test-treeguard.py`).
