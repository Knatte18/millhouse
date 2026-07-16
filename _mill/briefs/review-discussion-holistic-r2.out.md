MILL_REVIEW_BEGIN
# Review: Miscellaneous small tooling and doc/template accuracy gaps

```yaml
verdict: APPROVE
reviewer_model: opushigh
reviewed_file: _mill/discussion.md
date: 2026-07-16
```

## Findings

### [NOTE] #651: absent `effort` on haiku not in tier spec
**Section:** Decisions / fixer-tier-warning-scope-and-callsite
**Issue:** The default fixer `haiku` (and `haiku_bulk`) has no `effort` key in mill-agents.yaml, but the tier tuple `(family, effort)` spec defines no rank for a missing effort; `fixer_spec.get("effort")` returns None.
**Fix:** State the default rank for absent effort (e.g. treat None as lowest) so the helper cannot KeyError/TypeError; in practice haiku's family rank dominates, so behaviour is safe once specified.

### [NOTE] #640: git_root param optionality vs "ROOD tests unchanged"
**Section:** Decisions / cleanliness-revert-hub-prefix-fix + Testing
**Issue:** Decision adds a `git_root: Path` (non-optional) parameter, but Testing requires existing flat-layout ROOD-* tests to "continue passing unchanged" — a required positional would break their `revert_out_of_scope_drift(worktree, task_dir, parent_branch)` call sites.
**Fix:** Clarify that `git_root` should default to `None` (flat), mirroring `compute_scope_violations`'s `git_root: Path | None`, so existing call sites need no edit.

### [NOTE] Stale sequential-batch claim in Q&A log
**Section:** Q&A log (line ~318)
**Issue:** An earlier Q&A entry still states #651 and #640 are "marked sequential (both touch mill-go/SKILL.md)", contradicting the corrected batch-structure Decision and the later correcting Q&A entry.
**Fix:** Mark the superseded entry as corrected inline so a plan writer skimming the log is not misled; the authoritative Decision is already correct.

## Verdict

APPROVE
Round-1 GAPs resolved; all five source claims verified accurate; only non-blocking NOTEs remain.
MILL_REVIEW_END
