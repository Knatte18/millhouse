# Batch: Simple skill fixes

```yaml
task: Audit and clean up stale V2 references
batch: Simple skill fixes
number: 1
cards: 5
verify: "PYTHONPATH= bash -c \"! grep -lrq '_wiki[.]' plugins/mill/skills/mill-plan/SKILL.md plugins/mill/skills/mill-start/SKILL.md plugins/mill/skills/mill-merge-in/SKILL.md plugins/mill/skills/mill-resume/SKILL.md plugins/mill/skills/workflow/SKILL.md\""
depends-on: []
```

## Batch Scope

Five skills whose only stale V2 references are `_wiki.sync_pull` deletions, `_sidebar.regenerate` deletions, and Board-discipline footer rewrites. Each card edits one file independently. The verify grep confirms zero `_wiki.` hits across all five files after the batch completes.

## Cards

### Card 1: mill-plan — delete sync_pull

- **Context:**
  - `.scratch/v3-wiki-cheatsheet.md`
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  In Entry step 1 (line 14): remove the phrase ` and call \`_wiki.sync_pull(wiki_path, slug="mill-plan")\`.` from the end of the sentence. The step should end at `...and call \`_wiki.sync_pull(wiki_path, slug="mill-plan")\`.` being removed; the remaining sentence reads `1. Resolve the wiki path via \`_paths.resolve_wiki_path(_paths.resolve_git_root())\`.`

  Delete line 15 in its entirety: `` `signature: _wiki.sync_pull(wiki_path: Path, *, slug: str) -> None` ``
- **Commit:** `docs(mill-plan): remove stale _wiki.sync_pull from Entry`

### Card 2: mill-start — delete sync_pull and update Board discipline

- **Context:**
  - `.scratch/v3-wiki-cheatsheet.md`
- **Edits:**
  - `plugins/mill/skills/mill-start/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  In Entry step 1 (line 44): remove the phrase ` and call \`_wiki.sync_pull(wiki_path, slug="mill-start")\`.` The remaining step reads `1. Resolve the wiki path via \`_paths.resolve_wiki_path(_paths.resolve_git_root())\`.`

  Delete line 45 in its entirety: `` `signature: _wiki.sync_pull(wiki_path: Path, *, slug: str) -> None` ``

  In the Board discipline section (line 167), replace the bullet:
  `- Home.md writes go through \`_wiki.write_commit_push\` (which acquires the wiki lock internally). For multi-operation windows, use \`with _wiki.wiki_lock(wiki_path, slug):\`.`
  with:
  `- Wiki mutations go through \`_client\` calls (\`set_phase\`, \`upsert_task\`, \`merge_tasks\`); the daemon serializes all writes and pushes automatically. For multi-step atomic operations use \`_client.merge_tasks\`.`
- **Commit:** `docs(mill-start): replace stale V2 wiki refs`

### Card 3: mill-merge-in — delete sync_pull

- **Context:**
  - `.scratch/v3-wiki-cheatsheet.md`
- **Edits:**
  - `plugins/mill/skills/mill-merge-in/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  Delete Entry step 1 (line 12) in its entirety: `1. \`_wiki.sync_pull(<WIKI_PATH>, slug="mill-merge-in")\` — refresh the wiki clone before reading any task state.`

  Renumber the remaining steps: old step 2 becomes step 1, old step 3 becomes step 2, etc.
- **Commit:** `docs(mill-merge-in): remove stale _wiki.sync_pull from Entry`

### Card 4: mill-resume — delete sync_pull, sidebar phase, and update error table

- **Context:**
  - `.scratch/v3-wiki-cheatsheet.md`
- **Edits:**
  - `plugins/mill/skills/mill-resume/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  Delete the "Sync invariant" note (lines 14–15): the two-line block starting `**Sync invariant:** mill-resume MUST call \`_wiki.sync_pull(wiki_path, slug="mill-resume")\`` and its signature line `` `signature: _wiki.sync_pull(wiki_path: Path, *, slug: str) -> None` ``.

  Delete the entire "Phase 2: Sync wiki" section (lines 38–40): heading `### Phase 2: Sync wiki` plus the text and bash block that calls `_wiki.sync_pull(wiki_path, slug="mill-resume")`.

  Delete Phase 10 "Regenerate sidebar" entirely (lines 143–151): heading `### Phase 10: Regenerate sidebar`, the prose, and the bash block calling `_sidebar.regenerate(...)`. In V3 the daemon auto-renders `_Sidebar.md` after every mutation; an explicit regeneration step is obsolete.

  In the error table (line 177), replace the row:
  `| \`_wiki.sync_pull\` raises \`WikiPushError\` | Report error; do not proceed (stale state risk) |`
  with:
  `| \`_client\` mutation raises \`WikiPushError\` | Report error; daemon failed to push to wiki remote — do not proceed (stale state risk) |`
- **Commit:** `docs(mill-resume): remove stale V2 wiki sync refs`

### Card 5: workflow — update Board discipline

- **Context:**
  - `.scratch/v3-wiki-cheatsheet.md`
- **Edits:**
  - `plugins/mill/skills/workflow/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  In the "## Wiki mutations" section (line 32), replace the entire paragraph:
  `Wiki edits go through \`_wiki.write_commit_push(wiki_path, paths, msg, slug=...)\` (which acquires the wiki lock internally). For multi-operation read-modify-write windows (e.g. read Home.md → flip a phase → write back), wrap the whole sequence in \`with _wiki.wiki_lock(wiki_path, slug):\` — the inner \`write_commit_push\`'s lock acquire becomes a no-op via the held-lock counter. Never edit wiki files via raw \`Edit\` / \`Write\` — that bypasses the commit + push and the lock, leaving the wiki out of sync across machines. Per-task working state (\`status.md\`, \`discussion.md\`, \`plan/\`, \`reviews/\`) is NOT in the wiki — it lives at the worktree root on the task branch. Only \`Home.md\` and \`_Sidebar.md\` belong in the wiki.`
  with:
  `Wiki mutations go through \`_client\` calls (\`set_phase\`, \`upsert_task\`, \`merge_tasks\`); the daemon serializes all writes and pushes automatically. For multi-step atomic operations (e.g. remove + upsert + set phase together), use \`_client.merge_tasks\`. Never write wiki files via raw \`Edit\` / \`Write\` — the daemon owns the wiki repo. Per-task working state (\`status.md\`, \`discussion.md\`, \`plan/\`, \`reviews/\`) is NOT in the wiki — it lives on the task branch. \`Home.md\`, \`_Sidebar.md\`, and \`proposal-*.md\` are daemon-rendered derived files.`
- **Commit:** `docs(workflow): replace stale V2 wiki mutation docs`

## Batch Tests

All five files are pure documentation (SKILL.md). The verify command runs `grep -lrq '_wiki[.]'` across all five files and asserts zero matches. No unit test suite exists for SKILL.md content; correctness is validated by the grep check and the acceptance criteria in the overview.
