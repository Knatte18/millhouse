# Batch: Medium skill fixes

```yaml
task: Audit and clean up stale V2 references
batch: Medium skill fixes
number: 2
cards: 4
verify: "PYTHONPATH= bash -c \"! grep -rq '_wiki[.]\\|_tasks_md[.]\\|_sidebar[.]' plugins/mill/skills/mill-finalize/SKILL.md plugins/mill/skills/mill-fold/SKILL.md plugins/mill/skills/mill-merge/SKILL.md plugins/mill/skills/mill-groom/SKILL.md\""
depends-on: []
```

## Batch Scope

Four skills with medium-complexity V2 references: lock + write_commit_push + set_phase replacements, `_tasks_md.parse` replacements, `_tasks_md.LOCKED_FOLD_PHASES` inlining, `_sidebar.regenerate` deletions, and Board-discipline footer rewrites. Each card edits one file independently. The verify grep confirms zero `_wiki.`, `_tasks_md.`, and `_sidebar.` hits across all four files.

## Cards

### Card 6: mill-finalize — delete sync_pull, replace lock/set_phase/write_commit_push block, update Board discipline

- **Context:**
  - `.scratch/v3-wiki-cheatsheet.md`
- **Edits:**
  - `plugins/mill/skills/mill-finalize/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  In Entry (line 15): delete the line `2. \`_wiki.sync_pull(wiki_path, slug="mill-finalize")\`.` and renumber subsequent entry steps.

  Replace the entire code block at lines 78–86 (the `with _wiki.wiki_lock` block and its three signature lines). The current block is:
  ```
  with _wiki.wiki_lock(wiki_path, slug):
      _tasks_md.set_phase_at(wiki_path / "Home.md", slug, "pr-pending")
      _wiki.write_commit_push(wiki_path, ["Home.md"], f"task: pr-pending {slug}", slug=slug)
  ```
  followed by:
  ```
  `signature: _tasks_md.set_phase_at(path: Path, slug: str, phase: str | None) -> None`
  `signature: _wiki.wiki_lock(wiki_path: Path, slug: str) -> ContextManager[None]`
  `signature: _wiki.write_commit_push(wiki_path: Path, paths: list[str], msg: str, *, slug: str) -> None`
  ```
  Replace the whole block (code fences + signature lines) with:
  ```bash
  PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "
  from pathlib import Path; import _paths
  from wiki import _client
  wiki_path = _paths.resolve_wiki_path(_paths.resolve_git_root())
  _client.set_phase(wiki_path, '<slug>', 'pr-pending')
  "
  ```

  In the Board discipline section (line 97), replace the bullet:
  `- Home.md writes go through \`_wiki.write_commit_push\` (acquires the wiki lock internally). For the read-modify-write in Step 6, wrap in \`with _wiki.wiki_lock(wiki_path, slug):\`.`
  with:
  `- Wiki mutations go through \`_client\` calls (\`set_phase\`, \`upsert_task\`, \`merge_tasks\`); the daemon serializes all writes and pushes automatically. For multi-step atomic operations use \`_client.merge_tasks\`.`
- **Commit:** `docs(mill-finalize): replace stale V2 wiki refs`

### Card 7: mill-fold — replace LOCKED_FOLD_PHASES references and write_commit_push mention

- **Context:**
  - `.scratch/v3-wiki-cheatsheet.md`
- **Edits:**
  - `plugins/mill/skills/mill-fold/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  Line 8 (skill description paragraph): replace `` `_tasks_md.LOCKED_FOLD_PHASES` is the single source of truth for the locked-phase set.`` with `The locked phase set is \`{"active", "ready-to-merge", "pr-pending"}\` — inline this set in operator instructions; the locked-phase policy is authoritative.`

  Line 32: replace `After \`_wiki.write_commit_push\` succeeds it calls \`_gh_issues.close_with_comment(N, 'Folded into wiki task: <slug>', git_root=...)\`.` with `After the daemon commit/push succeeds (daemon auto-commits on each \`_client\` mutation) it calls \`_gh_issues.close_with_comment(N, 'Folded into wiki task: <slug>', git_root=...)\`.`

  Line 49: replace `\`_tasks_md.LOCKED_FOLD_PHASES\` is the source of truth — never duplicate the tuple in operator instructions or scripts.` with `The locked phase set \`{"active", "ready-to-merge", "pr-pending"}\` is the source of truth — never duplicate it in operator instructions or scripts.`
- **Commit:** `docs(mill-fold): replace stale _tasks_md.LOCKED_FOLD_PHASES refs`

### Card 8: mill-merge — delete sync_pull, replace two wiki_lock blocks, delete sidebar step, update Board discipline

- **Context:**
  - `.scratch/v3-wiki-cheatsheet.md`
