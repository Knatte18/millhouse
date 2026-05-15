# Review: 52 (A) — Fix unit_tests/run-all destroying wiki during batch verify

```yaml
verdict: APPROVE
reviewer_model: sonnetmax_tool
reviewed_file: _mill/discussion.md
date: 2026-05-15
```

## Findings

### [NOTE] "Every test is at risk" overstates junction exposure
**Section:** Q&A log / safe-temp-dir-scope decision
**Issue:** Three tests in `test-setup-hub-links.py` create zero junctions inside their temp dirs: `test_hardlink_inode_skip_idempotent` (uses `_HARDLINK_ONLY_CFG`, no SLUG → 0 junctions), `test_all_entries_filtered_return_empty_lists` (`_ALL_SLUG_CFG`, no SLUG → 0 junctions), `test_cross_volume_hardlink_raises_clear_error` (explicit `"junctions": {}` → 0 junctions). The stated rationale "create_hub_links unconditionally creates NTFS junctions; every test is at risk" is factually incorrect for these three; intra-temp junctions in the other tests point within the temp tree and don't reach the real wiki.
**Fix:** The conclusion (migrate all 12) is correct as a conservative consistency choice; state the real rationale: uniform migration simplifies maintenance and avoids case-by-case analysis of which tests create junctions.

## Verdict

APPROVE
All decisions are made, scope is unambiguous, and the implementation path is concrete enough to plan directly.