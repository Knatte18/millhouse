Batch 03-close-issue (round 1) complete.

Card 12 (close GitHub issue #1137, Commit: none): ran the idempotency check first — `gh issue view 1137 --json state,comments` showed `state: CLOSED` with `last_comment` already exactly matching the required closing comment body. Per the card's instructions, this means the GitHub actions (comment + close) already happened in a prior round, so I did NOT re-run `gh issue comment` or `gh issue close`. No file edits were required for this card (Edits/Creates/Deletes/Moves all "none"), so no commit was made or needed for this turn.

Verify command ran and passed: neither `CODEGUIDE_PLUGIN_ROOT` nor `codeguide-update` markers remain in `plugins/mill/skills/git-commit/SKILL.md` / `plugins/mill/skills/mill-merge-in/SKILL.md`, and both `test-sibling.py` and `test-guards.py` passed cleanly (per round-1's prior-failure note, `test-worktree-sibling-resolution.py` was already dropped from this batch's verify command since its Scenario A failure is pre-existing on `main` and unrelated to this plan).

`git status --porcelain --untracked-files=no` was clean before reporting.

Card-count self-check: batch declares 1 card total (Card 12, Commit: none). 1 of 1 complete — no matching commit-log entry expected since it's a Commit: none card, and requirements were freshly re-verified this turn via the `gh issue view` idempotency check.

Files read (no files edited this batch): `/home/hanf/Code/millhouse/wts/deactivate-codeguide/plugins/mill/skills/git-commit/SKILL.md`, `/home/hanf/Code/millhouse/wts/deactivate-codeguide/plugins/mill/skills/mill-merge-in/SKILL.md`.

{"status":"success","commit_sha":"f94eae89a70a933006a54f7418257ea0e4ac067e","session_id":"a135da84-17f4-430e-b46c-a5a317fa1255","cards_done":[12]}
