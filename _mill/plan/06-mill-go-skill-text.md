# Batch: mill-go-skill-text

```yaml
task: Remove batch review (plan-review.batch / code-review.batch)
batch: mill-go-skill-text
number: 6
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-phase-wait.py test-skill-helper-drift.py test-mill-go-variants.py test-mill-go-base-agent-only.py test-guards.py
depends-on: [5]
```

## Batch Scope

Rewrites the mill-go orchestrator skill text (`mill-go-base/SKILL.md` and its three companion files) so per-batch code review no longer appears as a stage.
The `### 3. Code Review loop` section becomes a short `### 3. Complete batch` step with the same effect as today's "reviewer is null" shortcut, and the per-batch resume, phase-gate and NIT-gate routes go away.
This batch only edits skill text plus the one unit test that mirrors the phase-gate predicate; it consumes the script contracts batches 1–5 established (`build_digest(reviews_dir)`, `_find_final_code_review(reviews_dir)`, `millpy-fix.py --scope holistic` only, `millpy-review-code.py` without `--batch`).

## Cards

### Card 17: Replace the per-batch Code Review loop in mill-go-base/SKILL.md

- **Context:**
  - `_mill/discussion.md`
  - `plugins/mill/skills/mill-go-base/resume.md`
  - `plugins/mill/skills/mill-go-base/holistic-review.md`
- **Edits:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `plugins/mill/skills/mill-go-base/SKILL.md`:
  - **Entry step 2 config reads:** delete the four `roles.code-review.batch.*` bullets (`rounds`, `min_rounds`, `auto_approve_on_cap`, `reviewer`).
  - **Entry phase table:** the `implementing` / `reviewing` / `fixing` row keeps its routing; reword "matching the widened batch-scoped set" to "matching the widened set" if the word "batch-scoped" no longer describes it.
  - **`### Mid-execution phase-gate widening`:** remove `r"^reviewing-.*-r\d+$"` and `r"^fixing-.*-r\d+$"` from the `_phase_wait.matches_wait_trigger` regex list (keep `r"^approved-.*$"` and `r"^holistic-reviewing$"`), delete the `reviewing-{batch_name}-rN` / `fixing-{batch_name}-rN` routing bullet and its follow-on sentence, and correct the "which of the seven branches fired" count to match the bullets that remain.
    Keep the bare `implementing` / `reviewing` / `fixing` exact-match set and the `running` / `reviewing` / `fixing` liveness checks: the batch `state` enum is unchanged (overview Decision `approved-batch-phase-and-state-enum-kept`).
  - **`### 3. Code Review loop`:** replace the whole section — from its heading through the end of step 5 "Max-rounds exhaustion", stopping before `### Stuck escalation` — with:

    ```
    ### 3. Complete batch

    Set batch state → `approved`, `_status.append_phase(status_path, f"approved-{batch_name}", _timestamp.now_utc_iso())`, commit on the task branch: `git -C <worktree> add <status_path> _mill/briefs/ && git -C <worktree> commit -m "<VARIANT_LABEL>: approve batch {batch_name}"`, and continue to the next batch.
    Code review runs once, holistically, after every batch is approved — see `## Holistic code review`.
    ```

    Keep `### Stuck escalation` and `### Blocked`: implementer-stage stuck handling and the cleanliness gate still route to them.
  - **Cross-references to the removed section:** search the file for `Code Review loop`, `Code Review`, `code review` (lower case, per-batch sense), `step 4.5`, `sub-step 4.5`, `Execute step 3`, `Execute step 4`, `review_round`, `--batch`, `--batch-name` and `scope batch`, and fix each hit:
    - end of `### 2b. Cleanliness gate`: "continue to "3. Code Review loop" as normal" → "continue to "3. Complete batch" as normal";
    - `### 2. Parse implementer report`: "`status: success` → continue to Code Review." → "continue to step 2b (cleanliness gate)."; keep the `review_round: 0` sentence only if a remaining step still reads `review_round`, otherwise delete it;
    - `### Stuck escalation` `transient` with `commits_made > 0`: "then code review as if the implementer had reported success" → "then batch completion as if the implementer had reported success";
    - "## Agent-mode dispatch" step 4's parenthetical "(see step 3 of "Code Review loop")" → point to `plugins/mill/skills/mill-go-base/holistic-review.md`'s own "Builder reads only the JSON envelope verdict" rule, or drop the parenthetical if that file states no such rule;
    - "## Agent-mode dispatch" step 5: "re-passing `--scope`, `--batch-name` (batch scope only), and `--review-file <path>`" → "re-passing `--scope` and `--review-file <path>`"; in the finalize-timeout note, "both batch and holistic scope" → "holistic scope";
    - `**Tree-guard checkpoint block**` post-dispatch form: drop "`### 3. Code Review loop` sub-step 4.5 and" so only the holistic-review sub-step 3.5 retry is named, and make the sentence singular.
  - Any remaining sentence that describes per-batch code review, a per-batch reviewer, or a per-batch NIT-fix pass as a live stage is rewritten or deleted.
    Sentences about per-batch *implementation*, per-batch `verify:`, batch state, and the `approved-{batch_name}` phase stay.
