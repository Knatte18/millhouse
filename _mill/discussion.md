# Discussion: mill-plan: Phase Plan Review's 4b/4c/4d re-validate gate says "7 kwargs", drops done_gate

```yaml
task: mill-plan: Phase Plan Review's 4b/4c/4d re-validate gate says "7 kwargs", drops done_gate
slug: mill-plan-done-gate-kwargs-count-drift
status: discussing
parent: main
```

## Problem

`plugins/mill/skills/mill-plan/SKILL.md` is internally inconsistent about the `_plan_validate.run` call signature it instructs the orchestrator to use.

Phase: Plan's own self-validate code block (SKILL.md lines 271-283) passes **eight** keyword arguments — `root`, `git_root`, `wiki_root`, `skip_checks`, `parent_branch`, `max_cards_per_batch`, `max_batch_context_tokens`, `done_gate` — and the surrounding prose (line 251) explicitly says "same eight keyword arguments" and lists all eight.

But Phase: Plan Review's steps 4b (line 565), 4c (line 581), and 4d (line 597) each instruct the orchestrator to re-run `_plan_validate.run` with "the identical 7 keyword arguments" / "the same 7 kwargs", and each enumeration omits `done_gate`. In a hub where `mill-config.yaml`'s `pipeline.done_gate` is set, an orchestrator following 4b/4c/4d's prose literally would call the full-validate re-run without `done_gate` — a silently narrower validation gate than the one Phase: Plan's own self-validate call already ran, at exactly the point (post fix-pass) where re-validation matters most.

This consolidates 7 duplicate GitHub issues (#1039, #1034, #1021, #1016, #1014, #1009, #1002), all reporting the identical drift between Phase: Plan's 8-kwarg call and Phase: Plan Review's 7-kwarg prose.

**Why now:** every one of these duplicate reports is the same doc-consistency bug re-discovered independently across 7 separate task runs — the drift is real and keeps costing review cycles until the prose is corrected.

## Scope

**In:**
- Correct the three prose sites in `plugins/mill/skills/mill-plan/SKILL.md` — Phase: Plan Review steps 4b (line 565), 4c (line 581), 4d (line 597) — so each enumerates the same eight keyword arguments Phase: Plan's own self-validate call uses, including `done_gate`.
- Update the kwarg-count language at each site from "7"/"identical 7 keyword arguments"/"same 7 kwargs" to "8"/"identical 8 keyword arguments"/"same 8 kwargs".

**Out:**
- No change to `_plan_validate.run`'s actual signature (`plugins/mill/scripts/_plan_validate.py`) — it already has 8 keyword-only parameters, `done_gate` included.
- No change to the actual re-validate call sites' behavior: `millpy-review-plan.py`'s own step-1.5 gate (lines 223 and 331) already calls `_plan_validate.run(..., done_gate=cfg.get("pipeline", {}).get("done_gate"))` — the CLI code was never missing `done_gate`; only the SKILL.md prose describing the orchestrator's *self-run* re-validate calls in 4b/4c/4d was wrong.
- No change to Phase: Plan's own code block (lines 271-283) — it is already correct (8 kwargs, `done_gate` included) and is the source of truth the other three sites should match.
- No change to Step 1.5's own fix table, the convergence gate, or any other mill-plan mechanics untouched by this drift.

## Decisions

### Align 4b/4c/4d prose to Phase: Plan's 8-kwarg enumeration

- Decision: In each of the three prose sites (4b line 565, 4c line 581, 4d line 597), change the kwarg count from 7 to 8 and add `done_gate` to the enumerated argument list, matching Phase: Plan's line 251 enumeration verbatim: `root`, `git_root`, `wiki_root`, `skip_checks=plan_skip_checks`, `parent_branch`, `max_cards_per_batch`, `max_batch_context_tokens`, `done_gate`.
- Rationale: Phase: Plan's own code block is the actual executable source of truth for this call shape (it's the block an orchestrator copies to build the real call), and it already correctly has 8 kwargs including `done_gate`, matching `_plan_validate.run`'s real signature and matching `millpy-review-plan.py`'s own already-correct step-1.5 gate. Making 4b/4c/4d's prose match Phase: Plan is strictly a doc-consistency fix — no design tradeoff, no alternative behavior worth considering.
- Rejected: Removing `done_gate` from Phase: Plan's 8-kwarg call instead (make it 7 everywhere) — rejected because that would be a real behavior regression: it would silently stop validating `pipeline.done_gate`-related consistency during Phase: Plan's own self-validate, contradicting the CLI's own step-1.5 gate which already includes `done_gate`, and defeating the purpose `done_gate` exists for in `_plan_validate.run` at all. [auto-pick, no operator present — see Q&A log]

### Value expression for `done_gate` at each site

- Decision: When adding `done_gate` to 4b/4c/4d's enumerated list, use the identical value expression Phase: Plan's own call uses: `done_gate=cfg.get("pipeline", {}).get("done_gate")`. `cfg` is already bound at mill-plan's Entry step and stays in scope through Phase: Plan Review, so no new binding or resolution is needed.
- Rationale: 4b/4c/4d already state they reuse "the identical N keyword arguments ... that Phase: Plan's own self-validate call already uses" — the fix is purely to make the enumerated list actually match that claim, so the value expression must be identical too, not merely the argument name.
- Rejected: Re-deriving `done_gate` from `mill-config.yaml` fresh at each of 4b/4c/4d (e.g. re-reading the hub config file) — rejected as unnecessary complexity; `cfg` was already loaded once at Entry and nothing in Phase: Plan Review invalidates it.

## Technical context

