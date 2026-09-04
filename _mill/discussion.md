# Discussion: millpy-review-plan: verdict/envelope disagreement and reviewer_model mis-recording

```yaml
task: millpy-review-plan: verdict/envelope disagreement and reviewer_model mis-recording
slug: review-plan-verdict-envelope-model-bugs
status: discussing
parent: main
```

## Problem

The wiki task was folded from six closed GitHub issues (#963, #922, #924, #912, #910, #949), reporting what looked like three duplicate/related bug classes in the mill review pipeline:

- **Bug A** (#963, #922) — `reviewer_model:` in a finalized review file records the config-resolved model tier, never the model actually dispatched, so an operator override (or a dispatch that silently inherits the wrong tier) is mis-recorded on disk.
- **Bug B** (#924, #912, #910) — a finalized review file's own `verdict:` (yaml frontmatter and `## Verdict` prose) can disagree with the JSON envelope's blocking-count-derived `verdict`, so a human reading the raw file sees a contradiction the orchestrator never acted on.
- **Bug C** (#949) — `review-plan-holistic.md` (and the batch variant) never requires a reviewer's claim about how the *target repo's production code* behaves to be source-verified and cited. A wrong mechanism claim was adopted into a plan and survived three rounds before a different reviewer caught it.

**Why now / what changed:** during Phase: Explore, reading `_review_common.py`'s current `finalize_scope` (not the stale issue text) plus `git log` showed bugs A and B are **already fixed** on this branch's base (`main`), by earlier, unrelated work:

- Bug A: `apply_actual_model_override` + the `--actual-model` finalize flag (issue #644; commits `feeab63e`, `5ffeefc8`, `d4db7253`, `a80876b5`, `1d09998d`, `82f4d80e`), wired into the shared Agent-mode dispatch pattern in `mill-go-base/SKILL.md` (line 361: "For the three **review** CLIs specifically, additionally pass `--actual-model <value>`...") that mill-start, mill-plan, and mill-go all follow.
- Bug B: `finalize_scope`'s `demoted_any`-gated verdict logic (commit `12916293`, "millpy-review-plan: finalize envelope verdict silently diverges from the review file's own written verdict"). The fix direction is the opposite of what the issues suggested (rewrite the file to match a forced-APPROVE envelope): instead, when `blocking_count == 0` and *this call's* blocking-class ceiling demoted nothing (`demoted_any is False`), the envelope now **preserves the reviewer's own verdict** unchanged rather than forcing `APPROVE` — so file and envelope stay naturally consistent without a rewrite. Covered by `test_verdict_preserved_when_reviewer_writes_request_changes_with_zero_blocking` and `test_verdict_preserved_for_plan_and_code_types` in `test-review-class-taxonomy.py` (both pass on this branch).

The six issues were closed as "Consolidated into wiki task" (folding bookkeeping), not as "fixed" — so their CLOSED state carries no signal either way; the fix commits are independent, unrelated work that landed on `main` before this task branched.

This narrows the task to **bug C only**: add a mechanism-claim source-verification requirement to the plan-review reviewer prompts.

## Scope

**In:**
- Add a new paragraph to the `## Source-grounding rule` section of `plugins/mill/templates/review-plan-holistic.md` and `plugins/mill/templates/review-plan-batch.md` (byte-identical section in both today), requiring that any finding resting on a claim about the target repo's production-code mechanism (which branch executes, what a predicate selects, which value survives a mutation) name the file and function/method/construct it was verified against, and that an unverifiable claim be downgraded to a question (`## Missing context`) or dropped rather than asserted as fact.
- Extend `test_plan_criteria_bullets_present` (or add a sibling assertion) in `plugins/mill/unit_tests/test-review-templates.py` to assert the new rule text is present verbatim in both templates, following the existing pattern used for the "Platform-behavior-claim verification" bullet.

**Out:**
- Any code change for bugs A or B — confirmed already fixed and tested; no regression tests need adding beyond what already exists (`test-review-class-taxonomy.py` covers both).
- Extending the new rule to `review-discussion.md` or the code-review templates (`review-code-*.md`) — #949 asked only for the plan-review templates, and the rationale (a plan holds a mechanism claim as fact across multiple rounds with no line-level grounding) doesn't transfer: code review grounds directly against real diffs, and discussion review concerns design intent rather than production-mechanism assertions.
- Any schema/parser change (e.g. a structured `**Verified:**` finding field, machine-enforced). This is prompt-only discipline, matching the one existing precedent in the same section (`Platform-behavior-claim verification`, also prompt-only).
- The two pre-existing, unrelated unit test failures observed on this branch's base (`test-review-plan-flow.py::test28` — an `ActiveWorktreeSlugMismatch` triggered by this environment's `hanf/...`-prefixed branch naming; `test-mill-go-base-agent-only.py` — a banned-literal regression guard already failing against current `mill-go-base/SKILL.md` content). Neither is caused by, or fixable within, this task's scope.

## Decisions

### bugs-a-b-already-fixed

- Decision: do not touch `_review_common.py`'s `apply_actual_model_override` / `finalize_scope` verdict logic, and do not add new tests for bugs A/B beyond what already exists.
- Rationale: both fixes are present in the current worktree's source, wired through every orchestrator (mill-start/mill-plan/mill-go share the same Agent-mode dispatch pattern), and covered by passing unit tests. Re-implementing would be redundant work against a problem that no longer exists.
- Rejected: re-verifying with new dedicated tests "just in case" — the existing coverage (`test_verdict_preserved_when_reviewer_writes_request_changes_with_zero_blocking`, `test_verdict_preserved_for_plan_and_code_types`, plus the `#644` actual-model test suite) already exercises exactly these scenarios for discussion/plan/code review types.

### mechanism-claim-rule-scope

- Decision: add the new rule to `review-plan-holistic.md` and `review-plan-batch.md` only.
- Rationale: matches #949's explicit ask; plan review is uniquely exposed because a mechanism claim gets baked into the plan as accepted fact and re-read by later rounds and the implementer, with no line-level code in front of the reviewer to ground against directly. Code review reviews the actual diff, so a wrong mechanism claim is naturally harder to sustain unnoticed.
- Rejected: extending to discussion/code review templates for "consistency" — no reported failure there, and would be scope creep against a narrowly-described bug.

### mechanism-claim-rule-placement

- Decision: append the new rule as a paragraph inside the existing `## Source-grounding rule` section, not as a new bullet under `## Criteria`.
- Rationale: the failure mode is the *reviewer's own* unverified claim (an epistemic-honesty problem — "Never guess"), not a criterion for judging the plan's text. `## Source-grounding rule` already owns exactly this contract for the NEED_CONTEXT/file-manifest case; extending it keeps all of the reviewer's own evidentiary obligations in one place. A `## Criteria` bullet (like `Platform-behavior-claim verification`) instead judges whether the *plan* made an unverified claim that the reviewer should have caught — a different, narrower shape that doesn't fit "the reviewer itself asserted something false."
- Rejected: a new `## Criteria` bullet, or both — would split one coherent rule (reviewer must ground its own claims) across two sections with different audiences/framing.

### mechanism-claim-rule-enforcement

- Decision: prompt-only discipline. The citation must appear inline in the finding's own text (file + construct); no schema, parser, or `extract_findings` change.
- Rationale: matches #949's own suggested fix and the one existing precedent in the same templates (`Platform-behavior-claim verification`, also enforced by instruction only, not by machine-checking). Reliably machine-verifying a free-text citation (does the named file actually contain the named construct, does it actually support the claim) is a much larger undertaking than this bug warrants, and none of the other five bugs in this task's originating cluster needed schema changes either.
- Rejected: a structured `**Verified:** <file>:<construct>` field enforced in `extract_findings` — real capability, but disproportionate scope for a prompt-wording gap.

## Technical context

- `plugins/mill/templates/review-plan-holistic.md` and `review-plan-batch.md`: the two plan-review reviewer prompt templates. Their `## Source-grounding rule` sections (holistic: lines 16–25; batch: lines 17–26) are byte-identical today — copy the new paragraph into both, verbatim.
- `plugins/mill/scripts/_review_common.py`:
  - `build_tool_rule(mode, agent_mode)` (~line 1415) returns one of four `<TOOL_RULE>` blocks. Only the two tool-use variants (`_TOOL_RULE_TOOL_USE`, `_TOOL_RULE_TOOL_USE_AGENT`) grant `Read`/`Grep`/`Glob` for verifying claims against source; the two bulk variants explicitly forbid requesting any tool call ("All content you need is in this prompt."). This matters for the new rule's wording: a bulk-mode reviewer has no way to verify a claim against a file that wasn't bulked into its prompt, so "downgrade to a question rather than assert" is the only honest option available to it in that mode — the rule text must not imply the reviewer can always go look something up.
  - `finalize_scope` (~line 2530) is the already-fixed function for bug B; not touched by this task.
  - `apply_actual_model_override` (~line 2430) is the already-fixed function for bug A; not touched by this task.
- `plugins/mill/unit_tests/test-review-templates.py`: `test_plan_criteria_bullets_present` (line 126) is the existing precedent — asserts specific bullet text is present verbatim in both plan templates' raw source. Follow this exact pattern for the new rule (either extend this test or add a sibling assertion next to it).
- The reviewer configured for this hub's `roles.plan-review.holistic` is `sonnethigh` (`max_review_rounds: 7`, `min_review_rounds: 1`); not relevant to the fix itself, just context for what will actually exercise the new rule text in this repo's own future plan reviews.

## Testing

- `plugins/mill/unit_tests/test-review-templates.py`: extend `test_plan_criteria_bullets_present` (or add a new sibling test) to assert the new mechanism-claim-verification paragraph's key phrase is present verbatim in both `review-plan-holistic.md` and `review-plan-batch.md`. This is the only automated coverage possible — the rule's actual effect (does a reviewer LLM behave differently) cannot be unit-tested, matching how `Platform-behavior-claim verification` has no behavioral test either.
- No other test changes. Bugs A and B need no new tests (see Decisions — existing coverage already exercises them).
- Before handoff, run the full `plugins/mill/unit_tests/run-all.py` suite and confirm the only failures are the two pre-existing/unrelated ones identified in Scope → Out (`test-review-plan-flow.py::test28`, `test-mill-go-base-agent-only.py`) — any other new failure means the template edit broke something and must be investigated.

## Q&A log

- **Q:** Bugs A and B (reviewer_model mis-recording; verdict/envelope mismatch) — already fixed on this branch, or still need work? **A:** [auto-pick] Confirm already fixed; scope this task to bug C only, document the verification as evidence. **Why:** git history (`feeab63e`…`82f4d80e` for #644; `12916293` for the verdict fix) plus current `_review_common.py` source plus passing dedicated unit tests all confirm both are resolved; redoing the work would be pure waste.
- **Q:** Which templates get the new mechanism-claim source-verification rule? **A:** [auto-pick] Only `review-plan-holistic.md` + `review-plan-batch.md`. **Why:** matches #949's explicit ask; code review already grounds against real diffs, discussion review concerns design intent rather than production-mechanism assertions.
- **Q:** Where does the new rule live — `## Source-grounding rule` or a new `## Criteria` bullet? **A:** [auto-pick] Append to `## Source-grounding rule`. **Why:** the failure is the reviewer's own unverified claim (an epistemics problem), matching that section's existing "Never guess" framing exactly; a `## Criteria` bullet would instead judge the plan's text, a different shape.
- **Q:** Enforcement — prompt-only discipline, or a structured/machine-checked `**Verified:**` field? **A:** [auto-pick] Prompt-only. **Why:** matches #949's own suggested fix and the one existing precedent (`Platform-behavior-claim verification`) in the same file, also prompt-only; a machine-checked citation field is disproportionate scope for a prompt-wording gap.
