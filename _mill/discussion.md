# Discussion: _review_common/_review_plan: verdict/count consistency and path-suppression gaps

```yaml
task: _review_common/_review_plan: verdict/count consistency and path-suppression gaps
slug: mill-review-backend-consistency-gaps
status: discussing
parent: main
```

## Problem

Four independent consistency defects in the shared review backend (`plugins/mill/scripts/_review_*.py`), sourced from GitHub issues `#808`, `#799`/`#797`, `#798`, `#790`, and grouped into one task by the wiki brief ("Several independent consistency bugs in the review backend, confirmed still present against current source"). Each was re-verified directly against this repo's task-worktree source during discussion (not taken on the issue text's word — see Decisions below, one issue's premise did not survive that check).

Three of the four are real, narrow, single-file consistency bugs: a missing opt-in flag causes an avoidable hard-fail, a finalize step rewrites part of a review file but not all of it (leaving the file self-contradictory), and a review loop has no floor on how many rounds it samples before trusting an `APPROVE`. The fourth (`#790`) turned out, on inspection of git history, to already be fixed — the "bug" it describes is the direct, intended result of an earlier deliberate fix (`8405e526`, `#184`), and is dropped from this task's scope (see Decisions).

**Why now:** these were reported opportunistically via `/millhouse-issue` from other repos consuming the mill review backend (loomyard) and via self-report during a prior millhouse task, then batched into one wiki task for a consolidated fix pass rather than four separate tiny tasks.

## Scope

**In:**
- `#808` — extend `_review_plan.py`'s ref resolution to soft-fail on confirmed-gitignored `Context:` refs, matching `_review_code.py`'s existing (deliberate, `#733`) behavior.
- `#799`/`#797` (same root cause) — `finalize_scope` must rewrite the persisted review file's own top-level `verdict:` YAML field and `## Verdict` section token when the `blocking_classes` ceiling changes the computed verdict, not just the per-finding headings/YAML it already rewrites.
- `#798` — add a `min_rounds` config floor and a "demoted-from-BLOCKING counts as not-converged" termination predicate to the discussion/plan/code review loops.
- Unit test coverage for all three, extending existing test files.

**Out:**
- `#790` — dropped from scope entirely; see Decisions.
- Any change to the `blocking_classes` ceiling mechanism itself (adjudication logic is sound per `#798`'s own "what should NOT change" section).
- Any change to `Edits:`/`Creates:`/`Deletes:` ref resolution — these remain hard-fail-only by design (see `#808` decision below). The literal `#808` repro (an `Edits:`-only gitignored+deleted path) is **not** fixed by this task.
- A `verdict_before_ceiling:` audit marker (considered for `#797`, rejected as unneeded — `Demoted-from:` markers on individual findings already provide the audit trail).
- New standalone test files — all four land in files that already have dedicated coverage.
- Any change to `mill-start`'s existing non-progress-extension machinery itself — `min_rounds` sits underneath it as a separate floor, not a replacement (per `#798`'s own noted interaction).

## Decisions

### drop-790-already-fixed

- Decision: `#790` ("_review_plan mid-round-resume discards `_disk_reviews`, recovered entries never reach envelope") is not implemented. It is documented here as resolved-by-design and explicitly excluded from this task.
- Rationale: `_review_plan.run`'s resume branch used to do `reviews.extend(_disk_reviews)`. Commit `8405e526` (`fix(_review_plan): exclude stale per-batch entries from resume-mode result (#184)`) deliberately removed that line, with the stated reason "prevents inflated blocking_count from already-processed per-batch findings." `test-review-plan-flow.py`'s `test9` and `test17` both assert `len(r.reviews) == 1` (holistic only) on resume, with comments explicitly citing "bug C fix #184". `#790`'s premise ("Expected: recovered entries merged into `reviews`") is the exact regression `#184` was written to prevent — implementing it would revert a reasoned, tested fix. `#790`'s own text notes it was "deliberately left unfixed by [a prior] task" without checking this history.
- Rejected: (a) implementing the merge as literally described in `#790` — reverts `#184`, reintroduces double-counting; (b) merging into a diagnostics-only field, `blocking_count` untouched — considered, but no evidence anything currently needs that visibility; adds surface for a problem no one has reported since `#184` shipped. Not pursued.

### plan-review-context-soft-fail-parity

