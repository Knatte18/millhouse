# Batch: rewrite-skill

```yaml
task: "Revise mill-ghissues-to-tasks to present all at once"
batch: rewrite-skill
number: 1
cards: 2
verify: PYTHONPATH= bash -c 'grep -Fq "groups all open issues" plugins/mill/skills/mill-ghissues-to-tasks/SKILL.md && grep -Fq "groups all open issues" SKILLS.md && ! grep -Fq "Process issues one at a time" plugins/mill/skills/mill-ghissues-to-tasks/SKILL.md'
depends-on: []
```

## Batch Scope

This batch rewrites the single hand-written skill `mill-ghissues-to-tasks` from
the per-issue interactive model to the all-at-once batch model, and re-syncs its
row in the root `SKILLS.md` index. It is one batch because the two edits are one
logical change: the `SKILLS.md` row must reproduce the new SKILL.md frontmatter
`description:` verbatim. No Python is touched — the existing `_gh_issues` and
`wiki/_client` APIs already cover every operation (see `## Shared Decisions ->
docs-only-no-code`). Card 1 authors the canonical description; Card 2 copies it
into the index. The batch `verify:` greps both files for the shared substring
`groups all open issues` and asserts the stale per-issue line is gone.

Batch-local decisions: none beyond `## Shared Decisions`.

## Cards

### Card 1: Rewrite the mill-ghissues-to-tasks SKILL.md to the all-at-once model

- **Context:**
  - `_mill/discussion.md`
  - `plugins/mill/skills/mill-fold/SKILL.md`
  - `plugins/mill/scripts/_gh_issues.py`
  - `plugins/mill/scripts/wiki/_client.py`
  - `plugins/mill/scripts/wiki/_render.py`
