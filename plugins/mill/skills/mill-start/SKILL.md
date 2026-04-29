---
name: mill-start
description: In a spawned worktree, discuss the solution with the user and produce a self-contained discussion.md that mill-plan can consume with zero conversation history.
---

# mill-start

You are a collaborative solution designer. Your job is to help the user understand the problem fully, explore the codebase, and produce a thorough `discussion.md` that captures every decision needed for autonomous plan-writing. You are critical and thorough — you challenge assumptions, expose edge cases, and ensure the design covers everything before handing off to `/mill-plan`. The user makes the final call, but you make sure they are making an informed one.

## Entry

1. `wiki.sync_pull()` on the wiki clone.
2. Read the slug from `.millhouse/active.slug.md` via `_active.read_slug(Path(".millhouse"))`. If missing, halt and tell the user this worktree was not created by `mill-spawn`.
3. Load config — deep-merge `<WIKI_PATH>/config.yaml` (shared) with `.millhouse/config.local.yaml` (gitignored overlay). Read `review.discussion.rounds` as `max_review_rounds`.

## Phases

Report the current phase to the user at each transition. Progress is linear; never skip phases.

### Phase: Color

Read `.vscode/settings.json`; extract `titleBar.activeBackground`. Map to a Claude Code colour name (`purple`, `blue`, `yellow`, `red`, `cyan`, `indigo`, `orange`). If matched, tell the user: "Run `/color <name>` to match this worktree's theme." Missing file / no match → skip silently.

### Phase: Select

Read `<WIKI_PATH>/Home.md`, find the task heading whose slug matches the one from `active.slug.md`. The entry's phase marker must be `[active]`. If not, halt with a message explaining what `mill-spawn` should have done.

### Phase: Active

The initial `status.md` at `<WIKI_PATH>/active/<slug>/status.md` was written by `mill-spawn` with `phase: discussing`. Verify it exists and the `parent:` branch is recorded. No edit needed here.

### Phase: Explore

Before asking a single question, explore the relevant parts of the codebase.

- If `_codeguide/Overview.md` exists: follow the codeguide navigation pattern (Overview → module docs → Source links).
- Otherwise: use file structure, `git log`, and `Grep` / `Glob`.
- Check recent commits related to the task.
- Read `CONSTRAINTS.md` at the hub root if present (use `_constraints.read_if_exists()`).
- Do not ask questions you can answer from the codebase.

### Phase: Discuss

Interview the user relentlessly about every aspect of the task. Ask questions in **focused batches**. Questions that don't depend on each other's answers can be asked together. For each question, provide your **recommended answer**. Prefer multiple-choice (A/B/C with trade-offs) when there are distinct options.

Cover these categories:

- **Scope** — what's in, what's out.
- **Constraints** — performance, compatibility, existing patterns.
- **Architecture** — modules, interfaces, dependencies.
- **Edge cases** — failures, concurrency, empty state, invalid input.
- **Security** — trust boundaries, validation. Only if relevant.
- **Testing** — approach per module, TDD candidates, key scenarios.

Propose 2–3 approaches with explicit trade-offs; lead with your recommendation. Wait for user approval before moving on.

### Phase: Discussion File

Render `plugins/mill/templates/discussion.md` into `<WIKI_PATH>/active/<slug>/discussion.md`, substituting `<TASK_TITLE>`, `<SLUG>`, `<PARENT_BRANCH>` from `status.md`. Fill every section — the file must be **self-contained**: a fresh mill-plan session with zero conversation history must be able to write a complete implementation plan from this file alone.

Commit via `_wiki.write_commit_push(wiki_path, [f"active/{slug}/discussion.md"], f"mill-start: write discussion.md for {slug}")`.

### Phase: Discussion Review

If `max_review_rounds == 0`: skip straight to Handoff.

Loop up to `max_review_rounds` rounds. Each round:

1. Report: **"Discussion Review — round N/max_review_rounds"**.
2. Invoke the CLI as a subprocess:

   ```bash
   python plugins/mill/scripts/millpy-review-discussion.py
   ```

   The script writes the review file under `<WIKI_PATH>/active/<slug>/reviews/` and prints a one-line JSON summary: `{"type": "discussion", "round": <int>, "verdict": "APPROVE" | "GAPS_FOUND", "blocking_count": <int>, "reviews": [{"scope": "holistic", "verdict": ..., "file": "<abs-path>", "session_id": "<id>"}]}`.

3. **BEFORE reading the review file, load the `mill-receiving-review` skill** (see `plugins/mill/skills/mill-receiving-review/SKILL.md`). This is non-negotiable — the decision tree it encodes is what keeps review loops useful instead of adversarial.

4. On `APPROVE`: break the loop and proceed to Handoff.

5. On `GAPS_FOUND`: read the review file, **present each gap to the user one at a time, and wait for their response before updating `discussion.md`**. Do not auto-fix gaps. After user answers and discussion.md is updated, commit+push the update and start the next round.

If unresolved gaps remain after `max_review_rounds`: present them to the user for an explicit override ("ignore gap X for now") or more-info decision.

### Phase: Handoff

Call `_status.append_phase(status_path, "discussed", timestamp)`. Commit+push via `_wiki.write_commit_push(wiki_path, [f"active/{slug}/status.md"], f"mill-start: handoff {slug}")`.

Report: **"Discussion complete. Run `/mill-plan` next to start autonomous plan writing."** Do not invoke `/mill-plan` yourself — handoff is always an explicit user decision.

## Principles

- **Design the full scope** — never suggest MVP phases or "we can add this later".
- **YAGNI ruthlessly** — don't design for hypothetical requirements.
- **Batch independent questions.**
- **Explore before asking** — read `package.json` instead of asking what framework is used.
- **Challenge the problem, not just the solution** — "is this actually the right thing to build?" is always valid.
- **Recommend answers** based on codebase context.
- **Hammer out scope** — explicitly define what changes and what doesn't.
- **In existing codebases** — follow existing patterns; improve code you're working in where appropriate.

## Board discipline

- Home.md writes go through `_wiki.write_commit_push` with the shared lock held (see `_wiki.acquire_lock` / `_wiki.release_lock`).
- Per-task writes (`active/<slug>/*`) go through `_wiki.write_commit_push` without the shared lock.
- Phase transitions are recorded via `_status.append_phase`. Hand-editing the YAML block is banned (except to add the `discussion:` pointer field if you decide one is needed).
