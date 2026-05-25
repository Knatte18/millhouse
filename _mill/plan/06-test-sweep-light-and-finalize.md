# Batch: test-sweep-light-and-finalize

```yaml
task: "Finish V3 wiki adoption — complete batch 3 port and test sweep"
batch: test-sweep-light-and-finalize
number: 6
cards: 4
verify: "PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py"
depends-on: [5]
```

## Batch Scope

Finish the V2 elimination across the remaining test surface and finalize the task. Cards in order:

1. Port `_test_helpers.py` + the small V2 block inside `test-millpy-spawn.py:967-970`.
2. Fix the `test-wiki-noop-commit.py` fixture's missing-`origin` issue (the in-scope surfaced bug from discussion's `## Decisions ## Surfaced-bug policy`).
3. Spot-clean integration tests that still reference V2 (out of verify gate per discussion, but cleaned to avoid future confusion).
4. Run the final `run-all.py` smoke and assert zero failures. (Note: `_mill/handoff.md` was already removed in commit `f5a186b` on this branch — no rm needed.)

Four S-effort cards, sum effort 4 — exactly fills the batch ceiling.

Depends on batch 5 because the helper-port in card 10 must come after the heavy test files port — otherwise we risk a chicken-and-egg situation where `_test_helpers` is mid-port while other tests still import its V2-flavoured shape.

Batch-local decisions (differ from `## Shared Decisions` in `00-overview.md`):

- **Integration tests are out of the verify gate, but the spot-clean is in-scope.** The discussion's `## Out` list excludes integration tests from gating, but the V2-elimination scope DOES require cleaning every reference — see discussion's framing: "End state has zero V2 references anywhere". The spot-clean treats integration tests as best-effort; if any can't be cleaned mechanically (e.g. requires fixture redesign), file a follow-up issue + add a `pytest.skip` mark in the test.
- **Zero failures is the final-batch criterion.** Per discussion's `## Decisions ## Per-batch verify mandatory + zero-failure end criterion`, this batch's verify (`run-all.py`) MUST exit 0 with zero failing tests. Any test that cannot be brought green in-scope gets a GitHub issue + a `pytest.skip("see #NNN")` mark with the issue link in the test file.

## Cards

### Card 10: Port `_test_helpers.py` and the `test-millpy-spawn.py:967-970` V2 block

- **Effort:** S
- **Context:**
  - `plugins/mill/scripts/wiki/_parse.py`
  - `plugins/mill/scripts/_spawn_core.py`
