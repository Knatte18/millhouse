# Discussion: mill-go-base SKILL.md: resume phase branch, entry routing, and undocumented flags

```yaml
task: mill-go-base SKILL.md: resume phase branch, entry routing, and undocumented flags
slug: mill-go-base-skilldoc-and-logic-bugs-2
status: discussing
parent: main
```

## Problem

`mill-go-base` (`plugins/mill/skills/mill-go-base/SKILL.md`, `resume.md`) is the Builder orchestrator prompt that drives `/mill-go`. It was consolidated from four GitHub bug/enhancement reports (#835, #836, #837, #840), all filed by live operators who hit gaps in the documented routing/resume logic during real `/mill-go` runs. Two of the four turned out to already be fixed by unrelated prior work on this branch; the other two are still live and need real edits. **Why now:** this task exists to close out the remaining live gaps and to record, with commit evidence, that the other two need no further action — so a plan-writer or future operator doesn't waste a batch "fixing" something already fixed.

## Scope

**In:**
- **#837** — `SKILL.md`'s "### Mid-execution phase-gate widening" table, `approved-{batch_name}` branch: add a `_status.read_batches()` check for any batch already in `running`/`reviewing`/`fixing` state before assuming none exists; route to `## Resume` when one is found.
- **#840** — `resume.md` step 1: add an explicit fallback for "zero non-terminal batch entries found" (the narrow window between Prepare's bare `implementing` phase-append and Execute's first batch dispatch) — fall through directly to `## Execute — sequential loop`, starting at the first `pending` batch in `order`.
- Recording, in this file (see Decisions), the verification evidence that #835 and #836 are already resolved, so no plan batch is created for them.

**Out:**
- No code changes for #835 or #836 — verified already fixed (see Decisions).
- No refactor of the bare `implementing`/`reviewing`/`fixing` unconditional-routing rule, and no change to the existing `approved-{batch}` "last batch → route to Holistic" edge case — both are already correct and out of scope.
- No new shared helper/unification between the #837 fix and the #840 fix — each closes its own independent gap; see Decisions for why unifying was rejected.
- No changes to `holistic-review.md` or `handoff.md` — neither source issue touches those files, and exploration found no related gap in them.

## Decisions

### 835-already-fixed

- Decision: No code/doc change for #835 ("per-batch cleanup block resolves status.md via `resolve_hub_path()` instead of the known `worktree_root`"). Treat as verified-resolved; do not create a plan batch.
- Rationale: The entire "per-batch cleanup block" the issue describes (including the exact `status_path = _paths.resolve_task_path(_paths.resolve_hub_path(), '_mill/status.md')` snippet quoted in the issue) was deleted wholesale by commit `4b3ce636` ("mill-go-base: remove subprocess/psmux dispatch branches"), the commit immediately preceding this task's spawn commit (`2386a53e`) on this same branch. `grep -n "resolve_hub_path\|cleanup block" plugins/mill/skills/mill-go-base/SKILL.md` finds zero remaining hits outside the unrelated hub-root config-load call at line 54/511 (which was never the buggy site). The psmux-session-reaping mechanism the bug depended on no longer exists at all under the agent-only dispatch model.
- Rejected: Adding a regression-guard test asserting the block stays gone — out of scope for a "fix these bugs" task; the drift/consistency tests already in `plugins/mill/unit_tests/test-skill-helper-drift.py` and `test-mill-go-base-agent-only.py` (added by the same `4b3ce636` commit) cover dead-literal and companion-reference drift generally.

### 836-already-fixed

- Decision: No code/doc change for #836 ("`--prior-blocking` flag documented in SKILL.md is absent from `millpy-fix.py`"). Treat as verified-resolved; do not create a plan batch.
- Rationale: Both the `_prior_blocking.py` module and the `millpy-fix.py --prior-blocking` argparse option exist and function today. `plugins/mill/scripts/millpy-fix.py --help` shows `--prior-blocking PRIOR_BLOCKING` with the documented help text; `git log --oneline -- plugins/mill/scripts/_prior_blocking.py` shows it was added by `fadd186c` ("mill-go: quality-gate coverage gaps"), which predates this task and is already on this branch. The issue's own "Source repo" is `Knatte18/loomyard.git` (a separate consuming repo), not this `millhouse` repo — the reporter was almost certainly running against a stale installed plugin cache that hadn't picked up `fadd186c` yet, not a bug in this repo's current `mill-go-base`.
- Rejected: Investigating further (e.g. re-deriving why the reporter's cache was stale) — that's a plugin-cache/install-freshness concern outside `mill-go-base`'s own scope and outside what this task's four source issues asked for.

### 837-approved-batch-liveness-check

- Decision: In `SKILL.md`'s "### Mid-execution phase-gate widening" table, the `approved-{batch_name}` bullet (currently starting "fires *between* batches: the just-finished batch is `state: approved`, every other batch is either already `approved` or still `pending`...") gets a check prepended: before applying that assumption, call `_status.read_batches(status_path)` and check whether any entry's `state` is `running`, `reviewing`, or `fixing`. If one is found, route to `## Resume` (`resume.md`) instead — its step 1 will correctly locate and resume that batch. Only when no entry is non-terminal does the existing continue-Execute-loop / last-batch-edge-case-to-Holistic logic apply, unchanged.
- Rationale: The `approved-{batch_name}` phase string only reflects the *last completed* transition — starting a batch's implementer (dispatching, setting `state: running`, recording `start_sha`/`implementer_session`) does **not** call `_status.append_phase`, so an interruption right after dispatching batch N+1 (before it reaches any state that *does* append a phase) leaves `phase:` on-disk still reading `approved-<batch-N>` even though batch N+1 is genuinely mid-implementation. Following the undocumented-check routing literally would cold-start-dispatch a batch that's actually mid-flight, discarding its existing session/`start_sha` instead of resuming it. This mirrors the existing precedent already in the same table for `self-resolved-verify-logic`, which does exactly this kind of `_status.read_batches()` liveness check to disambiguate before routing.
- Rejected: Routing `approved-{batch}` through `## Resume` unconditionally and generalizing Resume's own fallback to also cover the "last batch, zero pending remaining" edge case (would let one shared fallback serve both #837 and #840). Rejected because it's a bigger, riskier diff that touches already-correct behavior (the existing last-batch→Holistic edge case) for no material benefit — the conservative per-branch check is a strictly smaller, more auditable change, and #840's fix (below) already closes the *only* case that currently reaches Resume with zero non-terminal batches (the bare `implementing` phase), so no shared fallback is actually needed.

### 840-resume-step1-fallback

- Decision: In `resume.md` step 1 (currently: "Read `_mill/status.md`; locate the current batch entry (the single entry whose `state` is non-terminal: `running`, `reviewing`, or `fixing`)."), add an explicit fallback: if `_status.read_batches(status_path)` finds **no** entry with a non-terminal state, this is the narrow window between Prepare's bare `implementing` phase-append and Execute's dispatch of the first batch — skip the rest of Resume entirely and fall through directly to `## Execute — sequential loop` in `SKILL.md`, starting at the first `pending` batch in `order` (the same continuation the `approved-{batch_name}` widening-table branch already uses for the *between-batches* gap, applied here to the *pre-first-batch* gap instead).
- Rationale: Bare `phase: implementing` (unsuffixed) is set once by Prepare, immediately before any batch is dispatched, and unconditionally routes to `## Resume` per the widening table's first bullet ("`implementing` / `reviewing` / `fixing` (bare, unsuffixed) — route to `## Resume`, unchanged from today"). If the orchestrator is interrupted in the gap between that Prepare commit and the first batch's dispatch, every batch entry is still `state: pending` — Resume's step 1 has nothing to match and, as documented today, no defined next action. This is exactly the gap #840 reports hitting live.
- Rejected: Adding the fallback to `SKILL.md`'s widening table instead of `resume.md` — rejected per the issue's own primary suggestion and title (`mill-go-base/resume.md: Resume step 1 has no branch...`); keeping the fix local to `resume.md` also avoids touching the widening table a second time in the same task (it's already being edited for #837), keeping each file's diff self-contained and independently reviewable.
- Rejected: Fixing both files redundantly/cross-referenced — unnecessary duplication once the single fallback in `resume.md` step 1 fully closes the gap.

## Technical context

- `plugins/mill/skills/mill-go-base/SKILL.md` — Entry step 5 "Entry phase gate" (~line 88) reads `status["yaml"]["phase"]`; the "### Mid-execution phase-gate widening" table (~lines 123–155) is where the `approved-{batch_name}` bullet (~lines 141–143) lives.
- `plugins/mill/skills/mill-go-base/resume.md` — step 1 (lines 6–7) is the exact site for the #840 fallback. `_status.read_batches` is the existing helper (already used elsewhere in `SKILL.md`'s widening table, e.g. the `self-resolved-verify-logic` bullet) that returns per-batch state; reuse it rather than inventing a new accessor.
- Both files are pure orchestrator-prompt prose consumed by the LLM acting as Builder — there is no separate Python "router" implementing this routing logic, so both fixes are markdown text edits, not code changes. No Python signatures change.
- `order` (the topologically-sorted batch name list) is computed by `SKILL.md` Entry step 6, which runs after step 5's phase-gate routing decision is made but before that decision is actually acted on — so it is safely in scope by the time either `## Resume` or `## Execute — sequential loop` is entered, confirmed by the existing `approved-{batch_name}` branch already referencing `order` today.
- Existing tests to run as part of `verify:`: `plugins/mill/unit_tests/test-mill-go-base-agent-only.py` and `plugins/mill/unit_tests/test-skill-helper-drift.py` (added by `4b3ce636`) do drift/consistency checks over `SKILL.md`'s text (dead dispatch literals, companion-file references, helper existence) — these must still pass after the prose edits since they check structural invariants, not the specific wording being changed.

## Testing

- No new unit tests are needed: this task's two live fixes are prose-only edits to orchestrator instructions with no corresponding Python logic to unit-test, and the existing drift/consistency tests (`test-mill-go-base-agent-only.py`, `test-skill-helper-drift.py`) already exercise the structural properties (companion references, no dead literals) that could be broken by a careless edit.
- Verification approach: run the existing unit test suite (`plugins/mill/unit_tests/run-all.py` or equivalent, per `python-build`/repo convention) after each edit to confirm no drift/consistency regression, plus a manual read-through confirming the new `approved-{batch_name}` and `resume.md` step 1 text is internally consistent with the rest of each file's routing table (batch-state terminology, phase-string literals, and cross-references to `## Resume` / `## Execute — sequential loop` / `## Holistic code review` match exactly).

## Q&A log

- **Q:** Scope for #835/#836 given both are already fixed on this branch — 1) mark verified-resolved-no-action, cite commits (Recommended) 2) also add a regression-guard test 3) investigate further **A:** [auto-pick] mark verified-resolved-no-action, cite commits. **Why:** both are demonstrably fixed by prior commits already in this branch's history (`4b3ce636` deleted #835's offending code; `fadd186c` added #836's missing flag/module); adding a batch or a new regression test for already-fixed, out-of-scope-repo-drift issues is not this task's job.
- **Q:** Fix approach for #837 — 1) conservative targeted `_status.read_batches()` check added only to the `approved-{batch_name}` widening-table branch (Recommended) 2) unify by routing `approved-{batch}` through `## Resume` unconditionally and generalizing Resume's fallback **A:** [auto-pick] conservative targeted check. **Why:** matches the issue's own literal "Expected" text, minimal diff, doesn't risk the already-correct last-batch→Holistic edge case, and #840's fix independently closes the only case that currently reaches Resume with zero non-terminal batches.
- **Q:** Fix location for #840 — 1) `resume.md` step 1 gets the explicit fallback branch (Recommended) 2) `SKILL.md`'s widening table instead 3) both, cross-referenced **A:** [auto-pick] `resume.md` step 1. **Why:** matches the issue title's own file reference and its stated primary suggestion; keeps `SKILL.md`'s widening table's diff scoped to #837 only, avoiding two edits to the same table in one task.
