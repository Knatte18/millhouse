# Batch: small-clis-and-surface-fixes

```yaml
task: "Finish V3 wiki adoption — complete batch 3 port and test sweep"
batch: small-clis-and-surface-fixes
number: 4
cards: 2
verify: "PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-millpy-terminal.py && PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-millpy-vscode.py"
depends-on: [1]
```

## Batch Scope

Port the five small shipping CLIs to V3 (`millpy-inspect.py`, `millpy-status.py`, `millpy-terminal.py`, `millpy-vscode.py`, `millpy-wikipush.py`) and clean up V2 references in surface-only text (error messages and docstrings) in `_paths.py`, `_junction.py`, `_worktree.py`. No code behaviour changes in the surface-text card; only the small-CLI card has real wiring changes.

Independent of batches 2 and 3 — these files import only `_paths`, `_config`, `wiki`, and standard helpers; they do not import `_spawn_core` or `millpy-spawn`. Depends only on batch 1 because the small-CLI ports call `wiki.list_tasks_brief(wiki_path)` which exercises the daemon — the daemon must be reliable.

Two cards because the small-CLI port is structurally mechanical across five files but exceeds the S budget alone, and surface fixes are an unrelated cleanup that should land as its own commit for diff hygiene.

Batch-local decisions (differ from `## Shared Decisions` in `00-overview.md`):

- **`wiki_path` is resolved at the same point in each CLI as the existing `wiki = _paths.resolve_wiki_path(git_root)` (or similar) local.** Reuse the existing local; do not re-resolve.
- **`millpy-wikipush.py` keeps its direct-push semantics.** Only the `_wiki.wiki_lock` context manager and `_wiki.LockBusy` exception clause are removed; the `subprocess` + `git -C <wiki_path>` push logic is unchanged. The daemon does NOT mediate `wikipush`'s push — it is a manual-edit push tool, deliberately outside the daemon's transaction model.

## Cards

### Card 6: Port the five small CLIs to V3 wiki API

