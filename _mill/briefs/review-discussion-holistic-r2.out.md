MILL_REVIEW_BEGIN
# Review: status.md: rename parent to parent_branch, add parent_thread

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewed_file: _mill/discussion.md
date: 2026-09-24
```

## Findings

### [BLOCKING:consistency] `--parent` control-char rationale unverified, undertested
**Section:** Decisions > `millpy-spawn --parent`
**Issue:** `_yaml_writer.quote_scalar` (`plugins/mill/scripts/_yaml_writer.py`) only explicitly raises `ValueError` when the value contains `\n`; every other character, including other C0 control chars, is delegated to `yaml.safe_dump`, which represents them via double-quoted escapes (`"\x01"`) rather than raising. The decision's rationale ("without this check, `quote_scalar` would raise a bare `ValueError`") is only true for the newline case, not for "other control character" generally.
**Fix:** Either narrow the rationale/check to newline only, or if the broader control-char rejection is wanted as independent hardening (not "without this check X crashes"), say so and add a Testing-section case for a non-newline control char — currently Testing only exercises the newline path, leaving the decision's broader claim unverified by any test.

## Verdict

REQUEST_CHANGES
One decision's stated rationale doesn't match `quote_scalar`'s actual behavior and its coverage.
MILL_REVIEW_END
