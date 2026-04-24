---
kind: plan-batch
batch-name: skill
batch-depends: []
approved: false
---

# Batch 01: skill

## Batch-Specific Context

Write the `mill-groom` SKILL.md. The skill is interactive and prose-only —
no supporting Python helpers. Follows the `mill-ghissues-to-tasks` shape:
`---` frontmatter, intro paragraph, numbered steps, Rules section.

## Batch Files

- plugins/mill/skills/mill-groom/SKILL.md

## Cards

### Card 01: Create plugins/mill/skills/mill-groom/SKILL.md

- **Creates:** plugins/mill/skills/mill-groom/SKILL.md
- **Modifies:** nothing
- **Reads:** plugins/mill/skills/mill-ghissues-to-tasks/SKILL.md (shape reference), specs/component/11-mill-groom-skill.md (decisions)
- **Requirements:**
  - `---` frontmatter with `name: mill-groom` and a one-line `description:`.
  - Intro paragraph: what the skill does and when to use it.
  - **Step 1 — Entry checks**: wiki junction exists; `_wiki.sync_pull`.
  - **Step 2 — Read config**: load `wiki/config.yaml`; extract `groom.brevity-threshold-lines` (default 5) and `groom.brevity-threshold-chars` (default 500).
  - **Step 3 — Parse Home.md**: use `_tasks_md.py` (`parse()`). Filter to backlog markers (`[]` / `[s]`). Skip `[active]`. Offer only `drop` for `[done]`. Skip entries whose body contains `<!-- protected -->`.
  - **Step 4 — Identify candidates**: flag entries exceeding brevity thresholds; flag possible duplicates (LLM judgment); flag entries with no summary text.
  - **Step 5 — Interactive decisions**: present candidates in small batches. For each, propose an action (keep / shorten / fold / drop / extract) with alternatives. Do NOT auto-decide. Record every decision.
  - **Step 6 — Write proposal**: write `.scratch/groom-proposal.md`. Format: fenced table of decisions, then sections for shortened/folded/dropped/extracted entries showing before/after. Print path + one-line summary to chat. User replies `approve` or `reject`.
  - **Step 7 — Apply (on approve)**: build new Home.md content in memory. Write any `proposal-<slug>.md` extraction files to `<WIKI_PATH>/`. Check for collisions before writing — if `proposal-<slug>.md` already exists, error out and ask the user. Call `_wiki.write_commit_push` with all changed files and a message of the form `chore: groom Home.md — N shortened, N folded, N dropped, N extracted`. Regenerate sidebar (`_sidebar.regenerate`). Delete `.scratch/groom-proposal.md`.
  - **Step 8 — Report**: print counts (shortened / folded / dropped / extracted).
  - **Rules section**: mirror spec rules verbatim (never silently rewrite, protected tasks skipped, active tasks never touched, done tasks get only drop, one commit per session).
  - **Out of scope**: no GitHub issue integration, no multi-machine coordination.
- **Commit:** `feat(mill-groom): add SKILL.md`
