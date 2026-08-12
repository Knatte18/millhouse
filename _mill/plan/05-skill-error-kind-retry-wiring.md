# Batch: skill-error-kind-retry-wiring

```yaml
task: 'millpy-review-plan finalize: usage-error indistinguishability, flag issues, verdict rendering stale'
batch: skill-error-kind-retry-wiring
number: 5
cards: 4
verify: null
depends-on: [1, 3]
```

## Rename mechanic

N/A — no `Moves:` in this batch.

## Batch Scope

Update the ERROR-only-aggregate retry logic in all four consumer sites of the `error_kind` field
(`mill-start/SKILL.md` Step 3.5, `mill-plan/SKILL.md` Step 4.5, `mill-go-base/SKILL.md` Step 4.5,
and `mill-go-base/holistic-review.md` sub-step 3.5) so that any `reviews[]` entry carrying
`error_kind: "usage"` halts the round immediately — no retry, no round consumed — on its first
occurrence, with a message that names it as a usage error, distinct from the existing
`BLOCKED: <type> review ERROR-only round N` wording. Only when no entry in the envelope's
`reviews[]` is `error_kind: "usage"` does each site's existing trigger condition and two-pass
retry-then-halt behavior continue to apply, unchanged, to `"reviewer"`-kind or absent-`error_kind`
entries (the latter for back-compat with envelopes written before this field existed). This batch
does not unify the four sites' pre-existing ALL-vs-ANY trigger-condition asymmetry — `mill-start`,
`mill-go-base/SKILL.md`, and `mill-go-base/holistic-review.md` trigger on "every entry is ERROR"
while `mill-plan/SKILL.md` triggers on "at least one entry is ERROR" — that asymmetry is
independent of this fix and out of scope per the discussion's "Retry semantics keyed on
error_kind" Decision.

This batch depends on Batch 1 (the `error_kind` key must exist on every `print_error_envelope`
usage-error entry) and Batch 3 (the `error_kind` key must exist on every reviewer-parse-failure
entry) — both code paths this prose now reads from must already emit the field before these
SKILL.md sites can rely on it. It does not depend on Batch 2 (round threading is unrelated to
`error_kind`) or Batch 4 (the demotion note is unrelated to ERROR-round retry logic).

`verify: null` — every card in this batch edits prose-only SKILL.md/`.md` orchestration files with
no runnable surface; per the discussion's Testing section, these are verified by re-reading all
four files after editing to confirm identical `error_kind`-based halt behavior and consistent
halt-message wording, not by a unit test.

## Cards

