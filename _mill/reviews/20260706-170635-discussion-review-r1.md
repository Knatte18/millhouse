I have verified all key premises. The critical finding: the #605 fix enumerates exactly three read sites and states "three edits total, not one," but `millpy-review-plan.py:183` is a fourth, identical `--agent-output` read site — and mill-plan's SKILL.md (line 187) routes plan review through the same Agent-mode prepare→Agent→finalize flow, so it is subject to the same HTML-escaping corruption.

MILL_REVIEW_BEGIN
# Review: Fix agent-mode dispatch gaps: HTML escaping, missing flags, timeouts, and stale skill content

```yaml
verdict: GAPS_FOUND
reviewer_model: opushigh
reviewed_file: _mill/discussion.md
date: 2026-07-06
```

## Findings

### [GAP] #605 misses the review-plan read site
**Section:** Decisions › html-unescape-at-read-site; Technical context; Testing
**Issue:** The decision enumerates exactly three read sites and asserts "three edits total, not one," but `millpy-review-plan.py:183` (`raw_text = agent_output_path.read_text(...)` → `finalize(...)`) is a fourth, identical `--agent-output` read site; mill-plan/SKILL.md line 187 dispatches plan review via the same Agent-mode finalize flow, so it is equally exposed to the HTML-escaping corruption, yet the Scope "In" clause says "every site."
**Fix:** Add `millpy-review-plan.py` (~line 183) as a fourth `html.unescape(...)` site (four edits, not three), and extend the Testing section's per-CLI finalize case to cover it — or explicitly justify in Scope "Out" why plan-review is excluded.

## Verdict

GAPS_FOUND
The #605 fix omits an identical fourth agent-output read site in millpy-review-plan.py.
MILL_REVIEW_END