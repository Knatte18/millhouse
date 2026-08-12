Both cards committed, working tree clean, verify passes. Card-count self-check: 2 of 2 cards committed (Card 12, Card 13) — all complete.

{"status":"success","commit_sha":"ef7f7b5506f0b744b02366bc00d98456f413d0f7","session_id":"89de920e-ce1b-4207-ba63-be51031ad2bb","cards_done":[12,13]}

Summary: Implemented batch 3 (treeguard-dedup) of the mill-go-base strip task — 2 of 2 cards committed.

- `/home/hanf/Code/millhouse/wts/mill-go-base-agent-dispatch-only/plugins/mill/skills/mill-go-base/SKILL.md`: Card 12 added a new `**Tree-guard checkpoint block.**` definition inside `## Agent-mode dispatch` (between the `**Agent-mode properties:**` bullets and `**Why not fork?**`), defining pre-dispatch and post-dispatch forms with the shared body and both helper `signature:` lines. Card 13 replaced all twelve `_treeguard.check_and_restore(` call-site paragraphs (5 in `### 3. Code Review loop`, 7 in `## Holistic code review`) with one-line references to the named block, deleted the stale off-by-one "All 11 other tree-guard checkpoints..." sentence, and preserved the two site-specific sentences (the loop-header's modify-then-delete-window note, and sub-step 3.6's pre-dispatch-before-re-running-sub-step-3 requirement).

Post-edit grep confirms exactly 2 occurrences of `_treeguard.check_and_restore(` remain in the file, both inside the named block (one executable call, one signature line), matching the batch's postcondition.

Commits: `0a3610c0` (card 12), `ef7f7b55` (card 13). Verify command (`run-all.py --only test-guards.py test-mill-go-variants.py test-skill-helper-drift.py`) passed all 3 tests. Working tree is clean.