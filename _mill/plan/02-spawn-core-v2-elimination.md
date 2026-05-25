# Batch: spawn-core-v2-elimination

```yaml
task: "Finish V3 wiki adoption — complete batch 3 port and test sweep"
batch: spawn-core-v2-elimination
number: 2
cards: 1
verify: "PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-millpy-color.py"
depends-on: [1]
```

## Batch Scope

Convert `plugins/mill/scripts/_spawn_core.py` from its current V2/V3-hybrid state to fully V3. This is the largest single port in the task: drop all three deleted-V2 module imports (`_tasks_md`, `_wiki`, `_sidebar`), replace every V2 call site, convert every type hint and iteration-variable attribute access from `_tasks_md.Task` to dict shape, delete the `[s]` (spawn-ready) phase fast-paths, and delete the `_task_to_dict` scaffold helper introduced in `a1f7aac`.

This batch is a single L-effort card because every change is structurally interconnected: type hints and attribute accesses must move together, the helper deletion depends on no callers having Task objects, and the imports cannot be dropped until every call site is ported. Splitting would create intermediate broken states.

External interface change consumed by later batches: `_spawn_core.multi_select_groom_then_claim` and `_spawn_core.claim_in_wiki` change return type from `_tasks_md.Task` (or `list[_tasks_md.Task]`) to `dict` (or `list[dict]`). `millpy-spawn.py` (batch 3) consumes this change.

Batch-local decisions (differ from `## Shared Decisions` in `00-overview.md`):

- **`merge_tasks` is the V3 replacement for the `wiki_lock` + remove + append + claim window.** Per discussion's Technical-context API table (verified at `_client.py:289–331`), `wiki.merge_tasks(wiki_path, *, remove_slugs, upsert, set_phase)` is keyword-only and atomic. The card uses this in `multi_select_groom_then_claim`.
- **No `LockBusy` catches.** The V3 daemon serialises writes internally. Code that previously caught `LockBusy` lets `WikiPushError` propagate.

## Cards

### Card 4: Port `_spawn_core.py` to V3 wiki API — full V2 elimination

- **Effort:** L
- **Context:**
  - `plugins/mill/scripts/wiki/__init__.py`
  - `plugins/mill/scripts/wiki/_client.py`
  - `plugins/mill/unit_tests/test-millpy-color.py`