- **Edits:**
  - `plugins/mill/skills/mill-ghissues-to-tasks/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - Replace the frontmatter `description:` value with the exact canonical string in `## Shared Decisions -> canonical-description-string` (byte-for-byte, single line).
  - Keep the `---` frontmatter `name: mill-ghissues-to-tasks` line unchanged.
  - Rewrite the intro paragraph(s) under `# mill-ghissues-to-tasks` to state the all-at-once model: fetch all open issues, the assistant proposes a grouping into a small number of tasks plus fold-ins and skips, the operator gives one combined approval, then consumed issues are closed with a pointer comment and skipped issues are left untouched. Keep the existing "Leaving claimed-but-open issues on GitHub is a forgetting hazard" rationale sentence.
  - Keep the `## Entry checks` section unchanged in substance: (1) `gh auth status` must succeed (same stop message); (2) `.millhouse/wiki/` junction must exist (same stop message).
  - Keep `## Step 1 -- Fetch all open issues`: still call `_gh_issues.fetch(limit=100, git_root=_paths.resolve_git_root())` into `.scratch/issues.json` and record the repo name via `_gh_issues.detect_repo(git_root=_paths.resolve_git_root())`. Use the `${CLAUDE_PLUGIN_ROOT}` invocation form already present.
  - Keep `## Step 2 -- Read the current task list`: still call `_client.list_tasks_brief(wiki_path)` into `.scratch/wiki-tasks.json`; each task dict has keys `{id, slug, title, layer, brief, status, has_proposal}`. Store `wiki_path` for later `_client` calls.
  - Replace `## Step 3 -- Interactive decisions (per issue)` with a new `## Step 3 -- Analyse and group`. It must: instruct the assistant to read all fetched issues plus the current task list and propose, using judgment, (a) a grouping of related issues into a small number of NEW tasks (soft target 2-3, natural grouping by theme, no hard cap, do not force unrelated issues together or over-split tightly-related ones), (b) fold-ins where an issue clearly overlaps an existing UNLOCKED backlog task, and (c) skips for non-actionable issues. The assistant drafts each new task's slug (validate `[a-z][a-z0-9-]*`, must not collide with an existing slug from Step 2), title, and a 1-2 sentence brief. Explicitly state there is NO per-issue menu and NO per-issue prompting, and DELETE the current sentence `Process issues one at a time. Do NOT auto-decide; the user chooses for every issue.` For fold candidates, state the locked-phase guard: refuse fold targets whose `status` is in the locked set `{"active", "ready-to-merge", "pr-pending"}` (inline the set; route such issues to a new task or skip instead).
  - Rewrite `## Step 4 -- Propose` so it produces ONE consolidated proposal at `.scratch/ghissues-to-tasks-proposal.md` covering all decisions at once: a decisions table, a "New tasks (grouped)" section listing each drafted slug/title/brief and its source issues, a "Fold-ins" section listing target slug + source issues, and a "Skipped" section with reasons. The proposal MUST list, per consumed issue, the EXACT close-comment string that will be posted on approval -- `Consolidated into wiki task: <slug>` for new/grouped-task issues and `Folded into wiki task: <slug>` for fold-ins -- and state that skipped issues get no comment. Print a one-line summary + the path; the operator replies `approve` or gives feedback. State that "one-shot" means no per-issue prompting, NOT no iteration: on feedback the assistant revises the grouping and re-presents the full proposal, looping until `approve` or an explicit abort, and NOTHING is written to the wiki or closed on GitHub until `approve`.
  - Rewrite `## Step 5 -- Apply (on approve)`:
    - For each grouped NEW task, call `_client.upsert_task(wiki_path, slug, title=<title>, brief=<theme>, body=<manifest>)` where `<manifest>` is one `- Sources: #N - <issue title>` bullet per source issue followed by a line such as `Run \`gh issue view #N\` for full detail.` State that per `wiki/_render.py` a non-empty `body` renders `proposal-<slug>.md` and the Home.md slug line links to it -- this minimal manifest is intended, not a long-form proposal. The daemon commits+pushes on each `_client` mutation. Mention `_client.upsert_tasks_batch(wiki_path, tasks, message=...)` as an optional one-commit alternative for the new tasks.
    - For each FOLD-IN, call `task = _client.get_task(wiki_path, target_slug)`; if `task is None` (stale/typo'd target) report an error for that fold-in and continue the run rather than dereferencing `None`; otherwise re-check `task["status"]` against the locked set, then set `new_body = (task["body"] or "") + "\n- Sources: #N - <issue title>"` and call `_client.upsert_task(wiki_path, target_slug, body=new_body)`. The `- Sources: #N - <title>` bullet format matches `/mill-fold`.
    - For each consumed issue, close it after the wiki write succeeds: new/grouped-task issues via `_gh_issues.close_with_comment(N, 'Consolidated into wiki task: <slug>', git_root=_paths.resolve_git_root())`; fold-in issues via `_gh_issues.close_with_comment(N, 'Folded into wiki task: <slug>', git_root=_paths.resolve_git_root())`. The fold-in string MUST match `/mill-fold` verbatim. On any close failure, log the issue number + error and continue; report at the end. Skipped issues are untouched.
  - Rewrite `## Step 6 -- Report` to summarise: number of new grouped tasks, number of fold-ins, issues closed on GitHub, skipped (untouched), and failed-to-close counts.
  - Update the `## Rules` section for the batch model: keep one-shot (no resumable state; `.scratch/ghissues-to-tasks-proposal.md` is the only artefact); keep "skipped issues are untouched"; keep "close only on approval + actual write"; keep the pointer-comment invariant; keep the locked-set-is-source-of-truth rule; keep the two close-comment strings (New/grouped -> `Consolidated into wiki task: <slug>`, Fold-in -> `Folded into wiki task: <slug>` matching `/mill-fold`). Remove any rule language implying per-issue iteration.
  - All script-invocation examples must keep the `${CLAUDE_PLUGIN_ROOT}` cache form (never literal `plugins/mill/...` runtime paths).
- **Commit:** `docs(skills): rewrite mill-ghissues-to-tasks for all-at-once grouping`

### Card 2: Sync the SKILLS.md index row

- **Context:**
  - `plugins/mill/skills/mill-ghissues-to-tasks/SKILL.md`
- **Edits:**
  - `SKILLS.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - In `SKILLS.md`, find the table row whose link target is `plugins/mill/skills/mill-ghissues-to-tasks/SKILL.md` and replace its description cell so it is byte-identical to the new SKILL.md frontmatter `description:` value (the canonical string in `## Shared Decisions -> canonical-description-string`). Do not change the row's link text or target, the table structure, or any other row. This mirrors what `/mill-skills-index` would regenerate from frontmatter.
- **Commit:** `docs(skills): sync SKILLS.md row for mill-ghissues-to-tasks`

## Batch Tests

`verify:` is a grep-based consistency check, not a test run -- this is a
pure-docs batch with no runnable code surface (see `## Shared Decisions ->
docs-only-no-code`). The command asserts three invariants after implementation:
(1) the canonical substring `groups all open issues` is present in the rewritten
`plugins/mill/skills/mill-ghissues-to-tasks/SKILL.md` (frontmatter description),
(2) the same substring is present in `SKILLS.md` (the synced row -- proving
frontmatter/index parity), and (3) the stale per-issue line
`Process issues one at a time` is absent from the SKILL.md (proving the
per-issue loop was removed). No unit/integration test is added because no Python
behaviour changes; the underlying `_gh_issues` and `wiki/_client` modules are
untouched and already covered.
