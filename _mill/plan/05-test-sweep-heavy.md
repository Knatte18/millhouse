# Batch: test-sweep-heavy

```yaml
task: "Finish V3 wiki adoption — complete batch 3 port and test sweep"
batch: test-sweep-heavy
number: 5
cards: 2
verify: "PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-fold.py && PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-spawn-core.py"
depends-on: [3, 4]
```

## Batch Scope

Port the two large test files still carrying V2 references — `test-fold.py` and `test-spawn-core.py` — to the V3 wiki API. Each file gets its own card and its own commit (one card per file per discussion's `Decision: test-sweep-granularity-one-card-per-file`).

Depends on batches 3 and 4 because the test-port code assumes the shipping-code under test is already V3-clean — the patches and call shapes target the V3 import structure of `millpy-spawn.py` (batch 3) and the small CLIs (batch 4). Card 6 of batch 4 doesn't directly affect these test files, but the depends-on edge is conservative: every shipping-code port should be in before tests of related code change shape.

Two M cards, sum effort 4 — exactly fills the batch ceiling.

Batch-local decisions (differ from `## Shared Decisions` in `00-overview.md`):

- **For `_tasks_md.parse(home_text)` calls in pure-text test fixtures, use `wiki._parse.parse_home_md(home_text)`.** This V3 helper at `plugins/mill/scripts/wiki/_parse.py:6` takes a Home.md text string and returns `list[dict]` (verified at the source). It is a stateless text parser; it does NOT spawn the daemon, so it is the correct replacement for tests that build a temp Home.md string and want to assert what it parses to. Tests that exercised real daemon round-trip behaviour should use `wiki._client.upsert_tasks_batch(wiki_path, [...])` to seed via the daemon instead — but for the two cards in this batch, `parse_home_md` is sufficient (both files use text-only assertions on hard-coded fixture strings).
- **`_tasks_md.LOCKED_FOLD_PHASES`** is replaced by **`wiki.LOCKED_FOLD_PHASES`** (verified exported in `wiki/__init__.py`). The constant tuple is unchanged.
- **`_tasks_md.append_to_body`** has no direct V3 equivalent; replace with text-level manipulation in fixture code OR use `wiki.upsert_task(wiki_path, slug, brief=existing_brief + "\n" + new_line)` if the test asserts on daemon state. For `test-fold.py`, the assertions are on the returned text — keep the text-level shape but inline the regex-and-insert that V2's `append_to_body` did.

## Cards

### Card 8: Port `test-fold.py` to V3 wiki API

- **Effort:** M
- **Context:**
  - `plugins/mill/scripts/wiki/__init__.py`
  - `plugins/mill/scripts/wiki/_parse.py`
  - `plugins/mill/scripts/wiki/_client.py`
  - `plugins/mill/scripts/millpy-fold.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-fold.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Eliminate V2 references from `plugins/mill/unit_tests/test-fold.py`. Line numbers are from the current state on `hanf/wiki-v3-batch3-finish` HEAD.

  **Imports (lines 15, 16):**
  - Delete `import _tasks_md  # noqa: E402` (line 15).
  - Delete `import _wiki  # noqa: E402` (line 16).
  - Add `from wiki import _client as wiki, LOCKED_FOLD_PHASES, WikiPushError  # noqa: E402` in the same import block. This is the canonical V3 import (mirrors `millpy-fold.py:39`). `wiki/__init__.py` re-exports `LOCKED_FOLD_PHASES` and `WikiPushError` as top-level names; `_client` is the module that holds the functions, aliased to `wiki` so `wiki.upsert_task(...)` works.

  **`_tasks_md.LOCKED_FOLD_PHASES` assertions (lines 142-143):**

  Replace both references in the assert with the bare name `LOCKED_FOLD_PHASES` (now in scope via the `from` import above). The post-edit shape:

  ```python
  assert LOCKED_FOLD_PHASES == ("active", "ready-to-merge", "pr-pending"), (
      f"Got {LOCKED_FOLD_PHASES!r}"
  )
  ```

  **`_tasks_md.append_to_body` direct calls (lines 152, 175, 193, 207):**

  These test the V2 helper that no longer exists. The V3 equivalent is `wiki.upsert_task(wiki_path, slug, brief=...)` (daemon-mediated) or text-level manipulation if the test is checking text-shape invariants without a real wiki.

  Inspect each call site:

  - Line 152, 175, 193: these call `_tasks_md.append_to_body(<fixture_text>, <slug>, <line>)` and assert on the returned text. The V2 helper performed a text-level surgical insert. Since V3 has no text-surgery helper (text is rendered from TinyDB), the tests must either (a) seed a real wiki via `wiki.upsert_task` and assert on the rendered output, OR (b) be rewritten to test only the `millpy-fold.py` end-to-end flow without targeting an internal `append_to_body`.

    Choose (a): rewrite each test using the existing `_setup_tempfile_wiki(home_md_content)` helper at `test-fold.py:43` — it already creates a temp wiki with `Home.md`, `_Sidebar.md`, and a bare-clone `origin` remote ready for daemon-mediated `upsert_task` calls (verified by reading the helper body). Seed the initial task with `wiki.upsert_task(wiki_path, slug, brief=<initial>)`, call `wiki.upsert_task(wiki_path, slug, brief=<initial> + "\n" + <new_line>)` to append, then read via `wiki.get_task(wiki_path, slug)` and assert `task["brief"]` contains both `<initial>` and `<new_line>`. The bare-origin issue from card 11 (batch 6) does NOT apply here — `_setup_tempfile_wiki` already handles it.

  - Line 207: this is a negative test that V2 raised on unknown slugs. The V3 equivalent: `wiki.upsert_task(wiki_path, "no-such-slug", brief="- note")` would CREATE a new task (V3 upsert is upsert, not update-only). To preserve the V2 semantics ("unknown slug raises"), the test must FIRST check existence via `wiki.get_task(wiki_path, "no-such-slug")` (which returns `None`); if it returns `None`, raise the expected exception in the test code itself OR delete this test method outright (since V3 has no "update-only" mode and the semantic is gone). **Delete the test method** under the V2-only-tests-get-deleted principle from `## Shared Decisions ## Decision: card-4-deletes-_task_to_dict-helper` (the decision body explicitly extends the principle to V2-only test cases in batch 5).

  **`_wiki.write_commit_push` patching (lines 506, 511, 528):**

  These lines patch `_wiki.write_commit_push` to inject a failure for the failure-path test. V3 has no `write_commit_push`. The test's intent — "what happens when the push fails?" — translates to V3 as "what happens when `wiki._sync.commit_push` raises `WikiPushError`?". Two options:

  - Patch `wiki._sync.commit_push` directly OR
  - Patch the higher-level call site (`mill_fold.wiki.upsert_task`) to raise `WikiPushError`.

  Choose patching `mill_fold.wiki.upsert_task` to raise `WikiPushError("push failed")` — the test then asserts that `mill-fold`'s CLI flow surfaces the error correctly. Rename the local from `orig_wcp` to `orig_upsert`; the `try/finally` restoration logic stays the same shape.

  Concretely, replace the 506-528 block's three references. Because `millpy-fold.py:39` imports as `from wiki import _client as wiki, LOCKED_FOLD_PHASES`, the module attribute `mill_fold.wiki` is the `_client` module — `mill_fold.wiki.upsert_task` resolves correctly.

  - `orig_wcp = _wiki.write_commit_push` → `orig_upsert = mill_fold.wiki.upsert_task`
  - `_wiki.write_commit_push = _failing_write` → `mill_fold.wiki.upsert_task = _failing_upsert`
  - `_wiki.write_commit_push = orig_wcp` → `mill_fold.wiki.upsert_task = orig_upsert`

  Rename `_failing_write` to `_failing_upsert` and adjust its signature to match `upsert_task(wiki_path, slug, *, title=None, brief=None, body=None, group=None, status=None) -> dict` — raise `WikiPushError("simulated push failure")` from inside (the exception class is imported into the test's namespace by the `from wiki import` line above).

  Where `mill_fold` is the module reference — match whatever import shape the test already uses (look for `mill_fold = ...` near the top of the file).

  **Final verification (do inside the implementer's edit loop, before committing):**

  ```bash
  grep -nE "^import _(wiki|tasks_md|sidebar)|^from _(wiki|tasks_md|sidebar) " plugins/mill/unit_tests/test-fold.py
  grep -nE "_(wiki|tasks_md|sidebar)\." plugins/mill/unit_tests/test-fold.py
  ```

  Both must return zero matches.

  Then run `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-fold.py`. All tests except the one deleted (line 207's negative case) must pass.
- **Commit:** `test(fold): port to V3 wiki API; rewrite append_to_body assertions via daemon round-trip`

### Card 9: Port `test-spawn-core.py` to V3 wiki API

- **Effort:** M
- **Context:**
  - `plugins/mill/scripts/wiki/__init__.py`
  - `plugins/mill/scripts/wiki/_parse.py`
  - `plugins/mill/scripts/_spawn_core.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-spawn-core.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Eliminate V2 references from `plugins/mill/unit_tests/test-spawn-core.py`. Line numbers are from the current state on `hanf/wiki-v3-batch3-finish` HEAD.

  **Imports (line 25):**
  - Delete `import _tasks_md  # noqa: E402`.
  - Add `from wiki._parse import parse_home_md  # noqa: E402` in the same import block (the parse helper is the V3 replacement for text-fixture parsing).

  **Docstring reference (line 88):**

  The docstring text `The working clone is returned. ``_wiki.write_commit_push`` can push` references the deleted V2 helper. Rewrite to: `The working clone is returned. ``wiki._sync.commit_push`` can push` (matching the V3 helper).

  **`_tasks_md.parse(<text>)` calls (lines 190, 198, 206, 216, 231, 244, 260, 275, 302, 587, 611, 631):**

  Every call is `tasks = _tasks_md.parse(<hard-coded fixture text>)` — pure text parsing, no real wiki. Replace each with `tasks = parse_home_md(<same text>)`. The return shape is `list[dict]` with the V3 keys (`id`, `slug`, `title`, `group`, `brief`, `status`, `has_proposal`) — see discussion's Task-shape table for the V2→V3 field mapping.

  **`_tasks_md.Task` attribute access on iteration variables (file-wide):**

  After replacing the parse calls, the iteration variables (`t`, `task`, `entry`, `picked`, `cand`) hold dicts, not Task instances. Grep:

  ```bash
  grep -nE "\b(t|task|entry|picked|cand|c)\.(slug|title|phase|has_proposal|heading_line_no|brief|group|status)\b" plugins/mill/unit_tests/test-spawn-core.py
  ```

  Convert each access:
  - `<var>.slug` → `<var>["slug"]`
  - `<var>.title` → `<var>["title"]`
  - `<var>.phase` → `<var>["status"]` (field rename!)
  - `<var>.has_proposal` → `<var>["has_proposal"]`
  - `<var>.heading_line_no` → delete the access; rewrite the assertion or error message to be slug-only.

  Zero matches required after the conversion pass.

  **`_HOME_MD_*` fixture strings:**

  These hard-coded multi-line fixture strings at the module top (lines ~30-180) use V2 Home.md syntax — `## <title>\n[[<slug>]] [<phase>]\n\n_body_\n`. V3's `parse_home_md` accepts the same syntax (verified at `wiki/_parse.py:30+` which matches `[(?P<slug>[a-z][a-z0-9-]*)\]( \[(?P<status>s|active|ready-to-merge|pr-pending|done|blocked|abandoned)\])?`). Do NOT rewrite the fixture strings; they parse correctly under V3. The `[s]` (spawn-ready) phase token IS still parsed by V3 (the parser regex allows it) but `_parse.py` maps `[s]` to `status=None` — i.e. fixtures that exercised the `[s]` fast-path no longer trigger any special behaviour after batch 2's card 4 deletes those fast-paths. Tests that asserted on `t.phase == "s"` behaviour become dead — delete those test functions outright.

  **Tests to delete (enumerated at plan time from `test-spawn-core.py:230` and `:712`):**

  - `test_pick_task_single_fast_path_s` (defined at line 230; referenced in the main runner list)
  - `test_pick_task_single_or_multi_fast_path_s` (defined at line 712; referenced in the main runner list)

  Delete the function definitions AND remove their entries from the `tests = [...]` list at the bottom of `test-spawn-core.py:980+`. The commit message body lists both deletions by name.

  `test_pick_task_single_slug_matching_s` at line 197 stays — it exercises `--slug` mode (explicit slug matching), not the `[s]` fast-path. After V3 parses `[s]` to `status=None`, the test continues to validate slug-matching against the same fixture entry; only the implicit `[s]`-fast-path tests above die.

  **Test-name and assertion adjustments:**

  After the `.phase` → `["status"]` rename, any test name containing `phase` (e.g. `test_pick_task_returns_phase_s_entry`) refers to a now-dead behaviour. Either rename the test function to reflect the V3 semantics OR delete it under the `[s]`-dead-test rule above.

  **Final verification (do inside the implementer's edit loop, before committing):**

  ```bash
  grep -nE "^import _(wiki|tasks_md|sidebar)|^from _(wiki|tasks_md|sidebar) " plugins/mill/unit_tests/test-spawn-core.py
  grep -nE "_(wiki|tasks_md|sidebar)\." plugins/mill/unit_tests/test-spawn-core.py
  grep -nE "\.heading_line_no\b" plugins/mill/unit_tests/test-spawn-core.py
  ```

  All must return zero matches. Then run `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-spawn-core.py`. Expected: all remaining tests pass. The test count may decrease (deleted `[s]`-fast-path tests, deleted dead V2-only tests); commit body lists deletions by name.
- **Commit:** `test(spawn-core): port to V3 wiki API; drop [s]-fast-path tests`

## Batch Tests

The batch verify command is `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-fold.py && PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-spawn-core.py`. Both files must pass after their respective cards. The `&&` ensures the second test only runs if the first passes — preserving fast-fail.

The full unit-test suite remains partially red after this batch — `_test_helpers.py` and `test-millpy-spawn.py:967-970` still have V2 references that batch 6 (card 10) addresses. Do not gate this batch on `run-all.py`.