- **Edits:**
  - `plugins/mill/scripts/_spawn_core.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Eliminate every V2 reference from `plugins/mill/scripts/_spawn_core.py`. Apply the following changes; line numbers are from the current state on `hanf/wiki-v3-batch3-finish` HEAD.

  **Imports (lines 70, 73-74):**

  - Delete `import _sidebar` (line 70).
  - Delete `import _tasks_md` (line 73).
  - Delete `import _wiki` (line 74).
  - Add `from wiki import _client as wiki` near the top of the imports block (alongside the other absolute imports). This is the canonical V3 import pattern used by `millpy-add.py:36`, `millpy-claim.py:46`, `millpy-cleanup.py:25`, `millpy-fold.py:39`, and `_marker.py:22`. Note: `wiki/__init__.py` re-exports constants and exception classes only; the functions (`list_tasks_brief`, `set_phase`, `upsert_task`, `merge_tasks`, `get_task`, `remove_task`, `health_check`) live in `_client.py`. The `_client as wiki` alias gives a clean `wiki.<fn>` call surface that mirrors the API table in the discussion.

  **Type hints and the partial-port helper (lines 153, 232, 257-268, 271, 336-337, 405, 545):**

  - Line 153: change parameter type hint `home_tasks: list[_tasks_md.Task]` to `home_tasks: list[dict]`.
  - Line 232: change `def _prompt_numbered(candidates: list[_tasks_md.Task]) -> Optional[_tasks_md.Task]:` to `def _prompt_numbered(candidates: list[dict]) -> Optional[dict]:`.
  - Lines 257-268: **delete the entire `_task_to_dict` function**. It was added by commit `a1f7aac` as a partial-port scaffold and has no V3 purpose once all callers consume dicts.
  - Line 271: change `tasks: list[_tasks_md.Task]` to `tasks: list[dict]` (one of the `multi_select_groom_then_claim` signature lines).
  - Lines 336-337: change the `candidates: list[_tasks_md.Task]` / `) -> list[_tasks_md.Task]:` pair to `candidates: list[dict]` / `) -> list[dict]:`.
  - Line 405: change `tasks: list[_tasks_md.Task]` to `tasks: list[dict]`.
  - Line 545: change `source_tasks: list[_tasks_md.Task]` to `source_tasks: list[dict]` (this parameter is in `prompt_merged_entry`, not `multi_select_groom_then_claim`).

  Remove every remaining `_tasks_md.Task` reference (grep `_tasks_md\.Task` end-to-end after the above; zero matches required).

  **Iteration-variable attribute → dict-key access (file-wide, no specific line list):**

  Grep the file for every reference of the form `<var>.<attr>` where `<var>` is an iteration variable previously typed `_tasks_md.Task` (commonly `t`, `task`, `entry`, `picked`, `chosen`, `c`, `cand`) and `<attr>` is one of `slug`, `title`, `phase`, `has_proposal`, `heading_line_no`, `brief`, `group`, `status`. For each:
  - `<var>.slug` → `<var>["slug"]`
  - `<var>.title` → `<var>["title"]`
  - `<var>.phase` → `<var>["status"]` (note the V2→V3 field rename per discussion's Task-shape table)
  - `<var>.has_proposal` → `<var>["has_proposal"]`
  - `<var>.heading_line_no` → **delete the entire access**; if the access was inside an error message format string, rewrite the message to be slug-only (e.g. `f"task {t['slug']} at line {t.heading_line_no}: ..."` → `f"task {t['slug']}: ..."`).
  - `<var>.brief` → `<var>["brief"]` (or `<var>.get("brief")` if the original was guarded; `list_tasks_brief` always supplies the key).
  - `<var>.group` → `<var>["group"]`
  - `<var>.status` → `<var>["status"]`

  After this pass, run `grep -nE "\b(t|task|entry|picked|chosen|c|cand)\.(slug|title|phase|has_proposal|heading_line_no|brief|group|status)\b" plugins/mill/scripts/_spawn_core.py` — zero matches required.

  **Docstring references (lines 477-479):**

  - Line 477: change `1. Remove each source slug's entry from Home.md via ``_tasks_md.remove_entry``.` → `1. Remove each source slug's entry via ``wiki.merge_tasks(... remove_slugs=...)``.`
  - Line 478: change `2. Append the merged entry via ``_tasks_md.append_entry``.` → `2. Upsert the merged entry via ``wiki.merge_tasks(... upsert=...)``.`
  - Line 479: change `3. Mark the merged entry ``[active]`` via ``_tasks_md.claim``.` → `3. Mark the merged entry ``"active"`` via ``wiki.merge_tasks(... set_phase=(merged_slug, "active"))``.`

  **`multi_select_groom_then_claim` body (lines 504, 509-513, 515, 530, 534):**

  Replace the entire `with _wiki.wiki_lock(wiki_path, merged_slug):` block (line 504 through line ~534) with a single atomic call. The function's existing signature is `multi_select_groom_then_claim(wiki_path, source_slugs: list[str], merged_title, merged_slug, merged_body, has_proposal=False, proposal_body=None)` — verified at `_spawn_core.py:462–469`. **`source_slugs` is already `list[str]`, so pass it directly to `remove_slugs`:**

  ```python
  result = wiki.merge_tasks(
      wiki_path,
      remove_slugs=source_slugs,
      upsert={
          "slug": merged_slug,
          "title": merged_title,
          "body": merged_body,
          "group": merged_group,
      },
      set_phase=(merged_slug, "active"),
  )
  ```

  The variable names `merged_title`, `merged_body` exist already as parameters; `merged_group` may need to be derived (the function does not take a `group` param explicitly — read the existing body to see if a group is inferred from one of the source tasks or hardcoded; pass it through accordingly. If no group is in scope, drop the `"group"` key from the upsert dict — `upsert_task` treats omitted keys as no-change/inherit). Do NOT introduce a `source_tasks` local — only `source_slugs` exists in this function's scope. Do NOT pass `has_proposal` to the `upsert` dict — it is computed by `Store.list_tasks_brief` from `body`. After the call:

  - Delete the `_sidebar.regenerate(wiki_path)` line (line 515) outright — the V3 daemon renders the sidebar inside the same op.
  - Delete the `_wiki.write_commit_push(wiki_path, files_to_commit, commit_msg, slug=merged_slug)` line (line 530) — `merge_tasks` commits inline.
  - Delete the `parsed_tasks = _tasks_md.parse(new_text)` line (line 534) — `merge_tasks` returns the upserted dict directly. If downstream code in the same function needed `parsed_tasks` (e.g. to return the merged task), use `result` from the `merge_tasks` call. If it needed a re-fetch by slug, use `wiki.get_task(wiki_path, merged_slug)`.

  Update the function's return-type annotation accordingly: change `-> _tasks_md.Task` (if present) to `-> dict`.

  **`[s]` (spawn-ready) phase fast-paths:**

  Remove every code path that fast-tracks tasks with `phase == "s"`. V3 parses `[s]` to `None`, so no task carries `phase == "s"` at runtime, but the dead branches must go. Specifically:
  - In any allowlist of the form `t.phase in (None, "s")` (now `t["status"] in (None, "s")` after the dict-access pass above), remove `"s"` so it becomes `t["status"] is None`.
  - In any branch `fast = next((t for t in tasks if t.phase == "s"), None)` (or the dict-access equivalent), delete the lookup AND the surrounding fast-path branch that returns the fast-path task.
  - Update any docstring that mentions `[s]` or `"s"` to no longer reference it.

  After this pass, `grep -n '"s"' plugins/mill/scripts/_spawn_core.py` should return zero matches that refer to the spawn-ready phase (other string literals are fine).

  **`claim_in_wiki` body (lines 654, 656, 658, 659):**

  Replace the entire `with _wiki.wiki_lock(wiki_path, slug):` block at line 654 with a single call:

  ```python
  wiki.set_phase(wiki_path, slug, "active")
  ```

  Delete the surrounding context manager. Delete `_tasks_md.claim(home_text, slug)` (line 656). Delete `_sidebar.regenerate(wiki_path)` (line 658). Delete the `_wiki.write_commit_push(...)` call (line 659+). Update the return type if any (most likely `None` already).

  Drop any `home_text = ...` local that becomes unused after the rewrite.

  **`LockBusy` catches:** if any `except _wiki.LockBusy as e:` (or similar) clauses remain after the above edits, delete them outright. V3 has no equivalent exception; let `WikiPushError` propagate.

  **Final verification (do inside the implementer's edit loop, before committing):**

  Run these greps; each MUST return zero matches:

  ```bash
  grep -nE "^import _(wiki|tasks_md|sidebar)|^from _(wiki|tasks_md|sidebar) " plugins/mill/scripts/_spawn_core.py
  grep -nE "_(wiki|tasks_md|sidebar)\." plugins/mill/scripts/_spawn_core.py
  grep -nE "\.heading_line_no\b" plugins/mill/scripts/_spawn_core.py
  ```

  Then run `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-millpy-color.py` — this test currently fails with `ModuleNotFoundError: No module named '_sidebar'` because `millpy-color.py` imports `_spawn_core` which imports `_sidebar`. After this card, the import chain is clean and the test passes.

- **Commit:** `refactor(_spawn_core): full V2 elimination -- wiki._client API; drop [s] fast-paths; drop _task_to_dict`

## Batch Tests

The batch verify command is `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-millpy-color.py`. This file currently fails with `ModuleNotFoundError: No module named '_sidebar'` because `millpy-color.py` transitively imports `_spawn_core.py`, which still has `import _sidebar` at line 70. After card 4 lands, the import chain is clean and this test passes.

Note: `test-spawn-core.py` itself still has V2 references at lines 25, 88, 190+ — that file is the subject of card 9 in batch 5, NOT this batch. Do not use `test-spawn-core.py` as a verify gate here. Many other tests in the chain-failure cluster (`test-millpy-terminal.py`, `test-millpy-vscode.py`, `test-cleanup.py`, `test-marker.py`, etc.) also go green after this batch as a side effect; verify them as a smoke run after the verify gate passes, but they are not the gate itself.
