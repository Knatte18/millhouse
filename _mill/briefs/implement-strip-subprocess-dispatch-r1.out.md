41 chars including newline = 40-char SHA, correct: `d9cc532ce244f7efcf996589837d6ddda686af8b`.

{"status":"success","commit_sha":"d9cc532ce244f7efcf996589837d6ddda686af8b","session_id":"90df0501-a8b8-45ab-8a0c-8365ace5e461","cards_done":[2,3,4,5,6,7,8,9,10,11]}

All 10 cards declared in batch `02-strip-subprocess-dispatch.md` (cards 2 through 11) were implemented and committed this turn — 10 of 10 cards committed, all complete. Verify command (`test-guards.py`, `test-mill-go-variants.py`, `test-skill-helper-drift.py` via `run-all.py --only`) passed. An additional stray uncommitted drift file from the prior batch (`_mill/briefs/implement-regression-guard-r1.out.md`, outside this batch's scope) was found dirty at the pre-report self-check and committed to satisfy the cleanliness gate.

Key file modified: `/home/hanf/Code/millhouse/wts/mill-go-base-agent-dispatch-only/plugins/mill/skills/mill-go-base/SKILL.md` (1484 -> 1196 lines). All literal occurrences of `psmux`, `millpy-bg`, and `` `dispatch == subprocess` `` are gone from the file (confirmed via grep), every `` If `dispatch == agent`: `` conditional in the Implement/Code-Review/Resume/Holistic sections is now unconditional prose, and both psmux session-cleanup blocks (per-batch and holistic) plus all their call sites are removed, along with the holistic bg-log crash-recovery branch (c).

{"status":"success","commit_sha":"d9cc532ce244f7efcf996589837d6ddda686af8b","session_id":"90df0501-a8b8-45ab-8a0c-8365ace5e461","cards_done":[2,3,4,5,6,7,8,9,10,11]}