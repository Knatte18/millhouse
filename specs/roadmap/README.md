# Implementation Roadmap

```yaml
status: current
purpose: "High-level status tracker for the mill-v2 build. Layer-level detail lives in specs/active/<layer>/ while a layer is in design, and is promoted to specs/<layer>/ when finalised."
```

## Status

| Layer | Scope | Tag | Status |
|---|---|---|---|
| Bootstrap | `mill-setup`, `mill-add`, `mill-list` | `layer-01-done` | **done** |
| Review API | `mill-review-discussion`/`-plan`/`-code`, sonnetmax reviewer, Claude LLM-provider | `layer-02-done` (pending) | **done (impl)** — awaiting integration-test run |
| Orchestration | `mill-spawn`, `mill-go` (linear) | `layer-03-done` | not started |
| Extras | `mill-start`, `mill-plan`, `mill-merge`, `mill-cleanup`, `mill-status`, `mill-abandon`, `mill-groom` | `v2.0` | not started |

## Where does detail live

| State | Location |
|---|---|
| In-design | `specs/active/<layer>/discussion.md`, `discussion-review-rN.md`, `plan/` |
| Implemented | hub + wiki commits; per-layer canonical spec at `specs/<layer>-*.md` (TBD after audit) |
| Legacy ideas | `specs/_legacy/` — not authoritative, kept for reference |

## Cross-cutting checklist

- [ ] **Skills index** — rebuild `mill-skills-index` once the v2 skill catalog is stable. Tracked as task `skills-index-rebuild` in Home.md.
- [x] **.gitignore** — covers `**/.millhouse/`, `**/.env`, `**/worktrees/`.
- [x] **marketplace.json + cross-plugin setup** — done during Layer 0.5.

## Deviation protocol

You **may**:
- Work on a later layer before an earlier one is tagged if the dependency is inverted during discussion — but update this file and tag/sign the earlier one explicitly.
- Skip a milestone after updating this file to reflect the skip.

You **may not**:
- Write code that contradicts `specs/active/<layer>/discussion.md` (the canonical spec for in-design work). Update the discussion first, then code.
- Cite anything in `specs/_legacy/` as authority.

If you find yourself wanting to break a rule, stop and ask.
