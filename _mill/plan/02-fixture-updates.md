# Batch: fixture-updates

```yaml
task: Green the unit test suite on wiki-v3-adoption so it can merge to main
batch: fixture-updates
number: 2
cards: 9
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py
depends-on: [1]
```

## Batch Scope

This batch makes every still-red unit test pass by updating each affected fixture to use the foundation helpers added in batch 1 (`init_wiki_repo`, `seed_task`, `wait_for_daemon_exit` via `safe_temp_dir`, the `WIKI_DAEMON_IDLE_TIMEOUT` env default) AND by fixing the per-file failure modes that batch 1 cannot address generically (cfg keys missing in test-only config dicts, MagicMock plumbing, Home.md syntax in inlined fixture strings, etc.). One card per affected test file. After this batch, `run-all.py` is the verify -- all 77 tests pass.

The diagnosed failure modes were extracted from per-file runs of `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/<file>.py` against the current `hanf/wiki-v3-test-suite-green` branch (spawned off `hanf/wiki-v3-adoption`). Each card states the diagnosed mode and the surgical fix; the implementer should re-run the targeted test file after the change to confirm green before moving to the next card.

Batch-local decision: when a fixture's wiki dir layout differs from `_make_task_worktree`'s default (e.g. tests that nest `tmp/container/wts/<slug>/` and `tmp/wiki/`), keep the test's own layout helper -- do NOT swap to `_make_task_worktree`. Just splice in the foundation helpers (`init_wiki_repo`, `wiki.upsert_task`, env-var default) at the correct point. The discussion's RC1-seed decision (one of the operator-confirmed gap fixes from r1 review) requires seeding regardless of which layout helper the fixture uses.

## Cards

### Card 8: test-bg-launcher.py -- RC2 + RC1 infrastructure

- **Context:**
  - `plugins/mill/scripts/wiki/_client.py`
  - `plugins/mill/scripts/_marker.py`
  - `plugins/mill/unit_tests/_test_helpers.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-bg-launcher.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Update the file's local `_make_container_form_worktree` helper (currently `test-bg-launcher.py:18-109`) so that, after the existing `wiki_path.mkdir(parents=True, exist_ok=True)` step and BEFORE the raw `(wiki_path / "Home.md").write_text(...)` write, it calls `_test_helpers.init_wiki_repo(wiki_path)` to turn the wiki dir into a real git repo with a local bare origin. Change the inlined Home.md from V2 double-bracket form `f"## {title}\n[[{slug}]] [active]\n\n_body_\n"` to V3 single-bracket form `f"## {title}\n[{slug}] [active]\n\n_body_\n"`; update the sanity assertion on the next line from `if f"[[{slug}]]" not in home_body` to `if f"[{slug}]" not in home_body` to match. After the Home.md write, also call `wiki.upsert_task(wiki_path, slug, title=title, status="active")` to seed `tasks.json`. Add `from wiki import _client as wiki` to the file's imports. The three test functions in the file (`test_launcher_rejects_non_task_worktree`, `test_launcher_rejects_invalid_cwd_with_clean_error`, `test_launcher_accepts_valid_task_worktree`) require no further changes -- the assertion on `pid=` / `log=` already exercises the right path. Tempdir cleanup: tests already use `_test_helpers.safe_temp_dir()` (per current line 234) -- batch 1 Card 6 extended `safe_temp_dir` to wait for daemon exit, so no per-test wait-call is needed.
- **Commit:** `test(bg-launcher): seed task via wiki.upsert_task and init wiki as git repo`

### Card 9: test-marker.py -- pass seed_task=True

- **Context:**
  - `plugins/mill/scripts/_marker.py`
  - `plugins/mill/unit_tests/_test_helpers.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-marker.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Every call to `_test_helpers._make_task_worktree(...)` in this file (currently 14 callsites, one per happy-path / variant test) must pass `seed_task=True` so the task lands in `tasks.json` and `_marker.slug_from_branch` -> `wiki.list_tasks_brief` returns the expected entry. The current diagnostic mode is "PermissionError [WinError 32]" at tempdir teardown -- both root causes are addressed: (a) `seed_task=True` makes the test assertion path succeed cleanly via real daemon, (b) batch 1's `on_stop` handler-close + extended `safe_temp_dir` wait release the log lock before rmtree. The test bodies that expect `MarkerError` for negative cases (detached HEAD, prefix mismatch, unknown slug) must NOT pass `seed_task=True` -- those tests deliberately need an empty `tasks.json` so the marker check fails. Apply `seed_task=True` only to the positive-path tests; leave the negative-path tests untouched. Migrate every `with tempfile.TemporaryDirectory() as tmp:` block in this file to `with _test_helpers.safe_temp_dir() as tmp:` so the daemon-exit wait fires on cleanup (drop the inner `tmp = Path(tmp)` line that follows -- `safe_temp_dir` yields a `Path` already).
