# Batch: blocked-batch-resume

```yaml
task: "mill-go-base: orchestration robustness gaps"
batch: blocked-batch-resume
number: 4
cards: 1
verify: PYTHONPATH= uv run --project plugins/mill python -c "import pathlib; s = pathlib.Path('plugins/mill/skills/mill-go-base/SKILL.md').read_text(encoding='utf-8'); r = pathlib.Path('plugins/mill/skills/mill-go-base/resume.md').read_text(encoding='utf-8'); assert 'resume_batch' in s, 'missing resume_batch marker in SKILL.md'; assert 'resuming a blocked batch after external fix' in s, 'missing new subsection heading in SKILL.md'; assert 'resume_batch' in r or 'resuming a blocked batch after external fix' in r, 'missing cross-reference in resume.md'; print('ok')"
depends-on: [1, 6]
```

## Batch Scope

Fixes #1013: documents (and helper-backs, via batch 1's `resume_batch`) the resume procedure for a batch that reached `state: blocked` and was fixed externally by the operator, and fixes the Entry phase gate's `blocked` row so its halt message surfaces the real reason for the common case (a batch-level block never populates the task-level top-yaml `blocked_reason:` field — see `_mill/discussion.md`'s `1013-blocked-resume` Decision for the full analysis). Depends on batch 1 for `_status.resume_batch` (real dependency). Additionally depends on batch 6 (`agent-dispatch-liveness`) — not a real feature dependency, but required to serialize this batch against the other `SKILL.md`-editing batches (6, 5, 3), per the validator's `parallel-modifies-overlap` check. Single card, two files (`SKILL.md`, `resume.md`); estimated context ≈ (106,797 + 4,447) / 4 ≈ 27,811 tokens.

## Cards

### Card 6: document and helper-back the blocked-batch resume path

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
  - `plugins/mill/skills/mill-go-base/resume.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Two edits to `SKILL.md`, plus one cross-reference edit to `resume.md`.

  **Edit A — Entry phase gate `blocked`-row halt message fallback.** Locate the Entry phase gate's phase-inspection block (the `status = _status.read_full(status_path)` / `phase = status["yaml"]["phase"]` / `blocked_reason = status["yaml"].get("blocked_reason")` code block, immediately followed by the phase-table). In the phase table's `blocked` row (action text: "surface `blocked_reason` from status.md and halt"), add an explicit fallback: when the top-level `blocked_reason` read above is empty/`None`, call `_status.read_batches(status_path)` and scan for the entry whose `state == "blocked"`; if found, surface THAT entry's own `blocked_reason` field (plus its batch `name`) in the halt message instead of an empty string. When a top-level `blocked_reason` IS present (the `_status.set_blocked`-based task-halt case — e.g. a discussion-review or plan-review halt, which always populates the top-level field), the halt message uses it exactly as today, unchanged — the fallback applies only when the top-level field is absent. State explicitly, next to this fallback, WHY it's needed: every batch-level blocking call site in this file's own `### Stuck escalation` and Handoff-gate sections (e.g. the cleanliness gate, the scope-violations gate, the "review rounds exhausted" path) calls `_status.set_batch_field(status_path, batch_name, "blocked_reason", ...)` and `_status.append_phase(status_path, "blocked", ...)` directly — it never calls `_status.set_blocked`, so the task-level top-yaml `blocked_reason:` field is never populated for these, the most common, block reasons.

  **Edit B — new "Resume after external fix" subsection.** Add a new subsection titled exactly `### Entry: resuming a blocked batch after external fix`, placed immediately after the phase table and Edit A's fallback text, and immediately before `### Mid-execution phase-gate widening`. Its content, as a numbered procedure:
  1. Call `_status.read_batches(status_path)` and locate the entry whose `state == "blocked"`. If none is found, this is a task-level (`_status.set_blocked`-based) halt, not a batch-level one — this procedure does not apply; the operator must resolve the underlying cause named in the halt message and there is no batch to resume via `resume_batch`.
  2. Decide `preserve_start_sha`: inspect the located batch's `commit_sha` field (and/or run `git -C <worktree> log --oneline <start_sha>..HEAD -- <files the batch's cards touch>` if `commit_sha` alone is ambiguous) to determine whether any of this batch's cards already committed. If yes (partial progress exists), `preserve_start_sha = True`; if no commits exist yet, `preserve_start_sha = False`.
  3. Call `_status.resume_batch(status_path, batch_name, timestamp=_timestamp.now_utc_iso(), preserve_start_sha=<decided above>)`.
  4. Commit on the task branch: `git -C <worktree> add <status_path> && git -C <worktree> commit -m "<VARIANT_LABEL>: resume {batch_name} after external fix"`. Push.
  5. Re-run `/mill-go`. The phase is now `implementing` with the resumed batch at `state: pending` and no other batch entry non-terminal, so the Entry phase gate's existing "Mid-execution phase-gate widening" → `## Resume` (`resume.md`) routing picks it up unchanged — no further edit needed to that routing logic.
  State explicitly in this new subsection that this is a deliberate, explicit operator action (re-running `/mill-go` after confirming the external fix landed), never an automatic on-restart resume — `resume_batch` is only ever invoked by this documented procedure, never called speculatively.

  **Edit C — `resume.md` cross-reference.** `resume.md` currently has no mention of a `blocked` batch state at all. Add one sentence near the top of the file (before its first numbered step) noting that a batch which reached `state: blocked` is NOT handled by this file's own resume routing — it is handled by the `### Entry: resuming a blocked batch after external fix` subsection in `mill-go-base/SKILL.md`'s Entry phase gate, which runs BEFORE this file is ever reached (this file's own step 1, "locate the entry whose state is non-terminal: running, reviewing, or fixing," never matches a `blocked` batch, by design — `blocked` is a terminal state until `resume_batch` moves it back to `pending`).
- **Commit:** `mill-go-base: document and helper-back blocked-batch resume after external fix (#1013)`

## Batch Tests

`verify:` (see frontmatter above) is a `python -c` assertion confirming the `resume_batch` reference and the new `### Entry: resuming a blocked batch after external fix` heading both landed in `SKILL.md`, and that `resume.md` gained its cross-reference — per this plan's "prose-only batches verify via exact-marker grep/python assertions" Shared Decision in `00-overview.md`.