### Card 16: `mill-start/SKILL.md` Step 3.5 — usage-error immediate halt

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-start/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - Locate `### Phase: Discussion Review`'s `**Step 3.5: ERROR-only-aggregate retry (no round consumed)**` heading. Its body's first paragraph currently begins "When the JSON envelope from step 2 has top-level `verdict: "ERROR"` (or, equivalently, every entry in `reviews[]` has `verdict: "ERROR"`), skip steps 4a / 4b / 5 entirely and immediately re-run:" — this is the existing ALL-entries trigger condition.
  - Immediately before that paragraph, insert a new paragraph titled "**Usage-error immediate halt (checked first, every round).**" that: inspects the JSON envelope's `reviews[]` array (when present) for any entry with `error_kind: "usage"`; if found, halts immediately on this occurrence (no retry, no round consumed), regardless of what any other entry in the same `reviews[]` list contains; reuses the exact halt mechanics this same step's existing second-pass halt already uses two paragraphs below (the plain-mode `BLOCKED: discussion review ERROR-only round {N}` halt, and separately the `--auto`-mode `_status.set_blocked(status_path, f"auto: discussion review ERROR-only round {N}", ...)` + commit/push sequence) but with the message text replaced: plain mode halts with `BLOCKED: discussion review usage error: <message>` (where `<message>` is the offending entry's `error` field); `--auto` mode calls `_status.set_blocked(status_path, f"auto: discussion review usage error: <message>", timestamp=_timestamp.now_utc_iso())` then the same `git -C <worktree> add`/`commit -m "mill-start: blocked (auto: discussion review usage error) for <slug>"`/push sequence already documented for the existing auto-mode halt.
  - Amend the existing ALL-entries trigger paragraph's lead-in to read "When no entry in `reviews[]` is `error_kind: "usage"` (per the immediate halt above), and the JSON envelope from step 2 has top-level `verdict: "ERROR"` (or, equivalently, every remaining entry in `reviews[]` has `verdict: "ERROR"`), skip steps 4a / 4b / 5 entirely and immediately re-run:" — this scopes the existing two-pass retry-then-halt behavior to `"reviewer"`-kind and absent-`error_kind` entries only, per the overview's "error_kind is additive, per-reviews[]-entry only" Shared Decision. Do not otherwise change the two-pass mechanics, the Agent-mode/Subprocess dispatch branches, or the liveness-check block below it.
- **Commit:** `docs(mill-start): halt immediately on error_kind: usage instead of retrying`

### Card 17: `mill-plan/SKILL.md` Step 4.5 — usage-error immediate halt

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - Locate `### Phase: Plan Review`'s `**Step 4.5: ERROR-only-aggregate retry (no round consumed)**` heading. Its body's first paragraph currently begins "When the JSON envelope from step 2 has a non-empty `reviews[]` array AND at least one entry's `verdict` is `"ERROR"`, OR when no JSON line appears in the bg log ..., skip steps 4a/4b/4c/4d entirely and immediately re-run:" — this is the existing ANY-entry trigger condition (this file is the one site of the four whose pre-existing trigger is ANY, not ALL — do not change that asymmetry).
  - Immediately before that paragraph, insert a new paragraph titled "**Usage-error immediate halt (checked first, every round).**" that: inspects the JSON envelope's `reviews[]` array (when present) for any entry with `error_kind: "usage"`; if found, halts immediately on this occurrence (no retry, no round consumed), regardless of what any other entry in the same `reviews[]` list contains: `_status.set_blocked(status_path, f"plan review usage error: <message>", timestamp=ts)` (where `<message>` is the offending entry's `error` field); commit `git -C <worktree> add <status_path> && git -C <worktree> commit -m "mill-plan: blocked (plan review usage error) for {slug}"` and push; halt with `BLOCKED: plan review usage error: <message>` — distinct wording from the existing `BLOCKED: plan review ERROR-only round {N}` halt below it.
  - Amend the existing ANY-entry trigger paragraph's lead-in to read "When no entry in `reviews[]` is `error_kind: "usage"` (per the immediate halt above), and the JSON envelope from step 2 has a non-empty `reviews[]` array AND at least one remaining entry's `verdict` is `"ERROR"`, OR when no JSON line appears in the bg log ..., skip steps 4a/4b/4c/4d entirely and immediately re-run:" — this scopes the existing two-pass retry-then-halt behavior to `"reviewer"`-kind, absent-`error_kind`, and absent-JSON cases only. Do not otherwise change the two-pass mechanics, the Agent-mode/Subprocess dispatch branches, the tree-guard checkpoints, or the cost-line printing already documented in this step.
- **Commit:** `docs(mill-plan): halt immediately on error_kind: usage instead of retrying`

