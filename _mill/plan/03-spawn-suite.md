# Batch: spawn-suite

```yaml
task: "millpy-implement finalize/resume fixes and the red integration suites"
batch: "spawn-suite"
number: 3
cards: 1
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/integration_tests/test-spawn.py
depends-on: [1]
```

## Batch Scope

Repairs `test-spawn`, whose fixture no longer matches the wiki path resolution.
Separate from the other integration repairs because the failure is a chain: fixing the lookup may expose further stale assertions, all handled inside the single card.
Batch-local decision: fixture-first, product fix only for a proven spawn bug.

## Cards

### Card 10: test-spawn fixture resolves its wiki and matches current spawn behaviour

- **Context:**
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/scripts/millpy-spawn.py`
- **Edits:**
  - `plugins/mill/integration_tests/test-spawn.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Symptom: `millpy-spawn.py` exits 1 with a "Wiki not found at <container>/hub.wiki" message because `_setup_pair` builds `<container>/hub` and `<container>/wiki`, which is neither container layout (`wts/<slug>` plus a sibling `wiki/`) nor prefix layout (`<hub>.wiki`).
  Fix in `_setup_pair`: write a `paths:` mapping with `wiki: <absolute path of the clone>` into the hub's `.millhouse/config.local.yaml` (the documented override read by `resolve_wiki_path` in `_paths.py`), replacing the current empty overlay.
  Then run the suite and iterate: each further failure (worktree location assertions, junction names, stale docstring expectations such as `worktrees/<slug>`) is fixed by updating the fixture or assertion to the current documented behaviour, checked against `millpy-spawn.py` and `_paths.py`.
  If a remaining failure proves a genuine spawn bug rather than fixture drift, fix the product code minimally, note it in the commit body, and keep the assertion.
  If the override approach does not work, rebuild the fixture in container layout (`<container>/wts/hub` with a sibling `<container>/wiki`) instead.
  Update the module docstring's layout description to match the final fixture.
- **Commit:** `test(spawn): make the spawn fixture resolve its wiki and match current spawn behaviour`

## Batch Tests

`verify:` runs `test-spawn.py` alone; it is the only suite this batch edits.
