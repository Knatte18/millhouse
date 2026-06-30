# Batch: wiki-cold-daemon-retry

```yaml
task: Fix discussion review round-cap, daemon cold-start, and nits-only no-op in finalize
batch: wiki-cold-daemon-retry
number: 2
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-marker.py test-millpy-implement.py test-millpy-fix.py
depends-on: []
```

## Batch Scope

This batch closes GitHub issue #579: a cold wiki daemon after machine sleep/resume raises an uncaught `wiki.WikiStartupError` from `_marker.slug_from_branch()` (and, independently, from `_marker.task_data()`), since the only `except` clause at `millpy-implement.py`'s `main()` call site catches `_marker.MarkerError`, not `WikiStartupError`. The batch adds a single retry-on-cold-daemon helper inside `_marker.py` — the one chokepoint every mill script already routes through for cwd/slug validation — so the fix covers all current and future callers transparently, and adds a clean error path in `millpy-implement.py` (and, per plan review round 1's NIT, the identical unguarded pattern in `millpy-fix.py`'s `main()`) for the (now much rarer) case the retry is still exhausted. No external interface is produced for another batch; `_marker.slug_from_branch()`'s and `_marker.task_data()`'s public signatures are unchanged. Batch 3 depends on this batch (`depends-on: [2]`) solely because both batches' test coverage touches `test-millpy-fix.py`; sequencing avoids a same-file parallel-modify conflict — there is no logical/code dependency between the two fixes.

## Cards

### Card 2: Add `_list_tasks_brief_with_retry()` helper and route both call sites through it

- **Context:**
  - `plugins/mill/scripts/wiki/_client.py`
  - `plugins/mill/scripts/wiki/__init__.py`