### Card 18: `mill-go-base/SKILL.md` Step 4.5 — usage-error immediate halt

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - Locate the per-batch code-review loop's `**Step 4.5: ERROR-only-aggregate retry (no round consumed)**` heading (the one immediately followed by "5. **Max-rounds exhaustion.**" further down, distinguishing it from `holistic-review.md`'s separate sub-step 3.5). Its body's first paragraph currently begins "When the JSON envelope from sub-step 2 has top-level `verdict: "ERROR"` (or, equivalently, every entry in `reviews[]` has `verdict: "ERROR"`), skip sub-step 4 entirely and immediately re-run:" — this is the existing ALL-entries trigger condition.
  - Immediately before that paragraph, insert a new paragraph titled "**Usage-error immediate halt (checked first, every round).**" that: inspects the JSON envelope's `reviews[]` array (when present) for any entry with `error_kind: "usage"`; if found, halts immediately on this occurrence (no retry, no round consumed), regardless of what any other entry in the same `reviews[]` list contains — reusing the exact halt mechanics this same step's existing second-pass halt already uses below it (`halt with BLOCKED: code review ERROR-only round {N} and surface each entry's error string from reviews[] to the user`, including whatever batch-state/commit mechanics that halt already implies via the shared *Blocked* section this SKILL.md defines), but with the message replaced with `BLOCKED: code review usage error: <message>` (where `<message>` is the offending entry's `error` field) — distinct wording from the existing `ERROR-only round {N}` phrasing.
  - Amend the existing ALL-entries trigger paragraph's lead-in to read "When no entry in `reviews[]` is `error_kind: "usage"` (per the immediate halt above), and the JSON envelope from sub-step 2 has top-level `verdict: "ERROR"` (or, equivalently, every remaining entry in `reviews[]` has `verdict: "ERROR"`), skip sub-step 4 entirely and immediately re-run:" — this scopes the existing two-pass retry-then-halt behavior to `"reviewer"`-kind and absent-`error_kind` entries only. Do not otherwise change the two-pass mechanics, the tree-guard checkpoint blocks, or the Agent-mode dispatch pattern reference already documented in this step. Do not touch the "Post-dispatch form" cross-reference paragraph elsewhere in this file that names this step and `holistic-review.md`'s sub-step 3.5 as separate dispatch points — that paragraph is accurate unchanged.
- **Commit:** `docs(mill-go-base): halt immediately on error_kind: usage instead of retrying (per-batch code review)`

### Card 19: `mill-go-base/holistic-review.md` sub-step 3.5 — usage-error immediate halt (bypasses rate-limit fallback)

- **Context:**
  - `plugins/mill/skills/mill-go-base/holistic-review.md`
- **Edits:**
  - `plugins/mill/skills/mill-go-base/holistic-review.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - Locate `**Step 3.5: ERROR-only-aggregate retry (no round consumed)**` (immediately preceded by the `3.5.` line and immediately followed by `3.6.` `**Rate-limit fallback (no round consumed)**`). Its body's first paragraph currently begins "When the JSON envelope from step 3 has top-level `verdict: "ERROR"` (or, equivalently, every entry in `reviews[]` has `verdict: "ERROR"`), skip steps 4 and 5 entirely and immediately re-run:" — this is the existing ALL-entries trigger condition.
  - Immediately before that paragraph, insert a new paragraph titled "**Usage-error immediate halt (checked first, every round; bypasses sub-step 3.6 rate-limit fallback entirely).**" that: inspects the JSON envelope's `reviews[]` array (when present) for any entry with `error_kind: "usage"`; if found, halts immediately on this occurrence (no retry, no round consumed, and — unlike the existing second-pass ERROR-only path — never falls through to sub-step 3.6's rate-limit fallback, since a usage error is deterministic and not a transient/rate-limit reviewer condition) using the same mechanics as the existing second-pass halt below (`_status.set_blocked(status_path, ...)`; commit `git -C <worktree> add <status_path> && git -C <worktree> commit -m "..."` and push; `_notify.notify("<VARIANT_LABEL>.blocked", ...)`; release the builder lock via `millpy-builder-lock.py release`) but with the reason/message text replaced: `_status.set_blocked(status_path, f"holistic code review usage error: <message>", timestamp=_timestamp.now_utc_iso())`, commit message `"<VARIANT_LABEL>: blocked on holistic review (usage error)"`, and halt with `BLOCKED: holistic code review usage error: <message>` (where `<message>` is the offending entry's `error` field) — distinct wording from the existing `BLOCKED: holistic code review ERROR-only round {H}` phrasing, and this halt path never checks sub-step 3.6's `fallback_reviewer`/`fallback_on` condition at all.
  - Amend the existing ALL-entries trigger paragraph's lead-in to read "When no entry in `reviews[]` is `error_kind: "usage"` (per the immediate halt above), and the JSON envelope from step 3 has top-level `verdict: "ERROR"` (or, equivalently, every remaining entry in `reviews[]` has `verdict: "ERROR"`), skip steps 4 and 5 entirely and immediately re-run:" — this scopes the existing two-pass retry-then-(rate-limit-fallback-or-halt) behavior to `"reviewer"`-kind and absent-`error_kind` entries only. Do not otherwise change the two-pass mechanics, the tree-guard checkpoint blocks, the cost-line printing, or sub-step 3.6's own body (its `fallback_reviewer`/`fallback_on` condition and in-memory reviewer swap continue to apply exactly as today whenever this batch's new immediate-halt path is not the one that fired).
- **Commit:** `docs(mill-go-base): halt immediately on error_kind: usage instead of retrying (holistic code review)`

## Batch Tests

`verify: null` — prose-only orchestration-skill changes across all four cards. Verified by
re-reading `mill-start/SKILL.md` Step 3.5, `mill-plan/SKILL.md` Step 4.5, `mill-go-base/SKILL.md`
Step 4.5, and `mill-go-base/holistic-review.md` sub-step 3.5 after editing, confirming: (a) each
site's new usage-error paragraph precedes its existing trigger-condition paragraph; (b) each site's
existing trigger-condition paragraph's lead-in now excludes `error_kind: "usage"` entries; (c) all
four halt messages use consistent `usage error` wording distinct from each site's pre-existing
`ERROR-only round N` wording; (d) no other prose in any of the four files — dispatch patterns,
tree-guard checkpoints, cost-line printing, the ALL-vs-ANY trigger-condition asymmetry, and
`holistic-review.md`'s sub-step 3.6 rate-limit fallback — was altered beyond what this batch's
cards specify.
