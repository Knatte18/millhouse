# mill-groom (skill)

```yaml
type: skill
layer: 04
v1_ref: none (mill-ghissues-to-tasks covers a similar intent but via GitHub issues; mill-groom is for the Home.md backlog itself)
status: done — merged to main 2026-04-24 (branch impl/11-mill-groom-skill)
note: "Interactive backlog cleanup. Works on Home.md: consolidate duplicates, shorten bloated entries, kill dead tasks, surface gaps. Requires judgment — hence a skill, not a script."
```

**Implementation notes:** `SKILL.md` only — no new Python helpers. Follows the `mill-ghissues-to-tasks` shape: `---` frontmatter, numbered steps, Rules/Out-of-scope sections. Brevity thresholds (`groom.brevity-threshold-lines: 5`, `groom.brevity-threshold-chars: 500`) added to `wiki/config.yaml`. Duplicate detection is LLM-judgment only; extraction collisions error out and ask the user. Approval is all-or-nothing; `.scratch/groom-proposal.md` is deleted after commit.

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
- **Approval gate**: Claude writes a proposal to `.scratch/groom-proposal.md` with the full before/after, user replies `approve` or `reject` in chat.
- **Single commit on approve**: all backlog changes go in one `_wiki.write_commit_push` with a message listing counts ("chore: groom Home.md — 3 shortened, 2 folded, 1 dropped, 1 extracted").
- **No link to GitHub issues**: mill-groom does NOT fetch or close issues. That's `mill-ghissues-to-tasks`'s job. A future `mill-groom` could optionally call `mill-ghissues-to-tasks` first, but they stay as separate skills for now.
- **Brevity thresholds**: `groom.brevity-threshold-lines` (default 5) and `groom.brevity-threshold-chars` (default 500) live in `wiki/config.yaml` under a `groom:` block. Grooming targets the shared backlog — shared config is the right home.
- **Duplicate detection**: LLM judgment only. Catches semantic duplicates without extra code; add heuristics later only if false-positives become a real problem.
- **Extraction file naming**: use the same slug as the Home.md entry (`proposal-<slug>.md`). If that file already exists in the wiki, error out and ask the user what to do.
- **Invocation**: `/mill-groom` with no arguments. No `--max` or `--since` flags.
- **Approval**: all-or-nothing (`approve` / `reject`). The user can redirect mid-flow in chat if they want to change a specific decision before approving.
- **Scratch cleanup**: delete `.scratch/groom-proposal.md` after the approved changes are committed. Scratch is ephemeral.
- **Tests**: no new tests. The existing suite (`run-all.py` + integration tests) is the bar. No supporting Python helpers are planned, so there is nothing mechanical to test.

## Flow

1. `wiki.sync_pull(<WIKI_PATH>)`.
2. Read `Home.md`, parse tasks, filter to backlog-markers (`[]` / `[s]`).
3. Identify grooming candidates:
   - Long bodies (threshold: `groom.brevity-threshold-lines` / `-chars`, same defaults as v1's mill-ghissues-to-tasks: 5 / 500).
   - Possible duplicates (title overlap, body overlap — LLM judgment).
   - Short-form entries with no summary.
4. Present candidates to user in small batches. For each, propose an action + alternatives.
5. Build the consolidated proposal at `.scratch/groom-proposal.md` (table of decisions + new/shortened/folded entries + extraction targets).
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

- No GitHub issue integration (use `mill-ghissues-to-tasks`).
- No multi-machine coordination.
- No cross-wiki grooming.

