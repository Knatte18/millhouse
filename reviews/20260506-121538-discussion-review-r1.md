# Review: 8 (A) — Disable per-batch reviews (config-driven)

```yaml
verdict: APPROVE
reviewer_model: sonnetmax
reviewed_file: discussion.md (disable-per-batch-reviews)
date: 2026-05-06
```

## Findings

### [NOTE] Testing description diverges from existing test pattern
**Section:** Testing → `_review_plan.py` (unit)
**Issue:** Discussion says "mock `load_reviewer` to return a dummy reviewer" but the existing test file uses `_reviewer_test_stub` as a real named reviewer via `cfg["review"]["plan"]["batch"] = "test_stub"` — no monkey-patching anywhere in the file.
**Fix:** Clarify that the new test should set `batch: null, holistic: "test_stub"` in the cfg dict and `stub.seed(...)` one APPROVE response, consistent with every other test in the file.

## Verdict

APPROVE
One pattern-consistency note in testing; no gaps block plan writing.