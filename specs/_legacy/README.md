# Legacy specs (superseded — do not treat as canonical)

```yaml
status: legacy
moved: 2026-04-20
reason: "Pre-discussion ideas; contradicted the converged Layer 02 design"
```

## What's here

Every file in this folder is a **draft / idea** that predates the v2 design
discussions under `specs/active/<layer>/`. Agents and reviewers **must NOT**
cite these as authority. They often contradict the canonical specs.

Kept for reference (git history) — not for guidance.

## The canonical spec lives in:

- `specs/active/<layer>/discussion.md` — per-layer design discussion
- `specs/active/<layer>/plan/` — per-layer implementation plan

When a layer finishes, its `active/<layer>/` contents are the ground truth.
Nothing in this `_legacy/` folder supersedes that.

## How to use these files

- As background / starting-point ideas when planning a NEW layer.
- For git-history reference on "what we originally thought."

## How NOT to use these files

- As the source of truth.
- As a citation when flagging something as "wrong" in a review.
- As a dependency for any script or skill.
