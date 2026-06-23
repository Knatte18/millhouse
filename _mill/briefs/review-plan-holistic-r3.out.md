MILL_REVIEW_BEGIN
# Review: Fix agent-dispatch cwd guard, implementer self-termination, and false-success contracts — holistic

```yaml
verdict: APPROVE
reviewer_model: opushigh
reviewed_file: plan/
date: 2026-06-23
```

## Findings

### [NIT] Decision overstates resolve_hub_path "never cwd"
**Location:** 00-overview / Decision "cwd-independent hub resolution"; Batch 1 Cards 2-4
**Issue:** The Decision says `resolve_hub_path()` "walks up to the `.millhouse/config.local.yaml` marker, never on `Path.cwd()`", but the no-arg form does call `Path.cwd()` internally and only walks up from cwd; the nested-hub git-root case resolves correctly only when a worktree-root stub with `hub_relative_path` exists.
**Fix:** Reword the Decision to "anchors on `resolve_hub_path()` (cwd walk to the `.millhouse/` marker, stub-aware) rather than a raw `Path.cwd()` literal".

### [NIT] Card 8 card_count regex over-escaped for findall
**Location:** Batch 2 / Card 6 and Card 8
**Issue:** Card 8 specifies the pattern with doubled backslashes; in an actual .py raw string the pattern needs single backslashes. The doubled form could be copied literally and silently match nothing (card_count=0 -> gate disabled).
**Fix:** Clarify that the implemented regex uses single-backslash raw-string form; the doubled backslashes are markdown escaping only.

### [NIT] Manifest omits test-millpy-implement.py
**Location:** Batches 1 and 2 / verify and Batch Tests
**Issue:** Both batch verify commands run test-millpy-implement.py, which is not in any card manifest; the file mocks _subprocess_util.run to return a non-numeric sha — the exact case Card 6 guards against.
**Fix:** Add test-millpy-implement.py to a card manifest; informational.

## Verdict

APPROVE
Line numbers, signatures, decisions, and DAG all verified accurate; only minor wording/escaping clarifications.
MILL_REVIEW_END
