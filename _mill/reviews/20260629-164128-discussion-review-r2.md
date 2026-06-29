I have verified the key claims. The source files confirm the discussion's technical grounding (`_RE_REFS_HEADER`, `parse_batch_refs`, `reads-not-backtick-path` rejecting >1 backtick, `_review_code.py` docstring + `bulk_files_with_diff`/`start_sha`, `language_skills_directive` reading only Edits/Creates, and the existing `pipeline:` config section). I found one internal contradiction and one omission.

MILL_REVIEW_BEGIN
# Review: Add first-class Moves/Renames field to plan cards for rename-heavy batches

```yaml
verdict: GAPS_FOUND
reviewer_model: opushigh
reviewed_file: _mill/discussion.md
date: 2026-06-29
```

## Findings

### [GAP] Mechanical check severity self-contradicts (BLOCKING vs NIT)
**Section:** Testing + Q&A log vs Decisions/verification-scope
**Issue:** The verification-scope decision and round-1 resolution state the mechanical rename check emits an "advisory NIT, never auto-BLOCKING," but the Testing bullet (line 357-358) says the pure function "returns a BLOCKING finding for an add+delete pair" and the Q&A log (line 384) says "(BLOCKING on add+delete)" — a plan/test author cannot tell what the function must produce.
**Fix:** Update the Testing bullet and the line-384 Q&A entry to assert a NIT finding (never BLOCKING), matching the resolved decision; reserve BLOCKING for the LLM criterion only.

### [NOTE] New config knob not listed as a template edit
**Section:** Scope (code-review bullet) / Technical context
**Issue:** The proposed `pipeline.rename_detect_pct` knob is mentioned but no scope item adds it to `templates/mill-config.yaml`; unregistered `pipeline.*` keys trip the unknown-key warning (test-config.py line 826), and CLAUDE.md requires the hub config and plugin template stay in sync.
**Fix:** Add an explicit scope/file item to register `pipeline.rename_detect_pct` (default 30) in the `mill-config.yaml` template under the existing `pipeline:` block.

## Verdict
GAPS_FOUND
One must-resolve severity contradiction on the mechanical check; otherwise well-grounded and decided.
MILL_REVIEW_END
