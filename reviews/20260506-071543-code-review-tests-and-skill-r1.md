# Review: 1 — Implementer dispatch-CLI + Agent-resume fix (conflicts with 8) — tests-and-skill

```yaml
verdict: APPROVE
reviewer_model: sonnetmax
reviewed_file: tests-and-skill
date: 2026-05-06
```

## Findings

### [NIT] Test 1 does not assert `start_sha` written to status.md
**Location:** `plugins/mill/unit_tests/test-millpy-implement.py:110-119`
**Issue:** The initial-dispatch test verifies `state` and `implementer_session` but not `start_sha`, which the CLI also writes via `set_batch_field`. One more `assertIn("start_sha", batches[0])` would guard that field.
**Fix:** Add `self.assertIn("start_sha", batches[0])` after the `implementer_session` assertion.

### [NIT] `_render.render` is not patched — tests read real template files
**Location:** `plugins/mill/unit_tests/test-millpy-implement.py:40-80` (setUp)
**Issue:** Tests 1–3 invoke `_render.render` against the real `implementer-brief.md` on disk; Tests 4–5b invoke it against `implementer-fix.md`. If either template is missing or gains an unresolved token the tests fail silently as a fixture problem rather than a code problem. The plan spec doesn't require patching `_render`, so this is within scope, but it makes the suite fragile to template-side changes.
**Fix:** No action required (plan didn't specify it); document the implicit dependency in a comment.

## Verdict

APPROVE
All plan requirements for both cards are met; no blocking defects found.