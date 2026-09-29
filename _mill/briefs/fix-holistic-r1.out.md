Fixed the one review finding: bare `{lang}-build` references in git-commit (line 17) and git-pr (line 136) now read `scribe:{lang}-build`. A grep for bare `{lang}-build`, `{lang}-comments` and `{lang}-testing` across `plugins/` finds no other occurrences.

I added `git-pr/SKILL.md` to card 7's `Edits:` list in `_mill/plan/02-mill-skill-references.md` before editing it. All three changes went in one commit. Only markdown changed, so I skipped the lint step. I did not widen the card 11 sweep the review suggested, because its grep patterns aren't in the plan file I read.

All three batch `verify:` commands exit 0, and there are no uncommitted tracked changes.

{"status":"success","commit_sha":"2a3976a798a9268090997b10d054263cbb654749","session_id":"aa461993-1299-4877-8b52-5163dbadbda6"}
