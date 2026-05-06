# Plan: '9 (B) — Wiki-enhance: small wiki cleanups'

```yaml
task: '9 (B) — Wiki-enhance: small wiki cleanups'
slug: wiki-enhance
approved: false
started: 20260506-132723
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - name: wiki-enhance-fixes
    file: 01-wiki-enhance-fixes.md
    depends-on: []
    verify: "python plugins/mill/unit_tests/run-all.py"
```

## Shared Decisions

### Decision: single-batch scope

- **Decision:** All changes ship in one batch.
- **Rationale:** Three cards covering config-key removal, generator fixes, and test updates. No file is touched by more than one card, so there is no ordering dependency within the batch. Total modified-file count is seven (two config files, three script files, two test files) — well within Sonnet's context window.
- **Applies to:** wiki-enhance-fixes

### Decision: no tombstone comments for removed config keys

- **Decision:** Delete `pipeline.builder`, the entire `implementers:` block, and `pipeline.implementer` outright; leave no comment in their place.
- **Rationale:** Commented-out dead config implies the keys might return and invites maintenance. `_config.py:load_config` returns an empty dict for missing keys so callers are unaffected.
- **Applies to:** wiki-enhance-fixes

### Decision: `.md` suffix scope limited to proposal links

- **Decision:** Only proposal-link hrefs get `.md`; the hardcoded `(Home)` Navigation entry in the sidebar and all non-proposal links are untouched.
- **Rationale:** GitHub Wiki and VS Code can navigate `(Home)` without `.md`; only proposal links were broken. Widening scope risks regressions in other link types.
- **Applies to:** wiki-enhance-fixes

## All Files Touched

- `plugins/mill/scripts/_sidebar.py`
- `plugins/mill/scripts/_tasks_md.py`
- `plugins/mill/scripts/millpy-add.py`
- `plugins/mill/templates/wiki-config.yaml`
- `plugins/mill/unit_tests/test-sidebar.py`
- `plugins/mill/unit_tests/test-tasks-md.py`
- `wiki/config.yaml`
