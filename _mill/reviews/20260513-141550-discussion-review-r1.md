I have sufficient information to write the review.

# Review: (B) — Size-based reviewer switch (mechanism + configurable target)

```yaml
verdict: APPROVE
reviewer_model: sonnetmax_tool
reviewed_file: _mill/discussion.md
date: 2026-05-13
```

## Findings

### [NOTE] Signature discrepancy: Decisions vs Technical Context
**Section:** `### Helper location` (Decisions) vs `## Technical context`
**Issue:** Decisions shows a 6-arg signature returning `tuple[dict, str | None]`; Technical Context adds `reviewer_name: str` as the 3rd parameter and returns `tuple[dict, str]`. A plan writer reading only Decisions would implement a 6-arg function that derives the name internally and may return None, conflicting with the call-site pattern.
**Fix:** Note in the plan that Technical Context's 7-arg, `-> tuple[dict, str]` signature is authoritative; Decisions section was an earlier draft.

### [NOTE] Unit test list omits cluster-type rejection for `validate_role_refs`
**Section:** `## Testing`
**Issue:** Test #7 covers "bad `large_prompt.reviewer` name" (unknown name), but Constraints explicitly require `validate_role_refs` to reject a name that resolves to a cluster spec — a distinct case, since `_reviewers.resolve()` succeeds for cluster names without raising.
**Fix:** Add an 8th test: `validate_role_refs` with a `large_prompt.reviewer` pointing to a valid cluster-type name — confirm error is raised.

## Verdict

APPROVE
Two minor notes; no gaps block plan writing.