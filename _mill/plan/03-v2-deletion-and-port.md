# Batch: v2-deletion-and-port

```yaml
task: Adopt V3 wiki module in V2 scripts
batch: v2-deletion-and-port
number: 3
cards: 21
verify: uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py
depends-on: [1]
```

## Batch Scope

Port every V2 wiki caller to the structured V3 API delivered by batch 1, move the two helpers (`read_junctions`/`read_hardlinks` and `clone_or_init`) out of `_wiki.py` to their new homes, purge every `wiki/config.yaml` reference from runtime code, docs, templates, and fixtures, and delete `_wiki.py`, `_tasks_md.py`, `_sidebar.py`, `millpy-migrate-config.py`, `millpy-migrate-layout.py`, and their tests. After this batch, no shipping code references `_wiki`, `_tasks_md`, `_sidebar`, or `wiki/config.yaml`.

This batch depends only on batch 1; it can run in parallel with batch 2. There is no file overlap with batch 2 (batch 2 creates `millpy-wiki-migrate.py` and `test-wiki-migrate.py`; this batch never touches them).

External-facing change for users: nothing. Every CLI keeps its current surface; only the wiki-layer plumbing under the hood is reshaped.

Batch-local decisions (differ from `## Shared Decisions` in `00-overview.md`):

- **Card ordering reflects dependency direction.** Module-move cards (15-18) and config-purge cards (19-20) land before the call-site ports (21-29) because the ports reference the moved helpers. The V2-file deletions (30-32) land after every port — once nothing imports `_wiki`/`_tasks_md`/`_sidebar`, deletion is safe. Test-fixture updates (33-35) land last because they validate the post-deletion shape.
- **`wiki.list_tasks_brief()` is the default for parse replacements.** Every former `_tasks_md.parse(home_text)` becomes `wiki.list_tasks_brief()` unless the original code consumed `body` (in which case it becomes `wiki.list_tasks_full()` or per-slug `wiki.get_task(slug)`). Each card calls out which shape it needs.
- **No advisory lock anywhere.** Every `wiki_lock` / `LockBusy` reference is removed at the same time as the related call-site port; CAS retries inside `wiki._client` handle conflicts. There is no transition state where some callers still wrap mutations in `wiki_lock`.
- **`millpy-wikipush.py` is a minimal sliver.** Only the `_wiki` import + `wiki_lock`/`LockBusy` usage is removed (card 28). The push logic itself — direct `git -C <wiki>` subprocess + on-the-fly conflict resolution — stays untouched per discussion decision `keep-wikipush-direct`.

## Cards

### Card 15: Move `read_junctions` / `read_hardlinks` to `_junction.py`

- **Context:**
  - `plugins/mill/scripts/_wiki.py`
- **Edits:**
  - `plugins/mill/scripts/_junction.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Copy the bodies of `read_junctions(hub_root)` and `read_hardlinks(hub_root)` from `_wiki.py` into `_junction.py`, retaining their public signatures. Strip the `wiki/config.yaml` fallback path inside each — only `<hub>/mill-config.yaml` is consulted. If `mill-config.yaml` is missing, raise the same exception the V2 functions raised in the same condition (preserve error type so existing call-site error handling continues to work). Do not delete the V2 copies in `_wiki.py` in this card — that happens in card 30 when `_wiki.py` is deleted whole.
- **Commit:** `feat(_junction): move read_junctions/read_hardlinks from _wiki`

### Card 16: Move `clone_or_init` to `_setup.py`

- **Context:**
  - `plugins/mill/scripts/_wiki.py`
- **Edits:**
  - `plugins/mill/scripts/_setup.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Copy the body of `clone_or_init(wiki_path, ...)` from `_wiki.py` into `_setup.py` as a module-level function with the same signature. The function has exactly one caller (`_setup.py` itself), so the copy lives alongside its caller and is not exported beyond `_setup.py`. Update the single internal call inside `_setup.py` from `_wiki.clone_or_init(...)` to the local function. Do not delete the V2 copy in `_wiki.py` in this card — that happens in card 30.
- **Commit:** `feat(_setup): move clone_or_init from _wiki`

### Card 17: Update `_setup.py` callers of `read_junctions` / `read_hardlinks`

- **Context:**
  - `plugins/mill/scripts/_junction.py`