- Decision: `_review_plan.py` gets the same `Context:` vs `Edits:`/`Creates:`/`Deletes:` ref split that `_review_code.py` already has (added for `#733`), and passes `soft_fail_gitignored=True` only for the `Context:` subset, across all `resolve_ref_paths` call sites in `_review_plan.py` (currently 4: per-batch worker, single-batch prepare/finalize path, and two holistic paths).
- Rationale: `_review_code.py`'s split is deliberate and already documented in its own comment: "a missing `Edits:`/`Creates:`/`Deletes:` ref still hard-fails unconditionally, since those name files the batch is expected to produce or touch." `_review_plan.py` currently doesn't split refs at all — it has zero soft-fail capability for any ref type, which is a real asymmetry with `_review_code.py`, independent of the specific `Edits:` repro in `#808`'s original report.
- Rejected: extending soft-fail to `Edits:`/`Creates:`/`Deletes:` refs too — would fix the literal `#808` repro but contradicts `_review_code.py`'s established, comment-documented rationale (masks a batch silently failing to produce/touch a file it declared). Also rejected: a new plan-format "scratch/transient path" marker (`#808`'s suggested option (b)) — bigger surface (plan-format change), not needed once Context:/Edits: parity is established, deferred if a real need resurfaces.

### finalize-verdict-rewrite

- Decision: `finalize_scope` (in `_review_common.py`) gains a rewrite step, run whenever `blocking_classes` demotion changes the recomputed verdict from the reviewer's original: rewrite the fenced-yaml `verdict:` field and the `## Verdict` section's verdict token in `raw_text` to the recomputed value, before `write_review_file`. Applies uniformly across `discussion`/`plan`/`code` review types since `finalize_scope` is shared.
- Rationale: `finalize_scope` already rewrites demoted findings' headings/YAML via `rewrite_demoted_findings`, but never touches the file's own top-level verdict — so a file can persist `verdict: REQUEST_CHANGES` (and `## Verdict` prose asserting blocking gaps) while the finalize envelope and orchestrator correctly report `APPROVE`. This is a reporting defect in the persisted artifact only; the adjudication logic itself (`verdict-derives-from-surviving-blocking-count`) is correct and unchanged.
- Rejected: adding a `verdict_before_ceiling:` marker recording the pre-ceiling verdict — YAGNI; `Demoted-from: BLOCKING` markers already carried on each demoted finding provide sufficient audit trail without a second, file-level mechanism.

### review-loop-min-rounds-and-demoted-predicate

