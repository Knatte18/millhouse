MILL_REVIEW_BEGIN
# Review: Fix config unknown-key warning on git namespace and commit _mill/briefs/ after dispatch — holistic

```yaml
verdict: APPROVE
reviewer_model: opushigh
reviewed_file: plan/
date: 2026-06-19
```

## Findings

### [NIT] Card 4 brief-commit guard double-stages on porcelain check
**Location:** Batch 2 / Card 4
**Issue:** The guard `[ -n "$(git ... status --porcelain -- _mill/briefs)" ]` only reports changes vs HEAD; if a prior step already staged `_mill/briefs/` it still re-adds harmlessly, but if briefs were committed earlier in the run the porcelain output is empty and the commit is correctly skipped — behavior is correct, only the rationale prose could note the already-committed case explicitly.
**Fix:** Optional: add a one-line note that an already-committed brief yields empty porcelain and is skipped (no empty commit).

### [NIT] Card 5 assertion `mill-start: discussion-fix` substring count
**Location:** Batch 2 / Card 5
**Issue:** The substring `mill-start: discussion-fix` appears in both the interactive 4b commit (line 181) and the `--auto` 4b commit (line 37); a naive single-occurrence assertion is fine, but the suggested `_mill/briefs/ count >= 3` lower bound is loose given 5 add-sites land in mill-start.
**Fix:** Optional: tighten to count >= 4 (4b interactive, gap-fix, handoff guard, auto sites) or keep the per-message windowed checks already offered as the primary form.

## Verdict

APPROVE
Plan is sound, claims verified against source; findings are non-blocking nits only.
MILL_REVIEW_END