- **Edits:**
  - `plugins/mill/scripts/_setup.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Lines 85 and 86 of `_setup.py` currently call `_wiki.read_junctions(...)` and `_wiki.read_hardlinks(...)`. Replace with `_junction.read_junctions(...)` and `_junction.read_hardlinks(...)` (or matching `from _junction import read_junctions, read_hardlinks` if the file already uses that import shape elsewhere). Drop the `_wiki` import from `_setup.py` if no other reference remains in the file. Keep behaviour identical.
- **Commit:** `refactor(_setup): switch read_junctions/read_hardlinks to _junction`

### Card 18: Update `millpy-cleanup.py:636` caller of `read_junctions`

- **Context:**
  - `plugins/mill/scripts/_junction.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-cleanup.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Line 636 of `millpy-cleanup.py` currently calls `_wiki.read_junctions(...)`. Replace with `_junction.read_junctions(...)` (matching whatever import shape the file already uses for `_junction` — adjust the import if needed). This card does NOT touch any other line in `millpy-cleanup.py`; those changes belong to card 23.
- **Commit:** `refactor(millpy-cleanup): switch read_junctions to _junction`

### Card 19: Strip `wiki/config.yaml` fallback from `_config.py`

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_config.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `_config.load_config`, remove the `wiki/config.yaml` fallback at lines 179, 188, and 198-202. Only `<hub>/mill-config.yaml` is consulted. When `mill-config.yaml` is missing, raise a clean `FileNotFoundError` (or whatever the existing error type is) with a message that references only `mill-config.yaml` — no mention of `wiki/config.yaml`, no stale-warning text. Drop any `wiki/config.yaml` related warning/print emitted by `_config.load_config`. Leave the function's public signature and all other behaviour intact.
- **Commit:** `refactor(_config): drop wiki/config.yaml fallback`

### Card 20: Strip `wiki/config.yaml` fallback from `_review_common.py`

- **Context:**
  - `plugins/mill/scripts/_config.py`
- **Edits:**
  - `plugins/mill/scripts/_review_common.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Remove the parallel `wiki/config.yaml` fallback in the review-side config loader. Concrete edits: drop the assignment at lines 1235-1239, the presence check at 1248, the merge at 1254-1257, the stale-warning at 1250, the "using legacy" warning at 1260; rewrite the missing-config error message at line 1269 to reference only `mill-config.yaml`. Remove the docstring mentions at lines 34 and 1211. The runtime behaviour should match `_config.load_config` post-card-19: only `mill-config.yaml` is consulted; missing -> clean error.
- **Commit:** `refactor(_review_common): drop wiki/config.yaml fallback`

### Card 21: Port `millpy-add.py` to `wiki.upsert_task`

- **Context:**
  - `plugins/mill/scripts/wiki/_client.py`
  - `plugins/mill/scripts/wiki/__init__.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-add.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Replace the `wiki_lock` + `_tasks_md.append_entry` + `_wiki.write_commit_push` flow at lines 169 and 198 with a single call to `wiki.upsert_task(slug, title=..., brief=..., body=..., group=...)`. The normal-add flow does not pass `status=...` (new tasks default to unmarked / `None`; phase transitions happen later via `wiki.set_phase`). Drop the `from _wiki import ...` and `from _tasks_md import ...` imports. Drop the `_sidebar` regeneration call if present — the daemon renders `_Sidebar.md` automatically. Update any error handling for `LockBusy` -> `WikiConflictError` (raised by `wiki._client` after `CAS_RETRIES` exhaustion). The argparse and prompt flow are untouched.
- **Commit:** `refactor(millpy-add): port to wiki.upsert_task`

### Card 22: Port `millpy-claim.py` to `wiki.list_tasks_brief`

