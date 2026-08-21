# Discussion: millpy-review-plan: finalize envelope verdict silently diverges from the review file's own written verdict

```yaml
task: 'millpy-review-plan: finalize envelope verdict silently diverges from the review file''s own written verdict'
slug: millpy-review-plan-verdict-envelope-bugs
status: discussing
parent: main
```

## Problem

`millpy-review-plan.py --stage finalize` (and, via the same shared backend, the discussion- and
code-review CLIs) can emit a JSON envelope whose `verdict` field contradicts the review file it
just wrote to disk. Three independent bug reports (#891, #876, #865) describe the same repro: a
reviewer writes `REQUEST_CHANGES` in both the fenced yaml `verdict:` field and the `## Verdict`
section of its own output, with zero `[BLOCKING]` findings (only NITs, or the reviewer's own
judgment call). The finalize stage silently recomputes the envelope's `verdict` to `APPROVE`
(derived purely from `blocking_count == 0`) and — because no blocking-class ceiling demotion
happened — leaves the on-disk file's `REQUEST_CHANGES` text completely untouched. Nothing in
either artifact explains the disagreement.

This is more than cosmetic: `mill-plan/SKILL.md` already has a step 4c that exists specifically
to handle `REQUEST_CHANGES AND blocking_count == 0` as its own branch (distinct commit message,
distinct terminal actions from 4a/4b's APPROVE path). Because `finalize_scope()` always collapses
that combination to `APPROVE` before 4c ever sees it, **4c is currently unreachable** — exactly
what #891 reports. An operator reading the review file sees `REQUEST_CHANGES`; the orchestrator
silently takes the APPROVE path anyway.

Two more issues were folded into the same wiki task (#864, #867) but turned out, on reading the
current code, to already be fixed by commit `acdeab07` ("millpy-review-plan finalize: usage-error
indistinguishability, flag issues, verdict rendering stale", 2026-08-12) — which predates all
five issues' filing timestamps (2026-08-14 through 2026-08-19). The reporting repos were almost
certainly on a stale cached plugin build. See Decisions below for what's actually left to do with
those two.

A fourth candidate bug was investigated during discussion review and **rejected as a false
premise**: the finalize-stage CLI-level `except ReviewError` handlers in all three review CLIs
were suspected of misclassifying reviewer-origin parse failures as `error_kind: "usage"`. On
closer reading, each `finalize()` wrapper in `_review_plan.py`/`_review_discussion.py`/
`_review_code.py` already wraps its own call to `finalize_scope()` in a `try`/`except
ReviewError`, and returns a dict with `error_kind: "reviewer"` directly — it never re-raises. The
CLI-level catch these three files' finalize-stage try blocks wrap cannot receive a
`parse_verdict`-originated `ReviewError` in production; the only other call inside that block
(`resolve_blocking_classes`) never raises. See Decisions below.

## Scope

**In:**
- `_review_common.py::finalize_scope()` — stop force-downgrading a reviewer's own
  `REQUEST_CHANGES`-with-zero-`BLOCKING` verdict to `APPROVE` when no ceiling demotion happened
  this call. Both the returned envelope `verdict` and the persisted file must agree with the
  reviewer's original verdict in that case.
- Regression-test coverage for #864 (usage-error `error_kind` classification on the
  missing-`--agent-output` path) and #867 (`--actual-model` override reaching the persisted
  `reviewer_model` field) confirming the existing `acdeab07` fix, since neither appears to have
  had a test added that pins the exact repro shape from the issue.
- New/extended unit tests locking in both the fixed downgrade behavior and the still-intentional
  escalation behavior (`APPROVE` + real `BLOCKING` findings, no demotion, still recomputes to
  `REQUEST_CHANGES` — this must NOT regress).

**Out:**
- `NEED_CONTEXT` verdict handling — already correctly passed through untouched, orthogonal to
  this bug.
- Ceiling-demotion-driven verdict rewriting (`rewrite_verdict_token`, `append_demotion_note`,
  the `demoted_any` branch) — already correct and tested; this task does not change when a
  demotion is allowed to downgrade a verdict, only the non-demotion case.
- Prepare-stage and full-stage `except ReviewError` handlers — their `error_kind="usage"` default
  is correct (those catch genuine config/validation/batch-resolution failures) and is not
  touched.
- Any change to `mill-plan/SKILL.md`, `mill-start/SKILL.md`, or `mill-go-base/SKILL.md` — the
  consumer side (step 4c, the usage-error halt, the `--actual-model` passthrough) is already
  written correctly and does not need editing; only the producer-side backend was wrong.
- Actually re-implementing #864 or #867's underlying mechanisms — both already exist in the
  current codebase; this task only adds missing regression coverage for them.
- Changing `error_kind` classification on the three review CLIs' finalize-stage CLI-level
  `except ReviewError` handlers — investigated and rejected; see Decisions
  ("Fourth candidate bug: rejected as unreachable").

## Decisions

### Verdict derivation: escalate always, downgrade only on this-call demotion

- Decision: In `finalize_scope()`, change the verdict-recomputation block so that: (a) when
  `blocking_count > 0`, the verdict is always forced to `REQUEST_CHANGES` (unchanged — this is
  the existing escalation safety net, still needed for a reviewer that under-reports its own
  findings); (b) when `blocking_count == 0` AND this call's blocking-class ceiling demoted at
  least one finding (`demoted_any`), the verdict is forced to `APPROVE` (unchanged — the
  intentional, already-tested ceiling-demotion path, still followed by the existing
  `rewrite_verdict_token`/`append_demotion_note` file rewrite); (c) when `blocking_count == 0`
  AND `demoted_any` is `False`, the verdict is left as `original_verdict` (the reviewer's own
  parsed verdict) — no forced recompute, no file rewrite, since there's nothing to reconcile.
- Rationale: This is the narrowest change that fixes #891/#876/#865 without touching either of
  the two behaviors that are already correct and tested
  (`test_verdict_token_unchanged_when_mismatched_without_demotion` for the escalation direction,
  `test_verdict_token_rewritten_on_ceiling_flip`/`test_demotion_note_appended_when_verdict_flips`
  for the demotion direction). It also restores `mill-plan/SKILL.md` step 4c to reachability
  without any SKILL-side edit, since the envelope will now genuinely be able to carry
  `REQUEST_CHANGES` with `blocking_count == 0` again.
- Rejected: Always rewriting the on-disk file to match the derived envelope verdict on any
  divergence (keeps "always derive from blocking_count," permanently dead-codes 4c, would
  require rewriting three SKILL.md files to remove the now-unreachable branch). Trusting the
  reviewer's verdict completely verbatim with no blocking_count-derived override at all (breaks
  the existing escalation-direction test and removes a real safety net against a reviewer that
  writes `APPROVE` while a finding heading it forgot to self-flag is genuinely `BLOCKING`).

### Fix applies to the shared backend, not just plan review

- Decision: The fix lands in `_review_common.py::finalize_scope()`, the single function shared
  by `millpy-review-plan.py`, `millpy-review-discussion.py`, and `millpy-review-code.py`, rather
  than being special-cased for plan review only.
- Rationale: The bug mechanism (verdict recomputed purely from `blocking_count`, file rewrite
  gated on `demoted_any`) has nothing plan-specific about it; all three review types share the
  exact same `finalize_scope()` code path per CLAUDE.md's documented backend layering. Scoping
  the fix to plan review only would leave the identical bug live for discussion- and code-review,
  which the issue titles happen not to mention only because no one has reported it there yet.
- Rejected: A `review_type`-conditional branch inside `finalize_scope()` that only changes
  behavior for `"plan"` — adds a special case for no reason grounded in the actual bug mechanism.

### #864 and #867: already fixed, add regression coverage only

- Decision: Do not re-implement either mechanism. `error_kind="usage"` is already correctly the
  default for the missing-`--agent-output` finalize-stage usage check (a genuinely pre-reviewer
  usage error, checked before the try block that this task's `error_kind="reviewer"` change
  touches). `--actual-model` is already threaded end-to-end from the CLI flag through
  `apply_actual_model_override()` into the persisted `reviewer_model:` field, and
  `mill-go-base/SKILL.md`'s Agent-mode dispatch pattern already documents passing
  `--actual-model <dispatched-tier>` for all three review CLIs. Add unit tests that pin the exact
  repro shape each issue described, so a future regression is caught.
- Rationale: Commit `acdeab07` (2026-08-12) already implemented both fixes, before any of the
  five issues were filed (2026-08-14 to 2026-08-19) — the reporting repos were on a stale cached
  plugin build. Re-implementing already-correct code wastes the task; the actual gap is the
  missing regression test that would have caught a re-introduction.
- Rejected: Leaving #864/#867 out of the task's test coverage entirely, since they were folded
  into this wiki task and the task should close the loop on all five even if two need no
  production-code change.

### Fourth candidate bug: rejected as unreachable

- Decision: Do not change `error_kind` classification on the three review CLIs' finalize-stage
  CLI-level `except ReviewError` handlers. Treat this candidate like #864/#867 — investigated,
  found already correct, closed with no production-code change.
- Rationale: Discussion review round 1 (holistic, `sonnethigh`) flagged this as
  `[BLOCKING:design]` with the finding "Fourth bug's premise is false — the catch site is
  unreachable," citing `_review_plan.py:706-733`, `_review_discussion.py`, and `_review_code.py`
  as each already wrapping their own call to `finalize_scope()` in an internal
  `try`/`except ReviewError` that returns `error_kind: "reviewer"` directly, never re-raising.
  Independently re-verified by reading `_review_plan.py:662-733`: `finalize()`'s only other
  pre-try-block call, `resolve_blocking_classes()`, is documented "Never raises." — confirmed by
  reading its docstring. There is no live path in current code that reaches the CLI-level
  `except ReviewError` with a `parse_verdict`-originated failure; the original premise (that this
  catch site silently misclassifies reviewer-origin errors) does not hold. The reviewer also
  flagged two supporting `[NIT:consistency]` findings, both independently verified: (1) the
  original scope item contradicted three already-passing tests in
  `test-review-plan-finalize-round.py` (`review-{plan,discussion,code}-finalize-outer-catch-error-kind-usage`,
  cases e/f/g) that mock `finalize()` to raise `ReviewError` directly and pin `error_kind ==
  "usage"` as the correct value for that exact catch site — confirming "usage" is the intended
  contract if that path were ever hit by a genuinely unexpected error, not a bug; (2)
  `test-review-cli-error-envelope.py` was wrongly cited as the "existing regression home for
  error_kind" — a full read confirms it contains zero `error_kind` assertions, covering only the
  exit-code contract; actual `error_kind` coverage lives in `test-review-cli.py` and the
  finalize()-wrapper-level assertions in `test-review-{plan,discussion,code}-flow.py`.
- Rejected: Keeping the scope item and instead trying to find some other production path that
  reaches the CLI-level catch — none was found, and inventing a defensive-only path to "fix" would
  add code for a case that cannot occur today.

## Technical context

- **Root function:** `_review_common.py::finalize_scope()` (currently around line 2530–2649).
  Runs, in order: `apply_actual_model_override` → `apply_cost_metadata` → `parse_verdict(raw_text)`
  (captured as `original_verdict`) → `extract_findings(raw_text)` → (when `blocking_classes` is
  not `None`) `apply_blocking_ceiling` + `rewrite_demoted_findings` → the verdict-recomputation
  block this task changes (currently lines ~2616–2624) → conditional
  `rewrite_verdict_token`/`append_demotion_note` → `write_review_file`.
- **The bug's exact location:** lines ~2616–2624 today:
  ```python
  verdict = original_verdict
  if verdict != "NEED_CONTEXT":
      verdict = "REQUEST_CHANGES" if blocking_count > 0 else "APPROVE"
  if demoted_any and verdict != original_verdict:
      raw_text = rewrite_verdict_token(raw_text, verdict)
  ```
  The unconditional `else "APPROVE"` is what silently downgrades a non-demoted
  `REQUEST_CHANGES`-with-zero-`BLOCKING` verdict. The `rewrite_verdict_token` call is correctly
  gated on `demoted_any`, but that gate doesn't stop the recompute above it from happening
  first — the file simply falls out of sync with the (still-forced) envelope value.
- **`demoted_any`** is computed from `apply_blocking_ceiling(findings, blocking_classes)` —
  `any(f.demoted for f in findings)`. It is `True` only when this specific finalize call's
  blocking-class ceiling actually converted at least one `BLOCKING` finding to a lower severity.
  A reviewer's own independent decision to write `REQUEST_CHANGES` despite zero `BLOCKING`
  headings never sets it.
- **Existing test home:** `plugins/mill/unit_tests/test-review-class-taxonomy.py` — already
  contains `test_verdict_token_rewritten_on_ceiling_flip`,
  `test_verdict_token_unchanged_when_no_demotion`,
  `test_verdict_token_unchanged_when_mismatched_without_demotion`,
  `test_verdict_token_rewritten_for_plan_and_code_types`,
  `test_demotion_note_appended_when_verdict_flips`,
  `test_demotion_note_appended_without_verdict_flip`, `test_demotion_note_absent_when_no_demotion`
  — all currently passing and must continue to pass unchanged after this fix. New tests for the
  non-demotion downgrade case belong alongside these.
  `test_verdict_token_unchanged_when_mismatched_without_demotion` is the one that locks in the
  escalation direction (`APPROVE` + real `BLOCKING`, no demotion → envelope
  `REQUEST_CHANGES`, file left stale) — this fix must not touch that test's expected outcome.
- **`error_kind` mechanism:** `_review_cli.py::print_error_envelope()` already accepts an
  `error_kind` kwarg (default `"usage"`), documented as `"usage"` for pre-reviewer failures vs
  `"reviewer"` for failures inside the reviewer's own finalize step. `ReviewError` itself
  (`_review_common.py:115`) is a flat `Exception` subclass with no origin-distinguishing
  subclasses — call sites are the only signal. Each `finalize()` wrapper (`_review_plan.py:662-733`
  and structurally identical in `_review_discussion.py`/`_review_code.py`) already catches its own
  `ReviewError` from `finalize_scope()` internally and returns `error_kind: "reviewer"` directly;
  it never propagates to the CLI-level catch. `test-review-plan-finalize-round.py` cases (e)/(f)/(g)
  already pin `error_kind == "usage"` as correct for the CLI-level finalize-stage catch itself
  (a mocked/hypothetical raise, since no live path currently reaches it). No change needed here —
  see Decisions, "Fourth candidate bug: rejected as unreachable".
- **`--actual-model` / `reviewer_model` threading (#867, already fixed):**
  `_review_common.py::apply_actual_model_override()` (~line 2430) delegates to
  `_inject_or_rewrite_yaml_field(raw_text, "reviewer_model", actual_model)`; wired through
  `finalize()` in each `_review_*.py` module via an `actual_model` kwarg, sourced from each CLI's
  `--actual-model` argument (e.g. `millpy-review-plan.py` line ~290,
  `args.actual_model`). `mill-go-base/SKILL.md`'s "## Agent-mode dispatch" section (around line
  360) already documents passing `--actual-model <dispatched-tier>` for all three review CLIs at
  the finalize call site.
- **Usage-error immediate halt (#864, already fixed):** `mill-plan/SKILL.md` step 4.5 (around
  line 491), `mill-start/SKILL.md`'s equivalent Discussion Review step 3.5, and the code-review
  equivalent in `mill-go-base/SKILL.md` all already check `reviews[].error_kind == "usage"` and
  halt immediately without consuming a review round, distinct from the two-consecutive-ERROR
  retry-then-halt path used for other `verdict:"ERROR"` rounds.

## Testing

- **`finalize_scope()` downgrade fix** (`test-review-class-taxonomy.py`): add a case with a
  reviewer response carrying `verdict: REQUEST_CHANGES` in both the yaml header and `## Verdict`
  section, zero `[BLOCKING]` headings, and `blocking_classes` covering all present finding
  classes (so `apply_blocking_ceiling` demotes nothing). Assert `result["verdict"] ==
  "REQUEST_CHANGES"` and the written file still contains `verdict: REQUEST_CHANGES` (both sides
  agree, no rewrite happened, no demotion note appended). Run this once per review type
  (discussion/plan/code) mirroring the existing
  `test_verdict_token_rewritten_for_plan_and_code_types` pattern, since the fix is in the shared
  function all three call through.
- **Non-regression for the two already-correct directions:** re-run (unchanged) the existing
  escalation test (`test_verdict_token_unchanged_when_mismatched_without_demotion`) and the
  existing demotion-driven downgrade tests
  (`test_verdict_token_rewritten_on_ceiling_flip`, `test_demotion_note_appended_when_verdict_flips`)
  to confirm the fix doesn't touch either path.
- **`mill-plan/SKILL.md` step 4c reachability:** not directly unit-testable (SKILL.md is
  interpreted by the orchestrating session, not executed code), but the fix should be verified by
  confirming the envelope shape 4c expects (`verdict: REQUEST_CHANGES`, `blocking_count: 0`) is
  now producible by `finalize_scope()` for a non-demoted round — covered by the test above.
- **#864/#867 regression coverage:** confirm or add (if genuinely absent —
  check `test-review-cli-error-envelope.py` and the `apply_actual_model_override` tests in
  `test-review-common.py` first, since they may already cover the exact repro shape) a test per
  issue: (a) `--stage finalize` without `--agent-output` → envelope `verdict: "ERROR"`,
  `error_kind: "usage"`, `round: 0`; downstream, this must be excluded from mill-plan's
  ERROR-only-aggregate retry counter (already SKILL-side, not re-tested here); (b) a
  `finalize()` call with `actual_model="fable"` on raw text whose self-reported
  `reviewer_model: opushigh` line differs → assert the written file's `reviewer_model:` reads
  `fable`, not `opushigh`.

