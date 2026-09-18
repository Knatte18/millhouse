# Batch: review-loop-fixes

```yaml
task: "mill-go-base: orchestration robustness gaps"
batch: review-loop-fixes
number: 5
cards: 2
verify: null
depends-on: [1, 4]
```

## Batch Scope

Fixes #1005 (holistic crash-recovery's freshness check uses a positionally-indexed phase occurrence that breaks on a manual resume) and #997 (the holistic and per-batch APPROVE-branch NIT-fix dispatch instructions omit an explicit capture+finalize reminder, which already caused one live manual recovery — see `_mill/discussion.md`'s `1005-latest-occurrence` and `997-inline-capture-finalize-reminder` Decisions). Depends on batch 1 for `_status.phase_entry_timestamp`'s new `latest` parameter (real dependency). Additionally depends on batch 4 (`blocked-batch-resume`) — not a real feature dependency, but required to serialize this batch against the other `SKILL.md`-editing batches (4, 6, 3), per the validator's `parallel-modifies-overlap` check. Two cards, split by file-overlap: card 7 touches only `holistic-review.md`; card 8 touches both `holistic-review.md` and `SKILL.md` (the two files #997's fix mirrors the identical reminder across). Estimated context: card 7 ≈ 24,903/4 ≈ 6,226 tokens; card 8 ≈ (24,903+106,797)/4 ≈ 32,925 tokens; batch total ≈ 39,151, well under the cap.

## Cards

### Card 7: holistic crash-recovery uses latest-occurrence lookup

- **Context:**
  - `plugins/mill/scripts/_status.py`
- **Edits:**
  - `plugins/mill/skills/mill-go-base/holistic-review.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `holistic-review.md`'s step 1 ("Crash-recovery"), branch (a) ("Review file present"), the freshness-validation sentence currently reads: "If found, validate its freshness: fetch `ref_ts = _status.phase_entry_timestamp(status_path, "holistic-reviewing", occurrence=H)` (the Hth occurrence corresponds to round H);". Change the call to `_status.phase_entry_timestamp(status_path, "holistic-reviewing", latest=True)` and rewrite the parenthetical to explain why: `"holistic-reviewing"` is the one phase string in this codebase that is reused verbatim across every round (unlike the per-batch mirror in `SKILL.md`'s Execute step 3, which uses `f"reviewing-{batch_name}-r{N}"` — already unique per round by construction, so it correctly keeps `occurrence=1` unchanged), so a positional `occurrence=H` silently breaks when an operator manually resumes a `blocked` task without incrementing the round counter (re-appending the same phase entry shifts every later occurrence index). `latest=True` always resolves to the most recently appended matching entry regardless of how many times the phase string has been appended, which is the correct semantics here. Do not touch the per-batch call site in `SKILL.md` — it is already correct and out of scope for this fix.
- **Commit:** `mill-go-base: holistic crash-recovery uses latest-occurrence phase_entry_timestamp lookup (#1005)`

### Card 8: inline capture+finalize reminder in both NIT-fix dispatch sites

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-go-base/holistic-review.md`
  - `plugins/mill/skills/mill-go-base/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Two mirrored edits, one per file — the holistic and per-batch NIT-fix dispatch instructions currently share the identical gap and must be fixed identically.

  **Edit A — `holistic-review.md`.** Locate step 4's NIT-fix dispatch: the sentence "Follow the Agent-mode dispatch pattern (see `mill-go-base/SKILL.md`'s "## Agent-mode dispatch") with `<cli> = millpy-fix.py` and `<args> = --scope holistic --review-file <review-file-abs-path> --round {H} --nits-only --prior-blocking <briefs_dir>/prior-blocking-holistic-r{H}.txt`.", immediately followed by "After the NIT-fix completes successfully (or is skipped because `nit_count = 0`): compute `converged` per the Convergence gate above." Insert, between those two sentences, an explicit inline restatement: "After the dispatch's `<task-notification>` is accepted: capture the notification to `<brief_path>.out.md` (step 4 of the Agent-mode dispatch pattern), then run `--stage finalize` (step 5 of that same pattern) — this is what appends the `nits-fixed-holistic` marker Handoff's nit-enforcement gate requires. Only after finalize completes does the next sentence's `converged` computation happen; do not skip straight from the dispatch notification to computing `converged`." Do not alter the two sentences the new text is inserted between.

  **Edit B — `SKILL.md`.** Locate the identical shape in the per-batch APPROVE branch of the Code Review loop (Execute step 4): the NIT-fix dispatch sentence "Follow the Agent-mode dispatch pattern (see "## Agent-mode dispatch" above) with `<cli> = millpy-fix.py` and `<args> = --scope batch --batch-name <batch_name> --review-file <review-file-abs-path> --round <N> --nits-only --prior-blocking <briefs_dir>/prior-blocking-<batch_name>-r<N>.txt`.", immediately followed (after the "The fixer loads `mill-receiving-review`..." sentence) by "After the NIT-fix completes successfully (or is skipped because `nit_count = 0`): compute `converged` per the Convergence gate above." Insert the identical inline restatement Edit A adds (adjusted only for the per-batch marker name: `nits-fixed-<batch_name>` instead of `nits-fixed-holistic`), in the same position relative to those two sentences.
- **Commit:** `mill-go-base: inline capture+finalize reminder in holistic and per-batch NIT-fix dispatch (#997)`

## Batch Tests

`verify: null` at the batch level. Both cards edit only LLM-read instruction prose with no code-identifier-like surface distinctive enough to assert deterministically beyond what card 7's own change (`latest=True`, a real Python keyword argument) already is — but since card 7 and card 8 land in the same batch and card 8's insertion is genuinely prose (a restated procedural reminder, not a new flag/function name), a single reliable marker for both cards together is not available. This batch is verified by direct read-through during code review instead (confirming both mirrored insertions read unambiguously in isolation, matching the bar #997's own incident report sets), consistent with `mill-plan/SKILL.md`'s "Verify command scope" note that `verify: null` requires stating why — here, no deterministic code-identifier marker exists for the prose inserted, unlike batches 3, 4, 6, and 7 in this same plan, each of which mandates at least one literal flag/function/heading name in its own Requirements.
