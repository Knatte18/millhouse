# mill-start (skill)

```yaml
type: skill
layer: 03
v1_ref: plugins/mill/skills/mill-start/ + doc/prompts/discussion-review.md
status: done — merged to main 2026-04-22 (branch impl/03-mill-start)
note: "Interactive. Runs in a task-worktree (spawned by mill-spawn) and produces the discussion.md that mill-plan consumes."
```

**Implementation notes:** `plugins/mill/skills/mill-start/SKILL.md` written v2-style (~95 lines vs v1's 267) with most body content delegated to referenced templates and helper modules. New helpers: `_constraints.py` (`read_if_exists` resolves hub root via `git rev-parse` — works from any subfolder), `_active.py` (`read_slug` / `read_all` / `write` for `.millhouse/active.slug.md`). Extended helper: `_status.py` grows `update_field` + `append_phase` so the skill's phase-transition/handoff writes go through the module, not free-form edits. New template: `plugins/mill/templates/discussion.md` (self-contained skeleton consumed by mill-plan). **Retrofit of mill-spawn** (`61a3f01`): now writes `.millhouse/active.slug.md` at spawn time and records `parent:` branch in `status.md`. Discussion-review loop uses `mill-review-discussion.py` CLI (not `spawn_reviewer`); `-dr N` flag dropped — rounds come from `review.discussion.rounds` only. Handoff remains explicit (user runs `/mill-plan`, mill-start does not chain). Skill content is prose-driven; validated end-to-end via the helper smoke tests + the mill-spawn integration test (which exercises the retrofitted spawn path).

## Purpose

In a freshly spawned worktree, help the user design the solution through interactive discussion and produce a self-contained `discussion.md` that mill-plan can consume without conversation history.

## Decisions

- **Slug lookup**: Read `.millhouse/active.slug.md` (per-worktree, gitignored; written by `mill-spawn`, replaces v1's `handoff.md`). Parse the fenced yaml block for `slug:`. Never use `.active/` or the wiki junction path as an authoritative path — always `<WIKI_PATH>/active/<slug>/` via resolved wiki path.
- **Phases carried over from v1 nearly verbatim**: Color, Select, Active, Explore, Discuss, Discussion File, Discussion Review, Handoff. See v1 `skills/mill-start/SKILL.md` for prose — the discussion approach (batched questions, A/B/C with recommended answers, YAGNI, explore-before-ask) is the proven thing and must be preserved.
- **Discussion Review integration — v2 simplification**: Instead of spawning a reviewer via `spawn_reviewer` entrypoint, invoke the CLI `plugins/mill/scripts/mill-review-discussion.py` as a subprocess. Parse verdict via the same logic already in `_review_common.parse_verdict`. After each review call, **MUST** load the `mill-receiving-review` skill before reading the review output file.
- **Gap handling — keep v1**: On `GAPS_FOUND`, present each gap to the user and wait for their response. Do NOT auto-fix. Only after user has answered do we update `discussion.md` and re-invoke the reviewer.
- **`-dr N` removed**: Discussion-review round count comes from config only (`review.discussion.rounds`). Override during a session happens via conversation, not a flag. (Henrik has never used the flag.)
- **CONSTRAINTS.md**: Still supported — read from hub repo root if present. Added helper `_constraints.read_if_exists(repo_root)` for a consistent one-liner used by mill-start and by the review scripts.
- **Handoff**: Update status.md to `phase: discussed`. Do NOT invoke `mill-plan` — handoff is always explicit user decision (carried over from v1).

## Flow

1. `wiki.sync_pull(cfg)`.
2. Read slug from `.millhouse/active.slug.md`.
3. Phase: Color — read `.vscode/settings.json`, suggest `/color <name>` if hub-green mismatch.
4. Phase: Select — read `<WIKI_PATH>/Home.md`, find entry matching slug, verify `[active]` marker.
5. Phase: Active — initialise/update `<WIKI_PATH>/active/<slug>/status.md` (task, parent). Append-phase `discussing`.
6. Phase: Explore — codeguide first (if `_codeguide/Overview.md` exists), else git log + grep.
7. Phase: Discuss — structured interview per v1 principles (batched independent questions, A/B/C with recommended, YAGNI, challenge the problem).
8. Phase: Discussion File — write `discussion.md` (self-contained for plan-writer with no conversation history).
9. Phase: Discussion Review — loop up to `review.discussion.rounds` (config). Invoke `mill-review-discussion.py`, load `mill-receiving-review` skill, present each GAP to user, re-invoke after update.
10. Phase: Handoff — `status.md` → `phase: discussed`. Tell user to run `mill-plan` next.

## Backend

**New / to add:**
- `_constraints.py` — `read_if_exists(repo_root: Path) -> str | None`. Reads CONSTRAINTS.md from hub root. Returns `None` if absent. Used by mill-start and by `_review_*.py` to avoid duplicate scan logic.
- `_active.py` — `read_slug(mill_dir: Path) -> str`. Reads `.millhouse/active.slug.md`. Parses fenced yaml for `slug:`. Raises if missing/malformed.
- `_status.py` — already planned (for mill-spawn). Needs `append_phase()` + `update_field()` for this skill too.

**Reused / already exists:**
- `_wiki.py` — sync_pull, write_commit_push, lock.
- `_review_common.parse_verdict` — parses review script output.
- `mill-review-discussion.py` — invoked as subprocess.

## Templates

- No new templates from mill-start itself. The skill is prose instructions (v1-style) and an optional discussion-file skeleton:
  - `templates/discussion.md` — skeleton with fenced yaml frontmatter (`task:`, `slug:`, `status:` = "discussing") + empty sections (Problem, Scope, Decisions, Technical Context, Testing, Q&A log). Written at the start of Phase: Discussion File; filled in by the skill.

## Discussion file YAML (proposed)

```yaml
task: <task-title>
slug: <slug>
status: discussing      # or discussed after review loop approves
parent: <parent-branch>
```

Rest of the file is free-form markdown sections. Parser-friendly but not strictly validated — only the review-CLI and mill-plan need to read it, and both tolerate free-form.

## Out of scope vs v1

- No DAG / v3-card considerations — v2 plan is linear.
- No `spawn_reviewer` entrypoint wrapping — CLI-direct invoke only.
- No `-dr N` flag.
- No pipeline.discussion-review.rounds override via flag — config-only.

## Open design points

- **`.millhouse/active.slug.md` format**: fenced yaml with `slug:` (+ maybe `task_title:` for convenience)? Exact key names and whether the skill should rewrite this file or leave it read-only after spawn.
- **`_constraints.read_if_exists`**: should hub-root be passed in or resolved via `git rev-parse`? Latter is more robust across sub-folder cwd but adds subprocess.
- **Status.md "parent:" field**: v1 reads parent branch via `git worktree list --porcelain`. Confirm v2 approach (probably same).
- **Review-round counter persistence**: if user kills session mid-loop, how does mill-start resume? v1 doesn't resume — every run starts from round 1. Confirm.
- **mill-receiving-review skill load mechanism**: skill auto-loads via `Skill` tool invocation (verify the exact trigger).
- **Discussion file skeleton template**: does the template go in `templates/` or is it inline in the SKILL.md? v1 had no skeleton — the skill wrote from scratch each time.
