# Plan: Auto-approve on review-round cap

```yaml
task: "Auto-approve on review-round cap"
slug: review-cap-auto-approve
approved: false
started: "20260918-175506"
parent: main
root: ""
verify: null
skip_checks: ["wiki-config-mutation"]
discussion_sha: "329d555e7beb298299058401e607ef8f1bb41d0d"
```

## Batch Index

```yaml
batches:
  - number: 1
    name: config-schema-auto-approve-on-cap
    file: 01-config-schema-auto-approve-on-cap.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-config.py
  - number: 2
    name: mill-plan-auto-approve-wiring
    file: 02-mill-plan-auto-approve-wiring.md
    depends-on: [1]
    verify: null
  - number: 3
    name: mill-go-base-batch-auto-approve-wiring
    file: 03-mill-go-base-batch-auto-approve-wiring.md
    depends-on: [1]
    verify: null
  - number: 4
    name: mill-go-base-holistic-auto-approve-wiring
    file: 04-mill-go-base-holistic-auto-approve-wiring.md
    depends-on: [1]
    verify: null
```

## Shared Decisions

### Decision: config key shape

- **Decision:** `auto_approve_on_cap: bool` (default `false`/absent), added independently under `roles.plan-review.holistic`, `roles.code-review.batch`, and `roles.code-review.holistic`. Read at each use site with `cfg.get("roles", {}).get(<role>, {}).get(<scope>, {}).get("auto_approve_on_cap", False)` — mirrors how `rounds`/`min_rounds` are already read inline in each SKILL.md, with no separate Entry-step variable binding for mill-go-base (mill-plan's Entry step 2 does bind named locals for `rounds`/`min_rounds`, so `auto_approve_on_cap` is bound the same way there for consistency).
- **Applies to:** all batches.

### Decision: `wiki-config-mutation` skip-check bootstrap justification

- **Decision:** batch 1 edits `mill-config.yaml` at the hub root (adding `auto_approve_on_cap: false` to three existing blocks) alongside the plugin template. This is a pure key *addition* with an explicit default (`false`) identical to the schema's implicit default when the key is absent — no existing behavior changes for this hub or any other hub, before or after batch 1 lands. Batches 2-4 (this same plan) are the sole future consumers of the new key. Safe to commit mid-flight; `skip_checks` includes `wiki-config-mutation` for batch 1's validator run.
- **Rationale:** satisfies the `wiki-config-mutation` skip-check's condition (a) — a documented reason the `mill-config.yaml` change is safe mid-flight for this task — since the key addition ships with an explicit-false default matching today's behavior.
- **Applies to:** batch 1 only.

### Decision: commit-message suffix for the config-driven auto-approve-at-cap path

- **Decision:** every commit produced by the new config-driven auto-approve-at-cap terminal action (mill-plan step 6; mill-go-base per-batch step 5; mill-go-base holistic step 7) appends the literal suffix `" (auto-approved on round-cap exhaustion, config auto_approve_on_cap)"` — distinct from the existing operator-live-waiver suffix (`" (operator waived remaining BLOCKINGs at round cap)"` in mill-plan) and from the existing convergence-gate implicit-approve-at-cap suffix (`" (min_rounds/demoted-predicate not satisfied by round cap)"` / `" (min_rounds not satisfied by round cap)"`), so all three triggers are distinguishable in status.md/git history.
- **Applies to:** batches 2, 3, 4.

### Decision: per-batch site requires an explicit last-round-verdict guard

- **Decision:** mill-go-base's per-batch Code Review loop's step 5 ("Max-rounds exhaustion") fires on round-count alone, regardless of the last round's verdict — unlike mill-plan's step 6 and mill-go-base's holistic step 7, which are already conditioned on the exhausted round's verdict having been `REQUEST_CHANGES`. The per-batch wiring in batch 3 must therefore track the most recently processed round's verdict and gate the new auto-approve-on-cap branch on `last_verdict == "REQUEST_CHANGES"` specifically. When the last round's verdict was `NEED_CONTEXT` (step 4's `NEED_CONTEXT` branch never dispatches a fixer), cap-exhaustion stays today's unconditional hard halt regardless of the flag — there is no finding-set to have "applied," so nothing was ever reviewed for correctness.
- **Rationale:** caught during `_mill/discussion.md`'s own review round 1 (BLOCKING, class `design`) — see that file's "Per-batch site: gate explicitly on the last round's verdict" Decision for the full writeup.
- **Applies to:** batch 3 only.

## All Files Touched

- `mill-config.yaml`
- `plugins/mill/skills/mill-go-base/SKILL.md`
- `plugins/mill/skills/mill-go-base/holistic-review.md`
- `plugins/mill/skills/mill-plan/SKILL.md`
- `plugins/mill/templates/mill-config.yaml`
- `plugins/mill/unit_tests/test-config.py`
