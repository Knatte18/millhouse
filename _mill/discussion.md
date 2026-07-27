# Discussion: Plan review verdict correctness: unverified platform claims and missing nit_count in subprocess dispatch

```yaml
task: Plan review verdict correctness: unverified platform claims and missing nit_count in subprocess dispatch
slug: mill-review-verdict-and-counting-gaps
status: discussing
parent: main
```

## Problem

Plan-review round verdicts and finding counts are unreliable in two independent ways. First, reviewers can approve a plan based on a factual claim about Claude Code's own platform/harness behavior (agent auto-discovery, plugin manifest semantics, etc.) without ever checking that claim against the actual manifest/docs — one such approval (#714) let a plan ship six undispatchable agent definitions because `plugin.json`'s explicit `agents` array silently disables directory-based auto-discovery, and the reviewer never opened that file. Second, the finalize envelope's finding counts are structurally incomplete: `_review_plan.py`'s subprocess/psmux `run()` path computes `blocking_count` at every terminal point but never computes `nit_count` anywhere (#709), and (per #717) the holistic reviewer brief omits a plan-format rule it's expected to know, causing it to raise a false NIT that would itself fail the plan validator. Together these mean an APPROVE verdict from plan review cannot be trusted at face value — orchestrators (`mill-plan`) branch directly on `blocking_count`/`nit_count` to decide whether to read the review file at all, so an undercounted or wrong verdict silently skips real findings.

## Scope

**In:**
- Fix `_review_plan.py`'s `run()` (subprocess/psmux dispatch) to compute and aggregate `nit_count` correctly, matching the Agent-mode `finalize()`/`finalize_scope()` path (#709).
- Add a regression test proving `[MEDIUM]`-only (or any off-vocabulary severity) findings fold into `blocking_count` on both dispatch paths — confirming #720's fold-in behavior (already shipped in `cf075f93`) holds and stays covered.
- Add the "All Files Touched excludes Deletes-only paths and Move sources" rule to `review-plan-holistic.md` and `review-plan-batch.md` (#717).
- Add a platform-behavior-claim verification criterion to `review-plan-holistic.md` and `review-plan-batch.md`, plus a `_plan_validate.py` rule requiring `plugin.json` in a batch's `Context:` when that batch touches plugin-registered mechanics (new agent-definition files, slash commands, hooks) (#714).
- Unit test coverage for all of the above in `plugins/mill/unit_tests/`.

**Out:**
- `_review_discussion.py` and `_review_code.py` — confirmed by exploration to already delegate to `finalize_scope()` in their `run()` paths (no duplicated inline counting logic), so they don't share #709's bug. No changes needed there.
- Redesigning the severity vocabulary itself (adding a formal MEDIUM tier, an `other_count` field, etc.) — #720 is being treated as already resolved by the existing fold-into-blocking behavior; not reopening that design.
- Any change to how `mill-plan`/`mill-go` branch on `blocking_count`/`nit_count` (SKILL.md logic) — this task fixes the counts feeding into that logic, not the branching logic itself.
- General plan-validator (`_plan_validate.py`) rule authoring beyond the one new `plugin.json`-in-Context rule for #714.

## Decisions

### nit-count-fix-mechanism

- Decision: In `_review_plan.py`'s `run()`, refactor the 4 terminal-write call sites that write a NEW review file (per-batch in `_review_one_batch()`; holistic NEED_CONTEXT retry-success; holistic NEED_CONTEXT no-resolve; holistic normal) to call `finalize_scope()` from `_review_common.py` instead of duplicating `parse_verdict` + `write_review_file` + `parse_blocking_count` + `count_unrecognized_severity_findings` inline. Use `finalize_scope()`'s returned `verdict`, `blocking_count`, `nit_count`, `file` for the review entry dict.
- The 5th site — the resume-round disk-scan block that re-reads an ALREADY-WRITTEN review file from disk — must NOT call `finalize_scope()` (it would write a spurious duplicate file). Patch this site narrowly: add `nit_count = parse_blocking_count(_file_text, severity="NIT")` alongside the existing `_parsed_blocking` computation, matching `finalize_scope`'s exact math (no unrecognized-severity fold for `nit_count` — the fold only ever applies to `blocking_count`, per existing `finalize_scope` behavior).
- Also update the final `ReviewResult` construction (end of `run()`) to sum `nit_count` across `reviews[]` the same way `aggregate_blocking` already sums `blocking_count`, and pass it into the returned `ReviewResult(..., nit_count=aggregate_nit)`.
- Rationale: eliminates the exact code duplication that caused #709 (the 4 write-sites become single-source-of-truth via the shared helper, matching how `_review_discussion.py`/`_review_code.py` already work); the 5th site is architecturally different (no write) so a matching inline patch is correct there, not a forced call into a write-performing helper.
- Rejected: patching all 5 sites narrowly without refactoring — leaves the duplication (and its bug-recurrence risk) in place for the 4 write-sites.

### medium-severity-regression-test

- Decision: Treat #720 as already resolved by `cf075f93`'s `count_unrecognized_severity_findings` fold-in (confirmed present and exercised in both `finalize_scope()` and `run()`'s existing `blocking_count` computations on this branch's HEAD). Add a regression test asserting a `[MEDIUM]`-only review folds into `blocking_count` (not silently dropped) for both the per-batch and holistic paths of `run()`, and for `finalize()`/`finalize_scope()`. No production code change for #720 itself.
- Rationale: the loomyard repro predates the fix reaching that repo's plugin cache; millhouse's own code already does the right thing. A regression test is cheap insurance without reopening a settled design decision (fold vs. separate counter).
- Rejected: adding a distinct `other_count`/`medium_count` field — would be new API surface for a case the existing fold-in already makes safe (visible, forces attention via `blocking_count`).

### all-files-touched-brief-fix

- Decision: Add one sentence to both `review-plan-holistic.md` and `review-plan-batch.md` (near the existing criteria list) stating: the overview's `## All Files Touched` section is the union of `Edits:`/`Creates:`/Move-target paths across all batches, with `Deletes:` tokens and Move-source paths excluded — a Deletes-only or Move-source-only path missing from that list is correct, not a finding.
- Rationale: both templates bulk the full overview (including `## All Files Touched`) into the reviewer's prompt, so both are equally exposed to raising the same false NIT that #717 reported; `mill-plan/SKILL.md` and `_plan_validate.py` check 8 already encode this exact rule for the plan-writing side — the reviewer brief was the only place missing it.
- Rejected: holistic-only fix (matches the issue's literal title but leaves batch reviewers exposed to the identical false-positive).

### platform-claim-verification

- Decision: Add a criteria bullet to `review-plan-holistic.md` and `review-plan-batch.md`: when a plan or discussion claim describes Claude Code's own platform/harness behavior (plugin manifest semantics, tool-call parameter shapes, subagent resolution, hook wiring, etc.), the reviewer must verify that claim against an actual harness/manifest file present in its context before accepting it as given — BLOCKING if the claim is unverifiable from context and the plan's correctness depends on it. Tool-use-mode reviewers may Read `plugin.json`/platform docs directly to verify. Additionally, add a new `_plan_validate.py` check requiring any batch whose `Creates:`/`Edits:` introduces or modifies agent-definition files, slash commands, or hook wiring to include `plugin.json` (or the relevant manifest) in that batch's `Context:`, so bulk-mode reviewers actually receive the manifest in their prompt rather than depending on incidental inclusion.
- Rationale: matches #714's own "Suggested fix direction"; the new `_plan_validate.py` rule specifically closes the gap for bulk-mode reviewers, who cannot fetch files on their own — without it, the criteria bullet alone is a no-op for that dispatch mode, which is exactly the mode #714 occurred in.
- Rejected: a new orchestrator-side mandatory `claude-code-guide` verification dispatch — new orchestration surface for a narrow failure class; the reviewer-prompt + Context-completeness fix is cheaper and addresses the same root cause (the reviewer/plan never had the manifest in view).

## Technical context

- `_review_plan.py`'s `run()` (`plugins/mill/scripts/_review_plan.py:613-1037`) is the subprocess/psmux legacy dispatch path; `prepare()`/`finalize()` (same file) is the Agent-mode path and already delegates to `finalize_scope()` correctly.
- 5 inline `blocking_count` computations to touch, by line (current HEAD):
  - `_review_one_batch()` lines 285-291 (per-batch terminal write) → refactor to `finalize_scope()`.
  - Resume-round disk-scan block, lines ~738-749 (reads an existing file, no write) → narrow patch, add `nit_count` line only.
  - Holistic NEED_CONTEXT retry-success block, lines ~954-972 → refactor to `finalize_scope()`.
  - Holistic NEED_CONTEXT no-resolve block, lines ~975-993 → refactor to `finalize_scope()`.
  - Holistic normal block, lines ~995-1013 → refactor to `finalize_scope()`.
- Final `ReviewResult` construction at line ~1026-1037: add `aggregate_nit = sum(r.get("nit_count", 0) for r in reviews)` alongside the existing `aggregate_blocking` line, pass `nit_count=aggregate_nit`.
- `finalize_scope()` (`plugins/mill/scripts/_review_common.py:1870-1933`) is the canonical helper: `apply_actual_model_override` → `parse_verdict` → `write_review_file` → `parse_blocking_count(severity=blocking_severity)` + `parse_blocking_count(severity=nit_severity)` → fold `count_unrecognized_severity_findings()` into `blocking_count` only. Signature: `finalize_scope(reviews_dir, review_type, round_n, raw_text, *, scope=None, actual_model=None) -> dict` with keys `scope, verdict, file, blocking_count, nit_count`.
- `count_unrecognized_severity_findings()` (`plugins/mill/scripts/_review_common.py:1697-1752`) already exists (added in `cf075f93`, merged 2026-07-25, already an ancestor of this branch) and is exercised by both `finalize_scope()` and `run()`'s existing `blocking_count` math — the mechanism #720 needs already ships.
- Severity vocabulary is closed to `BLOCKING`/`NIT` by prompt instruction already present in `review-plan-holistic.md:85` and `review-plan-batch.md:90` (also `review-discussion.md:73` for `GAP`/`NOTE`, `review-code-holistic.md:82`, `review-code-batch.md:86`). No template needs a MEDIUM tier added — the existing instruction already forbids it; the fold-in is the defensive backstop for when a reviewer ignores the instruction anyway.
- `## All Files Touched` rule is currently documented only in `plugins/mill/skills/mill-plan/SKILL.md:140` (plan-authoring side) and enforced by `_plan_validate.py`'s check 8 (`_check_all_files_touched_mismatch`, lines 1253-1319) — neither `review-plan-holistic.md` nor `review-plan-batch.md` states it; both bulk the full overview into their prompt (`_review_plan.py`'s `all_bulked`/`bulked` construction includes `overview_path` in both the batch and holistic code paths).
- Existing test files to extend: `plugins/mill/unit_tests/test-review-plan-flow.py` (confirmed by grep — asserts `r.blocking_count` at the exact same `run()` branches that need `nit_count` coverage, e.g. line 875 "aggregate blocking_count", line 1691 holistic NEED_CONTEXT path; never asserts `nit_count` anywhere — this is why #709 shipped unnoticed).
- No existing test file targets `_review_plan.py`'s per-batch/holistic `[MEDIUM]`-fold behavior specifically — new test cases needed for the #720 regression coverage.
- `plugin.json` lives at `plugins/mill/.claude-plugin/plugin.json` (per this repo's `${CLAUDE_PLUGIN_ROOT}` convention) and already declares an explicit `agents` array (confirmed relevant per #714's repro).

## Testing

- `_review_plan.py::run()` — TDD candidate. Extend `test-review-plan-flow.py`: for each of the 5 patched sites, assert `nit_count` (per-entry and in the final aggregate `ReviewResult.nit_count`) matches the actual `[NIT]` heading count in mocked reviewer output, alongside the existing `blocking_count` assertions at those same branches (batch, resume-disk-scan, holistic normal, holistic NEED_CONTEXT retry-success, holistic NEED_CONTEXT no-resolve).
- `[MEDIUM]`-fold regression — new test cases (extend `test-review-plan-flow.py` and/or `test-review-common.py`) asserting a review body containing one `[MEDIUM]` finding and zero `[BLOCKING]`/`[NIT]` findings produces `blocking_count == 1, nit_count == 0` via both `finalize_scope()` directly and `run()`'s per-batch/holistic paths.
- Template changes (#717, #714 criteria bullets) — no runtime logic to unit test; prose-only change, verify by re-reading the rendered prompt (manual read-through is sufficient; these templates have no dedicated rendering-assertion tests to extend).
- `_plan_validate.py` new Context-completeness rule for `plugin.json` (#714) — TDD candidate, mirrors the existing `test-plan-validate.py` style (fixture overview + batch files, assert the new check's error/no-error cases): batch touching `plugins/mill/agents/*.md` without `plugin.json` in `Context:` → error; same batch with `plugin.json` in `Context:` → no error; batch not touching agent/command/hook files → no error regardless of Context.

## Q&A log

- **Q:** #709 fix mechanism — refactor `run()`'s duplicated inline logic to call `finalize_scope()`, or patch each site narrowly? **A:** [auto-pick] Refactor to call `finalize_scope()` at the 4 write-sites; narrow-patch the 1 no-write (resume-scan) site. **Why:** removes the exact duplication that caused #709; the resume-scan site is structurally different (reads an existing file, mustn't write a duplicate) so it can't use the same helper.
- **Q:** #720 disposition — already resolved by `cf075f93`, or needs new production code? **A:** [auto-pick] Already resolved; add a regression test only. **Why:** the fold-in mechanism is confirmed present and already exercised on this branch's HEAD; the loomyard repro predates that fix reaching its plugin cache.
- **Q:** #717 fix scope — holistic template only, or both holistic and batch templates? **A:** [auto-pick] Both. **Why:** batch reviewers bulk the same overview (including `## All Files Touched`) and are equally exposed to the same false-NIT failure mode.
- **Q:** #714 reviewer instruction — prompt-only criteria bullet, or new mandatory orchestrator-side verification dispatch? **A:** [auto-pick] Prompt-only criteria bullet. **Why:** matches #714's own suggested fix direction; a new orchestration surface is unjustified for this failure class (YAGNI).
- **Q:** #714 bulk-mode reachability — leave bulk-mode reviewers dependent on incidental Context inclusion, or add a `_plan_validate.py` rule requiring `plugin.json` in Context for plugin-mechanic-touching batches? **A:** [auto-pick] Add the validator rule. **Why:** without it, the prompt-only fix is a no-op for bulk-mode reviewers — exactly the dispatch mode #714 occurred in.
- **Q:** Testing approach — extend the existing `test-review-plan-flow.py`, or a new test file? **A:** [auto-pick] Extend the existing file. **Why:** it already asserts `blocking_count` at the exact branches needing `nit_count` coverage; fragmenting coverage across files has no benefit.
