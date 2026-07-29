MILL_REVIEW_BEGIN
# Review: mill-plan/review validation false-positives, hard-fails, and truncated failure reasons

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetxhigh
reviewed_file: _mill/discussion.md
date: 2026-07-29
```

## Findings

### [GAP] Fix 5 marker patterns miss mill's own run-all.py failure format
**Section:** Decision — Fix 5 / Testing — Fix 5
**Issue:** `plugins/mill/unit_tests/run-all.py` (this repo's own Python verify-command runner) emits per-test lines `--- FAIL <name> (Ns) ---` and a summary `FAIL -- <n> of <m> in <t>s: [...]` (run-all.py:91,107) — neither starts with `--- FAIL:` (needs a colon), `FAIL\t` (needs a literal tab), or `FAILED ` (needs the word "FAILED"), so Fix 5's extraction silently falls back to marker-only for self-hosted Python verify failures — one of the Problem section's three named real-usage contexts, and the same ecosystem Fix 3/CLAUDE.md's verify conventions center this task on.
**Fix:** Add a pattern covering `run-all.py`'s actual format (e.g. `^--- FAIL ` / `^FAIL -- `), or state explicitly that the enrichment is scoped to Go/pytest only and self-hosted Python `run-all.py` failures remain marker-only by design.

### [GAP] Fix 4's git check-ignore root/candidate choice unresolved for nested layouts
**Section:** Decision — Fix 4
**Issue:** `resolve_ref_paths` (`_review_common.py:820-923`) builds up to three fallback candidates before hard-failing (`git_root/root/raw`, `project_root/root/raw` or `project_root/raw`, `git_root/raw`), but the decision's `git -C <git_root or project_root> check-ignore -q <candidate>` doesn't say which root backs `-C` or which candidate (the primary `candidates[0]` used for error reporting, or each fallback in turn) is actually tested. This matters precisely in the nested-layout case (`hub_root != git_root`) CLAUDE.md treats as a first-class footgun, where the two roots diverge and a candidate under one root may not exist as a git working tree under the other.
**Fix:** State explicitly: for each fallback candidate in the existing resolution order, run `check-ignore` with `-C` set to the root that produced that candidate, short-circuiting on the first git-ignore hit; only hard-fail if none of the candidates resolve as git-ignored either.

## Verdict

GAPS_FOUND
Fix 5's failure-marker set misses this repo's own test-runner format; Fix 4's check-ignore root/candidate choice is unresolved for nested layouts.
MILL_REVIEW_END