- **Context:**
  - `plugins/mill/scripts/wiki/_client.py`
  - `plugins/mill/scripts/_config.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-claim.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** At line 45, delete `import _tasks_md`. At line 68, replace the direct `wiki_path / "config.yaml"` read with a call through `_config.load_config(wiki_path, worktree_root)` (matching the existing pattern in sibling scripts). At line 185, delete the `_wiki.sync_pull(...)` call entirely — the daemon lazy-refreshes inside every op. At line 187, replace `tasks = _tasks_md.parse(home_text)` with `tasks = wiki.list_tasks_brief()`; the brief shape (`id, slug, title, group, brief, status, has_proposal`) covers everything the claim flow reads. Update downstream consumers in the same file that previously accessed `Task` dataclass attributes -> use dict key access (`task["slug"]`, `task["title"]`, etc.). Drop the `_wiki` and `_tasks_md` imports.
- **Commit:** `refactor(millpy-claim): port to wiki.list_tasks_brief`

### Card 23: Port `millpy-cleanup.py` to `wiki.set_phase` / `wiki.list_tasks_brief`

- **Context:**
  - `plugins/mill/scripts/wiki/_client.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-cleanup.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Line-by-line:
  - `:25` — delete `import _tasks_md`.
  - `:75` — change the `list[_tasks_md.Task]` type hint to `list[dict]`.
  - `:523` — replace `_tasks_md.set_phase(home_text, slug, "done")` with `wiki.set_phase(slug, "done")`.
  - `:596` — replace `_tasks_md.set_phase(home_text, slug, None)` with `wiki.set_phase(slug, None)`.
  - `:603` — delete the surrounding `wiki_lock` context (the lock is gone; CAS handles concurrency).
  - `:627` — replace `_tasks_md.parse(_home_for_check)` with `wiki.list_tasks_brief()`. The `_home_for_check` local variable becomes unused — delete its assignment if appropriate.
  - `:635` — replace `_tasks_md.parse(home_text)` with `wiki.list_tasks_brief()`. The `home_text` local variable likewise.
  - `:653` — delete the `_wiki.write_commit_push(...)` call; `wiki.set_phase` commits inline through the daemon, so no separate commit step is needed.

  Drop the `_wiki` import if no other reference remains in the file (card 18 already handled the `read_junctions` reference). Adjust any downstream code that accessed `Task` attributes -> dict key access.
- **Commit:** `refactor(millpy-cleanup): port to wiki.set_phase / list_tasks_brief`

### Card 24: Port `millpy-fold.py` to V3 wiki API

- **Context:**
  - `plugins/mill/scripts/wiki/_client.py`
  - `plugins/mill/scripts/wiki/__init__.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-fold.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Line-by-line:
  - `:15` (docstring inside module docstring lines 1-32) — update the docstring text so the reference to `_tasks_md.LOCKED_FOLD_PHASES` points to `wiki.LOCKED_FOLD_PHASES` as the canonical home. No Python constant is at line 15; this is prose only.
  - `:39` — delete `import _tasks_md`.
  - `:76` — replace `_tasks_md._SLUG_RE.match(target_slug)` with a local compiled regex. At the top of `millpy-fold.py` add `_SLUG_RE = re.compile(r"^[a-z][a-z0-9-]*$")` and reference it at the call site. Do not export the regex; it stays local to this file.
  - `:87` — delete the `_wiki.wiki_lock` context-manager wrapping. The whole `with wiki_lock(...) as ...:` block becomes a flat sequence of statements.
  - `:93` — replace `tasks = _tasks_md.parse(home_text)` with `tasks = wiki.list_tasks_brief()`. The brief shape covers the fold flow's needs.
  - `:99` — replace `phase in _tasks_md.LOCKED_FOLD_PHASES` with `phase in wiki.LOCKED_FOLD_PHASES` (importing the constant from `wiki/__init__.py`).
  - `:135` — replace `_tasks_md.append_to_body(...)` with `task = wiki.get_task(target_slug); wiki.upsert_task(target_slug, body=(task["body"] + "\n" + fold_line))`. If `task["body"]` may be empty, handle gracefully (`(task["body"] or "") + fold_line`).
  - `:144` — delete the `_wiki.write_commit_push(...)` call; `wiki.upsert_task` commits inline.

  Drop the `_wiki` import. Drop any locally duplicated `LOCKED_FOLD_PHASES` constant if present.
- **Commit:** `refactor(millpy-fold): port to V3 wiki API`

### Card 25: Port `millpy-spawn.py` to `wiki.list_tasks_brief` and clean config guard

- **Context:**
  - `plugins/mill/scripts/wiki/_client.py`
  - `plugins/mill/scripts/_config.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-spawn.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Line-by-line:
  - `:44` — delete `import _tasks_md`.
  - `:66-72` — drop the `wiki_cfg = resolve_wiki_path(repo_root) / "config.yaml"` branch and any reference to `wiki_cfg` in the missing-config guard. The guard now checks only `mill_cfg.exists()`; on missing, raise the existing error message updated to reference only `mill-config.yaml`.
  - `:128` — delete the `_wiki.sync_pull(...)` call; daemon lazy-refreshes.
  - `:130` — replace `tasks = _tasks_md.parse(home_text)` with `tasks = wiki.list_tasks_brief()`.

  Drop the `_wiki` import. Update downstream `Task`-attribute accesses to dict keys.
