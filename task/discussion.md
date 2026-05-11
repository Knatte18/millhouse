# Discussion: 43 (A) — Discussion-review gaps in batches + NOTE-finding handling

```yaml
task: 43 (A) — Discussion-review gaps in batches + NOTE-finding handling
slug: discussion-review-gap-batching
status: discussing
parent: main
```

## Problem

Two related defects in `plugins/mill/skills/mill-start/SKILL.md` Phase: Discussion Review.

**(1) Gaps are presented one at a time.** Today step 5 reads:

> On `GAPS_FOUND`: read the review file, **present each gap to the user one at a time, and wait for their response before updating `discussion.md`**.

Task 39 (`mill-start question-format UX`) capped interview question batches at 5 and required every operator prompt to be a numbered-options list with the recommended option as #1. Phase: Discussion Review was not updated and is now inconsistent with Phase: Discuss — gap-resolution prompts are free-text, one-at-a-time, and burn round-trips that question-batching was designed to eliminate.

**(2) APPROVE with non-empty NOTE findings is undefined behaviour.** GitHub issue #222 (closed, consolidated into this task) reports that on a discussion review returning `{"verdict": "APPROVE", "blocking_count": 0}` with three `[NOTE]` findings, the SKILL has no rule:

> 4. On `APPROVE`: break the loop and proceed to Handoff.

This collides with `mill-receiving-review`'s "Default: fix everything" rule. The orchestrator made an ad-hoc judgment call to fix the NOTEs and proceed without re-running the review, but no SKILL clause covers the case. `mill-plan/SKILL.md` step 4b handles the analogous case (`REQUEST_CHANGES AND blocking_count == 0`) explicitly with a NIT-fix-pass that breaks the loop. mill-start needs the parallel rule for `APPROVE AND note_count > 0`.

**Why now.** Task 39 (`mill-start question-format UX`) shipped 2026-05-09 and established the question-batching contract; mill-start-auto (also 2026-05-09) exposed the NOTE-on-APPROVE behaviour gap during a real auto-run. Both defects are in production today.

## Scope

**In:**

