# Batch: helper-api

```yaml
task: "Sub-project repo (hub_relative_path) support"
batch: "helper-api"
number: 1
cards: 6
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py
depends-on: []
```

## Batch Scope

This batch establishes the helper API surface that every later batch consumes. Three production-code changes are TDD-driven: `_config.load_config` raise-removal, `resolve_ref_paths` git_root fallback, `resolve_existing_paths` git_root fallback. Two changes are pure renames: `_paths.resolve_mill_config_path` and `_review_common.load_config` first-arg `repo_root` → `hub_root`. One card adds a `resolve_active_hub` sub-project test in `test-paths.py` to lock in the helper's `hub_relative_path != "."` behaviour. No call sites are touched in this batch — that is batch 2's scope. The external interface that batches 2 and 3 consume is: the renamed positional arg `hub_root` (still positional, no kw-only) and the new `git_root: Path | None = None` kwarg on both `resolve_ref_paths` and `resolve_existing_paths`.

Batch-local decisions:
- Production-code edits and their unit tests live in the same card; tests are written first per the Shared Decision "TDD for new helper behaviour".
- The `FileNotFoundError` raise removal in `_config.load_config` is replaced by a no-op skip; no warning, no stderr message, no debug log.

## Cards

### Card 1: rename `_config.load_config` first arg and remove the missing-overlay raise

- **Context:**
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/templates/mill-config.yaml`
- **Edits:**
  - `plugins/mill/scripts/_config.py`
  - `plugins/mill/unit_tests/test-config.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `plugins/mill/scripts/_config.py`'s `load_config` function (currently `load_config(repo_root: Path, worktree_root: Path) -> dict`): rename the first positional parameter from `repo_root` to `hub_root` throughout the function — signature, docstring, every internal reference, and any error messages that name the parameter. Then remove the `FileNotFoundError` raise that fires when `_paths.resolve_mill_config_path(hub_root)` does not exist; replace it with a no-op skip of the hub-overlay merge step (continue with template defaults + later layers). Do not add stderr warnings or debug logs for the missing-file case — template-only is a valid configuration. In `plugins/mill/unit_tests/test-config.py`, add two test functions: `test_load_config_no_hub_overlay_returns_template` (constructs a tmp dir with no `mill-config.yaml`, calls `load_config(tmp_dir, tmp_dir)`, asserts the returned dict matches the plugin template defaults and does not raise) and `test_load_config_sub_project_hub_overlay` (constructs a fixture where `hub_root = <tmp>/projects/sub` with a custom `mill-config.yaml` declaring a non-default key, and `worktree_root` is the outer dir with no `.millhouse/config.local.yaml`; asserts the hub-overlay value wins over the template). Both tests must follow the TDD rule: write the test first, confirm it fails for the expected reason, then make the production change and confirm it passes.
- **Commit:** `refactor(_config): rename load_config first arg to hub_root; drop overlay-required raise`

### Card 2: rename `_paths.resolve_mill_config_path` first arg

- **Context:**
  - `plugins/mill/scripts/_config.py`
- **Edits:**
  - `plugins/mill/scripts/_paths.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `plugins/mill/scripts/_paths.py`'s `resolve_mill_config_path` function (currently `def resolve_mill_config_path(repo_root: Path) -> Path:`): rename the parameter from `repo_root` to `hub_root`. Update the docstring's argument description so the prose matches: `Args: hub_root: Absolute path to the hub directory ...`. No behavioural change. The function body has exactly one reference to the renamed argument (`return repo_root / "mill-config.yaml"` → `return hub_root / "mill-config.yaml"`).
- **Commit:** `refactor(_paths): rename resolve_mill_config_path arg to hub_root`

### Card 3: rename `_review_common.load_config` first arg

- **Context:**
  - `plugins/mill/scripts/_config.py`
  - `plugins/mill/scripts/_paths.py`
- **Edits:**
  - `plugins/mill/scripts/_review_common.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `plugins/mill/scripts/_review_common.py`'s `load_config` function (currently `def load_config(repo_root: Path, mill_dir: Path) -> dict:`): rename the first positional parameter from `repo_root` to `hub_root`. Update signature, docstring `Args:` line, and any internal references in the function body. The second parameter `mill_dir` is left unchanged (its name is correct per discussion.md `## Out:`). No behavioural change. The function does NOT raise on missing `<hub_root>/mill-config.yaml` either — verify the existing code already tolerates the missing file (read the function body during implementation; if it raises, mirror card 1's no-op-skip fix).
- **Commit:** `refactor(_review_common): rename load_config first arg to hub_root`

### Card 4: add `git_root` kwarg + fallback to `resolve_ref_paths`

