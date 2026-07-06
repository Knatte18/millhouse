All discussion claims verified against source. The read sites, the fix-CLI validation at line 128, the SKILL.md edit targets (mill-go step 6 "same standard arguments" at line 148, mill-start's 3-step Entry with no Step 0, mill-go's "Step 0" precedent, workflow's exactly-two Anti-patterns), and the test files all match. One nuance: the testing plan's conditional "if per-CLI unit test files exist" resolves to yes — `test-review-finalize.py` and per-CLI flow tests exist.

MILL_REVIEW_BEGIN
# Review: Fix agent-mode dispatch gaps: HTML escaping, missing flags, timeouts, and stale skill content

```yaml
verdict: APPROVE
reviewer_model: opushigh
reviewed_file: _mill/discussion.md
date: 2026-07-06
```

## Findings

### [NOTE] Review-CLI test coverage left conditional
**Section:** Testing
**Issue:** The plan for the three review CLIs' read sites is phrased "if per-CLI unit test files exist ... add a case"; they do exist (`test-review-finalize.py`, `test-review-{code,discussion,plan}-flow.py`), so the conditional is unnecessary and could be read as optional.
**Fix:** State plainly that HTML-escape cases are added to `test-review-finalize.py` (or the per-CLI flow tests) as required coverage for all four read sites, not just `test-implementer-common.py`.

### [NOTE] Whole-file unescape vs. legitimately-escaped review text
**Section:** Decisions / html-unescape-at-read-site
**Issue:** Unescaping the entire `.out.md` at read time also unescapes any entity-like text a reviewer legitimately wrote inside a finding (e.g. discussing `&amp;amp;` in code); the discussion frames escaping as uniform but does not note this asymmetry between the implementer notification payload and free-form review body text.
**Fix:** One sentence confirming the notification payload is uniformly escaped end-to-end (so whole-text unescape is the correct inverse), or scope the unescape to the captured-notification portion only.

## Verdict

APPROVE
Scope, decisions, and testing are grounded and verified; only non-blocking notes remain.
MILL_REVIEW_END