- Edit `plugins/mill/skills/mill-start/SKILL.md` Phase: Discussion Review to:
  - Replace current step 4 (`On APPROVE: break the loop and proceed to Handoff.`) with steps 4a + 4b mirroring mill-plan's 4a/4b/4c.
  - Replace current step 5 (one-gap-at-a-time) with a gap-batching protocol: present up to 5 gaps per batch as numbered questions with numbered-option resolutions (recommended option as #1); answer all 5 before moving to the next batch; continue batches until all gaps in the round are answered; then commit+push the updated `discussion.md` and run round N+1.
  - Add the same NOTE-handling rule under the existing Auto-mode subsection (auto-fix all NOTEs, write fixer report, commit+push, break loop).
- Add the fixer-report template requirement (sections `## Fixed` and `## Pushed Back`, mirroring mill-plan 4c).

**Out:**

- No changes to `_review_discussion.py`, `_review_common.py`, `_reviewer_single.py`, `_reviewers.py`, or the JSON envelope. The envelope keeps `{type, round, verdict, blocking_count, reviews}` — NOTE detection happens in mill-start by re-reading the review file. Rationale: mill-start already reads the file on GAPS_FOUND; reading it on APPROVE too is uniform and avoids a Python diff with its own test surface.
- No changes to `millpy-review-discussion.py` argument surface.
- No changes to `mill-plan/SKILL.md` or `mill-receiving-review/SKILL.md`.
- No changes to other skills (mill-go, mill-merge, etc.).
- No changes to the review prompt templates or the review-output schema (`plugins/mill/templates/review-output.schema.md`).
- No changes to the wiki `config.yaml` schema or `_config.py` — the `roles.discussion-review` config key surface stays as-is.
- No work on the unrelated `roles.discussion-review` vs legacy `review.discussion` config-schema migration. The wiki `config.yaml` on this developer's machine currently uses the legacy `review.discussion` top-level keys while `_review_discussion.py` reads the new `roles.discussion-review` keys, so the review CLI will fail at runtime in this worktree until the wiki is migrated. That is the user's separate concern; this task is SKILL.md-only.

## Decisions

### note-handling-on-approve-step-shape

- Decision: Replace current step 4 with `4a` and `4b`. Add `4a. On APPROVE with no NOTE findings: break the loop and proceed to Handoff.` Add `4b. On APPROVE with one or more NOTE findings: apply fixes per the mill-receiving-review decision tree, write a fixer report at task/reviews/<YYYYMMDD-HHMMSS>-discussion-fix-r<N>.md with sections ## Fixed and ## Pushed Back, append discussion-fix-r{N} to the status timeline, single commit covering task/discussion.md + task/reviews/ + task/status.md, push, break loop → Handoff. Do NOT run round N+1.` Renumber the existing `5. On GAPS_FOUND:` step to remain step 5 (no renumber needed).
- Rationale: Direct mirror of `mill-plan/SKILL.md` 4a/4b/4c. Future readers comparing the two skills should see the same shape. Matches the verbatim suggested fix in issue #222.
- Rejected: Inlining NOTE handling into a single step 4 with conditional sub-bullets — buries the rule and breaks visual parallel with mill-plan. Adding a new step 6 after the loop — wrong location; the routing decision happens at the top of the loop iteration.

### gap-batching-numbered-options

- Decision: Each gap is presented as a numbered question with a numbered-options resolution list. The recommended resolution is option 1 (per `mill:conversation`'s "the recommended option, if any, MUST be option 1"). The SKILL must coerce every gap into options form — free-text gap prompts are forbidden, mirroring the auto-mode rule that already exists for Phase: Discuss interview questions.
- Rationale: `mill:conversation` SKILL.md establishes numbered-options as the global operator-prompt format. Phase: Discussion Review is the only remaining operator-prompt site in mill-start that did not adopt it. Forcing options also disciplines the SKILL to think through resolutions before asking instead of dumping the gap on the user.
- Rejected: Free-text waits — inconsistent with Phase: Discuss post-task-39. Numbered options only when 2+ distinct resolutions exist — wishy-washy rule, easier to enforce "always options".

### batches-within-a-round

- Decision: Within a single review round, present gaps in sequential batches of ≤5 until all gaps are answered. Update an in-memory copy of `discussion.md` with each batch's answers before presenting the next batch. After the final batch is answered, write `discussion.md`, commit, push, and run round N+1.
- Rationale: Re-running the review LLM after every 5-gap batch costs reviewer tokens on a discussion that has barely changed. The wiki task entry's phrase "remaining gaps roll over" reads naturally as "remaining gaps within the round roll to the next batch", not "to the next round".
- Rejected: One batch per round — wastes reviewer tokens. Single batch of max 5 and drop the rest — silently loses gaps; user has no signal that more existed.

### note-detection-source

- Decision: mill-start detects NOTE findings by reading the review file after each round and parsing severity-prefix markers (`[NOTE]`, `[GAP]`). The JSON envelope's `blocking_count` is the routing key for GAP-vs-no-GAP; once GAPs are absent, mill-start reads the file to determine `note_count`. No new envelope field.
- Rationale: mill-start already reads the file on GAPS_FOUND to enumerate gaps; reading it on APPROVE too is one extra `Path.read_text` call. Adding `note_count` to the JSON envelope would touch `_review_discussion.py`, `_review_common.py`, and a unit test for the envelope shape — disproportionate to the savings. Single code path: "read file post-review, route on contents".
- Rejected: Add `note_count` to JSON envelope — three-file diff with test surface, micro-optimisation only. Both envelope-and-file — two sources of truth, redundant.

### note-fixes-applied-by-skill

- Decision: NOTE fixes are applied by the SKILL (mill-start) in both modes — interactive and `--auto`. The SKILL processes each NOTE through the `mill-receiving-review` decision tree (VERIFY → HARM CHECK → FIX or PUSH BACK) using its own judgment and the context already in conversation, and edits `task/discussion.md` directly. The fixer report is the audit trail; the user reviews it post-hoc, not during.
- Rationale: Mirrors mill-plan 4b ("Apply NIT fixes per the `mill-receiving-review` Decision Tree (no different from a regular fix-pass)"). NOTEs are non-blocking informational findings; user-in-the-loop for every NOTE would burn operator attention with no decision value, since the SKILL has the context to apply the obvious fix. The receiving-review escape hatch (PUSH BACK with cited evidence) is still available if a NOTE is genuinely wrong.
- Rejected: User-driven in interactive (present NOTEs as batched questions) — asymmetric with mill-plan, adds operator interaction for trivial fixes. Auto-only in `--auto`, user-driven in interactive — same problem, two code paths.

### gap-batching-not-applied-in-auto-mode

- Decision: Gap-batching is an interactive-mode feature only. Under `--auto`, the existing auto-resolve-all-gaps behaviour is preserved: the SKILL auto-picks option 1 (best-judgment resolution) for every gap in the round in a single pass, appends each to the Q&A log, commits+pushes, and re-runs review. No 5-cap chunking of auto-picks.
- Rationale: Batching is a user-interaction feature — it exists to bound how many questions the operator answers in one prompt. With no operator, there is nothing to chunk. Auto mode's Q&A-log lines are already short; rendering them in groups of 5 adds ceremony without value.
- Rejected: Apply 5-batch chunking to auto-picks for visual symmetry — pointless. Q&A-log in 5-row chunks — formatting concern, not a behaviour.

### fixer-report-format

- Decision: `task/reviews/<YYYYMMDD-HHMMSS>-discussion-fix-r<N>.md` has two sections — `## Fixed` (one line per fixed NOTE: reference to review file + quoted finding title) and `## Pushed Back` (one line per rejected NOTE: reference + reason citing code, doc, or scope, per the mill-receiving-review decision tree). The filename pattern matches mill-plan 4c (`<YYYYMMDD-HHMMSS>-plan-fix-r<N>.md`) with `plan` swapped to `discussion`.
- Rationale: Direct parallel with mill-plan 4c keeps the format predictable across skills. The two-section shape gives reviewers (human or LLM) an immediate read on what the fix-pass accepted vs declined.
- Rejected: Single list of fixed NOTEs — loses the PUSH BACK audit trail. Free-form summary — opaque, hard to mechanically check.

### fix-then-report-then-commit-order

- Decision: Order of operations in step 4b: (1) read review file; (2) apply each NOTE fix to `task/discussion.md` per the decision tree; (3) write the fixer report; (4) `_status.append_phase(status_path, f"discussion-fix-r{N}", iso_ts)`; (5) single git commit covering `task/discussion.md` + `task/reviews/` + `task/status.md`; (6) push; (7) break loop → Handoff. The round counter is NOT incremented.
- Rationale: Single commit keeps history clean and matches mill-plan 4c's pattern verbatim. The round counter is not incremented because step 4b is the terminal action for this round — no round N+1 runs.
- Rejected: Per-NOTE commits — pollutes history. Fixer report written before fixes applied — wrong order, the report references what was fixed. Increment round before commit — implies a round N+1 will run, which it does not.

### auto-mode-note-handling

- Decision: Add NOTE-handling rules to the existing Auto-mode subsection under "**Phase: Discussion Review — `--auto` changes:**". On `APPROVE` with one or more NOTE findings, the assistant auto-resolves each NOTE by editing `task/discussion.md` (best judgment), writes the same fixer report, appends `discussion-fix-r{N}` to the status timeline, commits+pushes, and breaks the loop. Identical action to interactive-mode 4b; the only difference is that no Q&A-log entry is written for NOTEs (NOTEs are reviewer findings, not operator-question answers — the fixer report is their audit trail). Round count for unresolved-gaps blocking remains unchanged.
- Rationale: Auto mode's existing rule "Every gap returned by the reviewer is treated as FIX regardless..." extends naturally to NOTEs: every NOTE is FIX. Symmetry with interactive 4b keeps mental model consistent.
- Rejected: Skip NOTEs entirely in auto mode (proceed to Handoff without fix) — keeps the bug from #222 alive under `--auto`. Treat NOTEs as gaps and put them in the Q&A log — conflates the two finding types and pollutes Q&A log with reviewer text instead of operator answers.

## Technical context

### Files to edit

- `plugins/mill/skills/mill-start/SKILL.md` — the only production file changed. Both the main `Phase: Discussion Review` subsection (lines ~92–116) and the `Auto mode` subsection's `Phase: Discussion Review — --auto changes:` bullets (lines ~29–36) need updates.

### Existing structures to mirror

- `plugins/mill/skills/mill-plan/SKILL.md` step 4a (APPROVE → break loop), 4b (REQUEST_CHANGES + 0-blocking NIT-only fix-pass), 4c (REQUEST_CHANGES + blocking BLOCKING fix-pass). Use the same prose shape. The fixer-report path pattern, status-timeline phase-name pattern, and commit-message verb (`mill-start: discussion-fix round {N} for {slug}`) mirror mill-plan's analogous strings with `plan` → `discussion`, `plan-fix` → `discussion-fix`, `mill-plan` → `mill-start`.

### Existing structures referenced (do NOT edit)

- `plugins/mill/skills/mill-receiving-review/SKILL.md` — the VERIFY → HARM CHECK → FIX-or-PUSH-BACK decision tree. NOTE-fix application invokes it; the SKILL itself does not change.
- `plugins/mill/skills/conversation/SKILL.md` lines around "Always use numbered text lists" — gap-batching numbered-options format inherits this rule.
- `plugins/mill/scripts/_review_discussion.py` — the discussion review backend. Reads `cfg["roles"]["discussion-review"]["holistic"]["reviewer"]` and produces the JSON envelope `{"type": "discussion", "round": N, "verdict": "APPROVE"|"GAPS_FOUND", "blocking_count": N, "reviews": [{scope, verdict, file, session_id}]}`. Unchanged.
- `plugins/mill/scripts/millpy-review-discussion.py` — the CLI entry point. Unchanged.
- `plugins/mill/scripts/_status.py` — `append_phase`, `update_field`. mill-start already uses these; no change.

### Severity vocabulary (from CLAUDE.md)

- `discussion` review uses severities `GAP` / `NOTE` and verdicts `APPROVE` / `GAPS_FOUND`. `GAP` is blocking, `NOTE` is informational.
- `plan` / `code` reviews use severities `BLOCKING` / `NIT` and verdicts `APPROVE` / `REQUEST_CHANGES`. Different vocabulary; do NOT cross-pollinate.

### Status timeline phase names

- `discussion-fix-r{N}` is the new phase-name prefix for fixer rounds. Mirrors mill-plan's `plan-fix-r{N}`. `_status.append_phase` validates phase names against a regex but accepts arbitrary lowercase-with-hyphens-and-digits; no regex change needed (verify by reading `_status.py` before final SKILL.md wording).

### Fixer-report filename pattern

- Pattern: `task/reviews/<YYYYMMDD-HHMMSS>-discussion-fix-r<N>.md`. Timestamp from `_timestamp.now_utc_compact()` (lowercase, no separator between date and time per existing convention). Matches mill-plan 4c's pattern.

### Commit message conventions

- `mill-start: discussion-fix round {N} for {slug}` — interactive-mode 4b commit. Mirrors mill-plan 4c's `mill-plan: plan-fix round {N} for {slug}`.
- Auto-mode commits inherit the existing mill-start commit-message format: `mill-start: <action> for <slug>`. The 4b auto path uses the same `discussion-fix round {N}` form as interactive — no separate auto verb.
- The existing auto-mode unresolved-gaps blocked commit (`mill-start: blocked (auto: discussion review gaps unresolved) for <slug>`) is unchanged.

### Where the gap-batching prompt format is anchored

- The numbered-options rule for gap-resolution prompts is anchored on `mill:conversation` SKILL.md. The mill-start update does not restate the rule — it references conversation-SKILL with one line such as: "Format per `mill:conversation` rule 'the recommended option, if any, MUST be option 1'." This avoids drift between the global rule and a per-skill copy.

### Round counter and re-review trigger

- The round counter `N` is determined by `_review_common.discover_round(reviews_dir, "discussion", "holistic")`, which counts existing review files. mill-start increments implicitly by writing a new review file on each `millpy-review-discussion.py` invocation. The fixer-report file (`<TS>-discussion-fix-r<N>.md`) does NOT match the discover-round pattern (which looks for `<TS>-discussion-r<N>.md`), so writing a fixer report does not advance the round counter — a separate concern that the existing mill-plan implementation has already validated.

### What "single commit" means in 4b

- A single git commit covering exactly three pathspecs: `task/discussion.md` (NOTE fixes applied), `task/reviews/` (new fixer-report file), `task/status.md` (`discussion-fix-r{N}` phase appended). The push is a separate `git push` command after the commit. Order: `git add … && git commit -m "…" && git push`.

## Constraints

No `CONSTRAINTS.md` was present at the worktree root at exploration time (verified by `_constraints.read_if_exists` callers; the file is not in `git ls-files`). Constraints from CLAUDE.md that apply:

- **Plugin scripts reference `${CLAUDE_PLUGIN_ROOT}`, never the source repo.** Not load-bearing for this task — the only file edited is a SKILL.md which renders as plain text; no path tokens.
- **Generated markdown uses fenced ```yaml for metadata, not `---` frontmatter.** Applies to any examples added in SKILL.md. SKILL.md itself uses `---` frontmatter (it is a skill, not generated markdown), but example blocks inside it must use fenced yaml.
- **Junctions and hardlinks are NEVER used by scripts or skills.** N/A — this task touches a single markdown file.

## Testing

This task is SKILL.md-only — no Python files change. The codebase's test conventions therefore apply selectively.

### Static review (primary verification)

- Read the rendered `plugins/mill/skills/mill-start/SKILL.md` end-to-end. Check that:
  - Phase: Discussion Review's main subsection has step `4a`, `4b`, `5` (renumbered from the previous `4`, `5`).
  - The Auto-mode subsection includes the NOTE-handling bullet under "**Phase: Discussion Review — `--auto` changes:**".
  - Step 4b and the auto-mode NOTE bullet both reference `mill-receiving-review` and the `discussion-fix-r{N}` status phase.
  - The gap-batching wording in step 5 specifies ≤5 gaps per batch, numbered-options resolution format with option 1 as recommended, sequential batches within a round, and a single commit+push after the round's gaps are exhausted.
  - The fixer-report filename pattern (`<YYYYMMDD-HHMMSS>-discussion-fix-r<N>.md`) and its two-section format (`## Fixed`, `## Pushed Back`) are explicitly stated.

### Unit tests

- None required. No public Python API surface changes. `_review_discussion.run`, `_review_common.parse_blocking_count`, `_reviewer_single.run`, `_reviewers.load`/`resolve`, `_status.append_phase`/`update_field`, `_timestamp.now_utc_compact`/`now_utc_iso` all keep their current signatures and behaviour.
- If the reviewer of this plan asks for one defensive test: a `plugins/mill/unit_tests/test-skill-mill-start-shape.py` could parse `SKILL.md` and assert the presence of `### Phase: Discussion Review`, `4a.`, `4b.`, `5.`, and the substrings `"discussion-fix-r"` and `"## Fixed"`. This is a brittle markdown-shape test and should not be added unless explicitly requested — it codifies prose that legitimately drifts.

### Integration tests

- None required. There is no live discussion-review integration test today; mill-start integration tests stub the review CLI. No new integration coverage is in-scope.

### Manual end-to-end (operator-driven, post-merge)

- Spawn a throwaway worktree with `mill-spawn`. Run `mill-start` (interactive) on a discussion.md guaranteed to produce a few `[NOTE]` findings (e.g. omit the "Constraints" heading). Verify:
  - Review returns `APPROVE` with NOTEs; step 4b runs; fixer report appears under `task/reviews/`; `task/status.md` shows `discussion-fix-r1`; the loop breaks (round 2 does NOT run); single commit covers all three paths.
- Same with `--auto`: verify Q&A log has no NOTE rows, fixer report is written, status timeline shows the same `discussion-fix-r{N}` entry, commit+push fired.
- Same with a discussion.md guaranteed to produce 7+ gaps to exercise sequential batches of 5+2. Verify the second batch is presented immediately after the first batch's answers are accepted, and that the round's commit+push happens once at the end of all batches (not after each batch).

## Q&A log

- **Q:** Where does the NOTE-handling rule live in the Phase: Discussion Review sequence? **A:** [auto-pick] Add 4a (APPROVE no NOTEs → Handoff), 4b (APPROVE with NOTEs → fix-pass → Handoff), 5 (GAPS_FOUND → batching). **Why:** Direct mirror of mill-plan's 4a/4b/4c makes the parallel obvious to any future reader, matches the suggested fix in #222 verbatim.
- **Q:** Should gap-question coercion (numbered-options format) apply in both modes (interactive + auto) or only auto? **A:** [auto-pick] Both modes — interactive also uses numbered-options for gaps. **Why:** mill:conversation post-task-39 is global ("Always use numbered text lists"), no scope-restriction; forcing options also disciplines the SKILL to think through resolutions before asking.
- **Q:** Within a single review round, how are gap batches sequenced when round returns >5 gaps? **A:** [auto-pick] Sequential batches within one round — answer all gaps in batches of ≤5 before running round N+1. **Why:** Re-reviewing after every 5-gap batch wastes reviewer tokens on a discussion that has barely changed; wiki task entry's "remaining gaps roll over" reads as "to the next batch", not "to the next round".
- **Q:** How does mill-start detect NOTE findings — JSON envelope or review file? **A:** [auto-pick] Read the review file post-review; parse `[NOTE]`-prefixed findings. **Why:** mill-start already reads the file on GAPS_FOUND; reading it on APPROVE too is uniform and avoids a Python diff with its own test surface.
- **Q:** Should NOTE fixes be user-driven (interactive) or auto-applied by the SKILL (both modes)? **A:** [auto-pick] Auto-applied in both modes — NOTE = non-blocking, SKILL applies via mill-receiving-review decision tree, fixer report is the audit trail. **Why:** Mirrors mill-plan 4b "no different from a regular fix-pass"; user-in-the-loop for every NOTE burns operator attention with no decision value.
- **Q:** Auto-mode handling when gaps remain unresolved after `max_review_rounds` — change or keep current behaviour? **A:** [auto-pick] Keep current (blocked phase, `_status.update_field(..., "blocked_reason", ...)`, commit+push, halt). **Why:** Unrelated to the issue; YAGNI.
- **Q:** Fixer-report sections for `discussion-fix-r{N}.md`. **A:** [auto-pick] Two sections: `## Fixed` and `## Pushed Back`, each with one-line references to the review file + quoted finding title + reason for pushback. **Why:** Direct parallel with mill-plan 4c keeps the format predictable across skills.
- **Q:** Should the gap-batching change apply to `--auto` mode too, or only interactive? **A:** [auto-pick] Interactive only — `--auto` already auto-resolves all gaps in one pass (no user interaction = nothing to batch). **Why:** Batching is a user-interaction feature; auto mode has no operator to wait on, chunking auto-picks would add ceremony without value.
- **Q:** NOTE-fix order — apply fixes before commit, or write fixer report first? **A:** [auto-pick] Apply fixes to `task/discussion.md` first, then write fixer report, then `_status.append_phase`, then single commit covering all three. **Why:** Single commit keeps history clean; the order matches mill-plan 4c; avoids "what if write fails between commits" race entirely.
