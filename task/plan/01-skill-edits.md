# Batch: skill-edits

```yaml
task: 43 (A) — Discussion-review gaps in batches + NOTE-finding handling
batch: skill-edits
number: 1
cards: 3
verify: null
depends-on: []
```

## Batch Scope

Single-file edit batch against `plugins/mill/skills/mill-start/SKILL.md`. Delivers three independent text replacements: (1) split current step 4 of Phase: Discussion Review into `4a` / `4b` to add NOTE-handling on `APPROVE`; (2) replace current step 5's one-gap-at-a-time wording with a gap-batching protocol that uses `mill:conversation`'s numbered-options format and sequential batches of ≤5 gaps per round; (3) extend the Auto-mode subsection's "**Phase: Discussion Review — `--auto` changes:**" bullets to apply the same FIX-everything rule to NOTEs and to add an `On APPROVE` bullet that mirrors interactive 4a/4b. All three edits target the same skill file. The batch consumes no upstream interface and exposes no new downstream interface — it documents behaviour for the orchestrator (a CC session running `/mill-start`) to follow on future runs.

Batch-local decisions (in addition to `## Shared Decisions` in overview):

- The fixer-report filename pattern uses `_timestamp.now_utc_compact()` returned by `plugins/mill/scripts/_timestamp.py` (format: `YYYYMMDD-HHMMSS`, no separator between date and time). This is the same helper mill-plan uses in step 4c. SKILL.md prose references the format as `<YYYYMMDD-HHMMSS>` so a reader matches the on-disk file pattern.
- The single-commit pathspec for 4b is exactly three paths: `task/discussion.md`, `task/reviews/`, `task/status.md`. Listed verbatim in the step-4b prose.

## Cards

### Card 1: Replace step 4 with steps 4a + 4b (NOTE handling on APPROVE)

- **Context:**
  - `task/discussion.md`
  - `plugins/mill/skills/mill-plan/SKILL.md`
  - `plugins/mill/skills/mill-receiving-review/SKILL.md`
- **Edits:**
  - `plugins/mill/skills/mill-start/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `plugins/mill/skills/mill-start/SKILL.md` Phase: Discussion Review main subsection (the section that begins `### Phase: Discussion Review` and contains the numbered steps 1–5), replace the single line "`4. On APPROVE: break the loop and proceed to Handoff.`" with two consecutive numbered steps `4a` and `4b`:

  - `4a. On APPROVE (verdict from JSON) with no NOTE findings: read the review file at the absolute path supplied by `reviews[0].file` in the JSON envelope from step 2 and confirm zero `[NOTE]`-prefixed findings. Break the loop and proceed to Handoff.`

  - `4b. On APPROVE with one or more `[NOTE]` findings: apply each NOTE fix per the `mill-receiving-review` decision tree by editing `task/discussion.md` directly. Write a fixer report at `task/reviews/<YYYYMMDD-HHMMSS>-discussion-fix-r<N>.md` (timestamp from `_timestamp.now_utc_compact()`) with two sections — `## Fixed` (one line per fixed NOTE: short reference to the source review file + quoted finding title) and `## Pushed Back` (one line per rejected NOTE: short reference + reason citing code, doc, or scope per `mill-receiving-review`'s legitimate-pushback rules). Call `_status.append_phase(status_path, f"discussion-fix-r{N}", _timestamp.now_utc_iso())`. Single git commit covering exactly three pathspecs — `task/discussion.md`, `task/reviews/`, `task/status.md` — with message `mill-start: discussion-fix round {N} for {slug}`. Push. Break loop → Handoff. Do NOT run round N+1. Do NOT advance the round counter; the fixer report's `discussion-fix-r<N>` reuses the just-completed review round's `N` value.`

  Verb shape, status-phase name, fixer-report filename, commit-message shape, and section list must match `plugins/mill/skills/mill-plan/SKILL.md` step 4c verbatim with the strings `plan` → `discussion` and `mill-plan` → `mill-start` substituted. Steps 1, 2, 3 above this insertion remain unchanged. The renumbered step 5 (`On GAPS_FOUND:`) keeps the same step number — no renumber needed.

  Detection rule: NOTE findings are detected by parsing the review-file markdown for the literal severity prefix `[NOTE]`, mirroring `_review_common.parse_blocking_count`'s `severity="GAP"` parser (which mill-start does not call directly; it reads the file).
- **Commit:** `docs(mill-start): NOTE-handling on APPROVE (steps 4a/4b)`

### Card 2: Replace step 5 with gap-batching protocol

- **Context:**
  - `task/discussion.md`
  - `plugins/mill/skills/conversation/SKILL.md`
  - `plugins/mill/skills/mill-receiving-review/SKILL.md`
