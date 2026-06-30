I have verified the key claims. The discussion is well-developed and accurate against source (fold-in close string `Folded into wiki task: <slug>` confirmed in `millpy-fold.py`; `to_contract` target shape matches `_gh_issues.py`; test fixture mocking style confirmed). I found one genuine consistency gap plus minor notes.

MILL_REVIEW_BEGIN
# Review: Split mill-ghissues-to-tasks into source adapter + source-agnostic analysis

```yaml
verdict: GAPS_FOUND
reviewer_model: opushigh
reviewed_file: _mill/discussion.md
date: 2026-06-30
```

## Findings

### [GAP] Per-bullet detail_hint changes ghissues body output
**Section:** Decisions — "`detail_hint` and `embed_body` apply per source bullet" vs Scope/Out + Decision 3
**Issue:** Current `mill-ghissues-to-tasks` SKILL.md Step 5 writes all `- Sources: #N` lines then a single trailing `Run 'gh issue view #N' for full detail.` line; Decision 5 mandates one hint line per source bullet, which alters the grouped-task body for any multi-issue task — yet Scope/Out and Decision 3 repeatedly require ghissues output to "stay unchanged." A plan writer cannot tell whether to preserve the old single-trailing-hint format for ghissues or adopt per-bullet uniformly.
**Fix:** State explicitly whether the per-bullet hint reformatting is an accepted, intended change to ghissues task-body output (and amend the "behave identically" criterion accordingly), or scope per-bullet emission to sandbox-report only.

### [NOTE] detail_hint string differs from today's verbatim text
**Section:** Decision — `_gh_issues.to_contract()`
**Issue:** Decision sets `detail_hint="Run \`gh issue view #{ref}\` for full detail."` (backticks), but current SKILL.md emits `Run 'gh issue view #N' for full detail.` (single quotes); if "identical output" is required this wording drift is a deviation.
**Fix:** Confirm the exact hint string to use, or note the formatting change is acceptable.

### [NOTE] `meta` undefined for the sandbox-report contract
**Section:** Decision — `_sandbox_report.py validates strictly`
**Issue:** The contract shape includes a top-level `meta`, and ghissues sets `meta={"repo": repo}`, but `read()`'s described return values omit what `meta` is set to for sandbox-report.
**Fix:** Specify `read()`'s `meta` value (e.g. `{}` or passthrough) and whether the shared skill ever reads it.

### [NOTE] No wiki-junction entry check for mill-report-to-tasks
**Section:** Decision — "`mill-report-to-tasks` takes a required positional path arg"
**Issue:** `mill-ghissues-to-tasks` has an explicit entry check that `.millhouse/wiki/` exists; the new entry skill's checks cover only file path/shape, though it also writes the wiki via the shared skill.
**Fix:** State whether the wiki-junction precondition is checked by the entry skill or relied upon inside `mill-triage-to-tasks`.

## Verdict

GAPS_FOUND
Per-bullet detail_hint placement conflicts with the repeated "ghissues output unchanged" acceptance requirement.
MILL_REVIEW_END