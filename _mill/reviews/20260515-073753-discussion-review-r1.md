Now I have enough source context to write the review.

# Review: 56 (A) — Fix mill-go/start/plan/merge runtime behavioral bugs

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax_tool
reviewed_file: _mill/discussion.md
date: 2026-05-15
```

## Findings

### [GAP] #279 extension limit is unimplementable as written
**Section:** `### #279` Decision + Technical Context
**Issue:** The decision says "allow one extra round" and rejects "any number of extra rounds," but the Technical Context implements this as an unconditional per-round check (`isdisjoint and round >= 2` → allow one extra), with no flag or counter to prevent the extension from re-triggering on subsequent rounds. A plan writer following the Technical Context verbatim produces unlimited extension — the behaviour the decision explicitly rejected.
**Fix:** State whether the extension is one-time-ever (add a `extension_used: bool` flag) or one-per-disjoint-transition. If one-time-ever, add the flag and blocking rule ("once extension_used is True, apply cap regardless of disjointness") to the Technical Context.

## Verdict

GAPS_FOUND
One behavioural contradiction between the #279 decision and its Technical Context; plan writer cannot resolve it without a coin-flip.