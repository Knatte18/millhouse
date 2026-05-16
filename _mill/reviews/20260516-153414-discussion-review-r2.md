I have enough to write the review.

# Review: 57 (A) — Move config.yaml and agents.yaml from wiki to hub worktree

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax_tool
reviewed_file: _mill/discussion.md
date: 2026-05-16
```

## Findings

### [GAP] Phase 3.1 / 3.2b ordering produces data loss or deadlock
**Section:** `## Technical Context — mill-setup phases`
**Issue:** Phase 3.1 is described as running *before* Phase 3.2b ("sits between 3.1 and 4.x"). Phase 3.1's new behaviour seeds `mill-config.yaml` from template "if missing". On first migration run, `mill-config.yaml` is missing → Phase 3.1 seeds it with template defaults → Phase 3.2b sees scenario 2 (both files exist) → deletes `wiki/config.yaml` without copying the operator's settings. The operator's customisations are silently discarded. Alternatively, if Phase 3.1's "halt if `wiki/config.yaml` still exists" fires unconditionally, mill-setup halts before Phase 3.2b ever runs. Both readings produce a broken migration.
**Fix:** Specify that Phase 3.2b runs *before* Phase 3.1 (or that Phase 3.1's seed step is gated on `wiki/config.yaml` being absent), and clarify exactly when Phase 3.1's halt check fires (only when `mill-config.yaml` already exists, not on first migration run).

### [NOTE] "No code reads autonomous_mode" is wrong
**Section:** `## Scope — Out`; `## Q&A log`
**Issue:** Scope "Out" states "no production code currently reads `cfg["pipeline"]["autonomous_mode"]`" and the Q&A log repeats "no code reads it today". Source-verified callsites: `mill-go:232`, `mill-go:349`, `mill-plan:153`, `mill-plan:155` — all read this key. The Technical Context section on the same page correctly identifies the callsites and explains why this is safe to leave alone; the Scope and Q&A claims simply contradict it.
**Fix:** Remove the "no production callsites" claim from Scope "Out" and Q&A; instead say "callsites in mill-go and mill-plan are left unchanged in this PR — covered by the intermediate-state analysis in Technical Context."

### [NOTE] load_config callsite count understated
**Section:** `## Technical Context — Current config load path`
**Issue:** Discussion says "nine lenient callsites and eight strict callsites" (17 total). Grep of `plugins/mill/scripts/` counts ~13 lenient callsites (`millpy-vscode.py` alone has four) and 8–9 strict, totalling ~21. A plan writer relying on the stated count would under-scope the callsite migration.
**Fix:** Correct the counts, or replace with "see grep output — update all callers of `_config.load_config` and `_review_common.load_config` that currently pass `wiki_path`."

## Verdict

GAPS_FOUND  
Phase 3.1 / 3.2b ordering has a concrete data-loss path; must be resolved before planning.