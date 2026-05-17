# Batch: branch-slug-helpers

```yaml
task: 60 (A) — Branch/slug/claim fixes
batch: branch-slug-helpers
number: 1
cards: 3
verify: python plugins/mill/unit_tests/run-all.py
depends-on: []
```

## Batch Scope

Three independent single-file helper changes that all sit on the "branch-prefix / slug story" — fixing the slug-derivation strictness in `_marker.slug_from_branch` (D1), the spurious `/` separator in `millpy-claim.py`'s branch construction (D5), and the same `/` bug in the `_status.read_branch` fallback path plus its docstring (D6). They are bundled because the implementer holds the same mental model across all three: the canonical schema documented in `mill-config.yaml` says `branch_prefix` is "prepended directly to the slug (no separator added)" and these three call sites all interact with that schema.

Tests for each change ship in this same batch, in the same card or an adjacent card. The batch's `verify:` runs the unit-test suite end-to-end.

No external interface introduced; the next batches consume `_marker.slug_from_branch`'s new lenient semantics (batch 4 transitively).

## Cards

### Card 1: `_marker.slug_from_branch` accepts bare branch as slug on prefix mismatch (D1)

- **Context:**
  - `plugins/mill/scripts/_tasks_md.py`
  - `plugins/mill/scripts/_subprocess_util.py`
  - `_mill/discussion.md`
- **Edits:**
  - `plugins/mill/scripts/_marker.py`
  - `plugins/mill/unit_tests/test-marker.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `_marker.slug_from_branch` (lines 28-68 of `_marker.py`), restructure so that the Home.md read + `_tasks_md.parse` happens BEFORE the prefix-mismatch check. Replace the existing `if prefix and not branch.startswith(prefix): raise MarkerError(...)` (lines 50-53) with: try `task = next((t for t in tasks if t.slug == branch), None)`; if `task is not None`, write `print(f"[_marker] warning: branch {branch!r} does not match prefix {prefix!r} but slug exists in Home.md; accepting", file=sys.stderr)` and `return branch`; otherwise raise `MarkerError(f"branch {branch!r} does not start with configured prefix {prefix!r} and is not a known slug")`. Add `import sys` at module top if not already imported. The post-removeprefix lookup (lines 54-68) is unchanged. The existing test `test_slug_from_branch_prefix_mismatch` (line 157) continues to pass unchanged (branch `other/foo` is not a known slug). Add two new tests in `test-marker.py`: `test_slug_from_branch_prefix_mismatch_bare_branch_known()` — fixture creates a Home.md entry with slug `foo`, branch `foo`, cfg `{spawn: {branch_prefix: "hanf/"}}` — asserts `slug_from_branch` returns `"foo"` and that the warning was emitted to stderr (capture via `contextlib.redirect_stderr(io.StringIO())`); and `test_slug_from_branch_prefix_mismatch_bare_branch_unknown()` — fixture with Home.md slug `foo`, branch `baz`, prefix `"hanf/"` — asserts `MarkerError` is raised. Register both new tests in the `main()` runner at the bottom of `test-marker.py`. The new `print()` warning string is ASCII-only.
- **Commit:** `fix(marker): accept bare branch as slug fallback on prefix mismatch (#297, #302)`

### Card 2: `millpy-claim.py` line 218 drops the spurious `/` (D5)

- **Context:**
  - `plugins/mill/scripts/millpy-spawn.py`
  - `plugins/mill/templates/mill-config.yaml`
  - `_mill/discussion.md`
- **Edits:**
  - `plugins/mill/scripts/millpy-claim.py`
  - `plugins/mill/unit_tests/test-millpy-claim.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** At line 218 of `millpy-claim.py`, change `branch_name = f"{branch_prefix}/{slug}" if branch_prefix else slug` to `branch_name = f"{branch_prefix}{slug}" if branch_prefix else slug`, mirroring `millpy-spawn.py` line 162. Add a new test function `test_branch_name_uses_no_extra_slash()` to `test-millpy-claim.py` that exercises the branch-name construction with `branch_prefix="hanf/"` and slug `"my-task"` and asserts the resulting `branch_name` equals `"hanf/my-task"` (not `"hanf//my-task"`). Use the existing `_load_claim_module` / `_make_stub_map` fixture pattern already in the file. If a direct unit-level entry point into the branch-name construction is impractical, route the test through `main()` with `--dry-run` and assert the `[DryRun] Branch:` line printed to stdout contains exactly `hanf/my-task`. Register the new test in `main()` at line 706+.
- **Commit:** `fix(claim): drop extra slash in branch name (#304)`

### Card 3: `_status.read_branch` fallback drops the same `/` + docstring fix (D6)

- **Context:**
  - `plugins/mill/templates/mill-config.yaml`
  - `_mill/discussion.md`
- **Edits:**
  - `plugins/mill/scripts/_status.py`
  - `plugins/mill/unit_tests/test-status.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `_status.py` at line 703, change `derived = f"{prefix}/{slug}" if prefix else slug` to `derived = f"{prefix}{slug}" if prefix else slug`. Update the `read_branch` docstring at line 681 — replace `` ``f"{cfg['spawn']['branch_prefix']}/{slug}"`` `` with `` ``f"{cfg['spawn']['branch_prefix']}{slug}"`` `` (drop the spurious `/`). The stderr warning message at lines 704-707 is unchanged. **Update the existing Case B test in `test-status.py`** (around line 555-569 — the `read_branch derives from prefix+slug and emits warning` test): the current cfg uses `branch_prefix="hanf"` (no trailing slash) and asserts the result is `"hanf/foo"`. That assertion only passes today because of the bug. After the fix, the same call returns `"hanffoo"`. Update the cfg literal to `cfg={"spawn": {"branch_prefix": "hanf/"}}` (with the canonical trailing-slash separator) and keep the expected value `"hanf/foo"` — the assertion then reflects the corrected formula `f"{prefix}{slug}"` and matches the documented schema. Case A (line 545-553, branch read from yaml block) is unaffected and needs no change. Add a NEW test function `test_read_branch_fallback_no_extra_slash()` to `test-status.py` that calls `read_branch` with a `tempfile`-backed nonexistent status path, `cfg={"spawn": {"branch_prefix": "hanf/"}}`, `slug="foo"`, captures stderr via `contextlib.redirect_stderr(io.StringIO())`, and asserts the return value equals `"hanf/foo"` (not `"hanf//foo"`). The new test name is distinct from the existing Case B test; both must coexist (Case B documents existing fallback behavior; the new test documents the no-double-slash regression guard). Register the new test in `main()` at the bottom of `test-status.py`.
- **Commit:** `fix(status): drop extra slash in read_branch fallback (#304 twin)`

## Batch Tests

`python plugins/mill/unit_tests/run-all.py` runs every test module under `plugins/mill/unit_tests/`. The cards above touch `test-marker.py`, `test-millpy-claim.py`, and `test-status.py` — all three are exercised by the suite. No external dependencies (no claude calls, no real git mutations on the host) — the existing test files use `tempfile` and `git init` fixtures via `_test_helpers`.
