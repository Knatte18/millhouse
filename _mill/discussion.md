# Discussion: mill-start: discussion-review timeline gaps and stray orch-review.md scratch file

```yaml
task: 'mill-start: discussion-review timeline gaps and stray orch-review.md scratch file'
slug: mill-start-discussion-review-timeline-and-orch-review-hygiene
status: discussing
parent: main
```

## Problem

Two independent bugs in mill-start's discussion-review machinery, folded into one task because both are small, low-risk hygiene fixes to the same phase of the same skill.

**Bug 1 — missing timeline row (GH #925).** `mill-start`'s interactive Phase: Discussion Review step 5 (the "gap-fix" round: a REQUEST_CHANGES round where the operator resolves BLOCKING findings, batch by batch, with any co-occurring NITs folded in) writes a commit (`mill-start: discussion-gap-fix round {N} for {slug}`) but never calls `_status.append_phase`. The round is invisible in `status.md`'s Timeline even though it ran, produced a review file, and produced a commit — a reader counting rounds from the timeline undercounts by one. Worse: `mill-go-base/SKILL.md`'s "Entry-gate wait for upstream mill-plan" section, and its regression-locking unit test `test-phase-wait.py`, already hard-code and test for a `^discussion-gap-fix-r\d+$` phase pattern as one of the "mid-round, keep polling" states. That consumer already expects this phase string to exist in `status.md` — it just never gets emitted, so a genuinely-in-progress gap-fix round is never recognized as such by that entry-gate wait.

**Bug 2 — stray untracked scratch file (GH #921, #911, duplicates of the same root cause).** `mill-start --orch`'s round-1 substitution (companion skills `orch-review` — orchestrator writes it — and `orch-wait` — the worker consumes it) hands off a review via a file written directly at `<worktree>/_mill/orch-review.md`. That path is inside `_mill/`, which `_cleanliness.compute_scope_violations()` deliberately excludes from scope-violation checks (task-state ownership boundary — mill-go doesn't own `_mill/`), so nothing in the existing cleanup gates ever flags or removes a stray copy. `orch-wait` Step 4 already deletes the file after a successful `finalize()` call (added in commit `6d241096`, after both GH issues were filed) — but that only covers the happy path; the underlying design still writes task-state-shaped output into `_mill/` for what is genuinely ephemeral, non-committed, single-use handoff data, contrary to `mill:conversation`'s own scratch-file convention and the issues' own "Expected" resolution.

**Why now:** both are cheap, well-understood fixes surfaced by triaged GH issues already consolidated onto this wiki task; no reason to defer.

## Scope

**In:**
- `plugins/mill/skills/mill-start/SKILL.md` — Phase: Discussion Review, step 5 (the interactive gap-fix round): add the missing `_status.append_phase` call and add `<status_path>` to the final commit's pathspec.
- `plugins/mill/skills/orch-review/SKILL.md` — change the write location of the hand-off file from `<worktree>/_mill/orch-review.md` to `<worktree>/.scratch/orch-review.md` (Fork-side Step 1's stale-file check, Step 3's write target, Step 4's report message).
- `plugins/mill/skills/orch-wait/SKILL.md` — change the read/poll/delete location to match (Step 1 announce message, Step 2 poll path, Step 3 read path, Step 4 delete path).
- Any doc text elsewhere in those three files that names the `_mill/orch-review.md` path.

**Out:**
- No change to `_status.append_phase`, `_review_discussion.finalize`, or any other `_status.py` / `_review_discussion.py` behavior — both fixes are call-site fixes in the SKILL.md prompt documents, not backend code changes.
- No change to step 4b (the APPROVE-with-NITs path) — it already calls `_status.append_phase` correctly; not touched.
- No change to `--auto`/`--orch` mode's own REQUEST_CHANGES handling (the "Phase: Discussion Review — `--auto` changes" section) — that path is structurally different (no gap-fix commit message, no operator, different phase-append already present via 4b's machinery) and step 5 is explicitly skipped entirely under `--auto`/`--orch` (guarded at step 5's own top line). This task only touches the plain-interactive step 5 path.
- No migration/cleanup sweep for pre-existing stray `_mill/orch-review.md` files already sitting on other task branches from before this fix — historical debris from a fixed mechanism, low blast radius, not worth adding cleanup-gate complexity for.
- No change to where `orch-review`/`orch-wait` do their `Monitor` waits, forking discipline, or review-content rubric — only the file's location changes.

## Decisions

### gap-fix-timeline-label

- Decision: The step 5 gap-fix round appends `_status.append_phase(status_path, f"discussion-gap-fix-r{N}", _timestamp.now_utc_iso())` immediately before the round's existing commit, using the label `discussion-gap-fix-r{N}` (not `discussion-fix-r{N}`).
- Rationale: `plugins/mill/skills/mill-go-base/SKILL.md`'s "Entry-gate wait for upstream mill-plan" section and its regression test `plugins/mill/unit_tests/test-phase-wait.py` (lines ~184-206) already reference and test the exact pattern `^discussion-gap-fix-r\d+$` as a distinct, already-anticipated phase string alongside `^discussion-fix-r\d+$`. Emitting anything else would leave that existing consumer's pattern permanently dead code.
- Rejected: Reusing `discussion-fix-r{N}` (4b's label) — would conflate two structurally different round types (BLOCKING-gap resolution vs. APPROVE-with-NIT-only fixups) under one phase name, and would not satisfy the already-existing `discussion-gap-fix-r\d+$` matcher.

### gap-fix-commit-pathspec

- Decision: Add `<status_path>` to step 5's final commit pathspec, producing `git -C <worktree> add <discussion_path> <reviews_dir>/ _mill/briefs/ <status_path> && git commit -m "mill-start: discussion-gap-fix round {N} for {slug}"`.
- Rationale: The phase-append writes to `status.md`; the append must land in the same commit as the discussion/review changes it's paired with, matching 4b's existing four-pathspec pattern (`<discussion_path>`, `<reviews_dir>/`, `<status_path>`, `_mill/briefs/`).
- Rejected: A separate follow-up commit — adds commit-count noise for no benefit; 4b already establishes the single-commit precedent.

### orch-review-scratch-location

- Decision: `orch-review`/`orch-wait`'s hand-off file moves from `<worktree>/_mill/orch-review.md` to `<worktree>/.scratch/orch-review.md`.
- Rationale: `.scratch/` is gitignored (`**/.scratch/` per the hub `.gitignore`), so `git status --porcelain` never reports it as untracked at all — this removes the file from `_cleanliness.compute_scope_violations()`'s consideration by construction, rather than relying on every code path that touches the file to remember to delete it. It also matches `mill:conversation`'s existing "Plugin-managed scratch: All plugins share `.scratch/` for ephemeral files" convention, and is exactly what GH #911/#921 asked for.
- Rejected: Staying under `_mill/` with a hardened try/finally delete plus a `mill-cleanup` sweep for strays — treats the symptom (a file surviving crashes) rather than the cause (writing ephemeral single-use handoff data into the task-state directory in the first place); more moving parts for the same outcome.

### orch-wait-delete-still-happens

- Decision: `orch-wait` Step 4 keeps deleting the file after `finalize()` succeeds, now targeting `.scratch/orch-review.md` instead of `_mill/orch-review.md`.
- Rationale: Even though `.scratch/` files are already invisible to cleanliness gates, `orch-review`'s Fork-side Step 1 has its own "if `orch-review.md` already exists, halt and ask whether to overwrite" check — a leftover file from a prior round would falsely trip that check on the next round. Deleting after consumption keeps that check meaningful.
- Rejected: Dropping the delete step now that gitignore handles cleanliness-gate invisibility — would still break the stale-file guard in `orch-review`.

## Technical context

- `plugins/mill/skills/mill-start/SKILL.md` step 5 (~line 404 in the current worktree source) is the sole edit site for Bug 1. Compare against step 4b (~lines 371-386) for the exact `_status.append_phase` / commit-pathspec pattern to mirror.
- `_status.append_phase(status_path: Path, phase: str, timestamp: str) -> None` — `plugins/mill/scripts/_status.py:429`. Use `_timestamp.now_utc_iso()` for the timestamp, matching every other call site in the same phase.
- `_cleanliness.compute_scope_violations()` — `plugins/mill/scripts/_cleanliness.py:57-110` — confirms the `_mill/`-prefix exclusion (line 105: `if not remainder.startswith("_mill/")`) that lets a stray `_mill/orch-review.md` slip through today. No change needed here; cited only as root-cause evidence.
- `plugins/mill/skills/orch-review/SKILL.md` — write side. Touch points: Fork-side Step 1 (`if <worktree>/_mill/orch-review.md already exists, halt`), Step 3 (`Write <worktree>/_mill/orch-review.md`), Step 4's report message text (`Wrote _mill/orch-review.md for <slug>`).
- `plugins/mill/skills/orch-wait/SKILL.md` — read side. Touch points: Step 1's announce string (`write _mill/orch-review.md next to discussion.md`), Step 2's poll target, Step 3's `open(worktree_root / '_mill/orch-review.md', ...)` read call, Step 4's delete target and rationale text.
- Existing regression-lock tests that constrain the shape of the fix (both are text-based checks against `SKILL.md` content, not runtime execution):
  - `plugins/mill/unit_tests/test-phase-wait.py` (~lines 184-206) — already asserts `matches_wait_trigger` accepts `discussion-gap-fix-r{N}` against the Entry-gate wait's regex set; this task's fix makes that pattern reachable in practice for the first time.
  - `plugins/mill/unit_tests/test-brief-commit.py` — asserts the `mill-start: discussion-gap-fix` commit message has `_mill/briefs/` within a 300-char window; the existing step 5 pathspec already satisfies this (`_mill/briefs/` is already in the commit), and adding `<status_path>` to the same pathspec must not push `_mill/briefs/` outside that window.
- `mill-go-base/SKILL.md` "Entry-gate wait for upstream mill-plan" (~lines 160-175) is the actual downstream consumer of the `discussion-gap-fix-r{N}` phase string — read for context, not modified.

## Constraints

- No `CONSTRAINTS.md` present at the hub root.
- Both fixes are SKILL.md prompt-document edits only — no Python backend changes, so the repo's `verify-not-isolated` `PYTHONPATH=` prefix rule for Python test commands still applies only to the unit tests that check these files' *text*, not to any new runtime code path.
- Must not change step 5's `--auto`/`--orch` inapplicability — step 5 stays interactive-only; do not touch the guard at its top.
- Must not change `orch-review`/`orch-wait`'s Monitor-wait ownership rules, forking discipline, or the review-content rubric — path-only change.

## Testing

- `plugins/mill/unit_tests/test-phase-wait.py` and `plugins/mill/unit_tests/test-brief-commit.py` already encode the expected shape for Bug 1's fix — run both (`uv run --project plugins/mill python plugins/mill/unit_tests/test-phase-wait.py` and the `test-brief-commit.py` equivalent, or via the suite's `run-all.py`) after editing `mill-start/SKILL.md` and confirm both still pass (they should now pass for the *intended* reason — the pattern they test is reachable — rather than passing vacuously).
- No existing unit test covers Bug 2's file path directly (grep confirmed no `orch-review`/`orch_review` hits under `_mill/` path assertions elsewhere). This is a text-only change to two SKILL.md files with no Python execution to test — mill-plan should judge whether a lightweight text-regression-lock test (mirroring `test-brief-commit.py`'s style: assert `.scratch/orch-review.md` appears in `orch-review/SKILL.md` and `orch-wait/SKILL.md`, assert `_mill/orch-review.md` no longer does) is worth adding, given the existing precedent of locking SKILL.md text shape via `test-brief-commit.py` and `test-phase-wait.py`.
- No TDD candidates in the traditional sense — these are prompt-document edits, not executable logic; "testing" here means grep-level regression locks per the existing test suite's own pattern for this exact class of change (SKILL.md text assertions), plus running the two named existing tests to confirm no regression.

## Q&A log

- **Q:** What phase label should the interactive step-5 gap-fix round append to `status.md`'s Timeline? **A:** [auto-pick] `discussion-gap-fix-r{N}` (distinct from 4b's `discussion-fix-r{N}`). **Why:** `test-phase-wait.py` and `mill-go-base/SKILL.md`'s Entry-gate wait already hard-code and test for exactly this pattern — it's the only label that closes the gap those existing consumers already anticipate.
- **Q:** Where does `<status_path>` get added to step 5's final commit? **A:** [auto-pick] Same commit as the existing three pathspecs, mirroring 4b's four-pathspec pattern. **Why:** avoids a second commit for no benefit; matches existing precedent exactly.
- **Q:** Where should the `orch-review.md` hand-off file live? **A:** [auto-pick] `.scratch/orch-review.md` instead of `_mill/orch-review.md`. **Why:** gitignored paths are invisible to `git status --porcelain`, so this removes the file from cleanliness-gate consideration at the root rather than depending on every consumer remembering to delete it; matches `mill:conversation`'s scratch convention and the filed issues' own suggested fix.
- **Q:** Keep `orch-wait`'s delete-after-consume step even though `.scratch/` is gitignored? **A:** [auto-pick] Yes, now targeting `.scratch/orch-review.md`. **Why:** prevents `orch-review`'s "already exists, halt and ask" guard from false-triggering on a stale copy across rounds.
- **Q:** Add a cleanup sweep for pre-existing stray `_mill/orch-review.md` files on other branches? **A:** [auto-pick] No, out of scope. **Why:** YAGNI — historical debris from a now-fixed mechanism, low blast radius, not worth extra cleanup-gate complexity.
