# Handoff — where to start next session

```yaml
written: 2026-04-20
written-by: Opus 4.7 (1M context), session ending after Layer 01 closeout
current-branch: main
current-state: tag layer-01-done (three commits ahead of origin/main)
hub-pushed: false   # push when you're ready
wiki-pushed: true   # commit 7355e2c on origin/master of millhouse.wiki.git
```

## Start sequence

1. Read [../00-overview.md](../00-overview.md) — discipline rules, LOC budget.
2. Read [../roadmap/README.md](../roadmap/README.md) — status overview + the "What to read when picking up work" checklist. It points you at the right per-layer file.
3. Confirm state: `git -C c:/Code/millhouse/hub describe --tags` should print `layer-01-done` (HEAD is the tagged commit) and `git log --oneline -5` should show three local M1.x commits ahead of `origin/main`.
4. Decide what to push (see below), then move to whatever comes next per roadmap.

That's the whole boot sequence. The roadmap and layer specs carry every design decision; this file is just a pointer.

## What just landed (Layer 01)

| # | Milestone |
|---|---|
| 1 | M1.3 extension + M1.3.5 — bracketed-slug format, `_sidebar.py`, `mill-add/SKILL.md` |
| 2 | M1.4 — `mill-list.py` with `[P]` proposal marker |
| 3 (HEAD, tagged `layer-01-done`) | M1.5 — integration test + this handoff |

Wiki has two real tasks: `skills-index-rebuild` (with proposal, pre-existing) and `m1-4-mill-list` (plain, added this session in commit `7355e2c` on `origin/master`).

## First actions when you resume

1. **Decide whether to push hub.** Three local commits ahead of `origin/main`. Hub push uses the same fine-grained PAT as the wiki — the wiki remote URL has the PAT baked in; the hub remote does not. Either:
   - Bake the PAT into the hub remote URL the same way (`git remote set-url origin https://Knatte18:<PAT>@github.com/Knatte18/millhouse.git`), then `git push`, or
   - Push one-shot with PAT in URL: `git push "https://Knatte18:<PAT>@github.com/Knatte18/millhouse.git" main`
2. **Pick the next layer.** Per the roadmap, Layer 02 (Review) is next. Read [../roadmap/M2-review.md](../roadmap/M2-review.md) then [../layer-02-review.md](../layer-02-review.md). Budget 750 LOC.
3. **Gate 2 before Layer 02 ships:** single-shot `mill-review` works with both Claude and Gemini providers. Ship both on day one — the provider pattern is only real if two providers exist.

## Open questions / follow-ups

- **LOC accounting.** Layer 01 is 857 non-blank/non-comment lines total, but 439 logical code (tokens). The 450 budget was met in the logical-code sense; the excess is module and function docstrings per the `python-comments` skill. Decide before Layer 02 whether the layer-spec budgets should be clarified as "logical code only" or left ambiguous. I left both numbers in `roadmap/M1-bootstrap.md` M1.5 exit criteria for reference.
- **mill-setup doesn't bake PAT.** Phase 3 (clone wiki) assumes the user's credential helper resolves auth. On a fresh machine where the helper isn't set up for the repo owner, the push from Phase 6/6a fails the same way it did here before the PAT was used in the URL. Either document the manual PAT step in the skill, or extend Phase 3 to prompt for a PAT and bake it into the wiki's remote URL. Not urgent — revisit when another operator needs to onboard.
- **Task lifecycle simplicity.** User raised the "how do tasks get claimed" question in this session. Current design (spec): `mill-spawn` creates `active/<slug>/` but leaves the Home.md entry alone; `mill-merge` removes from Home.md + moves to archive. No explicit "claim" state — active-dir existence *is* the claim signal. The user seemed OK with this after hearing the summary, but file a proposal if you want to change anything before Layer 03 lands `mill-spawn` and `mill-merge`.

## Session-end convention

**Every session ends by overwriting this file.** When you wrap up, rewrite `specs/_starter/handoff.md` to reflect:

- New `written:` date, `current-commit:`, push state, what just landed.
- A clean "what just happened" summary (one line per commit — don't let the table grow to a week's worth of commits).
- Updated "first actions when you resume" so the next session walks into clear work.
- Any new open questions; drop questions that have been resolved.

Keep it lean. The spec tree is the source of truth — this file is just the pointer at the front. If you find yourself duplicating content from the roadmap or layer specs, stop and link instead.
