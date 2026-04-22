# mill-codeguide (mill-go Handoff instruction + `_codeguide/` seed)

```yaml
type: skill-extension + doc-seed
layer: 04
status: placeholder — deferred until mill-v2 is self-sufficient enough to exercise it
note: "Internal codeguide for future CC sessions. Must be maintained by the skill the user actively triggers, not by a git hook (hooks have proven unreliable for this). mill-go owns it."
```

**For the thread that will do the full-write:** this is a placeholder so we don't forget the design during Layer-03/04 work. Do NOT implement by writing `_codeguide/Overview.md` manually now — if it lives outside the mill workflow it rots before it delivers value. Wait until mill-v2 is capable of running this spec through mill-plan + mill-go itself.

## Purpose

Future Claude Code sessions (and humans new to the repo) need a quick map of `plugins/mill/scripts/` — what each `_*.py` module is for, how they connect, where to start reading for each common task. The module top-of-file docstrings already carry the API detail; the codeguide only owns the **map** (lag inndeling, who calls whom, "endrer du X — start i Y").

## Shape

- `_codeguide/Overview.md` at hub root, ~200 lines max. Points to module docstrings for API detail; never duplicates them.
- `_codeguide/<subsystem>.md` per subsystem only when needed (review, orchestration, etc.).
- Renders naturally as a `mill-start` Explore-phase input: the skill already looks for `_codeguide/Overview.md` and follows it to module docs.

## Mechanism (already partially designed)

The trigger is **the `git-commit` skill**, not mill-go directly. `plugins/mill/skills/git-commit/SKILL.md` already has a "Codeguide sync" pre-commit step (step 2) that calls `@mill:codeguide-update` whenever `_codeguide/Overview.md` exists. This fires for any commit made through the skill — by mill-go's implementer, by the user manually, anywhere.

**Cadence is per-commit, not per-task.** This is the load-bearing property: mill-go's per-batch implementer uses `git-commit` for every card commit (already required by `implementer-brief.md`), so when batch 1 finishes and batch 2's implementer is spawned, batch 2 reads a `_codeguide/Overview.md` that already reflects batch 1's module additions. A per-task cadence would mean every batch-N+1 implementer reads a stale codeguide — defeating most of the value.

The design discipline: codeguide maintenance is owned by the skill the user actively triggers (`git-commit`), not by a git hook. Hooks have been tried and are not trusted — invisible to the user, easy to disable silently, fire on every trivial commit. Skill-owned instructions are reliable because the user chose to run them.

Two pieces need to ship for this to activate:

1. **The `codeguide-update` skill.** `@mill:codeguide-update` is referenced from git-commit but does not exist yet. It must: read the staged diff, detect module add/remove or top-of-file docstring changes, update `_codeguide/Overview.md` + affected subsystem pages, stage the updated files. No arguments expected — it operates on the current git staging area.
2. **The seed `_codeguide/Overview.md`.** Writing it manually is the first commit that will trigger the sync; subsequent commits keep it fresh.

## Scope when implemented

1. Write the `_codeguide/Overview.md` seed covering the state of the repo at implementation time (Layer 01 bootstrap, Layer 02 review, Layer 03 orchestration, Layer 04 extras). Points to module top-of-file docstrings for API detail; never duplicates them.
2. Implement `plugins/mill/skills/codeguide-update/SKILL.md` — called from git-commit step 2. Must stay short: delegate the actual detection + writing work to an LLM turn that reads the staged diff and decides what changes in `_codeguide/` are warranted.
3. Extend `specs/component/README.md`'s Definition-of-done: "If the spec added/removed a module or changed a subsystem interface, the codeguide update is expected in the same commit — `git-commit` handles this automatically once `codeguide-update` is shipped."

## Out of scope

- No hook-based variant.
- No config flag to disable — the git-commit skill already guards on `_codeguide/Overview.md` existence, which is the natural kill-switch.
- No mill-go-owned phase. The trigger path is `mill-go spawns implementer → implementer uses git-commit → git-commit calls codeguide-update`. Mill-go does not need a dedicated step.