- File to edit: `plugins/mill/skills/mill-plan/SKILL.md` (task-worktree path: `/home/knatte/Code/millhouse/wts/mill-plan-done-gate-kwargs-count-drift/plugins/mill/skills/mill-plan/SKILL.md`).
- Source-of-truth block (do not touch, only match): lines 251, 271-283 — Phase: Plan's self-validate prose + code block, 8 kwargs including `done_gate=cfg.get("pipeline", {}).get("done_gate")`.
- Three sites to fix (prose only, no code blocks at these sites — they're narrative `_plan_validate.run` descriptions, not fenced code):
  - Line 565 (step 4b): "Then run a full validator re-run: call `_plan_validate.run` with the identical 7 keyword arguments (`root`, `git_root`, `wiki_root`, `skip_checks=plan_skip_checks`, `parent_branch`, `max_cards_per_batch`, `max_batch_context_tokens`) that Phase: Plan's own self-validate call already uses..."
  - Line 581 (step 4c): "Run the identical full-validate gate steps 4b/4d's own full-validate gates use — call `_plan_validate.run` with the same 7 kwargs (`root`, `git_root`, `wiki_root`, `skip_checks=plan_skip_checks`, `parent_branch`, `max_cards_per_batch`, `max_batch_context_tokens`)..."
  - Line 597 (step 4d): "Run the identical full-validate gate step 4b's own full-validate gate uses — call `_plan_validate.run` with the same 7 kwargs, apply Step 1.5's mechanical-fix table..." (4d's enumeration is elided — it says "the same 7 kwargs" without re-listing them, referring back to 4b — only the count word needs to change here, from "7" to "8"; no list to edit since 4d never repeats the list itself).
- Confirmed via direct read of `_plan_validate.py:3687-3699` (task worktree, not plugin cache): `run()`'s actual signature is 8 keyword-only params — `root`, `wiki_root`, `git_root`, `skip_checks`, `max_cards_per_batch`, `max_batch_context_tokens`, `parent_branch`, `done_gate` — confirming Phase: Plan's 8-kwarg call is the correct one and 4b/4c/4d's "7" is the drift.
- Confirmed via direct read of `plugins/mill/scripts/millpy-review-plan.py:223,331` (task worktree): the actual CLI step-1.5 gate this SKILL.md text claims to mirror already passes `done_gate=cfg.get("pipeline", {}).get("done_gate")` at both call sites — the executable code was never wrong, only the SKILL.md's own narrative description of its analogous self-run calls in 4b/4c/4d.
- No other file references this same 7-vs-8 kwarg enumeration; `Grep` for `"identical 7\|same 7 kwargs\|7 keyword arguments"` in `plugins/mill/skills/mill-plan/SKILL.md` should return exactly the three sites above (plus line 565's own literal parenthesized list) after the fix, and zero occurrences of "7" in this specific context.

## Constraints

None beyond the existing `mill:markdown`/`mill:prose` conventions already governing this file (semantic line breaks, no fixed-column wrap) — this is a text-only edit to an existing `SKILL.md`, no new constraints apply.

## Testing

This is a documentation-only fix to a `SKILL.md` narrative instruction file — there is no unit-testable code path (`_plan_validate.py`'s actual `run()` signature is untouched and already correct; `plugins/mill/unit_tests/` has no test that parses SKILL.md prose).

Verification is by direct text inspection, not automated test:
- Grep `plugins/mill/skills/mill-plan/SKILL.md` for the strings `"7 keyword arguments"`, `"identical 7"`, `"same 7 kwargs"` post-fix — must return zero matches.
- Grep the same file for `"done_gate"` post-fix — must show it present at all four sites (Phase: Plan's original + the three corrected 4b/4c/4d sites), i.e. one more occurrence than before the fix (three new `done_gate` mentions added, one per site).
- Read lines 565, 581, 597 post-edit and confirm each enumerated list (where a list is repeated) exactly matches line 251's eight-item list, and each count word reads "8".
- No `verify:` command is meaningful here since no `.py`/code file changes; the plan's batch `verify:` should be a no-op / manual-inspection step, or `true` per the project's own convention for doc-only changes if the hub's `verify-not-isolated` validator requires a `PYTHONPATH=`-prefixed command — confirm this against `plugins/mill/scripts/_plan_validate.py`'s `verify-not-isolated` check semantics when writing the plan.

## Q&A log

- **Q:** No human operator is present for this run (unattended mill-start/mill-plan drive). How should Phase: Discuss's design-decision points be resolved? **A:** [auto-pick] Proceed with the task body's own named fix (align 4b/4c/4d's kwarg enumeration to Phase: Plan's 8-kwarg call) since it is the only defensible interpretation once the actual code (`_plan_validate.py`'s signature and `millpy-review-plan.py`'s own already-correct calls) is read — there is no genuine open design question here, only a doc-drift correction to make. **Why:** the task body, 7 duplicate GitHub issues, and direct source reads all agree on the same root cause and the same fix direction; inventing alternative designs for a one-directional doc-consistency bug would be manufacturing disagreement where none exists.
- **Q:** Should `done_gate` be removed from Phase: Plan's 8-kwarg call instead of added to 4b/4c/4d's 7-kwarg enumeration (i.e., resolve the drift by cutting the correct side down rather than raising the wrong side up)? **A:** [auto-pick] No — add `done_gate` to 4b/4c/4d, leave Phase: Plan untouched. **Why:** `millpy-review-plan.py`'s real CLI code already validates with `done_gate` included at its own step-1.5 gate; matching that behavior (not weakening it) is the correct direction, and the task's own title/brief ("drops done_gate") frames the omission in 4b/4c/4d as the defect, not the presence of `done_gate` in Phase: Plan.
