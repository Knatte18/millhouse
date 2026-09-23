MILL_REVIEW_BEGIN
# Review: mill-setup/wiki/docs/build-env: misc small bugs, round 3

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewed_file: _mill/discussion.md
date: 2026-09-23
```

## Findings

### [BLOCKING:design] #1113 testing plan doesn't cover the visible non-Python candidate site
**Section:** Testing (#1113) / Decision 1113-investigation-in-plan
**Issue:** `mill-triage-to-tasks/SKILL.md` Step 5 already shows a concrete, plausible corruption site for synthesized titles: `title='<title>'` substituted directly into a bash-embedded Python `-c` single-quoted string literal — agent-composed shell text, not deterministic `.py` code. The Testing bullet only says "regression test (unit test if the fix lands in a `.py` helper)" and trails into unit-test language (asserts a single apostrophe survives) without stating what verification applies if the fix instead means changing this raw string-interpolation pattern in the SKILL.md.
**Fix:** Read `mill-triage-to-tasks/SKILL.md` Step 5 as part of discussion (or explicitly state the non-Python fix/verification shape — e.g. pass title via a scratch JSON file instead of interpolation, verified manually like #1138/#1111) so mill-plan isn't left forcing a Python regression test onto a prompt-authored bug.

### [NIT:scope] millpy-fold.py listed as an #1113 candidate but never sets title
**Section:** Technical context (#1113)
**Issue:** `millpy-fold.py`'s only `upsert_task` call passes `brief=new_brief`; it never passes `title`, so it structurally cannot be the title-corruption site despite being listed as a candidate to check.
**Fix:** Drop it from the candidate list, or replace it with the concrete `mill-triage-to-tasks` Step 5 site found above.

### [NIT:design] #1111 fallback trigger condition ("network restriction") left undefined
**Section:** Decision 1111-sandbox-fallback
**Issue:** The fallback applies "specifically due to network restriction (transient dependency host unreachable)," but neither the decision nor the Technical context says how the skill should distinguish that failure mode from other `go install` failures (permissions, disk, broken toolchain) — those must still stop and report per current behavior.
**Fix:** Either broaden the fallback to any install failure, or name the error signature (e.g. "dial tcp", "no such host", connection timeout) that triggers it.

## Verdict

REQUEST_CHANGES
#1113's testing strategy doesn't account for the visible non-Python candidate site in mill-triage-to-tasks.
MILL_REVIEW_END
