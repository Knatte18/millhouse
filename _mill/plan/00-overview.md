# Plan: Fix nested-hub path resolution and SKILL.md vs shipped-API mismatches

```yaml
task: Fix nested-hub path resolution and SKILL.md vs shipped-API mismatches
slug: mill-nested-hub-and-skill-sync
approved: false
started: 20260618-091504
parent: main
root: ""
verify: null
```

## Batch Index

_The fenced yaml block below is the authoritative DAG mill-go reads to
schedule batches. Every batch lives at `NN-<batch-slug>.md` in this
directory and is mirrored as one entry here._

```yaml
batches:
  - number: 1
    name: drift-guard-and-regression-locks
    file: 01-drift-guard-and-regression-locks.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-skill-helper-drift.py
  - number: 2
    name: merge-skill-path-fixes
    file: 02-merge-skill-path-fixes.md
    depends-on: [1]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-skill-helper-drift.py
  - number: 3
    name: merge-integration-test
    file: 03-merge-integration-test.md
    depends-on: [2]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/integration_tests/test-merge.py
```

## Shared Decisions

### Decision: most reported issues are already fixed in source — verify, don't re-fix

- **Decision:** Four of the six source issues (#495, #496, #504, #505) were already fixed by
  commit `7fb8f586` and must NOT be re-implemented. They were reported against the stale
  plugin **cache 2.0.0** (version never bumped), not against current source. This task adds
  *regression coverage* for them and concentrates implementation on the genuinely-open
  mill-merge / mill-merge-in bugs (#497, #506).
- **Rationale:** Re-fixing correct code risks regressions and wastes budget. See discussion
  `## Decisions › treat-already-fixed-issues`.
- **Applies to:** all batches.

### Decision: hub resolution — resolve_active_hub for mill-merge, resolve_hub_path for mill-merge-in

- **Decision (mill-merge):** Resolve the hub via
  `_paths.resolve_active_hub(container_path, slug, cfg=cfg, git_root=git_root)` and derive all
  task-state paths from it with `_paths.resolve_task_path(hub, cfg['paths'][...])`. This is
  exactly mill-go's `Path Setup` (mill-go SKILL.md:38-47). mill-merge Step 1 already resolves
  `container_path`, `slug`, and `cfg` before Path Setup, so the inputs are in hand. **No in-place
  vs worktree mode branch is needed:** `resolve_active_worktree` (`_paths.py:376-395`) checks
  in-place mode *first* (returns `git_root` when `_inplace.is_inplace` is true) before falling to
  the `container/"wts"/slug` worktree path, and `resolve_active_hub`'s docstring (`_paths.py:429-437`)
  states it covers both modes; mill-go uses it unconditionally in both modes.
- **Decision (mill-merge-in):** Resolve the hub via `_paths.resolve_hub_path()` +
  `_paths.resolve_task_path(...)`, matching mill-merge-in's own line 56 (which already uses
  `resolve_hub_path()` for its config load). mill-merge-in's entry step 2 runs *before* cfg/slug
  are resolved, so `resolve_active_hub` (which requires `cfg`, `slug`, `container_path`) is not
  usable there without a larger reordering that is out of scope. `resolve_hub_path()` is the
  proven minimal fix — the #506 reporter's workaround used exactly `resolve_hub_path()` for the
  nested mill-merge case and it worked.
- **Rationale:** cwd-independent + slug-driven where the inputs exist (mill-merge); minimal and
  internally-consistent where they do not (mill-merge-in). Settles the discussion's in-place-mode
  caveat and the "make lines 13/54 consistent" note (`## Decisions › hub-resolution-helper`,
  `## Scope › mill-merge-in`).
- **Applies to:** merge-skill-path-fixes.

### Decision: config load uses _config.load_config(resolve_hub_path(), git_root)

- **Decision:** mill-merge's Step 1 config load must use
  `_config.load_config(_paths.resolve_hub_path(), git_root)` (the canonical deep-merge of
  `<hub>/mill-config.yaml` + `.millhouse/config.local.yaml`), replacing the obsolete
  `<wiki_path>/config.yaml` read. This mirrors mill-go Entry step 3 (which loads config via
  `resolve_hub_path()` *before* resolving the slug-driven hub). The cfg loaded here is then
  passed into `resolve_active_hub` in Path Setup.
- **Rationale:** The wiki no longer carries config (commit `ede22180`); correct config is a
  prerequisite for correct hub resolution. See discussion `## Decisions › config-load fix`.
- **Applies to:** merge-skill-path-fixes.

### Decision: SKILL.md edits are prose; the drift guard is their unit-level check

- **Decision:** mill-merge / mill-merge-in are prose. Their only automatable unit check is the
  new drift-guard test, which asserts every `_<module>.<fn>(` reference in mill SKILLs resolves
  to a real shipped helper. The runtime behavior of the squash-safety fix is validated by the
  integration test in batch 3. Use `${CLAUDE_PLUGIN_ROOT}` (literal) for intra-plugin paths in
  any SKILL.md prose; never an absolute path or `plugins/mill/...`.
- **Rationale:** No "run the skill" harness exists; the drift guard + integration test are the
  available checks. See discussion `## Constraints`.
- **Applies to:** all batches.

### Decision: ASCII-only and CLAUDE.md path invariants

- **Decision:** All generated Python (`print`/messages) stays ASCII (`—` -> ` -- `, `->` -> ` -> `).
  All path resolution goes through `_paths.py` helpers — never inline `container / "wts" / slug`.
- **Rationale:** CLAUDE.md hard constraints; Windows cp1252 stdout.
- **Applies to:** all batches.

## All Files Touched

- `plugins/mill/integration_tests/test-merge.py`
- `plugins/mill/skills/mill-merge-in/SKILL.md`
- `plugins/mill/skills/mill-merge/SKILL.md`
- `plugins/mill/unit_tests/test-skill-helper-drift.py`
