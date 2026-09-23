# Batch: skill-docs-baseline

```yaml
task: 'compute_baseline: use the task worktree''s own pre-edit state, not a parent-branch checkout'
batch: skill-docs-baseline
number: 7
cards: 2
verify: null
depends-on: [3, 5]
```

## Batch Scope

This batch updates the two SKILL.md files whose prose describes the mechanisms batches 3 and 5 change: `mill-go-base/SKILL.md`'s "0.5. Baseline pre-flight" section (the two-half module-wide/per-batch split, per Decision `two-half-stage-ownership`) and `mill-merge-in/SKILL.md`'s "3.5. Baseline recompute" step (the new asymmetric verdict mapping and the batch-clearing side effect). It depends on batches 3 and 5 so the prose describes the actual final code shape, not an intermediate one. Both edits also drop an `_mill/discussion.md` citation each currently carries, restating the rationale inline instead — CLAUDE.md forbids a permanent doc citing an `_mill/`-rooted path, since `_mill/` is deleted or restored-from-base at merge time.

## Cards

### Card 34: Rewrite mill-go-base/SKILL.md's "0.5. Baseline pre-flight" section

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In the "Entry-gate wait for upstream mill-plan" section's speculative-launch bullet, narrow the claim "the speculative early launch's single module-wide result IS the complete baseline computation for this batch, with nothing further to run" to the module-wide half only, and change that branch's handling from "leave the file as-is... nothing further to run" to: consume the speculative module-wide result exactly as today, but do not treat it as the whole computation — "0.5. Baseline pre-flight" below still invokes `--stage baseline` again afterward, where the module-wide half no-ops as `"cached"` and the per-batch half runs for real.
  In "0.5. Baseline pre-flight" itself: update both the speculative branch's JSON-line extraction and the main flow's JSON-line extraction to select the line by its `substage` key (`"module_wide"` vs `"per_batch"`) rather than positionally — a `--stage baseline` invocation may now print two JSON lines in one run, not always exactly one. Describe the per-batch line's result vocabulary alongside the existing module-wide one: `{"stage": "baseline", "substage": "per_batch", "result": "computed"|"cached"|"deferred"|"skipped"|"error", "value": ...}`, with a one-line description of each of the five values (mirroring how the existing module-wide vocabulary is described).
  Delete the sentence "The same `--stage baseline` invocation also idempotently pins the parent branch's tip SHA into status.md's `baseline_parent_sha:`..." and the following sentence "This on-demand computation happens transparently inside the implementer/fixer dispatch itself; no separate Builder-side step is needed to trigger or poll it." — neither the pin nor the on-demand mechanism they describe exists anymore.
  Replace the closing paragraph's citation "per `_mill/discussion.md`'s `baseline-aware module-wide verify gate (#590)` Decision (\"Compute it **eagerly, once, before the task's first batch implementer is ever dispatched**\")" with the rationale restated inline, with no `_mill/`-rooted path reference: state directly that this ordering guarantees no implementer session has touched dependency manifests yet, so the eager capture's reused worktree state is still guaranteed to match the parent branch tip at the moment it runs.
- **Commit:** `docs(mill-go-base): update 0.5 baseline pre-flight for the two-half module-wide/per-batch split`

### Card 35: Rewrite mill-merge-in/SKILL.md's "3.5. Baseline recompute" step

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-merge-in/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Drop the claim "`--recompute-baseline` runs the same deterministic computation `millpy-implement.py --stage baseline` uses" — the two now differ in exactly their verdict-mapping asymmetry (`--recompute-baseline` maps `"pre-existing-failures"` to "leave unset," while `--stage baseline`'s module-wide half caches it verbatim). Restate the sentence to describe `--recompute-baseline` as running the same underlying `compute_baseline` algorithm, with its own asymmetric mapping on top.
  Add a sentence describing the new, operator-visible side effect: `--recompute-baseline` also unconditionally clears every batch's `verify_baseline_failures`, so every remaining batch in the task gates strictly for the rest of the run after a merge-in.
  Replace the closing "Rationale (`_mill/discussion.md`'s `baseline-aware module-wide verify gate (#590)` Decision, merge-in paragraph): \"...\"" blockquote with the same rationale restated as this skill's own prose, with no `_mill/`-rooted path reference: state directly that whenever `mill-merge-in` pulls new parent commits into the task branch, it must recompute the baseline eagerly at its own clean post-sync boundary, mirroring the batch-1 pre-flight rule — the parent's dependency manifests just changed as of the merge-in, and recomputing eagerly at that boundary (rather than lazily inside a later batch's finalize) keeps the computation on the correct side of the "no implementer has touched manifests since this snapshot" invariant.
- **Commit:** `docs(mill-merge-in): update 3.5 baseline recompute for new verdict mapping and batch clearing`

## Batch Tests

`verify: null` — this batch edits only prose in two `SKILL.md` files, which have no runnable test surface of their own. Their accuracy is checked by cross-reading against the actual code shape landed in batches 3 and 5 (which this batch depends on), not by an automated command.
