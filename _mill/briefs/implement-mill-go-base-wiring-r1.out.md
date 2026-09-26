All 3 of 3 cards are committed, and all three verify tests pass (test-skill-helper-drift, test-mill-go-base-agent-only, test-mill-go-variants). No tracked changes are uncommitted.

- **Card 9:** `plugins/mill/skills/mill-go-base/SKILL.md` now sets up `parent_escalated_batches`, passes halt parameters from each stuck bullet, and has `### Blocked` as the parameterised funnel.
- **Card 10:** `holistic-review.md` got the new session-local flags, `--max-rounds` on both review dispatches, `escalate: false` on step 5's stuck bullets, and `go-holistic-cap` escalation at step 7 (approve, retry, halt).
- **Card 11:** `handoff.md` got the `go-handoff-nits` and `go-handoff-done-gate` escalation, plus a note that step 3 never escalates.

I committed each card with the git-commit skill but did not push.

{"status":"success","commit_sha":"300f5ce96b130c9c0dd0818d161a4c116262f630","session_id":"fa5824c4-c986-4a79-9181-2b4bdcea1a95","cards_done":[9,10,11]}