- **Commit:** `test(marker): seed tasks.json via _make_task_worktree(seed_task=True) and migrate to safe_temp_dir`

### Card 10: test-millpy-spawn.py -- fix MagicMock plumbing for slug/title

- **Context:**
  - `plugins/mill/scripts/millpy-spawn.py`
  - `plugins/mill/scripts/_spawn_core.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-millpy-spawn.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Diagnose: the 5 failing tests (`test_main_happy_path_calls_spawn_core_in_order`, `test_write_settings_uses_short_name_and_slug`, `test_create_hub_links_called_after_portal_creation`, `test_spawn_standard_layout_regression`, `test_spawn_subfolder_install_destination_layout`) all show `MagicMock` objects leaking into assertions where concrete strings/Paths are expected (e.g., `slug=<MagicMock name='mock.__getitem__()' id='...'>`). Root cause: the post-V3 `_spawn_core.pick_task_single` returns a `dict` (commit `94ef5e2` converted Task attribute -> dict-key access in scripts); tests still mock the helper to return a `MagicMock` whose `__getitem__` returns a child `MagicMock` instead of a concrete dict. Fix: locate every `MagicMock` / `mock.patch(...)` that stands in for the `pick_task_single` (or related) return value and replace it with a real `dict({"slug": "my-task", "title": "My Task", "id": 0, ...})` (matching the keys the production code accesses). Where the test currently does `mock.return_value = MagicMock()`, change to `mock.return_value = {"slug": "my-task", "title": "My Task", "group": None, "brief": "", "status": "active", "id": 0, "body": "", "has_proposal": False}` (use the brief-dict shape from `Store.list_tasks_brief`). For test `test_spawn_standard_layout_regression` and `test_spawn_subfolder_install_destination_layout`, the fixture additionally uses `tempfile.mkdtemp()` + `try/finally: _safe_rmtree.safe_rmtree(...)`; migrate those to `with _test_helpers.safe_temp_dir() as tmpdir:` for the daemon-wait sweep. Add `seed_task=True` to any `_make_task_worktree` calls if present (none expected based on current file -- confirm during implementation). Keep all existing assertions; only the mock-construction sites change.
- **Commit:** `test(millpy-spawn): replace MagicMock task stubs with concrete dicts`

### Card 11: test-review-cli.py -- (d) fixture must be a real git repo

- **Context:**
  - `plugins/mill/scripts/millpy-review-discussion.py`
  - `plugins/mill/scripts/_marker.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-review-cli.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** The single failing test in this file (`test_review_cli_emits_envelope_on_validate_role_refs_failure`, currently labelled `(d)` in `main()` at `test-review-cli.py:383-440`) fails because `_mod.main([])` exits with `ERROR: no active task detected (... not a git repository ...)` before reaching the role-validation step. The fixture creates `_tmp = Path(_tmpdir)` and writes wiki/config.yaml but never `git init`s `_tmp`. Fix: between the `_tmp = Path(_tmpdir)` line and the wiki setup, add the same git-init pattern used by `_test_helpers.init_wiki_repo` but on `_tmp` (worktree role, not wiki role): `git init --initial-branch=main`, `git config user.email/name`, create `.keep`, `git add .keep`, `git commit -m init`, `git checkout -b hanf/test-slug`. Also call `_test_helpers.init_wiki_repo(_wiki)` instead of the plain `_wiki.mkdir()` (replaces the bare-dir write with a real wiki git repo so the role-validation step's eventual `wiki.list_tasks_brief` does not fail on missing tasks.json). Then call `wiki.upsert_task(_wiki, "test-slug", title="Test", status="active")` so the slug exists. The Home.md and config.yaml writes the test currently does in `_wiki` stay -- `init_wiki_repo` only adds git state, it does not overwrite files. The `with tempfile.TemporaryDirectory() as _tmpdir:` block migrates to `with _test_helpers.safe_temp_dir() as _tmp:` (drops the inner `_tmp = Path(_tmpdir)` line). Add `from wiki import _client as wiki` to the imports. The four `print("ERROR: ...")`-named test functions that pass already keep passing -- they print "ERROR:" deliberately as part of `print_error_envelope` testing, not because they fail.
- **Commit:** `test(review-cli): make (d) fixture a real git repo and seed tasks.json`

### Card 12: test-review-code-flow.py -- add spawn.branch_prefix to test cfg

- **Context:**
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/scripts/_review_code.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-review-code-flow.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Every test in this file fails with `ActiveWorktreeSlugMismatch: ... has slug 'hanf/test-slug', expected 'test-slug'`. Root cause: `_paths.resolve_active_worktree` (`_paths.py:334`) does `dir_slug = branch.removeprefix(cfg.get("spawn", {}).get("branch_prefix", ""))`. The test's `cfg` dict (constructed inline at `test-review-code-flow.py:143-...`) has `paths`, `llm`, `roles` but no `spawn` block, so the prefix is `""`, the branch `hanf/test-slug` is not stripped, and the comparison against the expected `test-slug` fails. Fix: add `"spawn": {"branch_prefix": "hanf/"}` as a top-level key to the test cfg dict in `_make_fixture` (around line 143). Also: the fixture's Home.md write at line 113 uses the V2-form `[[{SLUG}]] [active]` (double brackets) which V3 `wiki._parse.parse_home_md` no longer matches; change to single brackets `[{SLUG}] [active]`. Then add `_test_helpers.init_wiki_repo(wiki_root)` after `wiki_root.mkdir(...)` (line ~110) and `wiki.upsert_task(wiki_root, SLUG, title="Test Task", status="active")` after `seed_wiki_config(wiki_root)` so `tasks.json` is seeded. Add `from wiki import _client as wiki` to imports. Migrate every `with tempfile.TemporaryDirectory() as tmpdir:` block to `with _test_helpers.safe_temp_dir() as tmpdir:` (drops the inner `tmpdir = Path(tmpdir)` lines).
- **Commit:** `test(review-code-flow): add spawn.branch_prefix and seed tasks.json in fixture`

### Card 13: test-review-discussion-flow.py -- same as Card 12

- **Context:**
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/scripts/_review_discussion.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-review-discussion-flow.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Same diagnosis and fix as Card 12 applied to this file. (1) Add `"spawn": {"branch_prefix": "hanf/"}` to the test cfg dict where constructed. (2) If the fixture writes Home.md with V2 double-bracket syntax, change to single-bracket. (3) After the wiki directory is created, call `_test_helpers.init_wiki_repo(wiki_root)` and `wiki.upsert_task(wiki_root, SLUG, title=..., status="active")`. (4) Migrate every `with tempfile.TemporaryDirectory() as tmpdir:` to `with _test_helpers.safe_temp_dir() as tmpdir:`. (5) Add `from wiki import _client as wiki`. If the file lays out the worktree differently from test-review-code-flow.py, follow the file's existing pattern but apply the same five edits.
- **Commit:** `test(review-discussion-flow): add spawn.branch_prefix and seed tasks.json in fixture`

### Card 14: test-review-plan-flow.py -- same as Card 12

- **Context:**
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/scripts/_review_plan.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-review-plan-flow.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Same diagnosis and fix as Card 12 applied to this file. Apply the five edits (cfg spawn block, Home.md single-bracket, init_wiki_repo, upsert_task seed, safe_temp_dir migration, wiki import). Follow the file's existing layout pattern.
- **Commit:** `test(review-plan-flow): add spawn.branch_prefix and seed tasks.json in fixture`

### Card 15: test-review-common.py -- safe_temp_dir migration

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/unit_tests/_test_helpers.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-review-common.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Diagnostic mode is "PermissionError [WinError 32]" at tempdir teardown -- same as test-marker. Fix: (1) every `with tempfile.TemporaryDirectory() as tmpdir:` block migrates to `with _test_helpers.safe_temp_dir() as tmpdir:` (drops any inner `tmpdir = Path(tmpdir)` line). (2) Any `_test_helpers._make_task_worktree(...)` callsite in this file passes `seed_task=True` (skip if the test deliberately needs an empty tasks.json -- determine by reading the test body; if the body never calls a wiki client function or `slug_from_branch`, `seed_task=True` is harmless). (3) If the file constructs an inline cfg dict that lacks `"spawn": {"branch_prefix": "hanf/"}` AND the test reaches code that calls `_paths.resolve_active_worktree`, add the spawn block. No production-code changes.
- **Commit:** `test(review-common): migrate to safe_temp_dir and seed tasks.json`

### Card 16: test-setup-hub-links.py -- hardlink/junction fixture fixes

- **Context:**
  - `plugins/mill/scripts/_setup.py`
  - `plugins/mill/scripts/_junction.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-setup-hub-links.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Five failing tests in this file (`test_token_scope_filter_no_slug`, `test_token_scope_filter_with_slug`, `test_junction_idempotent_skip_on_correct_target`, `test_hardlink_inode_skip_idempotent`, `test_hardlink_inode_mismatch_backup_and_recreate`). Diagnostic modes vary: "expected 1 hardlink created, got 0", ".portals not created at ...", "expected 2 junctions, got [.wiki only]". Root cause: the post-V3 setup helper (in `plugins/mill/scripts/_setup.py`) likely changed which junctions/hardlinks it creates by default (e.g., consolidated `.wiki` / `.active` / `.portals` set), but the tests still assert on the V2 expectations. Fix: for each failing test, read the current `_setup.py` to confirm what the post-V3 `create_hub_links` (or its V3 successor) creates, then update the test's expectations to match. This may mean changing assertion counts ("expected 2 junctions" -> "expected 1") or the set of relative paths the test checks. Do NOT change production code -- the tests are stale. Where the test uses `safe_temp_dir()` (it already does, per the file's import at line 33), no daemon-wait migration is needed. Where the test calls into the setup module (`_setup.create_hub_links` or its V3 successor), confirm the function still accepts the same arguments; if signatures changed during V3 work, update the test calls. Each fix is local to one test function; do not refactor the file's helpers unless multiple tests require it.
- **Commit:** `test(setup-hub-links): update assertions to match post-V3 _setup_hub_links output`

## Batch Tests

Verify `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py`. After this batch, all RC1-affected files (the eight from issue #377 plus test-bg-launcher's RC2) are green AND all tests in those files pass. Batch 3 (`gate-and-syntax-fixes`) has `depends-on: []` -- it is a root batch that mill-go schedules in parallel with batch 1 -- so by the time mill-go fires this batch's verify, batch 3 has typically already landed. If mill-go happens to schedule batch 2 before batch 3 (or batch 3 is delayed), the verify will still show 3 transient reds (test-no-direct-rmtree.py from RC3 in test-fold.py, plus 2 cases in test-spawn-core.py from RC4); those reds disappear when batch 3 lands. The final, authoritative pass condition is the overview-level verify run after all three batches: 77/77 pass. Per-card local verification while implementing: run `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/<file>.py` for the file the card just changed and confirm it is green before moving to the next card.
