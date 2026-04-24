# Batch: callsite-migration

```yaml
task: junction-rule enforcement + _paths.py consolidation
batch: callsite-migration
cards: 3
verify: python plugins/mill/integration_tests/test-spawn.py
depends-on: [foundation]
```

## Batch Scope

Delete the three private `_resolve_wiki_path()` + `_resolve_git_root()` copies in `mill-add.py`, `mill-spawn.py`, `mill-list.py`. Replace with `from _paths import resolve_git_root, resolve_wiki_path`. Update each script's top docstring so the next reader knows the junction is NOT a code contract.

One card per script — each is a local, mechanical edit with a tight diff.

Batch verify runs `test-spawn.py` only (fast, and it exercises both `resolve_git_root` and `resolve_wiki_path` end-to-end). The full `test-merge.py` runs at task-level verify.

## Cards

### Card 3: `mill-add.py` migrates to `_paths`

- **Reads:** `plugins/mill/scripts/mill-add.py`, `plugins/mill/scripts/_paths.py` (post-Card-1).
- **Modifies:** `plugins/mill/scripts/mill-add.py`
- **Creates:** (none)
- **Requirements:**
  - Replace the module docstring's first paragraph ("Resolves the wiki clone via the `.millhouse/wiki` junction in cwd, ...") with a version that says: "Resolves the wiki clone via `_paths.resolve_wiki_path`. Note: `.millhouse/wiki` is a junction for IDE/terminal convenience only — scripts never use it as a code path."
  - Delete the private `_resolve_wiki_path()` function (lines 59-66) and `_resolve_git_root()` if present (check for it in the same pass — it is NOT a verified duplicate in mill-add yet; see if it exists and remove it too if so).
  - Add `from _paths import resolve_git_root, resolve_wiki_path` at the top import block. Follow existing import ordering.
  - Replace the call-site `wiki_path = _resolve_wiki_path()` (line 131) with `git_root = resolve_git_root(); wiki_path = resolve_wiki_path(git_root)`. If `git_root` is only needed for the wiki lookup, inline as `wiki_path = resolve_wiki_path(resolve_git_root())` — prefer explicit variable since the rest of the flow may reuse it.
  - Error-message change: if the wiki-path does not exist on disk (the `_load_config` or equivalent read fails), surface a message that names BOTH the resolved path AND the override key. New text: `"Wiki not found at {wiki_path}. Run /mill-setup to create it, or set paths.wiki: in .millhouse/config.local.yaml."`. Apply at the obvious first consumer of `wiki_path` — typically the `_wiki.sync_pull` / Home.md read. Catch the FileNotFoundError or equivalent, re-raise SystemExit with the new message. If mill-add has no such error path today, skip this sub-step (the error naturally surfaces from `_wiki`).
  - Do NOT touch any other logic in mill-add. This is purely a plumbing swap.
- **Commit:** `refactor(mill-add): use _paths helpers instead of private junction-resolve`

### Card 4: `mill-spawn.py` migrates to `_paths`

- **Reads:** `plugins/mill/scripts/mill-spawn.py`, `plugins/mill/scripts/_paths.py` (post-Card-1), `plugins/mill/scripts/_sibling.py` (confirm no double-import shows up after the migration).
- **Modifies:** `plugins/mill/scripts/mill-spawn.py`
- **Creates:** (none)
- **Requirements:**
  - Mirror Card 3 strictly: docstring update, delete both `_resolve_wiki_path` (lines 178-186) and `_resolve_git_root` (lines 189-196), add `from _paths import resolve_git_root, resolve_wiki_path`.
  - Replace both call-sites: `wiki_path = _resolve_wiki_path()` → `wiki_path = resolve_wiki_path(git_root)` (reorder so `git_root = resolve_git_root()` runs first). Note that `mill-spawn.main` currently does `wiki_path = _resolve_wiki_path(); git_root = _resolve_git_root()` — the order inverts: git-root first, then wiki via git-root. Verify with a read of the function body.
  - **Important:** `mill-spawn._resolve_worktrees_dir` (after spec 00) already imports `_sibling` lazily. That import still points at `_sibling` — no change needed. OR it can switch to `from _paths import resolve_path` for consistency. Prefer the consistency change — smaller surface area mentally. Update the inline `import _sibling` to `from _paths import resolve_path`, and the call `_sibling.resolve_path("worktrees", git_root)` to `resolve_path("worktrees", git_root)`.
  - Error-message parallel to Card 3 — if mill-spawn has an obvious first-consumer-of-wiki-path, apply the new text. Look for FileNotFoundError handling near `home_path.read_text` (line ~283).
- **Commit:** `refactor(mill-spawn): use _paths helpers; drop private junction-resolve`

### Card 5: `mill-list.py` migrates to `_paths`

- **Reads:** `plugins/mill/scripts/mill-list.py`, `plugins/mill/scripts/_paths.py` (post-Card-1).
- **Modifies:** `plugins/mill/scripts/mill-list.py`
- **Creates:** (none)
- **Requirements:**
  - Mirror Card 3 line-for-line: update the docstring's opening paragraph, delete the private `_resolve_wiki_path` (lines 30-38) and `_resolve_git_root` if present, add `from _paths import resolve_git_root, resolve_wiki_path`, swap the call-site at line 46.
  - mill-list is read-only — no config mutation. No error-message path to update.
- **Commit:** `refactor(mill-list): use _paths helpers; drop private junction-resolve`

## Batch Tests

`python plugins/mill/integration_tests/test-spawn.py` — exercises both helpers end-to-end via the real `mill-spawn.py`. A failure here means either the helper is wrong (foundation batch caught the first but not all edge cases) or the call-site swap broke something.

No new integration fixture — the test already runs against a real git repo.