- **Commit:** `refactor(millpy-spawn): port to wiki API; drop wiki/config.yaml branch`

### Card 26: Port `_spawn_core.py` to V3 wiki API (full file)

- **Context:**
  - `plugins/mill/scripts/wiki/_client.py`
  - `plugins/mill/scripts/wiki/__init__.py`
- **Edits:**
  - `plugins/mill/scripts/_spawn_core.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Line-by-line:
  - `:73` — delete `import _tasks_md`.
  - `:153, 231, 257, 259, 321, 322, 390, 392, 454, 528` — replace every `list[_tasks_md.Task]` with `list[dict]`; every bare `_tasks_md.Task` with `dict`. Type hints only; no behavioural change yet.
  - `:461-463` — update docstring references to `_tasks_md.remove_entry` / `append_entry` / `claim` -> `wiki.remove_task` / `wiki.upsert_task` / `wiki.set_phase`.
  - `:488-514` (`groom_and_claim_merge`) — replace the `wiki_lock` + read-modify-write window with: for each slug to merge, `wiki.remove_task(slug)`; then `wiki.upsert_task(merged_slug, title=..., brief=..., body=...)` (the `has_proposal` field is computed by `Store.list_tasks_brief` from `body`, so callers do not pass it); then `wiki.set_phase(merged_slug, "active")`. There is no advisory-lock wrapper. CAS conflicts surface as `WikiConflictError` and are retried inside `wiki._client` up to `CAS_RETRIES` (= 5 per batch 1 card 6). On final exhaustion, the exception propagates to the caller. No local `max_retries = N` literal — the constant lives in `wiki._client`.
  - `:493` — already covered by the `wiki.remove_task(slug)` rewrite above.
  - `:494` — already covered by `wiki.upsert_task(merged_slug, ...)` above.
  - `:497` and `:638` — `_tasks_md.claim(text, slug)` -> `wiki.set_phase(slug, "active")`.
  - `:518` — `_tasks_md.parse(new_text)` (a re-parse after commit, intended to return a `Task` for the caller) -> `wiki.get_task(merged_slug)`. The function's return signature changes from `_tasks_md.Task` to `dict`; update the type hint at the function signature line accordingly.
  - `:636-641` (`claim_in_wiki`) — replace the `wiki_lock` + Home.md read + `_tasks_md.claim` + write + `_wiki.write_commit_push` flow with a single `wiki.set_phase(slug, "active")` call. Drop the surrounding `with wiki_lock(...)` context manager.

  Drop the `_wiki` import. Drop any `LockBusy` exception handling (replace with `WikiConflictError` handling if the caller previously distinguished — most callers should not need to special-case conflicts now that retries are inside `wiki._client`).
- **Commit:** `refactor(_spawn_core): port to V3 wiki API; drop advisory lock`

### Card 27: Port `_marker.py` to V3 wiki API

- **Context:**
  - `plugins/mill/scripts/wiki/_client.py`
- **Edits:**
  - `plugins/mill/scripts/_marker.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Line-by-line:
  - `:22` — delete `import _tasks_md`.
  - `:53` — replace `_tasks_md.parse(home_text)` with `wiki.list_tasks_brief()`. Inspect the surrounding code to see how the result is consumed: if the call uses a per-slug lookup, replace with `wiki.get_task(slug)` and adjust the surrounding logic to handle the dict shape (or `None` on miss).
  - `:97` — same treatment as `:53`.

  Drop unused locals (`home_text`, etc.). Update any downstream code that accessed `Task` attributes -> dict key access.
- **Commit:** `refactor(_marker): port to wiki.list_tasks_brief / get_task`

### Card 28: Port small CLI tools (`millpy-inspect`, `millpy-status`, `millpy-terminal`, `millpy-vscode`) and `millpy-wikipush.py` sliver

