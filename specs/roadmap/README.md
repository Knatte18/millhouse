# Implementation Roadmap — index

```yaml
status: draft
purpose: top-level status view for the mill-v2 build; detail lives in the per-M files in this folder
```

## How to read this

The roadmap is split per milestone level. This file is the **index**: it shows at-a-glance what is done, what is next, and which detail file to open for the work. Each linked file owns:

- Per-sub-milestone descriptions (e.g. M1.1, M1.2, …)
- Exit criteria as ticket boxes — tick them as the work lands
- Local gates (⛔) that block progress until met
- Layer-specific LOC budgets

**Legend:** `- [ ]` = not done, `- [x]` = done, ⛔ = stop-gate.

Work the layers in order. You may reorder sub-milestones within a layer if dependencies allow, but never jump between layers without tagging the previous one done.

## What to read when picking up work

The roadmap is a **status tracker + index**, not a complete briefing. Before touching code for a milestone, read (in order):

1. [`../00-overview.md`](../00-overview.md) — principles, discipline rules, LOC budget.
2. This file (you're here) — find the current layer row in the status table.
3. The per-layer file in this folder (e.g. [`M1-bootstrap.md`](M1-bootstrap.md)) — exit criteria + status for each sub-milestone.
4. The **full layer spec** linked from the per-layer file (e.g. [`../layer-01-bootstrap.md`](../layer-01-bootstrap.md)) — this is where v1 reuse tables, deliverables, design decisions, and acceptance criteria live.
5. As needed: [`../ref-v1-reuse.md`](../ref-v1-reuse.md), [`../ref-legacy-index.md`](../ref-legacy-index.md), [`../ref-formats.md`](../ref-formats.md), [`../ref-code-scope.md`](../ref-code-scope.md), [`../ref-workflows.md`](../ref-workflows.md), [`../ref-dev-loop.md`](../ref-dev-loop.md).

Rule of thumb: **roadmap = WHAT and WHEN; layer spec = HOW.** Skipping step 4 lands wrong code.

## Status overview

| Layer | File | Delivers | Gate tag | Status |
|---|---|---|---|---|
| M0 | [M0-decisions.md](M0-decisions.md) | Signed-off spec | — | [x] complete |
| M0.5 | [M0.5-scaffolding.md](M0.5-scaffolding.md) | Marketplace + skill carry | — | [x] complete |
| Layer 01 | [M1-bootstrap.md](M1-bootstrap.md) | `mill-setup`, `mill-add`, `mill-list` | `layer-01-done` | [ ] in progress (M1.1 done; M1.2 in progress) |
| Layer 02 | [M2-review.md](M2-review.md) | `mill-review` + Claude + Gemini providers | `layer-02-done` | [ ] not started |
| Layer 03 | [M3-orchestration.md](M3-orchestration.md) | `mill-spawn`, `mill-go` (linear) | `layer-03-done` | [ ] not started |
| Layer 04 | [M4-extras.md](M4-extras.md) | `mill-start`, `mill-plan`, `mill-merge`, `mill-cleanup`, `mill-status`, `mill-abandon`, `mill-groom` | `v2.0` | [ ] not started |

## Cross-cutting checklist (resolve inline during layers)

- [ ] **Skills index** — rebuild `mill-skills-index` fresh once the skill catalog is stable. Until then `SKILLS.md` is hand-maintained or absent.
- [x] **.gitignore** — covers `**/.millhouse/`, `**/.env`, `**/worktrees/` (added during M1.2).
- [x] **marketplace.json + cross-plugin setup** — done in M0.5.1.

## Estimated effort (very rough)

| Milestone | Estimate |
|---|---|
| M0 decisions | 30 min |
| M1 (Bootstrap) | 4–6 hours |
| M2 (Review) | 8–12 hours |
| M3 (Orchestration) | 8–12 hours |
| M4 (Extras) | 6–10 hours |
| **Total** | **26–40 hours of focused work** |

If reality diverges significantly from this, the discipline rules (LOC budget, no abstractions, no tests beyond integration) are being violated somewhere. Stop and audit.

## Deviation protocol

You **may**:

- Reorder within a layer (e.g. M1.4 before M1.3) if dependencies allow.
- Skip a milestone after updating the relevant spec file to reflect the skip.
- Insert a new milestone after updating the relevant spec file to reflect the insert.

You **may not**:

- Start a layer before the previous one is tagged done.
- Write code that contradicts the spec. Fix the spec first, then code.
- Skip ⛔ gates to "come back later".

If you find yourself wanting to skip a gate, stop entirely and reconsider whether the plan needs to change.
