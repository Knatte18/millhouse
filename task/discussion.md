# Discussion: 28 (A) — review-plan robustness

```yaml
task: 28 (A) — review-plan robustness
slug: review-plan-robustness
status: discussing
parent: main
```

## Problem

Five related robustness bugs in `millpy-review-plan.py` and the `mill-plan` skill surfaced during real session use. They fall into three clusters: (A) the plan-review CLI is invoked without the `millpy-bg` wrapper that every other review CLI uses, so Windows auto-backgrounding silently loses the JSON output; (B, C, D) error-and-resume paths in the holistic reviewer produce wrong verdicts — either crashing the script, inflating `blocking_count` with stale data, or incorrectly approving a plan the holistic never reviewed; (E) the `--skip-validate` flag disables all validator checks to work around a single legitimate finding, leaving the operator without validation on the rest of the plan.

All five bugs were observed in the same multi-session run (issues #185, #184, #187, #186, #188). Fixing them together avoids partial states where some bugs are present and some are not, and the test suite can cover the combined flows.

## Scope

**In:**
- `mill-plan SKILL.md` — wrap CLI in `millpy-bg.py` for all three autonomous call sites (step 2, step 4.5 retry, step 1.5 post-validator-fix re-run) (bug A); extend step 4.5 to handle partial-ERROR rounds (bug D)
- `_review_plan.py` — catch `ReviewError` from `parse_verdict` in holistic section (bug B); exclude stale per-batch entries from resume-mode JSON (bug C)
- `_plan_validate.py` — add `skip_checks` parameter to `run()`; update `_check_wiki_config_mutation` error message at line 642 from `--skip-validate` to `--skip-check wiki-config-mutation` (bug E)
- `millpy-review-plan.py` — add `--skip-check <name>` repeatable flag, pass to `_plan_validate` (bug E)
- `millpy-validate-plan.py` — add `--skip-check <name>` repeatable flag for consistency (bug E)
- `mill-plan SKILL.md` fix-table — update `wiki-config-mutation` row to use `--skip-check wiki-config-mutation` instead of `--skip-validate` (bug E)
- Unit tests for bugs B, C, E

**Out:**
- `millpy-review-discussion.py` and `millpy-review-code.py` — they already use `millpy-bg.py` and are not affected
- `_review_discussion.py`, `_review_code.py` — resume/parse logic in those backends is separate
- Any change to the `ReviewResult` API shape (type, round, verdict, blocking_count, reviews) — callers are stable
- Adding a `stale_reviews` field or any new JSON key — not needed
- Changes to per-batch error handling — already correct (caught by `except ReviewError` at line 247 of `_review_one_batch`)

## Decisions

### bug-b-parse-error-as-error-entry

- Decision: When `parse_verdict(raw)` raises `ReviewError` in the holistic section, catch it, write the raw LLM output to a review file anyway (for operator inspection), and append an `ERROR` entry with the parse error message. Do not re-raise.
- Rationale: Consistent with how `LLMError` is handled (per-batch returns ERROR entry; no retry at the backend level). Produces a JSON envelope for the SKILL to act on instead of exit 1. Writing the raw file lets the operator inspect what the LLM actually returned. The SKILL's step 4.5 (fix D) then handles the ERROR entry by retrying.
- Rejected: Retry-on-parse-error with reformatted prompt (adds complexity, risks retry loop, needs its own cap). Fallback prose parsing (fragile, unpredictable). Prompt-template enforcement (doesn't prevent the LLM from ignoring it).

### bug-c-resume-mode-holistic-only

- Decision: When `resume_round is not None`, do NOT include `_disk_reviews` in `reviews[]`. Log their count to stderr for debuggability. Run holistic. Return only the holistic entry in `reviews[]`.
- Rationale: The stale per-batch entries were already processed by the operator (that's why the holistic is being retried). Including them inflates `blocking_count` with already-fixed findings. The holistic reviews the full plan and will catch any actually-unfixed issues. Clean JSON means downstream automation reads live blockings only.
- Rejected: Zero out stale blocking_counts but keep entries in reviews[] (misleading history, still inflates `reviews` length). Add a `stale_reviews` key (API churn, callers don't need this).

### bug-d-partial-error-step-4-5

- Decision: Extend SKILL.md step 4.5 from "ALL entries ERROR → re-run" to "ANY entry has ERROR → re-run without consuming the round." Two-pass cap is unchanged: if two consecutive runs both contain any ERROR entry, halt with `BLOCKED: review ERROR-only round {N}`.
- Rationale: When holistic errors and per-batch APPROVEs, aggregate is `REQUEST_CHANGES` with `blocking_count == 0`. Without this fix, SKILL step 4b fires: "NITs-only → APPROVE." The plan gets approved without a successful holistic pass, which defeats the purpose of the holistic. The backend's resume detection + fix C ensure the re-run fires holistic-only and returns a clean holistic-only result.
- Rejected: Changing `aggregate_verdict` to emit a new verdict like "PARTIAL_ERROR" (API break). Adding 1 to blocking_count per ERROR entry (hack, misleading counts). Handling only "holistic alone errors" as a special case (insufficient; partial per-batch error should also re-run).

### bug-e-per-check-skip-flag

- Decision: Add `--skip-check <name>` (repeatable) to `millpy-review-plan.py` and `millpy-validate-plan.py`. In `_plan_validate.run()`, add `skip_checks: frozenset[str] = frozenset()`. Implementation: run all checks as before, then filter out errors whose `check` key is in `skip_checks` before returning. Unknown check names are silently ignored.
- Rationale: Filtering at the end is the simplest correct implementation — no changes needed inside individual `_check_*` functions. Silent ignore keeps the flag forward-compatible and lets operators add flags in anticipation of upcoming check names. The wiki-config-mutation row in the SKILL.md fix table is updated to use `--skip-check wiki-config-mutation`; `--skip-validate` is preserved for pipeline-level override (existing behaviour, not removed).
- Rejected: Pass `skip_checks` into each individual check function (complex, no benefit). Exit 1 on unknown check name (too strict, breaks forward-compatibility). Only adding the flag to `millpy-review-plan.py` (inconsistency; standalone validator should behave the same).

### bug-e-skip-validate-preserved

- Decision: Keep `--skip-validate` in `millpy-review-plan.py` as-is. Only update the `wiki-config-mutation` fix-table row in SKILL.md to use `--skip-check` instead of `--skip-validate` for that specific case.
- Rationale: `--skip-validate` is used by the `pipeline.skip_validate: true` config hook documented in SKILL.md. Removing it would break that documented escape hatch. The per-check flag is additive, not a replacement.
- Rejected: Deprecating `--skip-validate` (unnecessary churn, the hook still needs it).

## Technical context

### File map

- `plugins/mill/scripts/millpy-review-plan.py` — CLI entry point; argparse; calls `_plan_validate.run()` then `_review_plan.run()`.
- `plugins/mill/scripts/millpy-validate-plan.py` — standalone validator CLI; calls `_plan_validate.run()` only.
- `plugins/mill/scripts/_review_plan.py` — backend `run()` function. Sections: per-batch parallel (lines ~342–428), holistic (lines ~430–593), aggregate (lines ~595–604). Bug B and C live in the holistic section.
- `plugins/mill/scripts/_plan_validate.py` — public `run(plan_dir, project_root, *, root, wiki_root) -> list[dict]`. Eight checks; returns sorted error list.
- `plugins/mill/skills/mill-plan/SKILL.md` — three bare CLI calls for bug A (step 2, step 4.5 retry block, step 1.5 post-validator-fix re-run); step 4.5 trigger for bug D. Step 6's manual user-facing example stays bare.
- `plugins/mill/unit_tests/test-review-plan-flow.py` — existing flow tests using `_reviewer_test_stub`.
- `plugins/mill/unit_tests/test-plan-validate.py` — existing validator unit tests.
- `plugins/mill/unit_tests/test-millpy-validate-plan.py` — existing standalone-CLI tests.

### Bug B: holistic parse_verdict error path

In `_review_plan.py`, the holistic section structure:
```python
try:
    raw, session_id = holistic_reviewer.run(...)
except LLMError as exc:
    reviews.append({..., "verdict": "ERROR", ...})   # ← already handled
else:
    verdict = parse_verdict(raw)                      # ← raises ReviewError on prose output
    ...
    path = write_review_file(...)                     # ← only reached if parse succeeds
    reviews.append({...})
```

The fix adds a `try/except ReviewError` around `parse_verdict(raw)` in the `else` branch. On parse failure: write the raw text to a review file (for operator inspection), append an ERROR entry, and continue. This must cover both the first `parse_verdict(raw)` call and the second call (inside the NEED_CONTEXT retry sub-branch). The per-batch equivalent (`_review_one_batch`) already wraps the whole body in `except ReviewError` at line 247 — the holistic section should match.

### Bug C: resume mode in _review_plan.run()

Lines 342–380 in `_review_plan.py`:
```python
if resume_round is not None:
    _disk_reviews: list[dict] = []
    for _entry in reviews_dir.iterdir():
        if ... round == resume_round ...:
            _disk_reviews.append({...})
    reviews.extend(_disk_reviews)   # ← remove this; log count to stderr instead
```

After the fix, `reviews` stays empty when entering the holistic section. The holistic appends its entry normally. The final `reviews` list contains only the holistic entry.

### Bug D: SKILL.md step 4.5

Current text: "When the JSON envelope from step 2 has a non-empty `reviews[]` array AND every entry's verdict is `"ERROR"` …"

New text replaces "every entry's verdict is `"ERROR"`" with "at least one entry's verdict is `"ERROR"`". The re-run uses the normal CLI invocation (no extra flags); the backend's `detect_resume_round` + `_scan_approved_batches` automatically scope what gets re-reviewed. The two-pass cap wording changes to: "on the second consecutive run that still contains any `"ERROR"` entry, halt."

### Bug E: _plan_validate.run() signature change

Current:
```python
def run(plan_dir, project_root, *, root=None, wiki_root=None) -> list[dict]:
```

New:
```python
def run(plan_dir, project_root, *, root=None, wiki_root=None, skip_checks=frozenset()) -> list[dict]:
```

Filter applied after the existing sort line:
```python
errors.sort(key=lambda e: (e["batch"] or "", e["card"] or 0, e["check"]))
if skip_checks:
    errors = [e for e in errors if e["check"] not in skip_checks]
return errors
```

Also update the error message string in `_check_wiki_config_mutation` (line 642) from:
`"use --skip-validate if a bootstrap card is present"` →
`"use --skip-check wiki-config-mutation if a bootstrap card is present"`

The `millpy-review-plan.py` argparse addition:
```python
parser.add_argument(
    "--skip-check",
    action="append",
    dest="skip_checks",
    default=[],
    metavar="CHECK",
    help="Skip a named validator check (repeatable). Silently ignores unknown names.",
)
```
Pass `skip_checks=frozenset(args.skip_checks)` to `_plan_validate.run()`.

Same addition in `millpy-validate-plan.py` (and pass through to `_plan_validate.run()`).

### SKILL.md mill-plan fix-table update (bug E)

The `wiki-config-mutation` row's fix column currently ends with: `re-run the CLI with \`--skip-validate\``.

Change to: `re-run the CLI with \`--skip-check wiki-config-mutation\`` in the two places where `--skip-validate` is mentioned in that row (the fix description and the "If `wiki-config-mutation` co-occurs…" sentence). The surrounding logic about conditions (a) and (b) is unchanged.

### Interaction between B, C, D

These three fixes form a chain for the holistic-error scenario:
1. Fix B converts a `parse_verdict` exception from exit-1 into an ERROR entry → the CLI produces JSON.
2. Fix D detects the ERROR entry in SKILL step 4.5 → re-runs without consuming the round.
3. Fix C ensures the re-run (which fires holistic-only via resume detection) returns only the fresh holistic result → `blocking_count` reflects only live findings.

All three are needed. Applying only B+D without C would still count stale per-batch blockings on the retry. Applying only C+D without B would still crash to exit-1 on prose output before D can act.

## Testing

### test-review-plan-flow.py additions (bugs B and C)

**Bug B — holistic parse_verdict failure becomes ERROR entry:**
- Set up a plan with one batch and a holistic reviewer.
- Configure the test stub to return prose (no yaml block) for the holistic call.
- Call `_review_plan.run(...)`.
- Assert: `result.verdict == "REQUEST_CHANGES"`, `result.reviews` contains one ERROR entry with `scope == "holistic"`, a review file is written to `reviews_dir` containing the raw prose output, and no `ReviewError` is raised.

**Bug C — resume mode excludes stale per-batch:**
- Set up a plan with two batches. Write fake per-batch r1 files to `reviews_dir` with `REQUEST_CHANGES` verdicts (simulating a round that completed per-batch but not holistic).
- Write no holistic r1 file (simulating a mid-round holistic error).
- Configure the stub to return APPROVE for the holistic.
- Call `_review_plan.run(...)`.
- Assert: `result.verdict == "APPROVE"`, `result.reviews` contains exactly one entry (`scope == "holistic"`), and `result.blocking_count == 0`.
- Negative: without the fix, `blocking_count` would reflect the stale per-batch `REQUEST_CHANGES` counts.

### test-plan-validate.py additions (bug E)

**skip_checks filters the target check:**
- Create a plan that triggers the `wiki-config-mutation` check.
- Call `run(..., skip_checks=frozenset({"wiki-config-mutation"}))`.
- Assert: result list is empty (wiki-config-mutation suppressed).
- Also assert: other checks still run — create the same plan with an additional `card-missing-field` error, pass `skip_checks={"wiki-config-mutation"}`, assert the card-missing-field error is still present.

**skip_checks with unknown name is silent:**
- Call `run(valid_plan_dir, ..., skip_checks=frozenset({"nonexistent-check"}))` on a clean plan.
- Assert: no error raised, result list is empty.

### test-millpy-validate-plan.py additions (bug E)

**--skip-check flag is accepted and forwarded:**
- Invoke the CLI with `--skip-check wiki-config-mutation` on a plan that would otherwise trigger that check.
- Assert: exit code 0, `errors` list in JSON is empty.
- Invoke with `--skip-check wiki-config-mutation --skip-check card-missing-field` on a plan with both violations.
- Assert: both checks suppressed, exit 0.

### No integration tests needed

All five bugs are unit-testable without a real LLM or real git. The review-plan-flow tests already use `_reviewer_test_stub` for the reviewer backend. The validator tests use in-memory fixtures. Nothing here requires integration-test infra.

## Q&A log

- **Q:** For bug C resume mode, should stale per-batch entries appear in `reviews[]` at all? **A:** No — return only the holistic entry. Stale entries are logged to stderr for debuggability.
- **Q:** Should `millpy-validate-plan.py` (standalone CLI) also get `--skip-check`? **A:** Yes, for consistency.
- **Q:** Should an unknown check name passed to `--skip-check` be an error? **A:** No, silently ignore — keep the flag forward-compatible.