- **Commit:** `docs(mill-go-base): replace the per-batch Code Review loop with a batch-completion step`

### Card 18: Remove per-batch review branches from the mill-go-base companion files

- **Context:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
  - `plugins/mill/scripts/_nit_gate.py`
  - `plugins/mill/scripts/_prior_blocking.py`
- **Edits:**
  - `plugins/mill/skills/mill-go-base/resume.md`
  - `plugins/mill/skills/mill-go-base/handoff.md`
  - `plugins/mill/skills/mill-go-base/holistic-review.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `plugins/mill/skills/mill-go-base/resume.md`:
  - Intro: the CLIs named as atomic become `millpy-implement.py` only (drop `millpy-review-code.py`).
  - Step 2: replace the `reviewing` and `fixing` bullets with one bullet: "**`reviewing` / `fixing`** — only per-batch code review, since removed, wrote these states, so the entry was left by an older plugin version. The implementer report was already consumed: continue at `plugins/mill/skills/mill-go-base/SKILL.md`'s Execute step 3 (`### 3. Complete batch`)."
  - Step 4 (`mill-receiving-review` remains the fixer's responsibility): it only describes the removed `millpy-fix.py --scope batch` re-dispatch; delete the step.
  - Keep step 1's non-terminal lookup (`running`, `reviewing`, `fixing`) and its no-non-terminal fallback unchanged.

  In `plugins/mill/skills/mill-go-base/handoff.md`, **Nit-enforcement gate**:
  - The only gate scope is now `holistic`.
    Rewrite the review-file lookup sentence so it describes only the holistic match (`RE_SIMPLE`, type `code`: the leading `<timestamp>-` immediately followed by `code-review-r<digits>.md`), mirroring `_nit_gate._find_final_code_review`; drop the `RE_BATCH` / per-batch-scope description and the `retry-fix` glob example that only guarded against per-batch names (the regex names are quoted from the current text, no file read needed).
  - **Prior-blocking digest:** the snippet calls `_prior_blocking.build_digest(pathlib.Path('<reviews_dir-abs-path>'))` and writes `<briefs_dir>/prior-blocking-holistic-r<H>.txt`; delete the sentence choosing between `scope='batch'` and `scope='holistic'`; point the naming convention at `plugins/mill/skills/mill-go-base/holistic-review.md` step 4 only.
  - The NIT-fix dispatch sentence names only the holistic shape (`--scope holistic --review-file <review-file-abs-path> --round <H> --nits-only`) from `holistic-review.md` step 4; drop the per-batch shape and the reference to `SKILL.md`'s Execute step 4.
  - Keep the Manual recovery note, which describes `nits-fixed-<scope>`; narrow it to `nits-fixed-holistic` only where it names a per-batch scope.

  In `plugins/mill/skills/mill-go-base/holistic-review.md`:
  - Step 1(a): delete the parenthetical contrasting `"holistic-reviewing"` with "the per-batch mirror in `SKILL.md`'s Execute step 3"; keep the `latest=True` rationale.
    Delete the sentence "Provide the inline-Python comparison snippet as per `plugins/mill/skills/mill-go-base/SKILL.md`'s per-batch section (Execute step 3 sub-step 1, crash-recovery)." — the file's own inline helper below it already carries the comparison.
    Reword "per-batch files embed `{batch_name}` so the glob never collides" to say historical per-batch files from older tasks embed a batch name, so the glob never collides with them.
  - The `_prior_blocking.build_digest(...)` call drops `scope='holistic'`.
  - Step 3's dispatch args drop "(no `--batch` flag for holistic scope)".
- **Commit:** `docs(mill-go-base): drop per-batch review routes from resume, handoff and holistic review`

### Card 19: Narrow the phase-gate predicate test

- **Context:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
  - `plugins/mill/scripts/_phase_wait.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-phase-wait.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `plugins/mill/unit_tests/test-phase-wait.py`, Case 14 mirrors the predicate in `mill-go-base/SKILL.md`'s "Mid-execution phase-gate widening" subsection.
  Remove `r"^reviewing-.*-r\d+$"` and `r"^fixing-.*-r\d+$"` from `widened_regexes`, delete the two positive asserts for `"reviewing-foo-r1"` / `"fixing-foo-r3"`, and add two negative asserts that those phases no longer match.
  Update the Case 14 comment and PASS message counts to the number of widened phase values that remain.
- **Commit:** `test(phase-wait): drop per-batch review phases from the widened entry gate`

## Batch Tests

`verify:` runs `test-phase-wait.py` (the narrowed predicate), `test-skill-helper-drift.py` (every `_<module>.<fn>(` reference in the edited skills still resolves), `test-mill-go-variants.py` and `test-mill-go-base-agent-only.py` (structural locks on the mill-go-base files and their companions), and `test-guards.py` (guard checks over `mill-go-base/SKILL.md`).
