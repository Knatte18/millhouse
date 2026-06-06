# Plan: Revise mill-ghissues-to-tasks to present all at once

```yaml
task: "Revise mill-ghissues-to-tasks to present all at once"
slug: revise-ghissues-to-tasks
approved: true
started: "20260606-190057"
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: rewrite-skill
    file: 01-rewrite-skill.md
    depends-on: []
    verify: PYTHONPATH= bash -c 'grep -Fq "groups all open issues" plugins/mill/skills/mill-ghissues-to-tasks/SKILL.md && grep -Fq "groups all open issues" SKILLS.md && ! grep -Fq "Process issues one at a time" plugins/mill/skills/mill-ghissues-to-tasks/SKILL.md'
```

## Shared Decisions

### Decision: canonical-description-string

- **Decision:** The new skill frontmatter `description:` and the matching `SKILLS.md` row both use this exact string, byte-for-byte:
  `Drain the GitHub issue queue into Home.md. One-shot: the assistant groups all open issues into a few tasks (new or folded-in) and asks for one combined approval, then closes consumed issues with a pointer comment. Skipped issues are left alone.`
- **Rationale:** `SKILLS.md` is generated from frontmatter by `/mill-skills-index`; the two must stay identical or the index is stale. Pinning one canonical string lets the batch `verify:` grep both files for the substring `groups all open issues`.
- **Applies to:** all batches

### Decision: all-at-once-flow

- **Decision:** The skill fetches every open issue once, the assistant proposes a grouping of related issues into a small number of tasks (soft target 2-3, natural grouping, no hard cap) plus fold-ins and skips, writes one consolidated proposal to `.scratch/ghissues-to-tasks-proposal.md`, and applies it on a single `approve`. There is NO per-issue decision menu and NO per-issue prompting.
- **Rationale:** This is the task's core requirement (discussion `## Decisions -> all-at-once grouping`).
- **Applies to:** all batches

### Decision: issue-references-in-body

- **Decision:** Each grouped new task is created via `_client.upsert_task(wiki_path, slug, title=..., brief=..., body=...)` where `brief` is a synthesised 1-2 sentence theme and `body` holds one `- Sources: #N - <issue title>` bullet per source issue plus a line instructing the implementer to run `gh issue view #N` for full detail. Per `wiki/_render.py`, a non-empty `body` renders to `proposal-<slug>.md`; that minimal manifest IS the intended artefact (same mechanism as `/mill-fold`). No long-form proposal narrative by default.
- **Rationale:** Downstream implementer pulls live issue content via `gh issue view` rather than reading a stale copy (discussion `## Decisions -> body format` and `body -> proposal-<slug>.md`).
- **Applies to:** all batches

### Decision: preserved-invariants

- **Decision:** Carry over unchanged from the current skill: new/grouped-task issues close with `Consolidated into wiki task: <slug>`; fold-in issues close with `Folded into wiki task: <slug>` (byte-identical to `/mill-fold`); skipped issues are untouched (no comment/label/close); fold targets in the locked set `{"active", "ready-to-merge", "pr-pending"}` are refused; close only after the wiki write succeeds; the locked set is inlined, never redefined.
- **Rationale:** Other skills and historical closed-issue comments depend on the exact strings (discussion `## Decisions -> preserved invariants`).
- **Applies to:** all batches

### Decision: docs-only-no-code

- **Decision:** No Python is modified. `_gh_issues.fetch/close_with_comment/detect_repo` and `wiki/_client.upsert_task/get_task/list_tasks_brief` already provide every capability; the change is SKILL.md prose + frontmatter + the `SKILLS.md` row. `verify:` is therefore a grep-based consistency check, not a test run.
- **Rationale:** Discussion `## Scope -> Out` and `## Testing`.
- **Applies to:** all batches

## All Files Touched

- `SKILLS.md`
- `plugins/mill/skills/mill-ghissues-to-tasks/SKILL.md`
