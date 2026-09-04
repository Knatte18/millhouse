MILL_REVIEW_BEGIN
# Review: mill-merge-in/mill-finalize/codeguide-update: cleanup-ordering and path-resolution bugs

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 4.5 (self-assessed; exact minor version unconfirmed)
reviewed_file: _mill/discussion.md
date: 2026-09-04
```

## Findings

### [BLOCKING:design] Doc-note target location left unresolved among 3 candidates
**Section:** Scope/In, item 5 ("A doc note ... wherever the existing `_mill/` lifecycle convention is documented"). **Issue:** Repo grep finds three distinct existing sites that document the "`_mill/` lives on task branch, discarded on merge" convention — `CLAUDE.md:57`, `plugins/mill/skills/workflow/SKILL.md:38`, and `plugins/mill/skills/mill-self-report/SKILL.md:36` — and the discussion never picks one (or states "all three"). **Fix:** Decide explicitly which file(s) get the new "citing `_mill/discussion.md` from a permanent doc is unsafe" note; a plan writer currently has three equally-plausible, unranked options.

## Verdict

REQUEST_CHANGES
One unresolved multi-candidate decision (doc-note placement) needs an explicit choice.
MILL_REVIEW_END