- **Context:**
  - `plugins/mill/scripts/_review_code.py`
  - `plugins/mill/scripts/_review_plan.py`
- **Edits:**
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/unit_tests/test-review-common.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `plugins/mill/scripts/_review_common.py`, extend `resolve_ref_paths`'s signature with a new keyword arg `git_root: Path | None = None` placed before `caller_label`. Inside the per-raw loop, after the existing `if candidate.exists(): resolved.append(...); continue` block and BEFORE the creates_union/deletes_union suppression check, add: when `git_root is not None`, compute `gr_candidate = git_root / raw`; if `gr_candidate.exists()` then `resolved.append(gr_candidate); continue`. The wiki/-prefix branch is untouched; the fallback only fires for non-wiki paths that miss under `project_root / root`. Update the docstring to document the new precedence order: wiki/ prefix → project_root → git_root → creates/deletes suppression → ReviewError. Add five test functions in `plugins/mill/unit_tests/test-review-common.py`: `test_resolve_ref_paths_git_root_fallback_hit`, `test_resolve_ref_paths_git_root_fallback_miss`, `test_resolve_ref_paths_no_git_root_kwarg`, `test_resolve_ref_paths_creates_union_precedence`, `test_resolve_ref_paths_wiki_prefix_unaffected`. Behaviour per discussion.md `## Testing`: hit returns `git_root / raw`; miss raises `ReviewError`; no kwarg preserves current behaviour; creates_union suppresses even when both project_root and git_root miss; wiki/-prefixed paths still route through `wiki_root` and ignore `git_root`. Write tests first, confirm they fail for the expected reason, then make the production change.
- **Commit:** `feat(_review_common): add git_root fallback to resolve_ref_paths`

### Card 5: add `git_root` kwarg + fallback to `resolve_existing_paths`

- **Context:**
  - `plugins/mill/scripts/_review_code.py`
  - `plugins/mill/scripts/_review_plan.py`
- **Edits:**
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/unit_tests/test-review-common.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `plugins/mill/scripts/_review_common.py`, extend `resolve_existing_paths`'s signature with a new keyword arg `git_root: Path | None = None`. Apply the identical fallback logic to that of card 4: after the project_root candidate misses, try `git_root / raw` when `git_root is not None`; on hit, append and continue; on miss, fall through to the existing silent-drop behaviour. The function continues to silently drop paths that exist nowhere (unchanged). Update the docstring to document the new precedence (wiki/ → project_root → git_root → silent drop). Add three test functions in `plugins/mill/unit_tests/test-review-common.py`: `test_resolve_existing_paths_git_root_fallback_hit` (returns `git_root / raw`), `test_resolve_existing_paths_git_root_fallback_miss` (silently drops, no raise), `test_resolve_existing_paths_no_git_root_kwarg` (current behaviour unchanged). Write tests first, confirm failure, implement.
- **Commit:** `feat(_review_common): add git_root fallback to resolve_existing_paths`

### Card 6: lock in `resolve_active_hub` sub-project coverage in `test-paths.py`

- **Context:**
  - `plugins/mill/scripts/_paths.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-paths.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Read the existing `plugins/mill/unit_tests/test-paths.py`. If a test already exercises `_paths.resolve_active_hub` with `hub_relative_path != "."` (a sub-project layout), no edit needed beyond confirming the test is present and rename-resilient — but the card still verifies and documents the finding in its commit message. If no such test exists, add `test_resolve_active_hub_sub_project`: build a tmp container with `<container>/wts/<slug>/projects/sub/` as the hub subfolder; create a `.millhouse/config.local.yaml` stub at the worktree root declaring `hub_relative_path: projects/sub`; build a cfg dict that DOES NOT declare `hub_relative_path` (force the function to consult the stub); call `resolve_active_hub(container_path, slug, cfg=cfg, git_root=<worktree>)` and assert the returned path is `<container>/wts/<slug>/projects/sub`. The test exercises the stub-override branch of the two-tier lookup.
- **Commit:** `test(_paths): cover resolve_active_hub sub-project layout`

## Batch Tests

The batch's `verify:` runs the full unit-test suite via `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py`. Coverage:
- `test-config.py` — cards 1 (raise removal, hub-overlay merge in sub-project layout).
- `test-review-common.py` — cards 3 (rename smoke — existing test suite must still pass), 4 (5 new ref_paths tests), 5 (3 new existing_paths tests).
- `test-paths.py` — card 6 (sub-project `resolve_active_hub`).
- The other existing tests (`test-spawn-units.py`, `test-cleanliness.py`, etc.) must continue to pass — the rename in cards 1, 2, 3 must not break any existing positional caller.

TDD candidates: cards 1, 4, 5 (write tests first). Cards 2, 3, 6 are pure renames / coverage gaps.
