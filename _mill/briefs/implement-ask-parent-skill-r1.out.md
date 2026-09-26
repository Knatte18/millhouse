All 3 of 3 cards are committed and pushed, and all three verify tests pass (test-skill-helper-drift, test-skills-index, test-guards).

- Card 6: created `plugins/mill/skills/ask-parent/SKILL.md`.
- Card 7: edited `plugins/mill/docs/harness-tool-contracts.md`. The wait-section counts and consumer list now say five and three, and a new `SendMessage to a peer session` section follows the Monitor section.
- Card 8: regenerated `SKILLS.md`.

Card 8 changed a second row besides the new `ask-parent` one. The `mill-merge-in` description dropped "codeguide-update" because the committed row was stale against that skill's current frontmatter. The cached scanner and the worktree scanner both produce this diff. I ran the worktree scanner as the card directs and kept its output.

{"status":"success","commit_sha":"3d3dd964a3e422b1436b36c2c96b09c8e135625b","session_id":"a7bd68bf-b89a-4739-a568-891a899fb4b9","cards_done":[6,7,8]}