## Q&A log

- **Q:** Fix direction for the core verdict-divergence bug (#891/#876/#865)? **A:** [auto-pick] Keep escalation safety net (blocking_count>0 -> REQUEST_CHANGES always) and existing demotion-driven downgrade unchanged, but stop force-downgrading a reviewer's own REQUEST_CHANGES-with-zero-blocking verdict to APPROVE when no ceiling demotion happened this call; preserve it verbatim in envelope and file. **Why:** Restores mill-plan/SKILL.md's already-written, currently-unreachable step 4c (REQUEST_CHANGES AND blocking_count==0), matching #891's explicit complaint, without disturbing the existing escalation-direction test coverage.
- **Q:** Should the fix land in shared `_review_common.py::finalize_scope()` or be scoped to plan review only? **A:** [auto-pick] Fix the shared `finalize_scope()`. **Why:** It's the single code path backing all three review CLIs (discussion/plan/code); the bug mechanism is not plan-specific, and CLAUDE.md documents this as the intentionally shared backend.
- **Q:** How to treat #864 (usage-error consumes a round) and #867 (reviewer_model records config alias), both of which read as already fixed by commit acdeab07 (2026-08-12), predating all five issues' filing timestamps? **A:** [auto-pick] Treat as already resolved; add/confirm regression-test coverage for both instead of re-implementing; note the pre-fix in discussion.md. **Why:** Code read confirms `error_kind="usage"` is already correct for the missing-`--agent-output` path, and `--actual-model` threading into `reviewer_model` is already wired end-to-end with SKILL-side passthrough documented in mill-go-base/SKILL.md; the filing repos were almost certainly on a stale cached plugin build.
- **Q:** Include the unfiled adjacent bug (all three review CLIs default `error_kind` to "usage" for any caught `ReviewError`, including genuine reviewer-side parse failures that should be "reviewer") in this task's scope? **A:** [auto-pick] Yes, include it. **Why:** Same code family and call sites the core fix already touches; mill-plan's new usage-error immediate-halt (from the same commit that addressed #864) turns a transient reviewer hiccup into a no-retry operator halt when misclassified, which is a real correctness gap in the exact mechanism #864 established.
- **Q:** Does NEED_CONTEXT verdict handling need reconsideration as part of this fix? **A:** [auto-pick] No, leave NEED_CONTEXT passthrough unchanged. **Why:** Orthogonal signal (missing context, not pass/fail judgment), already correctly excluded from the blocking_count-derivation branch; out of scope.
- **Q:** Scope of the `error_kind` misclassification fix -- finalize-stage catches only, or a broader audit of every `except ReviewError` site? **A:** [auto-pick] Finalize-stage catches only, in all three review CLIs (`error_kind="reviewer"` instead of the default `"usage"`). **Why:** Traced the finalize-stage try block in `millpy-review-plan.py` (and the structurally identical discussion/code CLIs): the only `ReviewError` reachable there originates from `parse_verdict()` inside `finalize()`/`finalize_scope()` -- genuinely reviewer-origin, since the explicit `--agent-output`-missing usage check already short-circuits before the try block. Prepare-stage and full-stage catches wrap config/validation/batch-resolution logic that is genuinely usage-origin and stays "usage".
- **Q:** Testing approach for the core fix and the error_kind fix? **A:** [auto-pick] Extend existing test files rather than create new ones: add cases to `test-review-class-taxonomy.py` (reviewer REQUEST_CHANGES + zero BLOCKING + no demotion -> envelope and file both stay REQUEST_CHANGES; companion regression test locking in the existing escalation direction unchanged) and to `test-review-cli-error-envelope.py` (finalize-stage ReviewError -> error_kind="reviewer", per CLI or shared if structurally identical). **Why:** `test-review-class-taxonomy.py` is already the home of the adjacent `test_verdict_token_*`/`test_demotion_note_*` tests this bug sits next to; extending keeps related coverage co-located per existing repo convention rather than fragmenting it across new files. (Note: the `test-review-cli-error-envelope.py` half of this answer was later corrected -- see the round-1 gap-fix Q&A entry below; that file does not cover `error_kind` at all, and the error_kind scope item it was meant to test was dropped entirely.)
- **Q:** [gap, round 1] Discussion review round 1 (holistic, sonnethigh) found `[BLOCKING:design]` that the fourth-bug scope item's premise is false -- the CLI-level `except ReviewError` catch site it targeted is unreachable in production, since each `finalize()` wrapper already catches `ReviewError` from `finalize_scope()` internally and returns `error_kind: "reviewer"` directly without re-raising. Two supporting `[NIT:consistency]` findings: the item contradicted three already-passing tests pinning `error_kind == "usage"` as correct for that exact (unreachable-in-practice) catch site, and cited the wrong file as the "existing regression home for error_kind" (that file has zero error_kind coverage). How to resolve? **A:** [auto-pick] Drop the fourth-bug scope item entirely from Problem/Scope/Decisions/Technical context/Testing; treat it like #864/#867 (investigated, found already correct, no code change). **Why:** Independently re-verified the reviewer's claim by reading `_review_plan.py:662-733` directly (confirmed the internal catch-and-return, never-re-raise pattern) and confirmed `resolve_blocking_classes()` is documented "Never raises."; also confirmed both NIT citations by grepping the two test files directly. All three findings are factually accurate per the mill-receiving-review VERIFY step, and fixing means removing incorrect scope rather than risking any working code — no HARM CHECK objection applies. This is the "recommended option" auto-picked per mill-start --auto's gap-resolution rule (BLOCKING findings are always FIX under --auto, PUSH BACK is unavailable with no operator present).