- Decision: two additive, orthogonal changes to review-loop termination:
  1. New optional config field `roles.<role>.<scope>.min_rounds` (int, default `1` when absent — preserves today's behavior). The loop may not terminate on `APPROVE` before round `min_rounds`, regardless of verdict.
  2. New termination predicate: a round terminates the loop only if its `findings[]` contains **no** entry with `demoted: true` (a field the envelope already carries — no backend change needed for this half). A round where the reviewer raised a BLOCKING that got ceiling-demoted counts as not-converged, even if the post-ceiling verdict is `APPROVE`.
  Both apply symmetrically to every review loop in the codebase: `mill-start`'s discussion-review loop, `mill-plan`'s batch and holistic plan-review loops, and `mill-go`'s per-batch and holistic code-review loops (6 loop sites total across 3 `SKILL.md` files, since batch/holistic are independently configured scopes).
- Rationale: per `#798`'s observed run, a single lucky round-1 demotion previously ended a 5-round-configured loop, and rounds 2–5 (run manually by the operator) then found 17 further findings already present in the round-1-approved document, including a BLOCKING in every round. The two changes are orthogonal: `min_rounds` guards under-sampling (a floor, unconditional); the demoted-predicate guards `APPROVE != clean` (a signal, conditional on ceiling activity). Together they cover both failure modes `#798` observed without over-fitting to either alone.
- Rejected: "N consecutive clean rounds" as the primary termination rule — an LLM reviewer usually finds *something*, so a strict zero-findings rule risks non-termination; `#798`'s own observed run never had a fully clean round. Also rejected: a dedicated Python-side config validator for `min_rounds <= rounds` — no sibling field (`rounds`, `blocking_classes`) has one either; `_config.py` has no schema-validation layer today, and adding one for a single new field would be an inconsistent, out-of-place addition. `min_rounds` follows the same "documented convention, trusted at read time" pattern as its siblings.

## Technical context

- Shared backend module: `plugins/mill/scripts/_review_common.py` — `resolve_ref_paths` (path resolution + soft-fail), `finalize_scope` / `rewrite_demoted_findings` / `_rewrite_demoted_headings` / `_rewrite_demoted_yaml_entries` (verdict + finding rewrite machinery), `parse_verdict`, `apply_blocking_ceiling`, `resolve_blocking_classes`.
- Reference pattern for the `Context:` split: `_review_code.py` lines ~266–289 (`context_only_refs` vs `other_refs`, built via `parse_batch_refs(bp, fields=("Context",))` vs `parse_batch_refs(bp, fields=("Edits", "Creates", "Deletes"))`, then two separate `resolve_ref_paths` calls, only the `Context:` one passing `soft_fail_gitignored=True`).
- `_review_plan.py`'s 4 `resolve_ref_paths` call sites (as of this discussion, subject to drift — re-verify against source before editing): the per-batch worker (`_review_one_batch`), the single-batch prepare/finalize path (`scope is not None` branch), and two holistic paths (union-of-all-batch-refs, appears twice for prepare/finalize symmetry). All currently call `parse_batch_refs(batch_path)` unsplit.
- Reference pattern for the verdict-line rewrite: `apply_actual_model_override` (`_review_common.py`) already has fence-scanning logic to find "the yaml fenced block that carries the reviewer's `verdict:` line" — reusable for locating the `verdict:` field to rewrite. The `## Verdict` section's token is the first non-blank line after the `## Verdict` heading (see `review-output.schema.md` and any `review-*.md` template for the shape).
- `finalize_scope` is shared across `discussion`/`plan`/`code` review types (`_review_discussion.py`, `_review_plan.py`, `_review_code.py` all call it) — the verdict-rewrite fix lands once and applies to all three.
- Config schema precedent for `min_rounds`: `plugins/mill/templates/mill-config.yaml` (template, seeds new hubs) and this repo's own `mill-config.yaml` (hub file) — both must stay in sync per `CLAUDE.md`. `rounds` and `blocking_classes` are already nested per `roles.<role>.<scope>`; `min_rounds` slots in alongside them.
- Loop-termination sites to edit (prose, not Python): `plugins/mill/skills/mill-start/SKILL.md` "Phase: Discussion Review" (steps 4a/4b/5, plus the existing `--auto` non-progress-extension logic it must sit underneath without disrupting); `plugins/mill/skills/mill-plan/SKILL.md` (steps 4a/4c and the "Max-rounds escape" step, ~lines 400–490); `plugins/mill/skills/mill-go/SKILL.md` (the per-batch `APPROVE` branch ~line 731 and the holistic `APPROVE` branch ~line 1151, plus their respective rounds-exhausted branches). Line numbers are approximate/pre-implementation — re-locate by section heading, not line number, when writing the plan.
- `#798`'s own text flags the mill-start interaction explicitly: its `--auto` mode's non-progress extension (comparing BLOCKING titles across rounds, granting one extra round past the cap) already touches the round counter; `min_rounds` is a floor underneath that extension logic, not a replacement — both must be readable together in the edited SKILL.md text.
- Unit test files with existing, directly relevant coverage: `plugins/mill/unit_tests/test-review-common.py` (`resolve_ref_paths` — has a `soft_fail_gitignored`-adjacent Context: test already, given the `_review_code.py` precedent likely also covered there or in `test-review-code-flow.py`), `plugins/mill/unit_tests/test-review-finalize.py` (`finalize_scope`/`rewrite_demoted_findings`), `plugins/mill/unit_tests/test-review-plan-flow.py` (contains `test9`/`test17` — the tests documenting the `#184`/`bug C` resume behavior that `#790` must NOT disturb; any edit in this task must leave those two assertions (`len(r.reviews) == 1` on resume) passing unchanged).
- Run via `plugins/mill/unit_tests/run-all.py` (per `python-testing`/`python-build` skill conventions — `uvx ruff check .` for lint, no `uv add`/`uv sync` for ad-hoc tooling).

## Constraints

No `CONSTRAINTS.md` present at the hub root. `CLAUDE.md`'s repo-wide conventions apply, notably: `print()`/`_log()` output must stay ASCII-only (relevant to any new stderr warning text in the ref-resolution fix, mirroring `resolve_ref_paths`'s existing warning style); `mill-config.yaml` hub file and the plugin template must stay in sync when `min_rounds` is added; never use `sed` in any script or generated sub-agent prompt.

## Testing

