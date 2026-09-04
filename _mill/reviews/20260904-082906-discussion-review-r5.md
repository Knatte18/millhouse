MILL_REVIEW_BEGIN
# Review: mill-go: done-gate halt path and cleanliness-gate recovery are under-documented

```yaml
duration_s: 157.0
verdict: APPROVE
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 4.5 (self-assessed; exact minor version unconfirmable from within the session)
reviewed_file: _mill/discussion.md
date: 2026-09-04
```

## Findings

None. Cross-checked every technical-context claim against source: `handoff.md`'s four halt sites (pre-done-gate, unfixed-nits ~L33, terminal-dirt ~L53/59/61, scope-violations ~L84) confirmed to currently lack lock-release/notify; `SKILL.md`'s canonical `### Blocked` shape (~L859-868: notify, then lock-release, then message) confirmed as the mirrored precedent; `holistic-review.md`'s four halt paths (~L114-146) confirmed already release the lock, supporting the out-of-scope claim. `_done_gate.py`'s `run_preflight` confirmed to lack dotnet cleanup and to not currently call the Handoff inline block, supporting the DRY rationale; the inline block's `status: blocked` key (L116/128) confirmed as the thing `run_gate`'s `result` key must replace in lockstep. `_parent_branch.check_liveness`/`resolve_dead_parent` confirmed to exist with the exact three-outcome (`resolved`/`fallback`/`cycle`) shape the decision relies on, plus existing unit coverage (`test-parent-branch.py`), matching the Testing section's claim. `mill-merge`/`mill-merge-in`'s liveness-check-then-confirm flow confirmed as the correct reference pattern, and the decision's non-interactive auto-rebind-on-`resolved`-only deviation is justified against it. `mill-pause/SKILL.md` confirmed as the described 26-line, two-case file. `_cleanliness.py`'s rule-3 branch (~L306-313) confirmed as the correct extension-bearing edit site for `.pyc`/`__pycache__`. `SKILL.md` step 3(b)/(c) (~L297-341) and step 5.5 (~L379-403) confirmed as the liveness-probe precedent and target site respectively. `test-done-gate.py` and `test-cleanliness.py` both already exist, consistent with the Testing section's TDD framing. No undecided items, no scope ambiguity, all six Decisions carry rationale and rejected alternatives.

## Verdict

APPROVE
All technical claims verified against source; decisions, scope, and testing strategy are complete and internally consistent.
MILL_REVIEW_END
