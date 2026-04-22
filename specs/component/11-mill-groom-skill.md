# mill-groom (skill)

```yaml
type: skill
layer: 04
v1_ref: none (mill-revise-tasks covers a similar intent but via GitHub issues; mill-groom is for the Home.md backlog itself)
status: partially discussed — key decisions captured, not ready for full-write
note: "Interactive backlog cleanup. Works on Home.md: consolidate duplicates, shorten bloated entries, kill dead tasks, surface gaps. Requires judgment — hence a skill, not a script."
```

## Purpose

Keep `Home.md` readable. Over time the backlog accrues duplicate tasks, long-winded entries, done-but-not-cleaned residue, and vague wishes that never got a slug. `mill-groom` is a one-shot interactive pass that lets the user work through the list with Claude and emit a cleaner Home.md.

## Decisions

- **Skill, not script** — every consolidation / shorten / drop decision needs judgment. Claude proposes, user decides, skill applies on approval.
- **One-shot, no state** — if the user quits mid-session, nothing is half-written. The scratch-file proposal is the only intermediate artefact.
- **Scope by marker**:
  - No marker (backlog) / `[s]` (spawn-ready) — full action set (keep / shorten / fold / drop / extract).
  - `[done]` — only *drop* is offered, and only after user confirms. Useful to prune tombstone clutter from old completed work.
  - `[active]` — NEVER touched. Live work. (v2 has no `[abandoned]` marker; mill-cleanup resets abandoned tasks to unclaimed, so they re-appear in the full-action scope.)
- **Actions available per entry** (user picks per task):
  - **Keep as-is** — no change.
  - **Shorten** — Claude proposes a tighter summary, user approves/edits.
  - **Fold into `<other-slug>`** — merge this entry into an existing one; this entry is removed.
  - **Drop** — remove the entry entirely (with comment in the removal commit explaining why).
  - **Extract to proposal** — if the task body is long and exploratory, move it to `<WIKI_PATH>/proposal-<slug>.md` and leave a 1-line summary linking to it.
- **Protected marker**: entries whose body contains `<!-- protected -->` (HTML comment) are skipped entirely — user has flagged them as "hands off".
- **Approval gate**: Claude writes a proposal to `.millhouse/scratch/groom-proposal.md` with the full before/after, user replies `approve` or `reject` in chat.
- **Single commit on approve**: all backlog changes go in one `_wiki.write_commit_push` with a message listing counts ("chore: groom Home.md — 3 shortened, 2 folded, 1 dropped, 1 extracted").
- **No link to GitHub issues**: mill-groom does NOT fetch or close issues. That's `mill-revise-tasks`'s job. A future `mill-groom` could optionally call `mill-revise-tasks` first, but they stay as separate skills for now.

## Flow

1. `wiki.sync_pull(<WIKI_PATH>)`.
2. Read `Home.md`, parse tasks, filter to backlog-markers (`[]` / `[s]`).
3. Identify grooming candidates:
   - Long bodies (threshold: `groom.brevity-threshold-lines` / `-chars`, same defaults as v1's mill-revise-tasks: 5 / 500).
   - Possible duplicates (title overlap, body overlap — LLM judgment).
   - Short-form entries with no summary.
4. Present candidates to user in small batches. For each, propose an action + alternatives.
5. Build the consolidated proposal at `.millhouse/scratch/groom-proposal.md` (table of decisions + new/shortened/folded entries + extraction targets).
6. User replies `approve` / `reject`.
7. On `approve`:
   - Build the new Home.md content in memory.
   - Write any `proposal-<slug>.md` extraction files to `<WIKI_PATH>/`.
   - `_wiki.write_commit_push([...Home.md..., ...proposal-<slug>.md...], "chore: groom Home.md — ...")`.
   - Regenerate sidebar.
8. Report counts.

## Backend

**New:**
- None that aren't already planned. Uses `_wiki.py`, `_tasks_md.py` (planned), `_sidebar.py`.

**Reused:**
- `_wiki.py`, `_junction.py`, `_tasks_md.py`, `_sidebar.py`.

## Rules

- Never silently rewrite Home.md. The proposal/approval gate is non-negotiable.
- Protected tasks (`<!-- protected -->`) are never modified.
- `[active]` tasks are never modified. `[done]` tasks offer only the *drop* action — mill-groom never rewrites their body or folds them into other tasks.
- One commit per grooming session — easy to review in `git log`.

## Out of scope

- No GitHub issue integration (use `mill-revise-tasks`).
- No multi-machine coordination.
- No cross-wiki grooming.

## Open design points

- **Brevity thresholds in config**: same as v1's `revise.*` — but now under `groom.*`. Defaults 5 lines / 500 chars.
- **Duplicate detection**: pure LLM judgment or a heuristic (title Levenshtein, body overlap)? LLM judgment is easier and catches semantic duplicates; heuristics are a safety net. Start with LLM; add heuristic if false-positives become a nuisance.
- **Extraction file naming**: if a groom extracts to `proposal-<slug>.md`, use the same slug as the Home.md entry. Collisions with existing proposal files should error and ask the user.
