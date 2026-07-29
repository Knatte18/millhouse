All 3 cards (12, 13, 14) for batch 03-merge-in-semantic-duplication are complete: 3 of 3 cards committed. Cards 12 and 13 both edited `plugins/mill/templates/merge-in-conflict-brief.md` and were combined into one commit (`ad83f296`, named per Card 13's later commit message as required); Card 14 edited `plugins/mill/skills/mill-merge-in/SKILL.md` and got its own commit (`77c42fb0`). Batch `verify: null`, so no test run was required. Working tree is clean (no uncommitted tracked changes).

Files touched:
- `plugins/mill/templates/merge-in-conflict-brief.md` — added new step 4 (move-vs-duplicate instruction with confident/ambiguous branches and two worked examples), renumbered old steps 4-6 to 5-7, and extended the Report section's `discarded` field description to cover the ambiguous kept-both entry.
- `plugins/mill/skills/mill-merge-in/SKILL.md` — generalized Step 3's "Real code conflicts" row operator guidance to branch on each `discarded` entry's description text (drop vs. kept-both/ambiguous).

{"status":"success","commit_sha":"77c42fb0","session_id":"b6ae8e15-1a98-40c7-a4fb-45978b32a392","cards_done":[12,13,14]}