- **`resolve_ref_paths` / Context split (`#808`):** TDD candidate. Extend `test-review-plan-flow.py` (or add cases to `test-review-common.py` if the split helper itself is tested there) with: a `Context:`-only ref that is missing-on-disk and confirmed git-ignored → soft-skipped, no `ReviewError`; a `Context:`-only ref missing and NOT git-ignored → still hard-fails (regression guard); an `Edits:`/`Creates:`/`Deletes:` ref missing and git-ignored → still hard-fails (confirms the design boundary is preserved, this is the case this task deliberately does NOT fix). Cover both a per-batch call site and the holistic call site, since both are being changed.
- **Verdict rewrite (`#799`/`#797`):** TDD candidate. Extend `test-review-finalize.py`: a round where a BLOCKING finding gets demoted by the ceiling and the post-ceiling verdict flips from `REQUEST_CHANGES` to `APPROVE` → assert the written file's fenced `verdict:` field AND `## Verdict` section token both read `APPROVE`, not just the per-finding heading. A round with no demotion → assert the verdict lines are byte-identical to input (no spurious rewrite, mirrors `rewrite_demoted_findings`'s existing byte-identical-when-untouched guarantee). Cover at least one case each for `discussion` and `plan`/`code` review types, since templates differ slightly in the surrounding `## Verdict` prose but the token-rewrite logic must be type-agnostic.
- **`min_rounds` / demoted-predicate (`#798`):** this is prose-level orchestrator logic (`SKILL.md` steps), not independently unit-testable Python — verification is by careful review of the edited `SKILL.md` sections against `#798`'s observed-run table (round 1 APPROVE-after-demotion should NOT end the loop under the new rule) and against the existing round-cap / non-progress-extension text to confirm no interaction is silently broken. If mill-plan's implementation introduces any new Python helper (e.g. a shared "is this round converged" predicate function) rather than pure prose, add unit coverage for it in `test-review-common.py` alongside the other predicate-style helpers (`apply_blocking_ceiling`, `resolve_blocking_classes`).
- **Regression guard (`#790` non-change):** `test-review-plan-flow.py`'s `test9` and `test17` must continue to pass with their current `len(r.reviews) == 1` resume-mode assertions untouched — treat any diff touching these as a signal the `#790` scope decision above is being violated.
- Run `plugins/mill/unit_tests/run-all.py` before commit for all Python changes.

## Q&A log

- **Q:** How should `#790` be handled, given `_review_plan.py`'s resume branch appears to already exclude `_disk_reviews` from the returned envelope? **A:** [auto-pick] Drop it from scope — treat as already resolved by design (`#184`/commit `8405e526`), document the finding so it isn't re-reported. **Why:** git history shows the merge was deliberately removed with a stated rationale ("prevents inflated blocking_count from already-processed per-batch findings"), and two existing tests (`test9`, `test17`) assert the current no-merge behavior by name; implementing `#790` as literally reported would revert a reasoned, tested fix.
- **Q:** `#808` fix shape — should `_review_plan.py` mirror `_review_code.py`'s Context:-only soft-fail split, or extend soft-fail to `Edits:`/`Creates:`/`Deletes:` refs too (which would fix the literal repro)? **A:** [auto-pick] Mirror `_review_code.py`'s Context:-only split. **Why:** matches the existing, deliberate, comment-documented design in `_review_code.py` (`Edits:`/`Creates:`/`Deletes:` refs name files the batch is expected to produce/touch and must hard-fail); extending soft-fail to those would contradict that established rationale. This does not fix the original Edits:-only repro — that's out of scope by this decision.
- **Q:** `#799`/`#797` — fix the verdict rewrite only, or also add a `verdict_before_ceiling:` audit marker as `#797` suggests? **A:** [auto-pick] Fix the rewrite only, no added marker. **Why:** YAGNI — per-finding `Demoted-from:` markers already provide sufficient audit trail; a second file-level marker format is speculative scope.
- **Q:** `#798` — implement fully (config + all three `SKILL.md` files), scope down to config-only, or drop to a follow-up task? **A:** [auto-pick] Full implementation. **Why:** explicitly one of the four items the task brief scoped in; a partial fix (e.g. config-only) leaves the actual termination bug live since enforcement is in the orchestrator prose, not the backend.
- **Q:** Should `min_rounds` get a dedicated Python-side config validator? **A:** [auto-pick] No — follow the existing convention (no validation code for `rounds`/`blocking_classes` either; `_config.py` has no schema-validation layer to hang it on). Default `1` when absent.
- **Q:** Does `min_rounds`/demoted-predicate apply to both of `mill-go`'s review loops (per-batch and holistic code-review)? **A:** [auto-pick] Yes, both, symmetrically — `rounds`/`blocking_classes` are already configured per-scope independently, so `min_rounds` follows the same per-scope pattern.
- **Q:** Testing approach — extend existing unit test files or add new dedicated ones? **A:** [auto-pick] Extend existing files (`test-review-common.py`, `test-review-finalize.py`, `test-review-plan-flow.py`) — all four items land in files that already have dedicated coverage; no new test files needed.