- **Edits:**
  - `plugins/mill/scripts/_marker.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - Add a new private module-level function `_list_tasks_brief_with_retry(wiki_path: Path) -> list[dict]` in `_marker.py`, placed above `slug_from_branch()`. Body: call `wiki.list_tasks_brief(wiki_path)` inside a `try`; on `wiki.WikiStartupError`, call `wiki.health_check(wiki_path)` (NOT `wiki._client.health_check` — `_marker.py`'s existing `from wiki import _client as wiki` import already makes the local name `wiki` equal to the `_client` module, so `wiki._client.health_check` would raise `AttributeError`; confirmed `wiki/_client.py` has no nested `_client` attribute) to force-wake the daemon, then retry `wiki.list_tasks_brief(wiki_path)` once. If the retry also raises `wiki.WikiStartupError`, let it propagate unwrapped — do NOT catch it into a `MarkerError`.
  - In `slug_from_branch()`, replace its existing `tasks = wiki.list_tasks_brief(wiki_path)` call with `tasks = _list_tasks_brief_with_retry(wiki_path)`.
  - In `task_data()`, replace its existing independent `tasks = wiki.list_tasks_brief(wiki_path)` call with `tasks = _list_tasks_brief_with_retry(wiki_path)` (this is the second, previously-unprotected wiki touch point in the same module — both call sites must route through the new helper, not just the first).
  - Add a one-line addition to `_marker.py`'s module docstring's "Public API" list noting `_list_tasks_brief_with_retry` is private (not part of the public surface) if the docstring convention in this file calls out private helpers; otherwise leave the docstring's Public API section unchanged since the helper is private.
- **Commit:** `fix(_marker): retry wiki.list_tasks_brief on cold-daemon WikiStartupError`

### Card 3: Catch `wiki.WikiStartupError` cleanly in `millpy-implement.py`'s and `millpy-fix.py`'s `main()`

- **Context:**
  - `plugins/mill/scripts/_marker.py`
  - `plugins/mill/scripts/wiki/__init__.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-implement.py`
  - `plugins/mill/scripts/millpy-fix.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - Add `from wiki import WikiStartupError` to `millpy-implement.py`'s import block (alongside the existing local-module imports such as `import _marker`).
  - Around the existing `try: slug = _marker.slug_from_branch(git_root, wiki_path, cfg) \n except _marker.MarkerError as e: print(str(e), file=sys.stderr); return 1` block in `millpy-implement.py`, add a sibling `except WikiStartupError as e:` clause (either before or after the existing `except _marker.MarkerError` clause — order does not matter since the two exception types do not overlap after Card 2's fix) that prints a clean message to stderr (e.g. `f"wiki daemon unreachable: {e}"`) and returns `1`, exactly like the existing `MarkerError` branch's shape, instead of letting a raw traceback surface.
  - Apply the identical fix to `millpy-fix.py`: add `from wiki import WikiStartupError` to its import block, and add the same sibling `except WikiStartupError as e:` clause around its existing `try: slug = _marker.slug_from_branch(git_root, wiki_path, cfg) \n except _marker.MarkerError as e: print(str(e), file=sys.stderr); return 1` block (currently at `millpy-fix.py:158-162`), with the same clean stderr message and `return 1` shape. Flagged as a plan-review round-1 NIT: `millpy-fix.py` has the identical pre-fix unguarded pattern Card 3 was already correcting in `millpy-implement.py`, and the fix is a direct mechanical mirror with no design difference.
- **Commit:** `fix(millpy-implement,millpy-fix): catch WikiStartupError cleanly instead of raw traceback`

### Card 4: Unit test coverage for the retry helper and the new exception handlers

- **Context:**
  - `plugins/mill/scripts/_marker.py`
  - `plugins/mill/scripts/millpy-implement.py`
  - `plugins/mill/scripts/millpy-fix.py`
  - `plugins/mill/scripts/wiki/__init__.py`
  - `plugins/mill/unit_tests/_test_helpers.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-marker.py`
  - `plugins/mill/unit_tests/test-millpy-implement.py`
  - `plugins/mill/unit_tests/test-millpy-fix.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - In `test-marker.py` (function-style tests, no test classes, using `_test_helpers.safe_temp_dir()` + `_test_helpers._make_task_worktree()` to build `worktree_path`/`wiki_path`/`cfg` fixtures, matching the existing `test_slug_from_branch_happy_path` pattern), add `test_slug_from_branch_retries_on_cold_daemon()`: using `unittest.mock.patch.object(_marker.wiki, "list_tasks_brief")` with a `side_effect` of `[_marker.wiki.WikiStartupError("cold"), <real return value>]` (or an equivalent two-call side_effect list) and `unittest.mock.patch.object(_marker.wiki, "health_check")`, assert `slug_from_branch()` still returns the correct slug and that `health_check` was called exactly once. Reference the exception as `_marker.wiki.WikiStartupError` — `_marker.py`'s existing `from wiki import _client as wiki` import means the module-level `_marker.wiki` name already resolves to it; `wiki/__init__.py` (where `WikiStartupError` is defined) is read-only Context for confirming this, not a new import target for the test file.
  - Add `test_slug_from_branch_exhausted_retry_propagates_wiki_startup_error()`: same mocking pattern but with `list_tasks_brief` raising `_marker.wiki.WikiStartupError` on both calls; assert the raised exception from `slug_from_branch()` is `_marker.wiki.WikiStartupError` (NOT `_marker.MarkerError` — use `assertRaises`/manual try-except matching this file's existing assertion style, which raises bare `AssertionError` on mismatch rather than using `unittest.TestCase` methods).
  - Add `test_task_data_retries_on_cold_daemon()`: same `side_effect`-based mocking applied to `_marker.wiki.list_tasks_brief`, calling `task_data()` instead of `slug_from_branch()` directly, asserting it still returns the correct `{"slug", "branch", "task_title"}` dict — proving `task_data()`'s independent call site is now routed through the same retry helper as `slug_from_branch()` (Card 2).
  - `test-marker.py` does NOT use unittest auto-discovery: `main()` (lines ~241-258) manually enumerates every test function in an explicit `tests = [...]` list, and `run-all.py` runs each `test-*.py` file as `python test-X.py`, calling that `main()`. Append all three new function names — `test_slug_from_branch_retries_on_cold_daemon`, `test_slug_from_branch_exhausted_retry_propagates_wiki_startup_error`, `test_task_data_retries_on_cold_daemon` — to the `tests` list, after the existing `test_task_data_happy_path` entry. Omitting this registration means the new tests would never execute despite `verify:` reporting green (flagged by plan review round 2).
  - In `test-millpy-implement.py` (class `TestMillpyImplement`, whose `setUp()` already patches `millpy_implement._marker.slug_from_branch` to `return_value="test-slug"` at line ~129-132), add `test_main_reports_clean_message_on_exhausted_wiki_startup_error()`: override `self.mock_slug_from_branch.side_effect = millpy_implement.WikiStartupError("daemon did not start within timeout")` (clearing/ignoring the `setUp()` `return_value`) — `millpy_implement.WikiStartupError` resolves via Card 3's new `from wiki import WikiStartupError` import in `millpy-implement.py`, so this test file needs no fresh import of its own. Invoke `main(argv)` with the same minimal positional `batch_name` argv the existing tests in this class pass (e.g. matching `test_1_initial_dispatch_success`'s argv shape). The existing `_run_main()` helper only captures `sys.stdout`, so this test must separately wrap the call with `unittest.mock.patch("sys.stderr", io.StringIO())` (or equivalent) to capture stderr. Assert `main()` returns `1` and the captured stderr contains no `Traceback (most recent call last)` substring (proving the new `except WikiStartupError` clause caught it cleanly rather than letting it propagate as a raw unhandled exception).
  - In `test-millpy-fix.py` (whose `_run_main()` helper and `setUp()`-style fixtures mirror `test-millpy-implement.py`'s — confirm the actual patching target by reading the file's own `setUp()`), add a sibling `test_main_reports_clean_message_on_exhausted_wiki_startup_error()` for `millpy-fix.py`'s `main()`: same shape as the `test-millpy-implement.py` case above, referencing `millpy_fix.WikiStartupError` (resolves via Card 3's new import in `millpy-fix.py`), asserting return code `1` and no traceback substring in captured stderr.
- **Commit:** `test(_marker,millpy-implement,millpy-fix): cover cold-daemon retry and exhausted-retry error handling`

## Batch Tests

`verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-marker.py test-millpy-implement.py test-millpy-fix.py` covers all three edited modules: `test-marker.py` exercises the new `_list_tasks_brief_with_retry()` helper through both its callers (`slug_from_branch()`, `task_data()`), and `test-millpy-implement.py`/`test-millpy-fix.py` each exercise their own `main()`'s new exhausted-retry error path. Scoped to the three files this batch touches plus their existing regression coverage — no cross-cutting helper is touched, so the unbounded `run-all.py` is not needed.
