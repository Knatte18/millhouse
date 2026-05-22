# Plan: Write active-slug indicator file in hub

```yaml
task: Write active-slug indicator file in hub
slug: hub-active-slug
approved: true
started: 20260522-064846
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: Core helpers
    file: 01-core-helpers.md
    depends-on: []
    verify: uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py
  - number: 2
    name: Callers
    file: 02-callers.md
    depends-on: [1]
    verify: uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py
  - number: 3
    name: Tests
    file: 03-tests.md
    depends-on: [1, 2]
    verify: uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py
```

## Shared Decisions

### Decision: Use Path.unlink(missing_ok=True) for indicator deletion

- **Decision:** Delete the indicator file with `Path.unlink(missing_ok=True)` everywhere; never guard with an existence check.
- **Rationale:** The indicator is ephemeral; it may be absent after a manual delete or after upgrading from a pre-feature version. `missing_ok=True` makes teardown idempotent without extra conditionals.
- **Applies to:** Batch 2 (cleanup card), Batch 3 (test assertions).

### Decision: Glob fallback reads from git_root/_mill, not cwd/_mill

- **Decision:** `find_active_slug` globs `git_root / "_mill" / "*.active"` — the same `git_root` already passed to `slug_from_branch`.
- **Rationale:** The caller always passes the resolved git root; using that same path keeps the fallback consistent with branch detection. There is no separate "hub_root" concept in the review stack — git_root IS the hub when running from the hub.
- **Applies to:** Batch 1 (card 3), Batch 3 (card 9 tests).

### Decision: OSError on missing _mill/ dir is treated as zero matches

- **Decision:** In `find_active_slug`, catch `OSError` when calling `Path.glob` on an absent `_mill/` directory and treat it as zero matches, then raise `ReviewError`.
- **Rationale:** A hub that has never had a task claimed will not have `_mill/` at all. This is not an error; it simply means no task is active.
- **Applies to:** Batch 1 (card 3), Batch 3 (card 9 tests).

## All Files Touched

- `.gitignore`
- `plugins/mill/scripts/_gitignore.py`
- `plugins/mill/scripts/_review_common.py`
- `plugins/mill/scripts/_spawn_core.py`
- `plugins/mill/scripts/millpy-claim.py`
- `plugins/mill/scripts/millpy-cleanup.py`
- `plugins/mill/scripts/millpy-spawn.py`
- `plugins/mill/unit_tests/test-cleanup.py`
- `plugins/mill/unit_tests/test-review-common.py`
- `plugins/mill/unit_tests/test-spawn-core.py`