- **Effort:** M
- **Context:**
  - `plugins/mill/scripts/wiki/__init__.py`
  - `plugins/mill/scripts/wiki/_client.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-inspect.py`
  - `plugins/mill/scripts/millpy-status.py`
  - `plugins/mill/scripts/millpy-terminal.py`
  - `plugins/mill/scripts/millpy-vscode.py`
  - `plugins/mill/scripts/millpy-wikipush.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** For each of the four reader CLIs (`inspect`, `status`, `terminal`, `vscode`), make the same mechanical V2 → V3 swap:

  - Delete the `import _tasks_md` line near the top of the file.
  - Add `import wiki` in the absolute-imports block.
  - Replace the `_tasks_md.parse(home_md.read_text(encoding="utf-8"))` (or equivalent) call with `wiki.list_tasks_brief(wiki_path)`. The `wiki_path` local is already in scope at each call site as the wiki path used for the V2 parse — see Context. Delete the `home_md = ...` / `home_md.read_text(...)` lines that fed `_tasks_md.parse`; they become unused.
  - Update any downstream code in the file that accessed `Task` attributes (`.slug`, `.title`, `.phase`, `.has_proposal`, `.group`, `.brief`, `.status`) to dict-key access (`t["slug"]`, etc.). Field-rename note: `.phase` → `["status"]`.

  Per-file specifics:

  - `millpy-inspect.py:20` (`import _tasks_md`), `:45` (the `wiki = _paths.resolve_wiki_path(...)` local is `wiki`; the existing call site uses that name — keep), `:54` (`_tasks_md.parse(home_md.read_text(...))`). Replace `:54` with `home_tasks_list = wiki.list_tasks_brief(wiki)` (note `wiki` here is the local Path; do NOT alias the V3 module to a clashing name — rename the local to `wiki_path` if the new `import wiki` causes a NameError or shadowing warning; otherwise the imported module and the local can coexist in Python because `wiki.list_tasks_brief(wiki)` resolves `wiki` from local first, but THIS IS A FOOTGUN — rename the local to `wiki_path` for clarity).
  - `millpy-status.py:20` (`import _tasks_md`), `:24` (local `wiki = _paths.resolve_wiki_path(...)` — apply the same `wiki` → `wiki_path` rename as inspect), `:32` (`_tasks_md.parse(home_md.read_text(...))` → `wiki.list_tasks_brief(wiki_path)`).
  - `millpy-terminal.py:23` (`import _tasks_md`), `:55` (local — apply rename), `:59` (`_tasks_md.parse(...)` → `wiki.list_tasks_brief(wiki_path)`).
  - `millpy-vscode.py:31` (`import _tasks_md`), `:176` (local — apply rename), `:180` (`_tasks_md.parse(...)` → `wiki.list_tasks_brief(wiki_path)`).

  The local `wiki = ...` → `wiki_path = ...` rename in each file MUST be done end-to-end (rename every reference to that local) to avoid a name collision with the new `import wiki` statement. Use the editor's rename-symbol feature or a targeted grep-and-replace within each file's scope.

  For `millpy-wikipush.py` (sliver):

  - Line 32: delete `import _wiki`.
  - Line 102: the comment `# Capture changed files BEFORE acquiring the lock — _wiki.wiki_lock` is now misleading; either delete the entire comment line or rewrite as `# Capture changed files BEFORE pushing` (one-line, no reference to the deleted helper).
  - Line 111: delete the `with _wiki.wiki_lock(wiki, "wikipush"):` context manager. The body of the `with` block becomes a flat sequence of statements at the previous outer indentation.
  - Line 113: delete the `except _wiki.LockBusy as e:` clause and its body. There is no V3 equivalent — the daemon serialises writes for daemon-mediated ops, and `wikipush` is deliberately NOT daemon-mediated. Any `git push` failure manifests as the existing subprocess error path; no special LockBusy handling needed.
  - Local-variable name: `wiki` is used as the wiki path local; rename to `wiki_path` to avoid the same import-collision footgun as the reader CLIs, OR confirm that no `import wiki` is added to this file (since this file does not call any `wiki.<fn>`, an `import wiki` is unnecessary and should NOT be added).

  Confirm at the end:

  - `millpy-wikipush.py` does NOT have `import wiki` (no need; never calls `wiki.<fn>`).
  - The four reader CLIs each have `import wiki` and use `wiki.list_tasks_brief(wiki_path)`.

  **Final verification (do inside the implementer's edit loop, before committing):**

  ```bash
  grep -nE "^import _(wiki|tasks_md|sidebar)|^from _(wiki|tasks_md|sidebar) " plugins/mill/scripts/millpy-inspect.py plugins/mill/scripts/millpy-status.py plugins/mill/scripts/millpy-terminal.py plugins/mill/scripts/millpy-vscode.py plugins/mill/scripts/millpy-wikipush.py
  grep -nE "_(wiki|tasks_md|sidebar)\." plugins/mill/scripts/millpy-inspect.py plugins/mill/scripts/millpy-status.py plugins/mill/scripts/millpy-terminal.py plugins/mill/scripts/millpy-vscode.py plugins/mill/scripts/millpy-wikipush.py
  ```

  Both must return zero matches. Then run the verify gate (`test-millpy-terminal.py && test-millpy-vscode.py`). Both must pass.
- **Commit:** `refactor(millpy-*): port small CLIs to wiki.list_tasks_brief; drop _wiki from wikipush`

### Card 7: Update surface-only V2 text references in `_paths.py`, `_junction.py`, `_worktree.py`

- **Effort:** S
- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/scripts/_junction.py`
  - `plugins/mill/scripts/_worktree.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Update text references only — no signature changes, no behaviour changes. Each edit is a literal string replacement.

  `plugins/mill/scripts/_paths.py`:
  - Lines 125, 140, 407: each contains the sub-string ` or _wiki.write_commit_push.` at the end of an error message. Replace each with `.` (drop the entire ` or _wiki.write_commit_push` clause, keeping the preceding `git -C <wiki_path>` reference). The post-edit message reads: `... Wiki mutations go through git -C <wiki_path>.`
  - Lines 318-319: rename the local variable `_wiki` (currently `_wiki = resolve_wiki_path(git_root)`) to `wiki_path` to avoid the implication of a V2 module. Update the single reference on line 319 (`_marker.slug_from_branch(git_root, _wiki, cfg)`) to `_marker.slug_from_branch(git_root, wiki_path, cfg)`. The local is function-scoped; no other references exist.

  `plugins/mill/scripts/_junction.py`:
  - Line 301: the docstring text `Caller passes this\n            in to avoid a circular import on ``_wiki``.` references the deleted `_wiki` module. Replace with: `Caller passes this\n            in for separation of concerns; ``_junction`` does not depend on the wiki subpackage.`

  `plugins/mill/scripts/_worktree.py`:
  - Line 207: the docstring text `as returned by ``_wiki.read_junctions``.` references the deleted `_wiki` module. Replace with: `as returned by ``_junction.read_junctions``.` (the helper moved to `_junction.py` in card 15 of the parent plan).

  After both files are edited, run:

  ```bash
  grep -nE "_wiki\.(read_junctions|write_commit_push|sync_pull|wiki_lock|LockBusy)" plugins/mill/scripts/_paths.py plugins/mill/scripts/_junction.py plugins/mill/scripts/_worktree.py
  ```

  Zero matches required.

  No behavioural test gate; the verify is the grep above + the batch verify in `00-overview.md` (terminal+vscode tests still pass, proving no incidental regression from the rename).
- **Commit:** `docs(scripts): drop V2 _wiki references from error and docstring text`

## Batch Tests

The batch verify command is `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-millpy-terminal.py && PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-millpy-vscode.py`. Both files currently fail with `ModuleNotFoundError: No module named '_sidebar'` (chain-failure through `_spawn_core`'s old `import _sidebar`). Batch 2 unblocks the chain failure; THIS batch's card 6 finishes the job by porting the CLIs themselves so the tests pass end-to-end (the tests exercise the CLI's main path including the `wiki.list_tasks_brief` call).

`millpy-wikipush.py` has no dedicated unit test; its sliver port is verified indirectly by the `grep` checks in card 6's verification block. The surface-fix card 7 has no behavioural verify; the grep checks in its Requirements are the verify.
