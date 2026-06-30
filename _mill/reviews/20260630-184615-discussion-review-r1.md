I have enough to evaluate. Let me confirm one detail about how item `body` is currently written to task bodies (it's a minimal manifest, not the issue body) which is central to a finding — already confirmed in SKILL.md Step 5 line 91.

MILL_REVIEW_BEGIN
# Review: Split mill-ghissues-to-tasks into source adapter + source-agnostic analysis

```yaml
verdict: GAPS_FOUND
reviewer_model: opushigh
reviewed_file: _mill/discussion.md
date: 2026-06-30
```

## Findings

### [GAP] Per-item `body` embedding into task bodies unspecified
**Section:** Decisions — "contract carries ref-display fields" / Scope (In)
**Issue:** Current ghissues writes only a minimal manifest (`- Sources: #N — <title>` + run-hint, never the issue body — confirmed in SKILL.md Step 5). The discussion never says whether the shared skill embeds each item's `body` into grouped-task bodies, yet sandbox-report items carry full QA content and `detail_hint=null` implies the body is the only place that detail lives — so the two adapters need divergent body-writing, with no contract field controlling it.
**Fix:** State explicitly whether `mill-triage-to-tasks` embeds per-item `body` in task bodies, that ghissues must NOT (to preserve current output), and what contract signal (not just `detail_hint=null`) drives the difference — or where sandbox detail is preserved if bodies stay minimal.

### [NOTE] new/grouped close-comment string not carried in handoff
**Section:** Decisions — "Close-with-pointer stays out" / "Handoff uses two scratch files"
**Issue:** The results file carries only `ref` + route; the entry skill must reconstruct `Consolidated into wiki task: <slug>` (new) vs `Folded into wiki task: <slug>` (fold-in). Technical context names only the fold-in string verbatim; the "Consolidated" string is left to "exactly as today."
**Fix:** Note that the ghissues entry skill maps route→comment (new_task → `Consolidated into wiki task:`, fold_in → `Folded into wiki task:`) so the unchanged-behavior acceptance is met from the results file alone.

### [NOTE] Proposal markdown file owner/name not pinned post-split
**Section:** Decisions — "Handoff" / "required positional path arg" (empty-items "no proposal file")
**Issue:** Current proposal is `.scratch/ghissues-to-tasks-proposal.md`. After the split the shared skill does the proposing, but only `triage-contract.json` / `triage-result.json` are named; the proposal markdown's owner and filename are unstated.
**Fix:** Name the proposal artefact the shared skill writes (e.g. a single source-agnostic `.scratch/triage-proposal.md`) so both adapters present consistently.

## Verdict

GAPS_FOUND
Resolve how/whether sandbox item bodies are embedded before plan writing.
MILL_REVIEW_END