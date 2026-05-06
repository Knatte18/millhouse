# Review: 23 (A) — mill infra bugfix-batch — 01-bugfix-batch

```yaml
verdict: APPROVE
reviewer_model: sonnetmax
reviewed_file: 01-bugfix-batch
date: 2026-05-06
```

## Findings

### [NIT] `_call` helper mock returncode unspecified
**Step:** Card 5
**Issue:** "patch `millpy_implement.subprocess.run` to avoid real git calls in those tests" doesn't specify `returncode=1`; a naive `returncode=0` mock overwrites `commit_sha` and breaks existing `test_fo_1`–`test_fo_6` assertions.
**Fix:** Add to Card 5 requirements: "mock subprocess.run with returncode=1 (simulating git failure) so existing assertions remain valid; tests 7–8 override this with their own per-test mock."

### [NIT] "sequential-letter naming convention" reference orphaned in Card 4
**Step:** Card 4
**Issue:** `test-status.py` uses no letter-prefix convention; the PASS messages specified in Card 4 also omit letters, making the "continuing from the last letter in use" phrase misleading.
**Fix:** Drop the convention reference; the PASS messages as written are sufficient.

### [NIT] `set_batch_fields` `None`-value behaviour unspecified
**Step:** Card 1
**Issue:** `set_batch_field` pops the key when `value is None`; `set_batch_fields` type annotation includes `None` but requirements don't say how to handle it.
**Fix:** Add one line to Requirements: "For entries where `value is None`, pop the key from the entry (matching `set_batch_field` behaviour)."

### [NIT] Import instruction slightly contradictory in Card 2
**Step:** Card 2
**Issue:** "Import `set_batch_fields` from `_status`" conflicts with "match the existing import style" (`import _status`); no per-function import exists in the file.
**Fix:** Change to "call via `_status.set_batch_fields(...)`, no import change needed."

## Verdict

APPROVE — zero BLOCKINGs; NITs are minor underspecifications an implementer can resolve.