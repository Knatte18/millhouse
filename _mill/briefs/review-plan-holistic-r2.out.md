MILL_REVIEW_BEGIN
# Review: millpy-implement.py --stage baseline: WinError 3 snapshotting a transient/generated file on Windows — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewed_file: plan/
date: 2026-07-29
```

## Findings

### [NIT] Card 4 omits MagicMock import despite needing DirEntry stand-ins
**Location:** Batch 1 / Card 4
**Issue:** Requirements add only `from unittest.mock import patch`, but cases 1-2 need mocked `DirEntry`-shaped objects (`is_symlink()` raising) which typically require `MagicMock` or an equivalent stand-in, unlike Card 3 which explicitly imports both `MagicMock, patch`.
**Fix:** Note that `MagicMock` (or a plain stand-in class) is available/needed for constructing the fake entries, matching Card 3's explicit import list.

### [NIT] Inner per-entry log message in `_junction.py` reuses directory-scan wording
**Location:** Batch 1 / Card 2
**Issue:** The per-entry guard's message `"[junction] WARNING: vanished entry scanning {ep}; skipping"` reuses the "scanning" phrasing designed for the directory-level `os.scandir` failure, even though `ep` is a single entry being processed, not a directory being scanned — slightly misleading log semantics.
**Fix:** Non-blocking; implementer may adjust wording (e.g. "vanished entry: {ep}; skipping") as long as it stays distinct from the `PermissionError` text, which is the only hard requirement stated.

## Verdict

APPROVE
Plan is precise, source-grounded (line numbers, function names, message text all verified against source), and fully scoped; only cosmetic nits remain.
MILL_REVIEW_END
