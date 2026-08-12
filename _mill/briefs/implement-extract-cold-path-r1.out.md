All 6 of 6 cards committed (cards 14-19), verify passes, and the tree is clean.

{"status":"success","commit_sha":"1c7d2a7b6537672505ab5cd7ec7f82c60cf31b95","session_id":"68ccc393-72df-44db-b5a0-3fdb037e7618","cards_done":[14,15,16,17,18,19]}

Summary of work done, all paths relative to `/home/hanf/Code/millhouse/wts/mill-go-base-agent-dispatch-only`:

- Card 14: created `plugins/mill/skills/mill-go-base/resume.md` — verbatim `## Resume` body extraction.
- Card 15: created `plugins/mill/skills/mill-go-base/holistic-review.md` — verbatim `## Holistic code review` body extraction.
- Card 16: created `plugins/mill/skills/mill-go-base/handoff.md` — verbatim `## Handoff` body extraction.
- Card 17: edited `plugins/mill/skills/mill-go-base/SKILL.md` to replace the three section bodies with mandatory-read pointers and appended `## History`. Discovered and fixed a real plan defect first: the discussion/plan's mandated `## History` note text contained the literal `psmux`, which conflicts with `test-mill-go-base-agent-only.py`'s banned-literal check. Edited `_mill/plan/04-extract-cold-path.md` to reword the note (avoiding the literal while preserving meaning) and committed that plan fix (`797da0a8`) before implementing.
- Card 18: repaired cross-file references in all four files (`SKILL.md`, `resume.md`, `holistic-review.md`, `handoff.md`) — rewrote every "above"/"below" positional reference that now crosses a file boundary to name the target file explicitly, and named companion files in SKILL.md's forward references (Mid-execution phase-gate widening routing bullets, Blocked's "Do not proceed to Handoff", 0.55's Handoff-time comparisons, Entry step 3's "Handoff step 6").
- Card 19: edited `plugins/mill/unit_tests/test-skill-helper-drift.py` — widened the helper-reference scan to union SKILL.md files with the mill-go-base companion `*.md` files, and re-pointed the `#496` `reviews_dir` lock to search across SKILL.md plus companions.

Verify command ran clean: `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-mill-go-base-agent-only.py test-guards.py test-mill-go-variants.py test-skill-helper-drift.py` — all 4 tests PASS. Working tree is clean (`git status --porcelain --untracked-files=no` empty). 6 of 6 declared cards committed.