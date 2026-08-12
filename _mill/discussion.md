# Discussion: Review-plan finalize: usage-error indistinguishability, flag issues, verdict rendering stale

```yaml
task: Review-plan finalize: usage-error indistinguishability, flag issues, verdict rendering stale
slug: review-pipeline-consistency-bugs
status: discussing
parent: main
```

## Problem

`millpy-review-plan.py --stage finalize` (and its `_review_common.py` shared machinery, used
identically by the discussion- and code-review CLIs) has several consistency bugs in how it
reports errors and renders demoted findings, folded together from five GitHub issues (#838,
#830, #829, #822, #820) into this one task:

1. A CLI **usage** error (e.g. missing `--agent-output`, bad config, unresolvable slug) emits
   the exact same `verdict: "ERROR"` JSON-envelope shape as a genuine **reviewer-output**
   failure (the LLM reviewer produced text `parse_verdict` couldn't extract a verdict from).
   Consumers (mill-start Step 3.5, mill-plan Step 4.5, mill-go-base Step 4.5) cannot tell these
   apart, so a deterministic CLI misinvocation burns one of the two allowed ERROR-retry passes
   and can halt the loop with a misleading `BLOCKED: review ERROR-only round N` for a reason
   that has nothing to do with the reviewer.
2. The same usage-error envelope always reports `"round": 0`, even when the real round number
   was already known from `--round` or discoverable from disk — misleading in halt messages and
   logs.
3. When the stage's `blocking_classes` ceiling demotes one or more `BLOCKING` findings to `NIT`,
   the individual finding headings/yaml entries are correctly rewritten, and the machine-readable
   `blocking_count`/`verdict` fields in the JSON envelope are correctly recomputed — but the
   reviewer-authored one-sentence `## Verdict` summary is never touched. It keeps stating the
   pre-demotion BLOCKING count/rationale, so the rendered review file self-contradicts its own
   frontmatter and JSON envelope. This happens whether or not the demotion also flips the
   aggregate verdict token (APPROVE vs REQUEST_CHANGES).

**Why now:** all five issues were filed by `/mill-self-report --auto` or operator feedback
across recent `/mill-plan` and `/mill-go` runs on unrelated tasks, then consolidated into this
one task via the standard ghissues-fold flow (all five GitHub issues are `CLOSED` with a
"Consolidated into wiki task" pointer comment — none were closed because they were already
fixed in code, except #838, addressed below).

## Scope

**In:**
- `_review_cli.py::print_error_envelope` — add an `error_kind: "usage" | "reviewer"` field to
  the JSON envelope, and thread through the correct round number instead of hardcoding `0`.
- `millpy-review-plan.py`, `millpy-review-discussion.py`, `millpy-review-code.py` — the
  finalize-stage `except ReviewError` block that catches a `parse_verdict` failure on the
  reviewer's own raw text is reclassified `error_kind: "reviewer"`; every other
  `print_error_envelope` call site (config/registry/slug resolution, prepare-stage errors,
  missing `--agent-output`, full-stage errors) stays `error_kind: "usage"` (the default).
- `mill-start/SKILL.md` Step 3.5, `mill-plan/SKILL.md` Step 4.5, `mill-go-base/SKILL.md` Step
  4.5, and `mill-go-base/holistic-review.md` sub-step 3.5 — update the ERROR-only-aggregate
  retry logic to read `error_kind`: `"usage"` halts immediately (no round consumed, no two-pass
  wait) with a distinct halt message; `"reviewer"` (or absent, for back-compat with envelopes
  that predate this field) keeps the existing two-pass retry-then-halt behavior unchanged.
- `_review_common.py::finalize_scope` — add a new helper (e.g. `append_demotion_note`) called
  unconditionally whenever `demoted_any` is `True`, appending a deterministic note to the
  `## Verdict` section's summary line stating the post-ceiling BLOCKING/NIT counts. Independent
  of `rewrite_verdict_token`'s existing `demoted_any and verdict != original_verdict` gate, which
  stays as-is (it only ever controlled the *token*, not the summary sentence, and does not need
  to change).
- Regression test confirming `--stage finalize --duration-s <float>` is accepted by all three
  review CLIs (locks in #838's current, already-fixed behavior — see Decisions below).
- Unit tests per the Testing section.

**Out:**
- No change to `rewrite_verdict_token`'s token-rewrite gating logic itself — it already does its
  one job correctly (see #838/#822 investigation notes under Decisions).
- No change to the `"full"` review-run stage's error handling beyond the shared
  `print_error_envelope` signature change — it stays `error_kind: "usage"` uniformly (see
  Decisions, "error_kind bucketing").
- No new top-level `verdict` value (e.g. `"USAGE_ERROR"`) — rejected in favor of an additive
  `error_kind` sub-field (see Decisions).
- No rewrite of the reviewer's original Verdict summary sentence — only an appended note, so the
  reviewer's rationale prose is preserved (see Decisions).
- No changes to `mill-go-base/SKILL.md`'s "## Agent-mode dispatch" section's `--agent-output`
  documentation — already names the flag explicitly at each call site in the versions of
  mill-start/mill-plan/mill-go-base read during discussion; #820's secondary documentation
  suggestion appears already addressed and needs no further action.

## Decisions

### #838 is already fixed — no code change, add regression test only

- Decision: Treat #838 as resolved by existing code. Add one regression test per review CLI
  locking in `--stage finalize --duration-s <float>` succeeding; do not change any CLI argparse
  setup for this issue.
- Rationale: Direct read of `millpy-review-plan.py`, `millpy-review-discussion.py`,
  `millpy-review-code.py` confirms all three already accept `--duration-s` (added by commit
  `479f806b`, "Surface reviewer time/tool-call cost + a review-summary command", which is on
  `main` and on this task branch). `mill-plan/SKILL.md` and `mill-go-base/SKILL.md`'s documented
  dispatcher behavior already matches the CLI signature exactly — no drift found. The GitHub
  issue was closed only because it was folded into this task (pointer comment), not because it
  was already fixed at fold time — the fix landed in the same window, separately.
- Rejected: Re-investigating further edge cases (e.g. other cost-metadata flags) — grep confirms
  `--tool-calls`/`--cost-usd` are present and consistently threaded in all three CLIs too; no
  further drift found.

### error_kind field, not a new verdict value

- Decision: Add `error_kind: "usage" | "reviewer"` as an additive sub-field on each `reviews[]`
  entry (mirrored at the top level for single-scope agent-mode calls), rather than introducing a
  new top-level `verdict` value.
- Rationale: `verdict: "ERROR"` already has meaning to consumers that only care "did this round
  produce a usable result" (e.g. `mill-receiving-review`, `review-summary`) — those must keep
  working unmodified. An additive field lets only the ERROR-retry-logic consumers (mill-start,
  mill-plan, mill-go-base) opt into the finer distinction without touching every other
  `verdict == "ERROR"` check across the codebase.
- Rejected: `verdict: "USAGE_ERROR"` (the issue author's own suggestion) — would require auditing
  and updating every existing `verdict == "ERROR"` check across the whole review subsystem to
  also treat the new value as an error, a much wider blast radius for the same outcome.
  Also rejected: emitting no JSON envelope at all for usage errors (stderr + exit code only) —
  breaks the existing contract that every finalize/prepare invocation prints exactly one JSON
  line, which `millpy-bg`/Agent-mode dispatch parsing and `review-summary` both currently rely on.

### error_kind bucketing: pre-reviewer vs. reviewer-output-parsing

- Decision: Every `print_error_envelope` call site defaults to `error_kind: "usage"` — this
  covers config load failure, reviewer-registry validation, slug resolution, prepare-stage
  `ReviewError`/unhandled exceptions, missing `--agent-output`, and full-stage `ReviewError`/
  unhandled exceptions. The **sole** exception is the finalize-stage `except ReviewError` that
  wraps the call into `finalize()` → `_review_common.finalize_scope()` → `parse_verdict()`: that
  is reclassified `error_kind: "reviewer"`.
- Rationale: Grounded in direct code reading (`millpy-review-plan.py:169-358`,
  `_review_common.py:2465-2571,1569-1608`) — contrary to an earlier (incorrect) hypothesis that
  `finalize_scope` internally catches parse failures and returns an ERROR-shaped dict with cost
  metadata, it does **not**: `parse_verdict` raises `ReviewError` uncaught, which propagates to
  the CLI's single `except ReviewError` block around the `finalize()` call
  (`millpy-review-plan.py:307-309`). That is the only call site where the *reviewer's own output*
  is the cause of the error; every other site fails before or entirely outside reviewer-output
  processing (config, registry, slug, missing flags) and is therefore always non-retryable.
- Rejected: Treating the full-stage (`--stage full`) `ReviewError` catch as potentially either
  kind — it wraps an entire multi-round `run()` loop that could fail for many reasons (config,
  registry, slug, or reviewer-output problems all funnel through the same catch), so unwrapping
  the inner cause to pick a kind would need its own dedicated logic. Defaulting it to `"usage"`
  (fail-fast, no wasted retry) is simpler and safe even though `--stage full` is not purely
  vestigial — `mill-plan/SKILL.md:370` documents it as the second-consecutive-Agent-API-error
  fallback path via `millpy-bg`, so this stage does still see real invocations; the multi-cause
  rationale alone is what justifies the `"usage"` default here, independent of how often the
  stage runs.

### Retry semantics keyed on error_kind

- Decision: `mill-start/SKILL.md` Step 3.5, `mill-plan/SKILL.md` Step 4.5, and
  `mill-go-base/SKILL.md` Step 4.5 change their ERROR-only-aggregate retry logic: when the
  envelope's `error_kind` is `"usage"`, halt immediately on the first occurrence — no retry, no
  round consumed — with a message that names it as a usage error (distinct wording from the
  existing `BLOCKED: <type> review ERROR-only round N`, e.g.
  `BLOCKED: <type> review usage error: <message>`). When `error_kind` is `"reviewer"` or absent
  (older envelopes / any review type not yet touched by this fix), keep the existing two-pass
  retry-then-halt behavior unchanged.
- Rationale: A usage error is deterministic — the identical CLI invocation will fail identically
  on retry, so the existing two-pass wait only delays the operator-visible halt without any
  chance of success. This is the exact complaint in #830/#820.
- Rejected: Leaving retry behavior unchanged and treating `error_kind` as informational-only —
  doesn't fix the actual behavioral bug the issues describe, only improves debuggability.

### round: 0 fix

- Decision: `print_error_envelope` gains an optional `round` parameter (default `0`, preserving
  today's behavior for callers that don't pass it). Every call site in `millpy-review-plan.py`
  passes `args.round` when available — which is every site, since `args = parser.parse_args(...)`
  runs before any error branch. Prepare-stage call sites keep `round=0` (or omit the param)
  since no round has been assigned yet at that point in a genuine failure.
- Rationale: `args.round` is parsed once at the very top of `main()`, before any try/except
  block — it costs nothing to thread through, and directly fixes the "round: 0 is also wrong"
  complaint in both #830 and #820.
- Rejected: Calling `discover_round()` from the error path to recover a round number even when
  `--round` wasn't passed — adds filesystem I/O and complexity to an error path for a case
  (`--round` omitted entirely) that isn't what either filed issue actually reproduced.

### Verdict-summary staleness: append, don't rewrite

- Decision: Add a new helper, called unconditionally in `finalize_scope` whenever `demoted_any`
  is `True` (independent of `rewrite_verdict_token`'s own gate), that appends one line directly
  after the existing `## Verdict` section's one-sentence summary:
  `_Note: N finding(s) demoted from BLOCKING to NIT by the stage's blocking-class ceiling;
  current blocking_count is M._`
- Rationale: Direct read of `rewrite_verdict_token` (`_review_common.py:2186-2253`) confirms its
  docstring and code both explicitly leave the summary line untouched by design — it only
  rewrites the fenced-yaml `verdict:` field and the `## Verdict` token line. Its invocation gate
  (`demoted_any and verdict != original_verdict`, `_review_common.py:2552`) is correct for its
  own narrow purpose (only rewrite the token when it actually needs to change) but has nothing to
  do with the summary-sentence staleness — that staleness exists unconditionally whenever
  `demoted_any` is true, whether or not the token flips. #822's repro (token flipped to APPROVE,
  summary still says "the blocking issue") and #829's repro (token didn't need to flip, count in
  prose still overstated) are the same underlying gap, not two different bugs needing different
  fixes.
- Rejected: Regenerating the summary sentence from scratch — destroys reviewer-authored rationale
  text (which may explain *why* something was originally judged BLOCKING, useful context beyond
  the raw count) for no added correctness over an appended note. Also rejected: folding this
  logic into `rewrite_verdict_token` itself and dropping its `verdict != original_verdict` gate —
  keeps that function's single responsibility (token only) intact and independently testable;
  the two concerns (token accuracy, summary-count accuracy) have different trigger conditions in
  general even though they happen to co-occur in both filed repros.

## Technical context

- `plugins/mill/scripts/_review_cli.py` — `print_error_envelope()` (lines 24-45), the single
  shared usage-error envelope emitter for all three review CLIs.
- `plugins/mill/scripts/millpy-review-plan.py` — `main()` (lines ~150-358). All
  `print_error_envelope` call sites: 180, 187, 193, 260, 263, 267 (`--agent-output` missing),
  308 (finalize `ReviewError` — the one reviewer-kind site), 354, 357. `args.round` is parsed at
  line 162, available at every one of these sites.
- `plugins/mill/scripts/_review_common.py`:
  - `parse_verdict()` (line 1569) — raises `ReviewError` when no valid verdict can be extracted
    from reviewer raw text; this is the sole source of a genuine reviewer-kind error.
  - `finalize_scope()` (line 2465) — orchestrates `apply_actual_model_override` →
    `apply_cost_metadata` → `parse_verdict` → `extract_findings` → (if `blocking_classes` set)
    `apply_blocking_ceiling` + `rewrite_demoted_findings` → conditionally `rewrite_verdict_token`
    → `write_review_file`. `demoted_any` is computed at line 2540; the existing
    `rewrite_verdict_token` gate is at line 2552 — the new demotion-note helper call should sit
    near there, keyed on `demoted_any` alone.
  - `rewrite_verdict_token()` (line 2186) — rewrites the fenced-yaml `verdict:` field and the
    `## Verdict` section's token line only; explicitly (by docstring and code) leaves the
    following summary line untouched. Do not change this function's own gating; add new logic
    alongside it.
  - `DEFAULT_BLOCKING_CLASSES` (line 2601) — per-role default ceilings; not directly relevant to
    the fix but explains why `blocking_classes` is non-`None` on every production call site.
- `plugins/mill/scripts/millpy-review-discussion.py` and `millpy-review-code.py` — same
  `print_error_envelope` usage pattern and same finalize-stage `ReviewError` catch shape as
  `millpy-review-plan.py` (confirmed by grep for `--duration-s` and `print_error_envelope`
  call-site structure); apply the identical `error_kind` bucketing to each.
- `plugins/mill/skills/mill-start/SKILL.md` Step 3.5 "ERROR-only-aggregate retry", ~line 200s of
  the rendered skill (Phase: Discussion Review) — this session's own consumer of the pattern
  being fixed.
- `plugins/mill/skills/mill-plan/SKILL.md` Step 4.5 (line ~449),
  `plugins/mill/skills/mill-go-base/SKILL.md` Step 4.5 (line ~778), and
  `plugins/mill/skills/mill-go-base/holistic-review.md` sub-step 3.5 (line ~112) — the other
  three consumer sites; grep confirms these four files are the only ones referencing
  `ERROR-only-aggregate` (`mill-go-base/SKILL.md:420` documents the `holistic-review.md` site as
  a distinct dispatch point from its own per-batch Step 4.5, not a sub-cycle of it).
- `plugins/mill/templates/review-output.schema.md` — documents the `## Verdict` section's
  two-line contract (verdict token, then one-sentence summary); the demotion-note addition is an
  appended third line within that section, so this schema doc needs a one-line update describing
  when the note appears.
- Five source GitHub issues (all `CLOSED`, consolidated via pointer comment into this task):
  #838, #830, #829, #822, #820 — full bodies read during discussion for exact repro steps and
  the issue authors' own suggested fixes (see Decisions above for what was adopted vs. rejected
  from those suggestions).

## Constraints

_No `CONSTRAINTS.md` present at hub root._

## Testing

- **`_review_cli.py::print_error_envelope`** (TDD candidate): unit test asserting the emitted
  envelope carries `error_kind: "usage"` by default, and a specific `error_kind` value when
  explicitly passed.
- **`millpy-review-plan.py` finalize-stage error paths**: unit test (invoking `main()` or the
  relevant internal function with a fixture) confirming a missing-`--agent-output` invocation
  produces `error_kind: "usage"` with the correct (non-zero) round when `--round` was supplied,
  and a reviewer raw-text that fails `parse_verdict` produces `error_kind: "reviewer"`. Mirror
  for `millpy-review-discussion.py` and `millpy-review-code.py`.
- **`_review_common.py::finalize_scope`** (TDD candidate): unit test with a fixture review whose
  `blocking_classes` ceiling demotes at least one finding but does **not** flip the aggregate
  verdict (covers #829 — count-only staleness) asserting the demotion note is appended and the
  reviewer's original summary sentence is preserved above it. A second case where demotion *does*
  flip the verdict (covers #822 — token + note both change) asserting both the token and the
  appended note are correct and consistent with `blocking_count`.
- **Regression test** (all three review CLIs): `--stage finalize --duration-s <float>` (and
  `--tool-calls`, `--cost-usd`) succeeds without an argparse error — locks in #838's
  already-resolved state so a future regression is caught.
- **SKILL.md consumer changes** (mill-start Step 3.5, mill-plan Step 4.5, mill-go-base Step 4.5,
  mill-go-base/holistic-review.md sub-step 3.5): not unit-testable (prose/orchestration logic in
  markdown skill files) — verify by re-reading all four files after editing to confirm identical
  `error_kind`-based halt behavior and consistent halt-message wording.
- Follow existing project convention: `plugins/mill/unit_tests/test-<name>.py`, in-memory/tempfile
  fixtures, no real git or LLM calls (per `CLAUDE.md` repo layout notes).

## Q&A log

- **Q:** Is #838 in scope for code changes? **A:** [auto-pick] Out of scope — already fixed; add
  a regression test only. **Why:** Direct code read confirms `--duration-s` is already accepted
  by all three finalize CLIs (commit `479f806b`, on `main` and this branch); the GitHub issue was
  closed only via fold-in, not because the code fix was already known at filing time.
- **Q:** Should the `error_kind` fix apply to all three review types via the shared layer? **A:**
  [auto-pick] Yes, shared-layer fix. **Why:** `_review_cli.py`/`_review_common.py` are shared by
  plan/discussion/code review; the bug is structurally identical in all three (confirmed by grep
  for matching `print_error_envelope` call-site patterns), and #820 itself asks to check the
  other two CLIs.
- **Q:** Should the Verdict-prose staleness fix apply uniformly across all three review types?
  **A:** [auto-pick] Yes. **Why:** `finalize_scope` is the single shared implementation used by
  all three CLIs' finalize stage.
- **Q:** How should usage-vs-reviewer errors be distinguished in the envelope? **A:** [auto-pick]
  Additive `error_kind: "usage" | "reviewer"` field. **Why:** Preserves every existing
  `verdict == "ERROR"` consumer unmodified; a new top-level verdict value would require auditing
  and updating every such check across the codebase for the same outcome.
- **Q:** Should retry behavior change based on `error_kind`? **A:** [auto-pick] Yes — `"usage"`
  halts immediately, no retry; `"reviewer"`/absent keeps the existing two-pass behavior. **Why:**
  A usage error is deterministic; retrying it can never succeed, and the two-pass wait only
  delays an inevitable, misleadingly-labeled halt — the exact complaint in #830/#820.
- **Q:** Should the `round: 0` misreport also be fixed? **A:** [auto-pick] Yes, in the same pass.
  **Why:** `args.round` is already parsed before every error call site; threading it through
  costs nothing and directly addresses both issues' secondary complaint.
- **Q:** How should the stale Verdict summary sentence be corrected? **A:** [auto-pick] Append a
  deterministic note after the existing sentence whenever `demoted_any` is true, independent of
  whether the verdict token flipped. **Why:** Direct read of `rewrite_verdict_token` confirms it
  by design never touches the summary line; its flip-gate controls the token only. #822 and #829
  are the same underlying gap (summary never updated), not two distinct bugs.
- **Q:** Where should the note-append logic live? **A:** [auto-pick] New, separate helper, called
  unconditionally on `demoted_any` in `finalize_scope`. **Why:** Keeps `rewrite_verdict_token`'s
  single responsibility (token only) intact and independently testable.
- **Q:** What are the TDD candidates? **A:** [auto-pick] Unit-level tests per function (envelope
  `error_kind`, round threading, demotion-note append in both flip/no-flip cases, `--duration-s`
  regression), matching existing `plugins/mill/unit_tests/` conventions; SKILL.md prose changes
  verified by manual re-read, not unit tests. **Why:** Matches project testing conventions
  (in-memory/tempfile fixtures, no real git/LLM) and keeps fast, deterministic coverage on the
  pure-Python logic while treating markdown orchestration prose appropriately as non-unit-testable.
