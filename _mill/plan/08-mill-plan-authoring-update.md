# Batch: mill-plan-authoring-update

```yaml
task: Fix nested-hub-layout path resolution bugs across scope violations and review CLIs
batch: mill-plan-authoring-update
number: 8
cards: 1
verify: null
depends-on: [3]
```

## Batch Scope

Updates the `mill-plan` skill's authoring guidance so future plans on nested-layout tasks correctly opt into the `cwd` field (batch 3) instead of defaulting to `cwd: git_root` on a repo that actually needs hub-relative verify commands — closing the loop on #604 at the authoring source, not just the execution sites fixed in batches 4-7. This is a pure documentation/template batch with no runnable code surface; `verify: null` is justified below.

## Cards

### Card 28: Document the verify cwd mapping form in mill-plan's authoring guidance

- **Context:**
  - `plugins/mill/scripts/_plan_dag.py`
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
  - `plugins/mill/templates/plan-batch.md`
  - `plugins/mill/templates/plan-overview.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `mill-plan/SKILL.md`'s "Verify command shape" guidance (Phase: Plan), add a paragraph documenting the `{cwd: hub|git_root, command: <string>}` mapping form as an alternative to the plain-string `verify:` value, and instruct the planner: when `_paths.resolve_hub_path() != _paths.resolve_git_root()` (nested layout) for the task being planned, and the verify command it is about to author would naturally be hub-relative, write it as the mapping form with `cwd: hub` rather than the plain-string form (which implies `cwd: git_root`); when the natural verify command is git-root-relative even in a nested layout, the plain-string form (or an explicit `cwd: git_root` mapping) remains correct — the field exists to describe how the command is actually written, not to force a specific choice. Add the same guidance to the `<!--` template comment blocks at the top of `plan-batch.md` (for per-batch `verify:`) and `plan-overview.md` (for the module-wide `verify:`), so it is visible to the planner at the point of rendering each file, not only in the SKILL body.
- **Commit:** `docs(mill-plan): document authoring the verify cwd mapping form for nested layouts (#604)`

## Batch Tests

`verify: null` — this batch only edits SKILL.md prose and template HTML-comment guidance; there is no runnable code surface to verify. Batches 3-7's own test suites already cover every runtime behavior this documentation describes.
