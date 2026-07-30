MILL_REVIEW_BEGIN
# Review: Blocking phase-wait gate for mill-plan/mill-go chaining — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 5
reviewed_file: plan/
date: 2026-07-30
```

## Findings

### [NIT] Batch 1 "Batch Tests" rationale misstates `_config.py`'s key check
**Location:** 01-phase-wait-foundation.md, Batch Tests section
**Issue:** Claims "`_config.py` has no central key-allowlist/schema check" as justification for skipping extra verify coverage on card 3's config edits, but `_config.py` does have `warn_unknown_keys`/`walk_unknown_keys`, which diffs the merged config against the template and warns on divergence — a template-as-schema allowlist check.
**Fix:** Reword the rationale to acknowledge `warn_unknown_keys` exists (it's warning-only, not load-blocking, and fires only on template/hub divergence — which card 3 avoids by adding identical keys to both files) rather than asserting no such check exists at all.

### [NIT] Unit test's CRLF regression case hard-depends on a `bash` binary with no graceful fallback
**Location:** 01-phase-wait-foundation.md, Card 2, test case 13
**Issue:** `subprocess.run(["bash", "-c", cmd], ...)` is a new pattern for this test suite (no existing `unit_tests/*.py` file shells out to `bash`); on a machine without `bash` on PATH this raises `FileNotFoundError` rather than a clean `FAIL:` assertion message, unlike the rest of the suite's uniform `AssertionError`-only failure contract.
**Fix:** Either accept the dependency as already implied by the feature (Monitor always runs bash per `cli/SKILL.md`) or wrap the `subprocess.run` call so a missing-bash environment produces a clean `SKIP`/`FAIL` message instead of an uncaught exception.

## Verdict

APPROVE
Plan is internally consistent, DAG-valid, source-grounded, and CRLF-safe; only two non-blocking NITs found.
MILL_REVIEW_END