- **Edits:**
  - `plugins/mill/skills/mill-merge/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  Delete line 37: `2. \`_wiki.sync_pull(<WIKI_PATH>, slug=slug)\`.` and renumber subsequent entry steps.

  Replace lines 43 (the long fallback block): the current text reads (paraphrased) "If status.md is absent, call `_wiki.sync_pull(wiki_path, slug=slug)`, read home_text, parse with `_tasks_md.parse(home_text)`, get Task with `.phase` attribute, compare `task.phase == "pr-pending"`". Replace the sync_pull + `_tasks_md.parse` + `.phase` fallback path with: "If `status_path` is absent: call `task = _client.get_task(wiki_path, slug)` (where `from wiki import _client`). Guard: `if task is None: halt(...)`. If `task["status"] == "pr-pending"` → treat as pr-pending. Otherwise → halt with error message."

  Replace the first `with _wiki.wiki_lock` block (lines 162–168) — which reads Home.md, calls `_tasks_md.set_phase`, writes Home.md, then `_wiki.write_commit_push` for "pr-pending" — with a single `_client.set_phase(wiki_path, slug, "pr-pending")` call.

  Replace the second `with _wiki.wiki_lock` block (lines 193–199) — which reads Home.md, calls `_tasks_md.set_phase` for "done", writes Home.md, then `_wiki.write_commit_push` — with a single `_client.set_phase(wiki_path, slug, "done")` call.

  Delete the sidebar regeneration in "### 8. Regenerate sidebar + release merge lock" (line 203–205): remove the `_sidebar.regenerate(<WIKI_PATH>)` instruction and its prose. Rename the section heading to `### 8. Release merge lock`. Keep only the "Delete `<parent-path>/.scratch/merge.lock`" instruction.

  In the Board discipline section (line 254), replace:
  `- Home.md writes go through \`_wiki.write_commit_push\` (which acquires the wiki lock internally). For multi-operation windows use \`with _wiki.wiki_lock(wiki_path, slug):\`.`
  with:
  `- Wiki mutations go through \`_client\` calls (\`set_phase\`, \`upsert_task\`, \`merge_tasks\`); the daemon serializes all writes and pushes automatically. For multi-step atomic operations use \`_client.merge_tasks\`.`
- **Commit:** `docs(mill-merge): replace stale V2 wiki refs`

### Card 9: mill-groom — delete sync_pull, replace parse step, replace write_commit_push step, delete sidebar step, update Board discipline

- **Context:**
  - `.scratch/v3-wiki-cheatsheet.md`
- **Edits:**
  - `plugins/mill/skills/mill-groom/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  Delete Entry step 3 (lines 26–32): the `_wiki.sync_pull(<WIKI_PATH>)` call and its bash code block.

  Replace "Step 2 — Parse Home.md" (lines 44–53): rename the section to "Step 2 — Read task list". Replace the Home.md read + `_tasks_md.parse(text)` pattern with `_client.list_tasks_brief(wiki)`. The bash snippet becomes:
  ```bash
  PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "
  import json, _paths
  from wiki import _client
  wiki = _paths.resolve_wiki_path(_paths.resolve_git_root())
  tasks = _client.list_tasks_brief(wiki)
  print(json.dumps(tasks, indent=2))
  "
  ```
  Note: V3 task dicts have `"status"` (not `"phase"`), `"slug"`, `"title"`, `"brief"`, `"body"`, `"group"`, `"has_proposal"`.

  In Step 3's scope rules table: update the column header from `` `task.phase` `` to `` `task["status"]` `` so the table matches the dict shape returned by `_client.list_tasks_brief`.

  Replace step 4 "Write all changed files and push via `_wiki.write_commit_push`" (lines 192–199): since mutations go through `_client.upsert_task` (which the daemon auto-commits and pushes), the explicit write_commit_push call is gone. Replace with: "For each task whose fields changed, call `_client.upsert_task(wiki, slug, brief=..., body=...)`. The daemon commits and pushes to the wiki remote automatically on each mutation."

  Delete the `_sidebar.regenerate` step (lines 204–209): the entire code block calling `_sidebar.regenerate(wiki)`. In V3 the daemon auto-renders `_Sidebar.md`.

  Replace line 231 Board discipline:
  `**One commit per session** — all changes land in a single \`_wiki.write_commit_push\` call.`
  with:
  `**Daemon auto-commits per mutation** — each \`_client.upsert_task\` call triggers a daemon commit + push; no explicit write_commit_push step is needed.`
- **Commit:** `docs(mill-groom): replace stale V2 wiki refs`

## Batch Tests

All four files are pure documentation (SKILL.md). The verify command runs `grep -rq` for `_wiki[.]`, `_tasks_md[.]`, and `_sidebar[.]` across all four files and asserts zero matches. No unit test suite covers SKILL.md content.
