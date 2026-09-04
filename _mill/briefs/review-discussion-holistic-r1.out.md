MILL_REVIEW_BEGIN
# Review: Review prompt/output file listings resolve plan-relative paths to absolute before display, instead of keeping them relative

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 5 (claude-sonnet-5)
reviewed_file: _mill/discussion.md
date: 2026-09-04
```

## Findings

### [BLOCKING:consistency] Testing item 7's four-site labels don't match Technical Context's four sites
**Section:** Testing, item 7 (`test-review-plan-flow.py`) vs. Technical context (`_review_plan.py` intro + Scope)
**Issue:** Technical Context and Scope both enumerate the four `_review_plan.py` assembly sites as batch-mode (~232), second batch-mode block (~505), holistic (~614), run-holistic (~1045) — two distinct per-batch code paths in two different functions (`_review_one_batch` vs. `prepare()`'s scope-branch). Testing item 7 instead labels its four cases "per-batch bulk, per-batch tool-use, holistic, run-holistic," which reads as bulk/tool-use *mode* variants of a single per-batch site, not the two separate per-batch *sites*. Verified: only one `def _review_one_batch` (line 134) and the second per-batch block lives inside `prepare()` (382-661) under `if scope is not None`.
**Fix:** Rename item 7's four cases to match the canonical four sites (batch-mode, second batch-mode, holistic, run-holistic) and confirm the flow test actually exercises both per-batch code paths — otherwise the flow-level test, explicitly relied on as "the real guard against a missed call site" for the defaulted-`None` `roots` param, may silently skip one of the two near-duplicate per-batch sites.

### [NIT:consistency] `_review_code.py` function is `_build_artefact_section` (private), not `build_artefact_section`
**Section:** Scope, Technical context (`_review_code.py`)
**Issue:** Both sections repeatedly name the function `build_artefact_section()`; the actual definition (line 136) is `_build_artefact_section`, called once at line 349. Minor naming inaccuracy in an otherwise line-exact Technical Context.
**Fix:** Correct the name to `_build_artefact_section` in Scope and Technical context.

### [NIT:consistency] "six sites" count doesn't match the five enumerated `build_manifest_section` call sites
**Section:** Decisions > display-only-layer, rationale
**Issue:** Rationale says relativizing per-template "duplicates the same longest-match logic at six sites"; elsewhere the same decision says the layer "keeps the blast radius to the six assembly sites." Verified via grep: `build_manifest_section` has exactly 5 call sites (4 in `_review_plan.py`, 1 in `_review_code.py`), matching the Scope's own site list.
**Fix:** Correct "six" to "five" or clarify what the sixth counted item is (e.g. if `bulk_files_with_diff`'s extra delimiter pair is being counted separately).

## Verdict

REQUEST_CHANGES
Fix the item-7 site/mode labeling ambiguity that undermines the stated call-site-miss guard; two NIT naming/count inaccuracies noted.
MILL_REVIEW_END