- **Edits:**
  - `plugins/mill/skills/mill-start/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In the same `### Phase: Discussion Review` subsection (after the changes from card 1), replace the entire existing step 5 ("`5. On GAPS_FOUND: read the review file, **present each gap to the user one at a time, and wait for their response before updating `discussion.md`**. Do not auto-fix gaps. After user answers and discussion.md is updated, commit+push the update and start the next round.`") with this expanded step 5:

  `5. On GAPS_FOUND: read the review file and enumerate each `[GAP]` finding. Present gaps to the user in **sequential batches of at most 5 gaps per batch**. Each gap is formatted as a numbered question whose resolution options follow the `mill:conversation` rule — numbered text list, the recommended option is option 1 (the SKILL must use its judgment + context to propose a recommended resolution and 1–3 distinct alternatives). Free-text gap prompts are forbidden; the SKILL must coerce every gap into options form, just as the auto-mode rule does for interview questions in Phase: Discuss. Wait for the user to answer every gap in the current batch before presenting the next batch. As each batch's answers arrive, apply them to an in-memory copy of `task/discussion.md` (do NOT write the file mid-round). When the final batch in this round is answered, write `task/discussion.md`, commit on the task branch (`git -C <worktree> add task/discussion.md && git commit -m "mill-start: discussion-gap-fix round {N} for {slug}"`), push, and start round N+1. If a gap is genuinely impossible to answer (operator does not know yet), the operator may pick the recommended option and add a follow-up note inline — that is the same fallback as Phase: Discuss.`

  The "≤5 per batch" cap matches the Phase: Discuss cap introduced by task 39 (`mill-start question-format UX`). The Q&A log is NOT updated for gap answers — the Q&A log records operator-driven interview decisions, not reviewer-driven gap-resolution answers; the updated `task/discussion.md` content is the audit trail for gap resolutions. Card 1's step 4b path is independent of this step 5 path; the routing decision between them is the JSON envelope's `verdict` field.
- **Commit:** `docs(mill-start): gap-batching protocol (step 5)`

### Card 3: Add NOTE-handling rules to Auto-mode subsection

- **Context:**
  - `task/discussion.md`
  - `plugins/mill/skills/mill-receiving-review/SKILL.md`
- **Edits:**
  - `plugins/mill/skills/mill-start/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In the same file's Auto-mode subsection ("`## Auto mode`"), under the bold heading "**Phase: Discussion Review — `--auto` changes:**", make two edits:

  (a) Replace the existing bullet "`Every gap returned by the reviewer is treated as FIX regardless of the decision-tree outcome (factually-wrong gaps included).`" with: "`Every gap AND every NOTE returned by the reviewer is treated as FIX regardless of the decision-tree outcome (factually-wrong findings included). PUSH BACK is unavailable because no operator is present.`"

  (b) Immediately after the existing bullet "`On GAPS_FOUND, the assistant auto-resolves each gap by adding the missing information to discussion.md using best judgment, commits, **pushes**, and re-runs the review.`" (and before the existing "`If gaps remain after max_review_rounds`" bullet), insert this new bullet: "`On APPROVE, read the review file. If zero `[NOTE]` findings: break the loop and proceed to Handoff (auto-path identical to interactive 4a). If one or more `[NOTE]` findings: take the interactive 4b path verbatim — auto-resolve each NOTE by editing `task/discussion.md` using best judgment (per the `mill-receiving-review` decision tree, with PUSH BACK unavailable), write the same fixer report at `task/reviews/<YYYYMMDD-HHMMSS>-discussion-fix-r<N>.md` with `## Fixed` / `## Pushed Back` sections, append `discussion-fix-r{N}` to the status timeline, single commit covering `task/discussion.md` + `task/reviews/` + `task/status.md` with message `mill-start: discussion-fix round {N} for {slug}`, push, break loop → Handoff. The Q&A log is NOT touched for NOTEs — the fixer report is the audit trail.`"

  No other bullets in the Auto-mode subsection change. The "Phase: Discuss — `--auto` changes:" subsection above is untouched. The trailing paragraph about `--auto` vs `pipeline.autonomous_mode` independence is untouched.
- **Commit:** `docs(mill-start): auto-mode NOTE handling`

## Batch Tests

`verify: null` in this batch's frontmatter and in the overview frontmatter — pure docs batch with no runnable surface. The verification surface is the rendered `plugins/mill/skills/mill-start/SKILL.md`. Reviewer (human or LLM) must confirm by reading the file end-to-end:

- Phase: Discussion Review main subsection has steps `1`, `2`, `3`, `4a`, `4b`, `5` (renumbered: previous `4` is now `4a` + `4b`; previous `5` remains `5`).
- Step `4a` references reading the review file and confirming zero `[NOTE]` findings before breaking the loop.
- Step `4b` names: the `mill-receiving-review` decision tree; the fixer-report path `task/reviews/<YYYYMMDD-HHMMSS>-discussion-fix-r<N>.md`; the two report sections `## Fixed` and `## Pushed Back`; the `discussion-fix-r{N}` status-timeline phase; the single-commit pathspecs `task/discussion.md` + `task/reviews/` + `task/status.md`; the commit message `mill-start: discussion-fix round {N} for {slug}`; the rule that round N+1 does NOT run; and the rule that the round counter does NOT advance.
- Step `5` names: ≤5 gaps per batch; numbered-options format per `mill:conversation`; sequential batches within a round; in-memory `task/discussion.md` between batches; single commit + push after the round's final batch; commit message `mill-start: discussion-gap-fix round {N} for {slug}`.
- Auto-mode subsection's "Phase: Discussion Review — `--auto` changes:" bullets include: an updated "Every gap AND every NOTE … is treated as FIX" rule, and a new "On APPROVE" bullet that points to interactive 4a/4b verbatim plus the rule that Q&A log is not touched for NOTEs.

No regression surface: existing scripts (`millpy-review-discussion.py`, `_review_discussion.py`, `_review_common.py`, `_reviewers.py`, `_status.py`, `_timestamp.py`, `_yaml_writer.py`) are not touched and their signatures are not consumed in any new way by the SKILL changes. No new unit tests are added per the discussion's "Testing → Unit tests" decision; the brittle SKILL-shape-parse test that could exist was explicitly rejected.
