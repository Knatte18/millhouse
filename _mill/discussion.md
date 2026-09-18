# Discussion: Review output reliability: metadata misattribution and factual-accuracy failures

```yaml
task: Review output reliability: metadata misattribution and factual-accuracy failures
slug: review-output-reliability-and-attribution-bugs
status: discussing
parent: main
```

## Problem

Four incidents (GitHub issues #1018, #1003, #991, #989 — all closed and consolidated into this
task) show the Layer 02 review system producing review output that is either misattributed
(records the wrong model as having produced it) or factually wrong about the artefact it reviewed
(miscounts characters, contradicts a golden file's actual bytes). Both failure modes cost real
orchestrator time: a wrong `reviewer_model` breaks `/mill-review-summary` and any audit trail, and
a factually-wrong BLOCKING finding forces a fixer to push back twice and an operator to manually
re-verify before the loop can proceed. This task closes each of the four gaps at the root — three
require template/doc changes, and one (#1018) turns out, on reading the current code, to already
be fixed.

## Scope

**In:**
- Remove the free-text `reviewer_self_id` field from every review template and from the schema doc
  (fixes #989).
- Extend the existing "Mechanism claims must be source-verified" source-grounding rule — already
  present in the two plan-review templates — to the two code-review templates (fixes #991 and
  #1003, which are both code-review incidents of the same defect class: a confidently-worded
  finding asserting a fact about file content that the reviewer did not actually verify against
  the bulked text).
- Update/extend the corresponding unit tests in `test-review-common.py` and
  `test-review-templates.py` to match.
- Document, in this file, the verification that #1018's underlying mechanism (`reviewer_model`
  attribution under an operator-directed agent-mode tier override) is already correctly
  implemented, tested, and wired into every orchestrator SKILL that dispatches a reviewer —  no
  code change for #1018.

**Out:**
- Any change to the `--actual-model` / `apply_actual_model_override()` mechanism itself — verified
  correct (see Decisions).
- A harness-side mechanical fact-checker (e.g. a regex that detects SHA-shaped strings in a
  finding and cross-checks their length/charset against the bulked source) — #1003's issue text
  raises this as one option ("consider..."), but it is new detection machinery, not a fix to an
  existing gap, and the same defect class (#991) is not SHA-specific — a generic
  "verify against the text in front of you" prompt rule already covers both. See Decisions
  for the full YAGNI rationale.
- `review-discussion.md`'s source-grounding rule — none of the four issues report a
  discussion-review factual-accuracy incident, so extending the mechanism-claim rule there is out
  of scope. (`review-discussion.md` does lose `reviewer_self_id`, since that field removal is
  reported directly against it by #989.)
- `millpy-review-summary.py` — already reads only `reviewer_model`, never `reviewer_self_id`
  (confirmed by reading the source); no change needed.

## Decisions

### reviewer-self-id-removed

- Decision: Delete the `reviewer_self_id:` field and its accompanying prompt instruction
  ("Independently state, in the `reviewer_self_id:` field below, what model/version you believe
  yourself to be…") from all three templates that currently carry it:
  `plugins/mill/templates/review-discussion.md` (line ~39, ~64),
  `plugins/mill/templates/review-plan-holistic.md` (line ~85, ~107),
  `plugins/mill/templates/review-plan-batch.md` (line ~85, ~107).
  `review-code-holistic.md` and `review-code-batch.md` never had the field — nothing to remove
  there. Also update `plugins/mill/templates/review-output.schema.md`'s "Metadata block fields"
  section: remove the `reviewer_self_id` row from the field table, and edit — not delete — the
  explanatory paragraph at line ~59. That paragraph is two sentences sharing one line: the first
  ("`reviewer_self_id` is unverified and reviewer-reported…own best-effort claim about what
  model/version it is…") is entirely about the removed field and must go; the second ("This is
  distinct from `reviewer_model`, which is orchestrator-supplied… and which
  `apply_actual_model_override()`… can rewrite after the fact.") documents `reviewer_model` /
  `apply_actual_model_override()` and stays — reworded to stand alone as its own sentence (it no
  longer needs "this is distinct from" framing once there is nothing left to distinguish it from),
  e.g. "`reviewer_model` is orchestrator-supplied — dictated to the reviewer up front — and
  `apply_actual_model_override()` (invoked via the CLIs' `--actual-model` flag) can rewrite it
  after the fact." Delete only the first sentence; keep and reword the second. This is the only
  place in the schema doc that documents `apply_actual_model_override()`'s role, so a whole-
  paragraph deletion would silently lose that.
- Rationale: #989's own repro showed the same fixed reviewer alias giving five different
  self-identifications across five rounds, one naming the wrong model generation outright — the
  field is asking an LLM to introspect something it structurally cannot observe reliably.
  `reviewer_model` already does the job #989 wants `reviewer_self_id` to do, correctly: it is
  orchestrator-supplied (from the resolved config alias at prepare time, or corrected via
  `--actual-model` at finalize time when the operator dispatched a different tier — see
  `apply_actual_model_override()` in `_review_common.py` and every review SKILL's Agent-mode
  dispatch step 5), not reviewer-self-reported. #989's own suggested fix is "populate the field
  from the dispatch envelope… or drop it in favour of the existing `reviewer_model` field, which
  was correct in all five rounds" — since `reviewer_model` already *is* dispatch-envelope-sourced,
  dropping the redundant, unreliable field is the more direct of the two suggested fixes, and
  avoids inventing new plumbing to populate a field that would then duplicate `reviewer_model`
  exactly.
- Rejected: Populating `reviewer_self_id` from the dispatch envelope instead of dropping it. This
  was #989's alternative suggestion, but it would make `reviewer_self_id` and `reviewer_model`
  carry identical, always-equal values — a second column with no information the first doesn't
  already have. Dropping is simpler and removes the field's live footgun (an LLM writing a wrong
  or hedging self-assessment into a permanent review file) rather than just making the footgun
  redundant.
- Compatibility note: historical review files already on disk that carry a `reviewer_self_id:`
  line are untouched by this change — nothing parses or validates that field today
  (`parse_verdict()` only reads `verdict:`), so an old file with the line still present remains
  fully readable. This is a "stop emitting it going forward" change, not a migration.

### code-review-mechanism-claim-rule

- Decision: Add the same "Mechanism claims must be source-verified." paragraph already present in
  `review-plan-holistic.md` and `review-plan-batch.md` (added by commit `fbf501ea`, 2026-09-04,
  under `## Source-grounding rule`, immediately after the existing "Never guess." paragraph) to
  `plugins/mill/templates/review-code-holistic.md` and `plugins/mill/templates/review-code-batch.md`,
  in the same position (their own `## Source-grounding rule` sections already exist and already end
  with "Fabricating file contents — or inferring them from filename / position alone — is a worse
  failure than halting honestly." — insert the new paragraph directly after that line, matching the
  plan templates' placement exactly). Reuse the paragraph text verbatim — do not reword it — so
  `test_plan_mechanism_claim_rule_present`-style substring assertions can extend cleanly to the code
  templates.
- Rationale: #991 (holistic code review, `mcp-thin` task) and #1003 (holistic code review,
  `ladder-kickstart` task) are both cases of a code reviewer asserting a specific, checkable fact
  about file content — "this key is absent from lines 6-10", "this SHA is 39 not 40 characters" —
  that turned out to be false on the file's actual bytes. This is exactly the defect class the
  mechanism-claim rule was written to close for plan review (#949, per the rule's own docstring
  reference), just observed here in the review type that doesn't have the rule yet. The rule's
  wording ("must name the file and the function/method/construct it was verified against"; "if you
  cannot verify the claim against source in your context… do not assert it") generalizes cleanly:
  a character-count claim about a SHA string and a key-presence claim about a JSON golden file are
  both "claims about the target artefact's actual bytes" in exactly the sense the rule already
  covers — no code-review-specific wording is needed beyond reusing the existing paragraph.
- Rejected: A harness-side mechanical SHA/hex-string length-and-charset checker that runs against
  reviewer findings before they're surfaced as BLOCKING. Rejected for three reasons: (1) it only
  addresses #1003's SHA case, not #991's "key absent from a JSON file" case — the two issues share
  one root cause (an ungrounded factual claim) and the prompt-level fix already closes both with one
  paragraph reused from existing repo precedent; (2) it requires new detection code (regex-matching
  SHA-shaped substrings inside free-text findings, correlating them back to a specific bulked file)
  that has no existing analogue anywhere in `_review_common.py` today — every other "which finding is
  well-formed" check in this repo (severity vocabulary, class taxonomy) validates structure, not
  semantic content; (3) YAGNI — the issue text itself only says "consider" this as one option, and
  the repo's own established response to this exact defect class (#949 -> the plan-review
  mechanism-claim rule) was prompt discipline, not mechanical verification. If prompt discipline
  proves insufficient after this change ships, mechanical verification is a reasonable follow-up,
  but there is no evidence yet (a single fixed rule has not been tried in code review) that it's
  needed.

### reviewer-model-attribution-already-fixed

- Decision: No code change for #1018. Document the verification here instead.
- Rationale: #1018 reports that `millpy-review-plan.py --stage finalize` records `reviewer_model`
  from the configured alias rather than the actually-dispatched agent-mode reviewer, and that
  "mill-plan/SKILL.md's agent-mode branch documents no way to thread a per-invocation reviewer
  override at all… there is no equivalent [to the subprocess branch's `--reviewer`] for the
  agent-mode dispatch". Reading the current code (not trusting the issue text, per this repo's own
  CLAUDE.md rule to verify against the task-worktree source) shows this claim is no longer
  (and, on the dates involved, may never have been) accurate for this codebase:
  - `_review_common.py` (`apply_actual_model_override()`, `finalize_scope()`) has taken an
    `actual_model` parameter that rewrites the persisted `reviewer_model:` line since commit
    `1d09998d` ("feat(review-cli): add --actual-model finalize flag for code/plan/discussion
    review (#644)"), dated **2026-07-16** — a full seven weeks before #1018's incident
    (**2026-09-08**).
  - `plugins/mill/skills/mill-go-base/SKILL.md`'s shared "## Agent-mode dispatch" pattern (step 5,
    "Run finalize stage") already instructs: *"For the three **review** CLIs specifically,
    additionally pass `--actual-model <value>` using the model value… actually passed to this
    round's Agent tool call… this keeps the finalized review file's `reviewer_model` field accurate
    even when the Builder dispatched a different tier than the prepare envelope's `model` field
    named (a manual override)."* This text (and step 2's companion instruction to record "the
    `model` value actually passed to this Agent tool call" whenever "the operator explicitly
    instructs a different tier for this specific dispatch") predates the incident too (commit
    `6cda129c`, **2026-08-11**).
  - `mill-plan/SKILL.md`'s Phase: Plan Review dispatches `millpy-review-plan.py` by explicitly
    following "the Agent-mode dispatch pattern (see `## Agent-mode dispatch` in
    `mill-go-base/SKILL.md`)" for both the initial round and every re-fire round — it does not
    define a competing dispatch path that could skip the `--actual-model` step. mill-start and
    mill-go route through the identical shared pattern for their own reviewer dispatches.
  - `plugins/mill/unit_tests/test-review-finalize.py` carries dedicated round-trip tests —
    `test_review_plan_finalize_actual_model_overrides_reviewer_model_line` and
    `test_review_plan_finalize_omitted_actual_model_leaves_reviewer_model_unchanged` (plus the
    discussion/code equivalents) — asserting the CLI flag correctly overwrites (or correctly
    leaves untouched) the written `reviewer_model:` line. These pass today.
  - `millpy-review-summary.py` reads `reviewer_model` only (line ~138) — no separate path that
    could re-derive an attribution from something else.
  Given the flag, the finalize wiring, every orchestrator SKILL's dispatch instructions, and the
  regression tests are all already in place and all predate the reported incident, the most likely
  explanation is that the specific live session behind #1018 did not correctly follow its own
  already-documented SKILL instructions in the moment (a one-off execution slip by that session,
  not a residual defect in the mechanism itself) — SKILL-text discipline has no code-level
  enforcement that would catch an orchestrator session skipping a step. There is nothing further to
  build: the mechanism this issue asks for already exists, is already wired everywhere it needs to
  be, and is already tested.
- Rejected: Adding code-level enforcement (e.g. `--stage finalize` warning or failing when
  `--actual-model` is omitted under agent-mode dispatch) to guard against a *future* orchestrator
  session skipping the already-documented step. Rejected per YAGNI — this is speculative hardening
  against a failure mode with exactly one observed occurrence, predating both the flag's finalize
  wiring and its SKILL-level dispatch instructions being tested and in place; it is not something
  any of the four source issues actually asks for, and the CLI cannot reliably distinguish
  "operator genuinely used the configured tier, no override needed" from "orchestrator forgot to
  pass the flag" without additional signal it doesn't have.

## Technical context

Layer 02 review system, `plugins/mill/scripts/`:
- `_review_common.py` — shared helpers; `apply_actual_model_override()` (~line 2587),
  `finalize_scope()` (~line 2694), `write_review_file()`, `parse_verdict()`.
- `_review_discussion.py`, `_review_plan.py`, `_review_code.py` — per-type backends; each threads
  `actual_model` through to `finalize_scope()`.
- `millpy-review-discussion.py`, `millpy-review-plan.py`, `millpy-review-code.py` — CLIs; each
  exposes `--actual-model` (finalize-stage only) per its own `argparse` block.
- `millpy-review-summary.py` — reads `reviewer_model` from each review file's yaml block (~line
  138); does not read `reviewer_self_id`.

Templates, `plugins/mill/templates/`:
- `review-discussion.md`, `review-plan-holistic.md`, `review-plan-batch.md` — currently carry
  `reviewer_self_id:` (field + prompt instruction); to be removed.
- `review-plan-holistic.md`, `review-plan-batch.md` — currently carry the "Mechanism claims must be
  source-verified." paragraph under `## Source-grounding rule`; unchanged, used as the copy source.
- `review-code-holistic.md`, `review-code-batch.md` — currently lack the mechanism-claim paragraph;
  to receive it, appended directly after their existing "Fabricating file contents…" sentence.
- `review-output.schema.md` — documents `reviewer_self_id` in the field table (~line 19, ~55) and in
  an explanatory paragraph (~line 59); table row to be removed, and the paragraph's first sentence
  (the `reviewer_self_id` explanation) deleted. The same paragraph's second sentence documents
  `apply_actual_model_override()`'s role — that content is already accurate and stays, reworded to
  stand alone as its own sentence per the `reviewer-self-id-removed` Decision above; it is not a
  net "no change" to the line, only to that sentence's content.

Orchestrator SKILLs (read-only verification, no edits expected):
- `plugins/mill/skills/mill-go-base/SKILL.md` — `## Agent-mode dispatch`, step 5 (~line 351-363):
  the shared `--actual-model` threading instruction every review dispatch across mill-start,
  mill-plan, mill-go, and mill-go2 relies on.
- `plugins/mill/skills/mill-plan/SKILL.md` — Phase: Plan Review, steps referencing "the Agent-mode
  dispatch pattern" for `millpy-review-plan.py` (~line 432, ~517).

Unit tests, `plugins/mill/unit_tests/`:
- `test-review-common.py` — two tests specific to `reviewer_self_id` round-trip preservation
  (~line 737 "apply_actual_model_override leaves reviewer_self_id line untouched", ~line 852
  "write_review_file preserves reviewer_self_id line verbatim"); these were written for a field
  this task deletes.
- `test-review-templates.py` — `test_plan_mechanism_claim_rule_present` (~line 142) currently
  asserts the mechanism-claim paragraph is present in `["review-plan-holistic", "review-plan-batch"]`
  only; `test_deleted_prose_stays_deleted` / `test_kept_prose_stays_kept` are the established
  pattern (lines 90-123) for "this phrase must/must not appear in template source" assertions this
  task's `reviewer_self_id` removal should follow.
- `test-review-finalize.py` — already-passing `--actual-model` round-trip tests (discussion/plan/code)
  cited as evidence in the reviewer-model-attribution-already-fixed Decision; no change expected.

## Constraints

No `CONSTRAINTS.md` present at the hub root.

## Testing

- **`test-review-templates.py`:**
  - Extend `test_plan_mechanism_claim_rule_present` (or add an analogous new test) so the
    "Mechanism claims must be source-verified." substring assertion also covers
    `review-code-holistic` and `review-code-batch` — mirroring how the existing test already covers
    both plan templates.
  - Add a `reviewer_self_id`-absence assertion, following the `test_deleted_prose_stays_deleted`
    pattern: assert `"reviewer_self_id"` is absent from the source of `review-discussion`,
    `review-plan-holistic`, and `review-plan-batch` (the three templates the field is removed
    from). Do not assert absence for `review-code-holistic`/`review-code-batch` as a new claim —
    they never had the field, so there is nothing to regress-test there beyond the existing
    render/token tests already covering all five templates.
  - `test_all_templates_render` already re-renders every template with a fixed token set — it will
    catch a stray leftover `<REVIEWER_SELF_ID>`-shaped token or a broken heading structure for free;
    no new token needs to be added or removed, since `reviewer_self_id` was free prose inside the
    template, never a `render_prompt()` keyword token.
- **`test-review-common.py`:** Remove (not merely rename) the two `reviewer_self_id`-specific
  round-trip tests (~line 737, ~line 852) — they exist purely to lock in preservation behaviour for
  a field this task deletes from every template that emits it. If generic "an unrecognized yaml
  field survives `write_review_file`/`apply_actual_model_override` untouched" coverage is judged
  independently valuable, write it as a new test using a clearly generic field name (e.g.
  `custom_note:`), not by keeping the old test under its old name — the old test's name and
  docstring are specifically about the now-removed field.
- **`test-review-finalize.py`:** No changes needed — already exercises `--actual-model` end to end
  for discussion/plan/code and is cited as evidence that #1018's mechanism works; re-running it as
  part of this task's own verify step reconfirms nothing regressed.
- No new runtime/integration test is needed for the reviewer-model-attribution-already-fixed
  Decision — it is a verification-only finding with no code change to test.

## Q&A log

- **Q:** Should `reviewer_self_id` be removed outright, or repointed to read from the dispatch
  envelope (issue #989's second suggested option)? **A:** [auto-pick] Remove it outright. **Why:**
  `reviewer_model` already is dispatch-envelope-sourced (via `--actual-model`); populating
  `reviewer_self_id` identically would just duplicate that column under a different name with no
  new information, while removal also eliminates the live footgun of an LLM writing an
  unreliable/wrong self-assessment into a permanent file.
- **Q:** For #1003's SHA-miscounting incident, should the harness mechanically verify SHA-shaped
  claims (the issue's own suggestion), or should this task rely on prompt-level discipline (the
  fix already used for the same defect class in plan review)? **A:** [auto-pick] Prompt-level
  discipline — extend the existing "Mechanism claims must be source-verified" rule to code review
  templates. **Why:** it is the repo's own established fix for this exact defect class (#949), it
  covers both #991 and #1003 with one reused paragraph, and a bespoke mechanical SHA checker would
  address only one of the two incidents while adding a new, untested detection mechanism with no
  precedent elsewhere in `_review_common.py`.
- **Q:** #1018 asks for `reviewer_model` to be corrected under an agent-mode operator override.
  Reading `_review_common.py`, `mill-go-base/SKILL.md`, and `test-review-finalize.py` shows the
  `--actual-model` flag, its SKILL-level dispatch instructions, and its regression tests already
  exist and predate the reported incident. Should this task still build something for #1018, or
  document the verification and change nothing? **A:** [auto-pick] Document the verification; no
  code change. **Why:** per this repo's own CLAUDE.md rule that reading the actual current
  task-worktree source takes priority over trusting the issue text when they conflict — and here
  they do conflict, since the issue's own "Related gap" paragraph describes a gap the current code
  does not have. Building speculative code-level enforcement against a hypothetical future
  SKILL-instruction-skipping session is out of scope per YAGNI; none of the four source issues asks
  for it.
