MILL_REVIEW_BEGIN
# Review: mill-go2: opt-in skill scaffold cloned from mill-go (no fork yet) — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewed_file: plan/ + source
date: 2026-08-11
```

## Findings

### [BLOCKING:scope] Two commit-message literals still hardcode `mill-go:` instead of `<VARIANT_LABEL>:`
**Location:** `plugins/mill/skills/mill-go-base/SKILL.md:684`, `:1016`
**Issue:** Card 4's grep-based site enumeration (`commit -m "mill-go: `) only matches the literal shell invocation shape, so it missed two narrative citations of the same commit-message content: line 684 reads `...append " (min_rounds/demoted-predicate not satisfied by round cap)" to the approve-commit message ("mill-go: approve batch {batch_name}")`, and line 1016 has the identical pattern for `"mill-go: holistic approve {slug}"`. Both quote the message with the literal `mill-go:` prefix even though the actual commit invocations they describe (lines 795 and 1233, respectively) correctly use `<VARIANT_LABEL>: approve batch {batch_name}` / `<VARIANT_LABEL>: holistic approve {slug}`. This is exactly the scenario `_mill/discussion.md`'s `variant-label-in-logs` Decision warns against ("A missed site silently keeps a `mill-go:` prefix under mill-go2, defeating `variant-label-in-logs`") and contradicts the `variant-token-form` Shared Decision. A Builder following line 684/1016 literally when constructing the round-cap-exhausted approve commit would compose a `mill-go:`-prefixed message under mill-go2 instead of `mill-go2:`.
**Fix:** Replace `"mill-go: approve batch {batch_name}"` at line 684 and `"mill-go: holistic approve {slug}"` at line 1016 with the `<VARIANT_LABEL>:` form, matching lines 795/1233.

### [NIT:scope] Parameterization-lock test doesn't catch the above miss
**Location:** `plugins/mill/unit_tests/test-mill-go-variants.py:34` (`MILL_GO_LITERALS`)
**Issue:** `MILL_GO_LITERALS` checks the exact substring `'commit -m "mill-go: '`, which requires `commit -m "` immediately adjacent to `mill-go:`. The two narrative citations above quote `"mill-go: ...` without that prefix, so check 7 (`_check_parameterization_lock`) passes despite the leftover literals — this is why the batch-3 `verify:` gate is currently green over the defect above.
**Fix:** Widen the literal to the narrower substring `'"mill-go: '` (or add a second entry covering the bare quoted form) so any quoted `mill-go:`-prefixed message, not just full `commit -m "..."` invocations, is caught.

## Verdict

REQUEST_CHANGES
Two commit-message citations in mill-go-base/SKILL.md still hardcode `mill-go:` where `<VARIANT_LABEL>:` is required.
MILL_REVIEW_END
