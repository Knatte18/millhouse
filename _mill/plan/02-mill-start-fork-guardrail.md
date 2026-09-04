# Batch: mill-start-fork-guardrail

```yaml
task: 'mill-plan: entry-gate, timeline, and script-portability bugs'
batch: mill-start-fork-guardrail
number: 2
cards: 1
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-skill-helper-drift.py test-guards.py test-brief-commit.py
depends-on: []
```

## Batch Scope

Fixes #919: mill-start's Phase: Explore "Sub-investigation guidance" section claims research forks there have "no tool restriction to lose," and carries no guardrail against unauthorized Edit/Write/mutating-Bash use — unlike `mill-plan/SKILL.md`'s own "Fork scope guardrail" (Phase: Plan) for the structurally identical problem. A live incident showed the claim is false: an in-context fork inherited full `--auto` session context and autonomously wrote+committed discussion.md, wrote a full plan, ran a plan-fix round, and dispatched a live reviewer — all pushed to origin. This batch ports mill-plan's guardrail into mill-start, adapted for Explore-phase scope, and corrects the disproven claim. Single batch, single card, single file — no batch-local decisions beyond `00-overview.md`'s Shared Decisions.

## Cards

### Card 4: Port mill-plan's fork scope guardrail into mill-start's Phase: Explore

- **Context:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Edits:**
  - `plugins/mill/skills/mill-start/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `plugins/mill/skills/mill-start/SKILL.md`, inside the `### Phase: Explore` section's "**Sub-investigation guidance (not a mandate).**" block, locate the standalone sentence: "This is the one site in mill with no brief, no resume requirement, no per-role model tier, and no tool restriction to lose, which is exactly why none of the three fork disqualifiers (see \"Why not fork?\" in `mill-go-base/SKILL.md`'s \"## Agent-mode dispatch\") apply here." — it sits in its own paragraph, immediately after the three-bullet list ending "...delegating either way is overhead." and immediately before the "**Fork echo caution.**" paragraph.

  Replace that entire sentence (the whole paragraph) with the following text, verbatim:

  "This is the one site in mill with no brief, no resume requirement, and no per-role model tier to lose from forking — but it is NOT a site with no tool restriction to lose: a fork inherits the parent's full tool access exactly as documented in `mill-go-base/SKILL.md`'s \"Why not fork?\" paragraph, and a live incident (#919) showed an in-context research fork, dispatched mid-`--auto` session for a narrowly-scoped read-only investigation, instead inherited the full session context and autonomously executed the entire downstream pipeline — writing and committing discussion.md, writing a full plan, running a plan-fix round, and dispatching a live reviewer, all pushed to origin before the operator noticed.

  **Fork scope guardrail.** Whenever a fork IS used under the guidance above, all of the following apply, mirroring `mill-plan/SKILL.md`'s own \"Fork scope guardrail\" (Phase: Plan) for the identical problem: (a) the fork's prompt must explicitly forbid Edit/Write calls, forbid mutating Bash commands, and forbid touching `discussion_path`, `status_path`, or any `mill-config.yaml`/`config.local.yaml` — and must explicitly state the fork is NOT the orchestrator and must not act on any active skill's phase instructions, only answer the narrow question it was dispatched with. (b) Immediately BEFORE dispatching the fork, capture a `git status --porcelain` snapshot (scoped to the worktree) as a baseline. (c) Immediately AFTER the fork returns, run `git status --porcelain` again and diff it against the pre-dispatch baseline. Treat only entries that are NEW in the post-return snapshot as a scope violation; the fork's report is not trusted until this diff is empty. (d) On a detected violation, revert the unauthorized changes (`git checkout --` / delete untracked files as appropriate) before proceeding, and never silently incorporate a fork's unauthorized writes into the discussion. (e) When multiple research investigations are needed, dispatch them serially, not in parallel — complete one dispatch and confirm a clean git-status diff before starting the next."

  Do not touch the "**Fork echo caution.**" paragraph that follows, or any other section of the file.
  `plugins/mill/skills/mill-plan/SKILL.md` is Context-only (read to confirm the "Fork scope guardrail" wording being mirrored) — do not edit it in this card.
- **Commit:** `docs(mill-start): port mill-plan's fork scope guardrail into Phase: Explore`

## Batch Tests

`verify:` runs `test-skill-helper-drift.py` (this card introduces no new `_<module>.<fn>(` references — the guardrail text uses only `git status --porcelain`/`git checkout --`, no Python helper calls), `test-guards.py` (catches stray non-ASCII arrows or other anti-patterns a careless edit could introduce), and `test-brief-commit.py` (locks `mill-start/SKILL.md`'s `_mill/briefs/` commit-message patterns in Handoff/discussion-gap-fix/discussion-fix, which sit near but are untouched by this card's edit — cheap, directly-relevant insurance against an accidental structural break). No Python source files are touched, so the broader suite is out of scope per mill-plan's "Verify command scope" guidance.
