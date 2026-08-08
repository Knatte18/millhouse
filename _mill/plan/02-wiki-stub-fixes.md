# Batch: wiki-stub-fixes

```yaml
task: 'Unit test suite: hangs, unmocked-path errors, and stuck/success envelope bug found in piecewise sweep'
batch: 'wiki-stub-fixes'
number: 2
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-millpy-claim.py test-millpy-spawn.py
depends-on: []
```

## Batch Scope

Both `millpy-claim.py` and `millpy-spawn.py` import `from wiki import _client as wiki`. Neither
test file's stub maps intercept that dotted-module import correctly today: `test-millpy-claim.py`
registers no wiki stub at all (real daemon-spawn hang), and `test-millpy-spawn.py` registers a
stub under the dead key `"_wiki"` (a module name `millpy-spawn.py` never imports), so 9 of its 16
scenarios fall through to the real `wiki._client` code against a fake `/fake/wiki` path
(`[Errno 2] No such file or directory: '/fake/wiki/tasks.json'`). Both files share the identical
root cause and the identical proven fix mechanic (see overview `## Shared Decisions`), so they are
one batch: 3 cards — one for `test-millpy-claim.py`'s single shared stub-map helper, one for
`test-millpy-spawn.py`'s shared `_run_main_with_mocks` helper (5 of the 9 failing scenarios), and
one for `test-millpy-spawn.py`'s 4 remaining standalone stub-map sites.