- **Context:**
  - `plugins/mill/scripts/wiki/_client.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-inspect.py`
  - `plugins/mill/scripts/millpy-status.py`
  - `plugins/mill/scripts/millpy-terminal.py`
  - `plugins/mill/scripts/millpy-vscode.py`
  - `plugins/mill/scripts/millpy-wikipush.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** For each of the four small CLI tools:
  - `millpy-inspect.py:20` — delete `import _tasks_md`. `:54` — replace `_tasks_md.parse(home_md.read_text(...))` with `wiki.list_tasks_brief()`. Drop any `home_md` local read.
  - `millpy-status.py:20` — delete `import _tasks_md`. `:32` — replace `_tasks_md.parse(...)` with `wiki.list_tasks_brief()`.
  - `millpy-terminal.py:23` — delete `import _tasks_md`. `:59` — replace `_tasks_md.parse(...)` with `wiki.list_tasks_brief()`.
  - `millpy-vscode.py:31` — delete `import _tasks_md`. `:180` — replace `_tasks_md.parse(...)` with `wiki.list_tasks_brief()`.

  Update any consumers in those files that accessed `Task` attributes -> dict key access. Brief shape includes `title` and `has_proposal` per batch 1 card 1, which covers every documented consumer in these files (discussion lines 36 enumerate the consumers).

  For `millpy-wikipush.py` (minimal sliver per discussion decision `keep-wikipush-direct`):
  - `:32` — delete `import _wiki`.
  - `:104, :111, :113` — remove the `wiki_lock(...) as lock_handle` context manager and the `LockBusy` exception clause. The body of the `with` block becomes a flat sequence of statements. The push logic — direct `git -C <wiki>` subprocess calls and on-the-fly conflict resolution — is untouched.

  This card spans five files; each edit is a small mechanical change. Treat as one card because the work is uniform.
- **Commit:** `refactor(millpy-*): port small CLIs to wiki.list_tasks_brief; drop _wiki from wikipush`

### Card 29: Update error/docstring text references in `_paths.py`, `_junction.py`, `_worktree.py`

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/scripts/_junction.py`
  - `plugins/mill/scripts/_worktree.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Update text references (no code changes, no signature changes):
  - `_paths.py:125, :140, :407` — drop any mention of `_wiki.write_commit_push` from error messages; reword to reference `wiki._client` or the relevant public op as appropriate.
  - `_junction.py:239` — update the docstring reference from `_wiki.*` to `_junction.read_junctions` / `read_hardlinks` as appropriate to the surrounding context.
  - `_worktree.py:207` — update the docstring reference from `_wiki.*` to `wiki._client.*`.

  These are surface-only changes — no behaviour shifts.
- **Commit:** `docs(scripts): update _wiki references in error/docstring text`

### Card 30: Delete `_wiki.py`, `_tasks_md.py`, `_sidebar.py`

- **Context:** none
- **Edits:** none
- **Creates:** none
- **Deletes:**
  - `plugins/mill/scripts/_wiki.py`
  - `plugins/mill/scripts/_tasks_md.py`
  - `plugins/mill/scripts/_sidebar.py`
- **Requirements:** Delete the three V2 wiki-layer modules entirely. Cards 15-29 have ported every caller; cards 33-34 will update test fixtures. Before deleting, grep the repo for `import _wiki`, `from _wiki`, `import _tasks_md`, `from _tasks_md`, `import _sidebar`, `from _sidebar` — there should be zero remaining matches in `plugins/mill/scripts/` (test files in `plugins/mill/unit_tests/` and `plugins/mill/integration_tests/` that still reference these are addressed in cards 33-34). If a hit appears that this plan did not anticipate, halt and surface the file path — it is a plan gap.
- **Commit:** `chore(scripts): delete _wiki.py, _tasks_md.py, _sidebar.py`

### Card 31: Delete `millpy-migrate-config.py` and its integration test

- **Context:** none
- **Edits:** none
- **Creates:** none
- **Deletes:**
  - `plugins/mill/scripts/millpy-migrate-config.py`
  - `plugins/mill/integration_tests/test-migration.py`
- **Requirements:** Delete both files. The script is a one-shot migration for a transition that is long since done; per discussion decision `purge-wiki-config-yaml`, no upgrade path uses it. The test is deleted with the script it covered.
- **Commit:** `chore(scripts): delete millpy-migrate-config and its test`

### Card 32: Delete `millpy-migrate-layout.py`

- **Context:** none
- **Edits:** none
- **Creates:** none
- **Deletes:**
  - `plugins/mill/scripts/millpy-migrate-layout.py`
- **Requirements:** Delete the script. Same disposition as `millpy-migrate-config.py` — one-shot layout migration for the old `hub/` + `worktrees/` layout that is long since done. If a sibling test file exists that covers only this script, delete it in the same commit. Grep for any importer; there should be none.
- **Commit:** `chore(scripts): delete millpy-migrate-layout`

### Card 33: Update prompt templates and skill docs

- **Context:** none
- **Edits:**
  - `plugins/mill/templates/review-plan-holistic.md`
  - `plugins/mill/templates/review-plan-batch.md`
  - `plugins/mill/skills/mill-claim/SKILL.md`
  - `plugins/mill/skills/mill-finalize/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In each prompt template, remove the BLOCKING rule that flagged plans touching `wiki/config.yaml`. The rule no longer applies — runtime code, fixtures, and docs do not consult `wiki/config.yaml` after this batch. In each skill doc, drop any sentence or paragraph that referenced `wiki/config.yaml`. Re-read both skill docs end-to-end to ensure no broken cross-references (e.g. a section heading referenced from elsewhere is not silently removed).
