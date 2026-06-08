# Plan: Track _mill/briefs/ instead of gitignoring them

```yaml
task: "Track _mill/briefs/ instead of gitignoring them"
slug: track-task-briefs
approved: true
started: "20260608-072059"
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: reviewer-tooluse-convention
    file: 01-reviewer-tooluse-convention.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-reviewers.py test-large-prompt-switch.py test-config.py
  - number: 2
    name: track-briefs
    file: 02-track-briefs.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-gitignore-phase.py
  - number: 3
    name: review-mode-tests
    file: 03-review-mode-tests.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-common.py
```

## Shared Decisions

### Decision: tool-use is the default name, _bulk is the suffixed exception

- **Decision:** Across the entire `mill-agents.yaml` catalogue, the unsuffixed name is
  the tool-use variant with an explicit `tooluse: true`; the `_bulk` suffix marks the
  bulk variant with `tooluse: false`. Every former `*_tool` name is removed (folded into
  the unsuffixed name). Every model/effort combo gets a symmetric `<name>` + `<name>_bulk`
  pair. All reviewer roles in config reference unsuffixed (tool-use) names.
- **Rationale:** Tool-use is now the norm; the naming must be uniform with no mixed
  formats (`*_tool` for tool-use here, unsuffixed-bulk there).
- **Applies to:** all batches (batch 1 implements it; batches 2-3 assume it).

### Decision: bulk is demoted, not deleted

- **Decision:** The bulk code path (`_read_for_bulk`, `run_bulk`, the bulk artefact
  assembly, the large-prompt `tooluse` override) is retained, reachable only through
  `_bulk` agents. No reviewer role references a `_bulk` agent today.
- **Rationale:** Cheap escape hatch; deleting it is a large, irreversible diff for no
  present benefit.
- **Applies to:** all batches.

### Decision: code default `tooluse` stays False; base entries set it explicitly

- **Decision:** `_reviewers.py`'s absent-`tooluse`→`False` default is unchanged. Tool-use
  is expressed by an explicit `tooluse: true` on each base entry, not by flipping the
  code default.
- **Rationale:** Explicit flags are self-documenting; the discussion specified adding
  `tooluse: true` to each tool-use definition.
- **Applies to:** batch 1.

### Decision: briefs are committed on the task branch via mill-go and mill-plan only

- **Decision:** Briefs (`_mill/briefs/`, both `.md` briefs and `.out.md` responses) are
  committed by folding `_mill/briefs/` into the existing task-branch state commits of
  mill-go (per-batch approve, holistic approve, done) and mill-plan (plan-review approve
  / plan-fix). No new dedicated commit; no CLI-side commit.
- **Rationale:** Those orchestrators already write the response file and already commit
  `_mill/` state; incremental commits preserve the audit trail even if a run dies midway.
- **Applies to:** batch 2.

### Decision: mill-start and mill-merge-in are OUT of scope for brief tracking

- **Decision:** Discussion-review briefs are written under the **hub** worktree
  (`millpy-review-discussion.py` sets `project_root = resolve_hub_path()`, line 69), not
  the task worktree, so they are not on the task branch and cannot be committed to it —
  relocating them is a separate design change. mill-merge-in's briefs are task-side but it
  exposes no augmentable task-branch commit pathspec and its briefs would be removed by
  mill-merge's `git rm -r _mill/` moments later. Both are excluded.
- **Rationale:** Correctness — committing hub-side briefs to the task branch is impossible
  without a separate change; merge-in tracking is marginal. This corrects the discussion's
  inclusion of mill-start, which the discussion reviewer did not catch.
- **Applies to:** batch 2.

### Decision: the `.gitignore` is NOT touched

- **Decision:** No change to `.gitignore` or `_gitignore.GLOB_ENTRIES`. Briefs are already
  un-ignored on this branch; the only work is to commit them and lock the un-ignored state
  with a test.
- **Rationale:** `git check-ignore _mill/briefs/x.md` exits 1; `GLOB_ENTRIES` has no
  briefs entry. The proposal's `.gitignore:40` premise was stale.
- **Applies to:** batch 2.

### Decision: SKILL edits take effect only after merge + cache refresh

- **Decision:** mill-go/mill-plan/SKILL edits change source; the running orchestrator loads
  SKILLs from the plugin cache. So this task's own mill-go run uses the OLD (cached) SKILLs
  — the brief-commit behavior does not self-apply during this implementation. This is
  expected and not a defect.
- **Rationale:** Avoids a false expectation that batch 2's behavior is observable in this
  task's own run.
- **Applies to:** batch 2 (reviewer context).

## All Files Touched

- `mill-config.yaml`
- `plugins/mill/integration_tests/test-review-code.py`
- `plugins/mill/integration_tests/test-review-discussion.py`
- `plugins/mill/integration_tests/test-review-plan.py`
- `plugins/mill/scripts/_test_registry.py`
- `plugins/mill/skills/mill-go/SKILL.md`
- `plugins/mill/skills/mill-plan/SKILL.md`
- `plugins/mill/templates/mill-agents.yaml`
- `plugins/mill/templates/mill-config.yaml`
- `plugins/mill/templates/review-output.schema.md`
- `plugins/mill/unit_tests/_test_registry.py`
- `plugins/mill/unit_tests/test-config.py`
- `plugins/mill/unit_tests/test-gitignore-phase.py`
- `plugins/mill/unit_tests/test-large-prompt-switch.py`
- `plugins/mill/unit_tests/test-review-common.py`
- `plugins/mill/unit_tests/test-reviewers.py`
