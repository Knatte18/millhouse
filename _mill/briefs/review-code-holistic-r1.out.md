MILL_REVIEW_BEGIN
# Review: Auto-name task sessions <slug>:<phase> — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewed_file: plan/ + source
date: 2026-09-24
```

## Findings

### [NIT:consistency] Block markers matched inside strings
**Location:** `plugins/mill/scripts/_vscode_keybindings.py:154-164`
**Issue:** `_find_block` uses plain `text.find(BLOCK_BEGIN)`, unlike the string-aware `_scan` used elsewhere, so a `// mill:begin` inside a JSON string would be treated as the block start.
**Fix:** Optional: locate the markers only in `_COMMENT`-kind spans from `_scan`.

## Verdict

APPROVE
Batches are consistent and the cross-batch contracts hold. Only one non-blocking nit. I did not run the tests.
MILL_REVIEW_END