- **Commit:** `docs(templates, skills): drop wiki/config.yaml references`

### Card 34: Update test-fixture creators across unit tests

- **Context:** none
- **Edits:**
  - `plugins/mill/unit_tests/test-cleanup.py`
  - `plugins/mill/integration_tests/test-cleanup.py`
  - `plugins/mill/integration_tests/test-merge.py`
  - `plugins/mill/unit_tests/test-millpy-implement.py`
  - `plugins/mill/integration_tests/test-review-discussion.py`
  - `plugins/mill/unit_tests/test-config.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Grep each file for `wiki/config.yaml`. For each match:
  - If the fixture writes `<wiki>/config.yaml` for general setup (so callers can find junctions/hardlinks), replace with writing `<hub>/mill-config.yaml` instead. The hub root is the parent of the worktree; the test fixture already creates the hub. Keys move verbatim from the V2 schema where applicable.
  - If the test's PURPOSE was to exercise the now-deleted fallback path (e.g. `test-config.py::test_load_config_falls_back_to_wiki_config_yaml`), delete the test function entirely (not the file). The legacy-fallback test and the fallback-precedence test in `test-config.py` go away outright.
  - Update remaining `test-config.py` tests to use only `mill-config.yaml`.

  After this card, no shipping test creates `wiki/config.yaml`. A grep across `plugins/mill/unit_tests/` and `plugins/mill/integration_tests/` for `wiki/config.yaml` returns zero matches.
- **Commit:** `test: drop wiki/config.yaml from fixtures; remove fallback tests`

### Card 35: Port and clean up the per-CLI tests; delete V2-only tests

- **Context:**
  - `plugins/mill/scripts/wiki/_client.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-millpy-add.py`
  - `plugins/mill/unit_tests/test-millpy-claim.py`
  - `plugins/mill/unit_tests/test-fold.py`
- **Creates:** none
- **Deletes:**
  - `plugins/mill/unit_tests/test-wiki.py`
  - `plugins/mill/unit_tests/test-tasks-md.py`
  - `plugins/mill/unit_tests/test-sidebar.py`
- **Requirements:** Two parts:

  **Delete V2-only tests:** `test-wiki.py` (V2 `_wiki.py` lock/write tests), `test-tasks-md.py` (V2 parser tests), `test-sidebar.py` (V2 sidebar regen). Their target modules are gone.

  **Port per-CLI tests:**
  - `test-millpy-add.py` — drop any V2 `_wiki`/`_tasks_md` mock or fixture; assert that running `millpy-add` results in `wiki.upsert_task` being called (mock the function or seed a real daemon fixture, matching the rest of the suite's style) and that `tasks.json` after the run reflects the new entry. The daemon-rendered `Home.md` includes the new task.
  - `test-millpy-claim.py` — adjust fixtures so the test seeds tasks via the V3 daemon (or directly via TinyDB if the suite already has a helper for that). Assert phase flip via `wiki.set_phase`.
  - `test-fold.py` — assert body amendment lands via `wiki.upsert_task` (body field updated, prior content preserved per the read-then-append pattern in card 24).

  Each ported test must still pass against the post-batch state. No test should still import `_wiki`, `_tasks_md`, or `_sidebar`.
- **Commit:** `test: delete V2 tests; port per-CLI tests to V3 wiki API`

## Batch Tests

The batch verify command is `uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py`. After this batch, no shipping code or test references `_wiki`, `_tasks_md`, `_sidebar`, or `wiki/config.yaml`; every V2 caller routes through `wiki._client`. The full unit-test suite must pass green. Integration tests covering V3 (`test-wiki-e2e.py` from batch 1, `test-wiki-migrate.py` from batch 2) are not re-run here — those batches own their verify gates. Cards 28's `millpy-wikipush.py` sliver is exercised manually if needed (no dedicated test exists; that script's push semantics are out of scope).