- **Edits:**
  - `plugins/mill/unit_tests/_test_helpers.py`
  - `plugins/mill/unit_tests/test-millpy-spawn.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Eliminate the remaining V2 references in the two test files.

  `plugins/mill/unit_tests/_test_helpers.py`:
  - Line 25: delete `import _tasks_md  # noqa: E402`.
  - Add `from wiki._parse import parse_home_md  # noqa: E402` in the same import block.
  - Line 114: replace `parsed = _tasks_md.parse(home_body)` with `parsed = parse_home_md(home_body)`.
  - Line 115: `next((t for t in parsed if t.slug == slug), None)` → `next((t for t in parsed if t["slug"] == slug), None)`.
  - Lines 119-120 (or wherever `found.phase` is referenced): rename `found.phase` to `found["status"]` (V2 `phase` → V3 `status` field rename per discussion's Task-shape table). The assertion text "expected phase=..." may stay as-is or be updated to "expected status=..." — choose the clearer wording; this is a test-internal error message, not a public contract.

  `plugins/mill/unit_tests/test-millpy-spawn.py`:
  - Locate the block at approximately lines 962-975 — the `test_spawn_discovery_round_trip_subfolder` test method clears `sys.modules`, then re-imports `_spawn_core`, `_config`, `_paths`, `_tasks_md`. The `_to_clear` list at line 961 contains `"_tasks_md"`; remove it from the list (the entry is now harmless but is a V2 reference that the grep would flag).
  - Line 967 (or thereabouts): `import _tasks_md as real_tasks_md`. Delete the line.
  - Line 970 (or thereabouts): `home_tasks = real_tasks_md.parse((wiki / "Home.md").read_text(encoding="utf-8"))` → `from wiki._parse import parse_home_md; home_tasks = parse_home_md((wiki / "Home.md").read_text(encoding="utf-8"))`. The `from wiki._parse import parse_home_md` can move to module top alongside the other re-imports for cleanliness.

  Also check the `stubs` list near the top of `test-millpy-spawn.py` (around line 39+ — the `_test_smoke_import`'s stub block). If `_tasks_md` and `_wiki` appear in the stubs list, remove them — the smoke import no longer needs to stub these modules because `millpy-spawn.py` (post-batch-3) no longer imports them.

  **Final verification (do inside the implementer's edit loop, before committing):**

  ```bash
  grep -nE "^import _(wiki|tasks_md|sidebar)|^from _(wiki|tasks_md|sidebar) " plugins/mill/unit_tests/_test_helpers.py plugins/mill/unit_tests/test-millpy-spawn.py
  grep -nE "_(wiki|tasks_md|sidebar)\." plugins/mill/unit_tests/_test_helpers.py plugins/mill/unit_tests/test-millpy-spawn.py
  ```

  Both must return zero matches. Then run `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-millpy-spawn.py`. All 11 tests must pass (the previously-failing `test_spawn_discovery_round_trip_subfolder` goes green).
- **Commit:** `test(_test_helpers, millpy-spawn): drop final V2 refs; use wiki._parse.parse_home_md`

### Card 11: Fix `test-wiki-noop-commit.py` fixture missing-`origin` remote

- **Effort:** S
- **Context:**
  - `plugins/mill/scripts/wiki/_sync.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-wiki-noop-commit.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** The test `test_real_change_commits_normally` in `plugins/mill/unit_tests/test-wiki-noop-commit.py` currently fails with `wiki.WikiPushError: git push failed: 'fatal: No configured push destination.'`. The cause is that the test fixture creates a wiki clone with no `origin` remote, but `wiki._sync.commit_push` calls `git push` unconditionally. Production `commit_push` is correct (wikis always have an `origin` in production); the test fixture is wrong.

  Add a bare-clone `origin` remote to the test's wiki fixture. All three tests in `test-wiki-noop-commit.py` build their fixture via the shared `_setup_wiki(wiki_path)` helper at the top of the file (line 31). Modify the helper itself — that's one edit that fixes all three tests at once (the two no-op tests already pass; the third reaches the push and currently fails).

  In `_setup_wiki(wiki_path)`, after the existing wiki-clone init steps, add:

  ```python
  # Bare-clone "origin" so commit_push's git push has a destination.
  bare = wiki_path.parent / f"{wiki_path.name}.git"
  subprocess.run(["git", "init", "--bare", str(bare)], check=True, capture_output=True)
  subprocess.run(["git", "-C", str(wiki_path), "remote", "add", "origin", str(bare)], check=True, capture_output=True)
  subprocess.run(["git", "-C", str(wiki_path), "push", "-u", "origin", "HEAD"], check=True, capture_output=True)
  ```

  Where `wiki_path` is the existing helper's parameter (line 31 signature: `def _setup_wiki(wiki_path: Path) -> None:`). The bare clone lives as a sibling of `wiki_path` so it shares the same tempdir lifecycle.

  Do NOT add per-test patching — the helper edit covers all three tests with one change.

  Then re-run the test to confirm it passes:

  ```bash
  PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-wiki-noop-commit.py
  ```

  All three tests in the file must pass (currently 2 of 3 pass; this card brings it to 3 of 3).

  Do NOT modify `plugins/mill/scripts/wiki/_sync.py`. Production behaviour is correct.
- **Commit:** `test(wiki-noop-commit): add bare-clone origin to fixture so commit_push push succeeds`

### Card 12: Spot-clean V2 references in integration tests

- **Effort:** S
- **Context:**
  - `plugins/mill/scripts/wiki/__init__.py`
  - `plugins/mill/scripts/wiki/_parse.py`
- **Edits:**
  - `plugins/mill/integration_tests/test-spawn.py`
  - `plugins/mill/integration_tests/test-spawn-units.py`
  - `plugins/mill/integration_tests/test-merge.py`
  - `plugins/mill/integration_tests/test-wiki-concurrency.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Spot-clean each integration test file's V2 references. Integration tests are out of the verify gate per discussion, but cleaning them is in-scope per the "eliminate every trace of V2" framing.

  For each file, apply the same V2→V3 rewrites used by batch 5 cards 8 and 9. Where the file genuinely calls V3 client functions (not just `LOCKED_FOLD_PHASES` or `WikiPushError`), use the canonical alias-import pattern `from wiki import _client as wiki` (mirrors `millpy-fold.py:39`).

  - `import _tasks_md` / `import _wiki` / `import _sidebar` → delete the line.
  - `_tasks_md.parse(text)` → `parse_home_md(text)` (after `from wiki._parse import parse_home_md`).
  - `_tasks_md.Task(slug=..., title=..., phase=..., has_proposal=...)` → `{"slug": ..., "title": ..., "status": ..., "has_proposal": ..., "id": <int>, "group": None, "brief": None}` dict literal (V3 dict shape with `id` int — pick any unique int per test).
  - `_tasks_md.set_phase(home_text, slug, phase)` → `wiki.set_phase(wiki_path, slug, phase)`.
  - `_wiki.write_commit_push(wiki, files, msg, slug=...)` → delete (V3 daemon-mediated ops commit inline) OR `wiki._sync.commit_push(wiki, files, msg)` if the test exercises non-daemon-mediated commit semantics.
  - `_wiki.wiki_lock(wiki, slug)` → unwrap the context manager (V3 has no advisory lock).
  - `_sidebar.regenerate(wiki)` → delete (V3 daemon regenerates internally).
  - `_wiki.sync_pull(wiki, slug=...)` → delete (V3 daemon lazy-refreshes).

  **Integration tests are bare scripts, not pytest collections.** Every file in `plugins/mill/integration_tests/` is invoked directly via `python <file>.py`; they use `assert` + `print("PASS:")` patterns and `def main() -> int` runners. There is no `import pytest` and no pytest collection wrapping. Therefore **`pytest.skip(...)` is forbidden in this card** — it raises `Skipped` outside a pytest context and crashes the script. Use the script-friendly skip pattern instead: delete the affected helper function entirely AND remove its caller (or, for the function bodies themselves, replace with an early `return 0` plus `print(f"SKIP: <reason>; see #NNN")` followed by a Python comment block documenting the deletion).

  **`wiki` local-variable collision (same shape as card 6).** Both `test-merge.py` (line 90: `wiki = container / "wiki"`) and any other integration test that uses `wiki` as a local Path AND needs to call V3 client functions will collide with `from wiki import _client as wiki`. Rename the local to `wiki_path` end-to-end in each affected file BEFORE adding the alias-import. Same pattern as card 6 (the four reader CLIs).

  Per-file specifics:

  - `test-spawn.py:42` (`import _tasks_md`), `:206` (`_tasks_md.parse(...)`). No `wiki` local-collision in this file's main code path (a brief grep shows `wiki` is used as a Path local; rename to `wiki_path` if `from wiki import _client as wiki` is added). If only `parse_home_md` is needed (text-only parsing), use `from wiki._parse import parse_home_md` and no `_client` import — no rename needed.
  - `test-spawn-units.py:23` (`import _tasks_md`), `:34-35` (uses `_tasks_md.Task(...)` builder). The fixture builder needs the dict-literal replacement; check the surrounding code for any `.slug`/`.title`/`.phase` attribute accesses and convert them to dict-key access. If the file calls V3 client functions, rename any `wiki` Path local to `wiki_path`.
  - `test-merge.py:56` (`import _sidebar`), `:57` (`import _tasks_md`), `:59` (`import _wiki`), `:90` (the `wiki = container / "wiki"` local — **rename to `wiki_path` end-to-end across the file** before adding `from wiki import _client as wiki`; this is mandatory because the file calls V3 client functions per the next bullets), `:298` (`_wiki.wiki_lock`), `:300` (`_tasks_md.set_phase` → `wiki.set_phase(wiki_path, slug, phase)`), `:302` (`_wiki.write_commit_push` → delete; daemon-mediated), `:315` (`_sidebar.regenerate(wiki)` → delete; daemon-mediated), `:320` (`print("PASS: _sidebar.regenerate ran without error")` → rewrite the print to no longer reference the deleted helper, or delete the test step entirely if it was only verifying the V2 helper ran).
  - `test-wiki-concurrency.py:6` (docstring mention), `:64` (docstring mention), `:72` (`_wiki.sync_pull` inside a subprocess source-template string). This file's `wiki` and `clone` locals are Path objects; if the rewrite needs V3 client functions in the subprocess template, write the template with `from wiki import _client as wiki` inside the template string itself and reference `wiki_path` as a string-formatted path. The subprocess source is a code template — rewrite to call a V3 sync if needed (e.g. `wiki.health_check(wiki_path)` to drive a daemon ping, which exercises the same network-roundtrip behaviour the V2 test wanted to exercise). If the test's purpose is specifically the V2 advisory-lock contention (which doesn't exist in V3), delete the test outright and file a follow-up issue noting that the V3 concurrency model is different and warrants its own test design.

  **Cap on script-level skips: at most 2 functions across the four integration test files can be converted to early-return-with-print skips.** A skip means: the function body becomes `print(f"SKIP: {reason}; see #NNN"); return 0` (or equivalent for non-`main` functions: drop the function from the runner list at the bottom of the file). If more would be needed to mechanically clean the references, halt under the stuck-policy (`## Shared Decisions ## Decision: stuck-policy-pause-for-human`) and ask the operator to redesign the card. The V2-elimination framing of this task does not tolerate an unbounded skip escape, and `pytest.skip()` is not an option for bare scripts.

  Do NOT touch `test-bootstrap.ps1` — it is a PowerShell integration test, out of scope (no PowerShell on this machine).

  **Final verification:**

  ```bash
  grep -rnE "^import _(wiki|tasks_md|sidebar)|^from _(wiki|tasks_md|sidebar) |_(wiki|tasks_md|sidebar)\." plugins/mill/integration_tests/test-spawn.py plugins/mill/integration_tests/test-spawn-units.py plugins/mill/integration_tests/test-merge.py plugins/mill/integration_tests/test-wiki-concurrency.py
  ```

  Zero matches required across all four files. The integration tests are not run as part of this card's verify; their cleanup is purely textual.
- **Commit:** `test(integration): spot-clean V2 references; skip deeply broken with follow-up issues`

### Card 13: Final V2-elimination smoke

- **Effort:** S
- **Context:**
  - `plugins/mill/unit_tests/run-all.py`
- **Edits:** none
- **Creates:** none
- **Deletes:** none
- **Requirements:** Final-batch wrap-up. Steps in order:

  1. Run the full unit-test smoke:

     ```bash
     PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py
     ```

     The command MUST exit 0 with zero failing tests. If any test fails:
     - Confirm the failure is reasonably attributable to the V2→V3 port. If yes, halt under the stuck-policy and ask the operator before adding new cards.
     - If no (orthogonal bug), file a GitHub issue, add a `pytest.skip("see #NNN")` mark with the issue link in the affected test file, and rerun. The skip-mark addition + issue-filing is a tiny extension of this card's scope; the commit message should mention the skip.

  2. Run a final V2-elimination grep across the entire repo to confirm the framing is honoured:

     ```bash
     grep -rnE "^import _(wiki|tasks_md|sidebar)|^from _(wiki|tasks_md|sidebar) " plugins/mill/scripts/ plugins/mill/unit_tests/ plugins/mill/integration_tests/
     ```

     Zero matches required across shipping + unit tests. Integration tests may still have residual references that card 12 skipped via `pytest.skip` — the skip-marked tests are acceptable; the imports themselves should still be gone.

  This card has no file edits — the verify itself is the only deliverable. If `run-all.py` is already green with no skip-marks added, this commit is empty; in that case skip the commit and let mill-go observe the batch verify-pass directly. (`_mill/handoff.md` was already removed in commit `f5a186b` on this branch — no rm step is needed.)
- **Commit:** `chore: final V2-elimination smoke`

## Batch Tests

The batch verify command is `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py`. This is the final smoke for the entire task. It MUST exit 0 with zero failing tests after card 13 lands.

Acceptable end-state failures are limited to `pytest.skip`-marked tests with a follow-up GitHub issue link in the skip reason; these still count as PASS in `run-all.py`'s exit code.

After this batch, the task is `phase: implemented` (mill-go handles the status transition). `mill-finalize` then squash-merges to `hanf/wiki-v3-adoption` per the discussion's merge-strategy decision.
