# Plan: mill-go2: opt-in skill scaffold cloned from mill-go (no fork yet)

```yaml
task: 'mill-go2: opt-in skill scaffold cloned from mill-go (no fork yet)'
slug: 'mill-go2-scaffold'
approved: false
started: '20260811-120222'
parent: 'main'
root: ""
verify: null
```

## Batch Index

_The fenced yaml block below is the authoritative DAG mill-go reads to schedule batches.
Every batch lives at `NN-<batch-slug>.md` in this directory and is mirrored as one entry here._

```yaml
batches:
  - number: 1
    name: extract-base
    file: 01-extract-base.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-guards.py test-skill-helper-drift.py
  - number: 2
    name: thin-variants
    file: 02-thin-variants.md
    depends-on: [1]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-mill-go-variants.py
  - number: 3
    name: repoint-refs
    file: 03-repoint-refs.md
    depends-on: [2]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py
```

## Shared Decisions

### Decision: variant-token-form

- **Decision:** the parameterized literal in `mill-go-base/SKILL.md` is written as the angle-bracket
  token `<VARIANT_LABEL>`, matching the file's existing placeholder convention (`<worktree>`,
  `<slug>`, `<batch_name>`). A variant binds it by declaring `VARIANT_LABEL: <value>` inside a fenced
  yaml block under its own `## Variant binding` heading.
- **Rationale:** the three literal families being parameterized are shell strings and Python call
  strings, not f-string interpolations, so a brace form would read as a runtime substitution the base
  never performs. Angle brackets already mean "the driver substitutes this" everywhere else in the
  file.
- **Applies to:** all batches

### Decision: three-literal-families-only

- **Decision:** exactly three literal families become `<VARIANT_LABEL>` in the base — the
  SKILL-authored `commit -m "mill-go: …"` subjects, the `_notify.notify("mill-go.…")` event names,
  and the `[mill-go]` operator-facing echo/halt prefixes. Every other occurrence of the string
  `mill-go` in the moved text (narrative prose, section cross-references, `mill-bg` slugs) is left
  byte-for-byte unchanged.
- **Rationale:** `variant-label-in-logs` in `_mill/discussion.md` scopes the parameterization to the
  three families that end up in git history and desktop notifications. Widening it would rewrite
  prose the `three-file-split` Decision guarantees moves verbatim.
- **Applies to:** all batches

### Decision: work-inventory-by-grep

- **Decision:** the site list for the three literal families is regenerated with grep at
  implementation time, never copied from a line-number list. Counts verified at plan time against
  commit `6442a688`: 26 `commit -m "mill-go: `, 8 `_notify.notify("mill-go.`, 10 `[mill-go]`.
  A count mismatch at implementation time means mill-go changed since planning — treat it as
  information, parameterize what grep actually finds, and note the delta in the commit message.
- **Rationale:** this repo is self-hosting and `mill-go/SKILL.md` is under active development, so
  line numbers go stale between discussion, plan, and implementation. A missed site silently keeps a
  `mill-go:` prefix under mill-go2, defeating `variant-label-in-logs`.
- **Applies to:** all batches

### Decision: no-hook-terminology

- **Decision:** the two variant-fillable sections are called **override points**. The word `hook`
  must not be introduced as a name for the mechanism — not in the SKILL files, not in card
  Requirements, not in commit messages, not in test names or comments. Two incidental pre-existing
  occurrences of the English word inside the moved text ("At the hook point, run all of:" and "this
  mode has no separate finalize call to hook before") are unrelated to override points and are moved
  unchanged.
- **Rationale:** `hook` already names Claude Code's `settings.json` hook mechanism. A blanket textual
  ban would collide with the byte-for-byte move guarantee, so the ban is scoped to new
  override-point naming.
- **Applies to:** all batches

### Decision: script-side-prefixes-unchanged

- **Decision:** commit subjects written by Python scripts keep the literal `mill-go` prefix under
  both variants. No `--variant-label` flag is threaded through any script, and no prefix parser is
  widened.
- **Rationale:** `_implementer_common.py` parses the literal string `"mill-go: start batch"` as part
  of the Bug #557 commit-recount logic. Cosmetic consistency is not worth risking batch-completeness
  detection.
- **Applies to:** all batches

### Decision: intermediate-missing-mill-go

- **Decision:** batch 1 relocates `plugins/mill/skills/mill-go/SKILL.md` to the base and does not
  recreate it; the thin `mill-go/SKILL.md` is created in batch 2. Between the two batch commits the
  `mill-go` skill directory does not exist on the task branch. This is intentional and is not a
  defect for a reviewer to flag.
- **Rationale:** the `move-redundant` validator check rejects a path that is both a `Moves:` endpoint
  and a `Creates:` entry within the same batch, so the relocation and the re-creation cannot share a
  batch. The running orchestrator loads its own skills from the plugin cache, not from the worktree,
  so the intermediate state cannot destabilise the session executing this plan.
- **Applies to:** extract-base, thin-variants

### Decision: no-new-config-keys

- **Decision:** mill-go2 reads the existing `roles.implementer.*`, `roles.fixer.*`,
  `roles.code-review.*`, and `pipeline.*` keys unchanged. Neither the hub `mill-config.yaml` nor
  `plugins/mill/templates/mill-config.yaml` is edited by this plan.
- **Rationale:** mill-go2 is behaviourally identical to mill-go in this task, and those keys are read
  by the Python CLIs rather than by SKILL prose, so a parallel section would require script changes
  for zero behavioural gain.
- **Applies to:** all batches

## All Files Touched

- `SKILLS.md`
- `plugins/mill/docs/harness-tool-contracts.md`
- `plugins/mill/scripts/millpy-implement.py`
- `plugins/mill/skills/cli/SKILL.md`
- `plugins/mill/skills/conversation/SKILL.md`
- `plugins/mill/skills/mill-go-base/SKILL.md`
- `plugins/mill/skills/mill-go/SKILL.md`
- `plugins/mill/skills/mill-go2/SKILL.md`
- `plugins/mill/skills/mill-merge-in/SKILL.md`
- `plugins/mill/skills/mill-plan/SKILL.md`
- `plugins/mill/skills/mill-quick/SKILL.md`
- `plugins/mill/skills/mill-start/SKILL.md`
- `plugins/mill/unit_tests/test-guards.py`
- `plugins/mill/unit_tests/test-mill-go-variants.py`
- `plugins/mill/unit_tests/test-phase-wait.py`
- `plugins/mill/unit_tests/test-skill-helper-drift.py`
