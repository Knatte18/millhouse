# Batch: skill-docs

```yaml
task: 50 (A) — Bug-fix batch 5 (post-44 triage)
batch: skill-docs
number: 2
cards: 3
verify: null
depends-on: [1]
```

## Batch Scope

Update three SKILL.md files to consume the new `_status.set_blocked` helper
introduced in batch 1, add mill-plan's missing APPROVE-with-NIT substep
(#247) and skip-review block (#249), fix mill-start's reviews-dir path typo
(#239), and add the missing `slug=` kwarg in mill-merge-in's `sync_pull`
example (#254). #246 is a verify-only strand bundled into Card 4's
Requirements (grep mill-start SKILL.md for stale `review.discussion.*`
references and confirm zero hits).

`verify: null` because this batch only changes Markdown documentation. The
existing test suite is unaffected. Reviewer-eye-on-diff catches regressions.

Batch-local decisions:

- Call-site translation pattern: every paired
  `_status.append_phase(status_path, "blocked", iso_ts)` + `_status.update_field(status_path, "blocked_reason", "<reason>")`
  becomes `_status.set_blocked(status_path, "<reason>", timestamp=iso_ts)`.
  The `iso_ts` variable name is preserved verbatim where it already exists in
  the SKILL.md text.
- The mill-plan 4a/4b split renumbers existing 4b → 4c and 4c → 4d. Step 4.5
  (ERROR-only-aggregate retry) keeps its `.5` placement (between 4a/4b and
  4c — its position relative to numbered steps stays the same: after the
  APPROVE branch and before the REQUEST_CHANGES branches).
- The mill-plan skip-review block lives at the top of `### Phase: Plan Review`
  (immediately after the heading, before "Loop up to `max_review_rounds`
  rounds.") mirroring mill-start's line-98 placement.

## Cards

### Card 4: mill-start SKILL.md updates

- **Context:**
  - `plugins/mill/scripts/_status.py`
- **Edits:**
  - `plugins/mill/skills/mill-start/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  1. **#238 call-site:** locate the auto-mode block-on-gaps path inside `### Phase: Discussion Review` (the bullet starting with "If gaps remain after `max_review_rounds`:"). Replace the chain `_status.append_phase(status_path, "blocked", _timestamp.now_utc_iso())`, then `_status.update_field(status_path, "blocked_reason", "auto: discussion review gaps unresolved after <N> rounds")` with a single call: `_status.set_blocked(status_path, f"auto: discussion review gaps unresolved after {N} rounds", timestamp=_timestamp.now_utc_iso())`. The subsequent `git add task/status.md && git commit -m "mill-start: blocked (auto: discussion review gaps unresolved) for <slug>" && git push` line stays unchanged; the commit pathspec is still `task/status.md` (set_blocked writes the same file).
  2. **#239 path typo:** in `### Phase: Discussion Review` step 2 (the paragraph beginning "This returns immediately with `pid=<N>` log=…"), change `The script writes the review file under \`<worktree_root>/reviews/\`` to `The script writes the review file under \`task/reviews/\``. No other word in that paragraph changes.
  3. **#246 verify-only:** grep the file for any reference matching the regex `review\.discussion\.` (escaped dots). Expected hit count: 0. If any hit exists, that is a regression from commit `560bed8`; halt and surface the line number rather than continuing. (No file edit expected; this is a guard.)
- **Commit:** `fix(mill-start): use set_blocked + correct task/reviews/ path`

### Card 5: mill-plan SKILL.md updates

- **Context:**
  - `plugins/mill/scripts/_status.py`
  - `plugins/mill/skills/mill-start/SKILL.md`
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  1. **#249 skip-review block:** insert a new paragraph at the top of `### Phase: Plan Review`, between the heading line and the existing `Loop up to \`max_review_rounds\` rounds.` paragraph. New paragraph text:

     > The new schema has two skip conditions: `rounds: 0` OR `reviewer: null` means "skip plan review". If `roles.plan-review.holistic.rounds == 0` OR `roles.plan-review.holistic.reviewer` is `None`: set overview frontmatter `approved: true` via direct Edit, commit on the task branch (`git -C <worktree> add task/plan/ && git commit -m "mill-plan: skip plan review (reviewer null or rounds 0) for {slug}"`), push, and proceed straight to Handoff. The skip is recorded in commit history; no `status.md` phase flip beyond the existing Handoff `planned` row.

     The wording mirrors mill-start SKILL.md's line-98 skip block. Indentation matches the surrounding ###-level body text.
  2. **#247 NIT-fix substep — split step 4a:** the existing step 4a (paragraph starting `4a. On \`APPROVE\` (verdict from JSON):`) handles both APPROVE-no-NITs and APPROVE-with-NITs identically. Split into:

     - **4a.** On `APPROVE` (verdict from JSON) with zero `[NIT]` findings (read the review file at `reviews[0].file` and confirm zero `[NIT]`-prefixed findings): set overview frontmatter `approved: true` via direct Edit. `_status.append_phase(status_path, f"plan-review-r{N}", iso_ts)`. Commit on the task branch: `git -C <worktree> add task/plan/ task/reviews/ task/status.md && git -C <worktree> commit -m "mill-plan: approve plan for {slug}"`. Push. Break loop → Handoff. `iso_ts` is `_timestamp.now_utc_iso()`.
     - **4b.** On `APPROVE` with one or more `[NIT]` findings: apply each NIT per the `mill-receiving-review` decision tree by editing the plan files directly. Write a fixer report at `task/reviews/<YYYYMMDD-HHMMSS>-plan-fix-r<N>.md` (timestamp from `_timestamp.now_utc_compact()`) with two sections — `## Fixed` (one line per fixed NIT: short reference to the source review file + quoted finding title) and `## Pushed Back` (one line per rejected NIT: short reference + reason citing code, doc, or scope per `mill-receiving-review`'s legitimate-pushback rules). Re-validate the plan DAG via `_plan_dag.validate`. Call `_status.append_phase(status_path, f"plan-fix-r{N}", iso_ts)`. Set overview frontmatter `approved: true` via direct Edit. Single git commit covering exactly three pathspecs — `task/plan/`, `task/reviews/`, `task/status.md` — with message `mill-plan: plan-fix round {N} for {slug}` (matches existing 4c message shape; the round counter is NOT advanced). Push. Break loop → Handoff.

     **Renumber subsequent steps:** existing step 4.5 keeps its `.5` placement (it now sits between the new 4a/4b APPROVE pair and the renumbered REQUEST_CHANGES branch). Existing step 4b (`REQUEST_CHANGES + blocking_count == 0`) becomes step 4c. Existing step 4c (`REQUEST_CHANGES + blocking_count > 0`) becomes step 4d. Existing step 5 (non-progress check) keeps its `5` numbering — it references "step 4b" generically as "the fixer-report-writing branch"; the existing text already names "fixer report" without a step number, so no renumber needed inside step 5. Existing step 6 (max-rounds escape) keeps its `6`.
  3. **#238 call-site (non-progress):** locate step 5's non-progress autonomous-mode branch. Replace the chained `_status.append_phase(status_path, "blocked", ts)` + `_status.update_field(status_path, "blocked_reason", f"non-progress round {N}")` with a single call: `_status.set_blocked(status_path, f"non-progress round {N}", timestamp=ts)`. The subsequent commit message and `git add` pathspecs stay unchanged.
  4. **#238 call-site (max-rounds):** locate step 6's max-rounds autonomous-mode branch. Replace the chained `_status.append_phase(status_path, "blocked", ts)` + `_status.update_field(status_path, "blocked_reason", f"max-rounds exhausted after {N} rounds, {M} BLOCKINGs remain")` with a single call: `_status.set_blocked(status_path, f"max-rounds exhausted after {N} rounds, {M} BLOCKINGs remain", timestamp=ts)`. The subsequent commit message and `git add` pathspecs stay unchanged.
- **Commit:** `fix(mill-plan): add skip-review block, APPROVE+NIT substep, set_blocked calls`

### Card 6: mill-merge-in SKILL.md updates

- **Context:**
  - `plugins/mill/scripts/_wiki.py`
- **Edits:**
  - `plugins/mill/skills/mill-merge-in/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `plugins/mill/skills/mill-merge-in/SKILL.md` line 12, change `\`_wiki.sync_pull(<WIKI_PATH>)\`` to `\`_wiki.sync_pull(<WIKI_PATH>, slug="mill-merge-in")\``. The surrounding paragraph wording stays unchanged. No other line in the file changes.
- **Commit:** `fix(mill-merge-in): pass required slug kwarg to sync_pull`

## Batch Tests

`verify: null` because the batch only edits Markdown documentation. The
existing unit-test suite is unaffected, and there is no executable assertion
to run. The plan reviewer and code reviewer cover regression — every
SKILL.md change is line-level and easy to diff.