Empirically verified today (`run-all.py`, before this batch's fix): `test-millpy-spawn.py` fails
exactly 9 of 16 tests — `test_main_happy_path_calls_spawn_core_in_order`,
`test_write_settings_uses_short_name_and_slug`, `test_main_backlog_empty_exits_zero`,
`test_main_value_error_from_picker_exits_one`,
`test_main_runtime_error_from_capture_branch_raises_system_exit`,
`test_create_hub_links_called_after_portal_creation`,
`test_main_dry_run_prints_worktree_status_path`,
`test_single_selection_does_not_call_multi_select_groom_then_claim`,
`test_spawn_aborts_when_origin_branch_already_exists`. The other 7 (`test_smoke_import`,
`test_spawn_standard_layout_regression`, `test_spawn_subfolder_install_destination_layout`,
`test_spawn_discovery_round_trip_subfolder`, `test_spawn_slug_help_text_has_no_s_marker`,
`test_spawn_empty_backlog_message_has_no_s_marker`,
`test_spawn_rolls_back_when_write_initial_status_fails`) do not exercise a
`wiki._client`-reaching path and must remain passing after this batch (the last of the 7 is the
test that already contains the proven fix pattern this batch replicates elsewhere — do not modify
it).

## Cards

### Card 2: Stub `wiki._client` in test-millpy-claim.py

- **Context:**
  - `plugins/mill/scripts/millpy-claim.py`
  - `plugins/mill/unit_tests/test-millpy-spawn.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-millpy-claim.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `_make_stub_map()` (`test-millpy-claim.py:79-107`), add a
  `"wiki._client": MagicMock()` entry to the returned stub-map dict — `_load_claim_module`'s
  existing `for name, stub in stub_map.items(): sys.modules[name] = stub` loop already injects any
  dict key verbatim, dotted or not, so this alone registers `sys.modules["wiki._client"]`. In
  `_load_claim_module()` (`test-millpy-claim.py:52-68`), immediately after
  `spec.loader.exec_module(mod)`, add `mod.wiki = stub_map["wiki._client"]` — the belt-and-suspenders
  step from the `## Shared Decisions` mechanic, needed because `from wiki import _client as wiki`
  (`millpy-claim.py:46`) resolves via `hasattr` on the real `wiki` package object before falling
  back to the `sys.modules["wiki._client"]` injection, and a prior test in the same process may
  already have cached a real `._client` attribute on that package object. Without this stub, every
  scenario's `mod.main()` call reaches the real `wiki.list_tasks_brief(wiki_path)`
  (`millpy-claim.py:160`) against the fake `/fake/wiki` path, hanging on `_ensure_daemon`'s
  daemon-spawn poll loop (`wiki/_client.py:620-662`). No scenario needs the mock to return specific
  task data: every scenario mocks `_spawn_core.pick_task_single_or_multi` with its own fixed return
  value, so `wiki.list_tasks_brief`'s return value is discarded — a bare `MagicMock()` is
  sufficient. `test_smoke_import` (`:115-161`) builds its own standalone stub list and does not call
  `_make_stub_map`/`_load_claim_module` or `mod.main()` — it needs no change and must remain
  passing.
- **Commit:** `fix(test): stub wiki._client in test-millpy-claim.py to prevent real daemon-spawn hang`

### Card 3: Stub `wiki._client` in test-millpy-spawn.py's `_run_main_with_mocks` helper

- **Context:**
  - `plugins/mill/scripts/millpy-spawn.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-millpy-spawn.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `_run_main_with_mocks()` (`test-millpy-spawn.py:121-221`), leave the existing
  `"_wiki": wiki_mock` stub-map entry (`:187`) in place unchanged (it is a harmless dead stub for a
  module name `millpy-spawn.py` never imports — `millpy-spawn.py` imports
  `from wiki import _client as wiki`, not `import _wiki`). Additionally apply the
  `## Shared Decisions` wiki-stub mechanic: before `spec.loader.exec_module(mod)` (`:201`), save
  `saved_wiki_client = sys.modules.get("wiki._client")` and set
  `sys.modules["wiki._client"] = <a fresh MagicMock()>`; immediately after `exec_module`, set
  `mod.wiki = <that same mock>`; in the existing `finally` block (`:214-219`), restore
  `sys.modules["wiki._client"]` to `saved_wiki_client` (pop the key if it was `None`) alongside the
  existing stub-restore loop. This helper is called by 5 of the 9 currently-failing tests:
  `test_main_happy_path_calls_spawn_core_in_order`, `test_main_value_error_from_picker_exits_one`,
  `test_main_runtime_error_from_capture_branch_raises_system_exit`,
  `test_main_dry_run_prints_worktree_status_path`,
  `test_single_selection_does_not_call_multi_select_groom_then_claim` — none of them assert on the
  helper's discarded third return value (`wiki_mock`), so this fix requires no change to any call
  site or to the helper's return signature.
- **Commit:** `fix(test): stub wiki._client in test-millpy-spawn.py's _run_main_with_mocks helper`

### Card 4: Stub `wiki._client` in 4 standalone test-millpy-spawn.py test functions

- **Context:**
  - `plugins/mill/scripts/millpy-spawn.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-millpy-spawn.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Apply the identical `## Shared Decisions` wiki-stub mechanic from Card 3 (save
  `sys.modules.get("wiki._client")`, inject a fresh `MagicMock()` at `sys.modules["wiki._client"]`
  before that test's own `spec.loader.exec_module(mod)` call, set `mod.wiki` to that mock
  immediately after `exec_module`, restore the saved value in that test's own existing `finally`
  block) independently to each of these 4 test functions' local stub-injection blocks — each
  currently only sets a dead `"_wiki"` stub-map entry, the same root cause as Card 3, but each
  builds its own standalone `stub_map`/`saved`/`finally` rather than sharing
  `_run_main_with_mocks`:
  - `test_write_settings_uses_short_name_and_slug` (`test-millpy-spawn.py:280-380`)
  - `test_main_backlog_empty_exits_zero` (`test-millpy-spawn.py:381-446`)
  - `test_create_hub_links_called_after_portal_creation` (`test-millpy-spawn.py:487-641`)
  - `test_spawn_aborts_when_origin_branch_already_exists` (`test-millpy-spawn.py:1076-1187`)
  None of these 4 tests assert on the wiki mock's calls or return value.
- **Commit:** `fix(test): stub wiki._client in 4 standalone test-millpy-spawn.py test functions`

## Batch Tests

`verify:` runs both files together via `run-all.py --only test-millpy-claim.py
test-millpy-spawn.py` (default parallel mode — neither file hangs after this batch's fix).
Confirms `test-millpy-spawn.py` reaches 16/16 passing (up from the empirically-verified 7/16
baseline) and `test-millpy-claim.py` completes with no hang and every existing assertion still
passing (the fix only unblocks scenarios from reaching a real daemon; it changes no scenario's
asserted behavior).
