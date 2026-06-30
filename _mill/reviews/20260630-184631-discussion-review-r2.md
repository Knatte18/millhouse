Final confirmation: line 22 of `_marker.py` is `from wiki import _client as wiki`, so the local name `wiki` inside this module already *is* the `_client` module. This solidifies the finding. I now have everything needed for the review.

MILL_REVIEW_BEGIN
# Review: Fix discussion review round-cap, daemon cold-start, and nits-only no-op in finalize

```yaml
verdict: GAPS_FOUND
reviewer_model: opushigh
reviewed_file: C:\Code\millhouse\wts\mill-review-and-finalize-gaps\_mill\discussion.md
date: 2026-06-30
```

## Findings

### [GAP] `wiki._client.health_check(...)` call site is wrong inside `_marker.py`
**Section:** Decisions -- "WikiStartupError retry lives in `_marker.slug_from_branch()`"; also Scope bullet 2; also Technical context (Gap 2 files)
**Issue:** The Decision/Scope text says the retry must "call `wiki._client.health_check(wiki_path)`", but `_marker.py` (verified: `plugins/mill/scripts/_marker.py:22`) already does `from wiki import _client as wiki` -- inside that module `wiki` *is* the `_client` module, so `wiki._client.health_check(...)` would raise `AttributeError` (`_client.py` has no nested `_client` attribute, confirmed by grep). The correct call in that namespace is `wiki.health_check(wiki_path)`. The Technical Context paragraph even states the alias exists, but the literal call expression repeated 3x (Scope, Decision rationale, and implicitly elsewhere) is never corrected to match it.
**Fix:** Change all three occurrences to `wiki.health_check(wiki_path)` (or explicitly note "within `_marker.py`'s existing `wiki` alias, call `wiki.health_check(...)`, not `wiki._client.health_check(...)`") so a plan writer doesn't copy the broken literal call site.

### [NOTE] `--max-rounds` precedent misattributed to mill-go
**Section:** Decisions -- "Round-cap extension is a SKILL.md-only fix"
**Issue:** Rationale says the design "mirrors the precedent already used by `millpy-review-plan.py --max-rounds` (driven by mill-go's own round-cap escape hatch)". Verified: the actual precedent is `plugins/mill/skills/mill-plan/SKILL.md:218,222` -- an *operator-driven* manual re-invocation offered as option B in mill-plan, not a SKILL-internal automatic mechanism in mill-go. `mill-go/SKILL.md` has no `--max-rounds` usage at all (grep confirmed). This new design (mill-start's `--auto` loop autonomously computing and passing `--max-rounds` with no operator involved) is actually a new pattern, not a straight mirror of the cited precedent.
**Fix:** Correct the citation to "mill-plan/SKILL.md's operator-driven escape hatch" and note this is the first *autonomous* (non-operator) use of the `--max-rounds` override, since that distinction doesn't change the soundness of the decision itself.

## Verdict

GAPS_FOUND
One GAP: corrected call-site notation needed for `health_check()` inside `_marker.py`.
MILL_REVIEW_END
