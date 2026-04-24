---
kind: plan-overview
task: mill-groom skill
slug: mill-groom
approved: false
started: 20260424
parent: main
root: plugins/mill
verify: python plugins/mill/unit_tests/run-all.py && python plugins/mill/integration_tests/test-spawn.py && python plugins/mill/integration_tests/test-merge.py && python plugins/mill/integration_tests/test-plan-assets.py && python plugins/mill/integration_tests/test-go-assets.py && python plugins/mill/integration_tests/test-cleanup.py && python plugins/mill/integration_tests/test-status.py && python plugins/mill/integration_tests/test-abandon.py && python plugins/mill/integration_tests/test-inspect.py
batches: [skill, register]
---

# mill-groom skill — Plan

## Context

`mill-groom` is an interactive skill (not a script) that lets the user clean up
`Home.md` by shortening bloated entries, folding duplicates, dropping dead tasks,
and extracting long exploratory entries to proposal files. Claude proposes; user
approves; one commit lands.

The core deliverable is `plugins/mill/skills/mill-groom/SKILL.md`. No new Python
helpers are planned — the skill uses existing `_wiki.py`, `_tasks_md.py`, and
`_sidebar.py` (which Claude invokes via the bash-snippet pattern established in
`mill-ghissues-to-tasks`).

## Shared Decisions

- Brevity thresholds: `groom.brevity-threshold-lines` (default 5) / `groom.brevity-threshold-chars` (default 500) in `wiki/config.yaml`.
- Duplicate detection: LLM judgment only.
- Extraction collisions: error out, ask user.
- Invocation: `/mill-groom` — no arguments.
- Approval: all-or-nothing (`approve` / `reject`).
- Scratch cleanup: delete `.scratch/groom-proposal.md` after commit.
- Tests: no new tests; existing suite is the bar.

## All Files Touched

- plugins/mill/skills/mill-groom/SKILL.md  (created)
- SKILLS.md                                (modified — one-line entry)
- wiki/config.yaml                         (modified — add `groom:` block)
