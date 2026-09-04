MILL_REVIEW_BEGIN
# Review: _plan_validate.py verify: command validation: false positives, missing escape hatches, and a doc/enforcement mismatch

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-4.5
reviewed_file: _mill/discussion.md
date: 2026-09-04
```

## Findings

### [NIT:consistency] Scope bullet overstates pytest's per-runner message
**Section:** Scope (in), item 5 / Decision `fix-table-runner-agnostic-remedy` **Issue:** Scope claims the check's message field is "runner-correct — `-k`/`--only` for run-all.py/pytest," but the actual bare-pytest message ("no path or -k filter; scope it or document...") never mentions `--only` (a run-all.py-only flag) and is less prescriptive than run-all.py's message; the Decision's own Rationale (line ~68) correctly names only go/dotnet/run-all.py, not pytest, so this is an internal overstatement in the Scope summary only. **Fix:** Note in the plan that the pytest message lacks explicit flag guidance, or accept the vaguer wording as-is when writing the fix-table row.

## Verdict

APPROVE
Verified against source: line numbers, regex/message strings, kwarg counts, and config keys all check out; one cosmetic NIT.
MILL_REVIEW_END
