# Batch: wiki-enhance-fixes

```yaml
task: '9 (B) — Wiki-enhance: small wiki cleanups'
batch: wiki-enhance-fixes
cards: 3
verify: "python plugins/mill/unit_tests/run-all.py"
depends-on: []
```

## Batch Scope

Delivers all three wiki-enhance fixes in one pass: (1) remove three dead config keys from the live wiki config and its template, (2) add `.md` suffix to the three code locations that generate proposal links, and (3) update the one affected unit-test assertion and add a new `test-sidebar.py`. The batch produces no external interface change — callers reading config get the same values for all live keys; callers receiving generated Home.md or sidebar text see the `.md` suffix added to new links only (existing links are unchanged since they are written verbatim by the parser).

## Cards

### Card 1: Remove dead config keys from wiki/config.yaml and template

- **Reads:**
  - `wiki/config.yaml`
  - `plugins/mill/templates/wiki-config.yaml`
  - `plugins/mill/scripts/_config.py`
  - `plugins/mill/unit_tests/test-config.py`
- **Modifies:**
  - `wiki/config.yaml`
  - `plugins/mill/templates/wiki-config.yaml`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Remove `pipeline.builder: sonnet` and `pipeline.implementer: null` from the `pipeline:` block in both files, leaving `pipeline.auto_merge`, `pipeline.auto_report`, and any accompanying comments intact. Remove the entire `implementers:` top-level block (it has a single key `code: sonnet` and no script reads it). Also remove the section comment header immediately above the `implementers:` block (the `# ---…---` banner + description lines that document only that block). Read `test-config.py` first and remove or update any assertion that references `cfg["implementers"]` or `cfg["pipeline"]["builder"]` or `cfg["pipeline"]["implementer"]` — if no such assertion exists, no test change is needed. Confirm `_config.py` has no reference to these keys (it uses generic `yaml.safe_load` + deep-merge; no special handling expected).
- **Commit:** `chore(config): remove dead pipeline.builder, pipeline.implementer, and implementers keys`

### Card 2: Add .md suffix to proposal-link generators

- **Reads:**
  - `plugins/mill/scripts/millpy-add.py`
  - `plugins/mill/scripts/_tasks_md.py`
  - `plugins/mill/scripts/_sidebar.py`
- **Modifies:**
  - `plugins/mill/scripts/millpy-add.py`
  - `plugins/mill/scripts/_tasks_md.py`
  - `plugins/mill/scripts/_sidebar.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `millpy-add.py`, change `_render_task_section()` so the linked slug line reads `f"[[{slug}]](proposal-{slug}.md)"` instead of `f"[[{slug}]](proposal-{slug})"`. In `_tasks_md.py`, make the same change inside `append_entry()` — the only line that constructs `[[{slug}]](proposal-{slug})`. In `_sidebar.py`, change the `render()` function's linked-task branch from `f"- [{task['title']}](proposal-{task['slug']})"` to `f"- [{task['title']}](proposal-{task['slug']}.md)"`. Do not change the hardcoded `(Home)` Navigation entry. Do not touch `_HEADING_RE`, `set_phase`, or any parse path — the regex already handles both suffix forms and `set_phase` reconstructs links verbatim from the captured group.
- **Commit:** `fix(wiki): add .md suffix to proposal links in millpy-add, _tasks_md, _sidebar`

### Card 3: Update test-tasks-md assertion and add test-sidebar.py

- **Reads:**
  - `plugins/mill/unit_tests/test-tasks-md.py`
  - `plugins/mill/unit_tests/test-millpy-add.py`
  - `plugins/mill/unit_tests/test-spawn-core.py`
  - `plugins/mill/scripts/_sidebar.py`
  - `plugins/mill/unit_tests/run-all.py`
- **Modifies:**
  - `plugins/mill/unit_tests/test-tasks-md.py`
- **Creates:**
  - `plugins/mill/unit_tests/test-sidebar.py`
- **Deletes:** none
- **Requirements:** In `test-tasks-md.py`, find the assertion that checks `"[[prop-task]](proposal-prop-task)" in result_proposal` (currently around line 68) and change it to `"[[prop-task]](proposal-prop-task.md)" in result_proposal`. Read `test-millpy-add.py` to confirm it has no assertion on the slug-line format inside Home.md (it only checks the proposal file content and mutual-exclusion CLI behaviour); if found, update to `.md`; if not found, no change. Read `test-spawn-core.py` to confirm `test_multi_select_groom_then_claim_with_proposal` checks proposal file creation, not the slug line format in Home.md; if found, update; if not found, no change. Create `plugins/mill/unit_tests/test-sidebar.py` that imports `_sidebar.render` directly (add the scripts directory to sys.path the same way other test files in this directory do), calls `render()` with one task that has `has_proposal=True` and one without, and asserts: (a) the linked task's output line contains `(proposal-{slug}.md)`, and (b) the plain task's output line does not contain a parenthesised link at all. The test must be runnable standalone (`python test-sidebar.py`) and print a PASS line on success. `run-all.py` discovers tests via `glob("test-*.py")` so no registration step is needed.
- **Commit:** `test(wiki): update test-tasks-md for .md suffix; add test-sidebar`

## Batch Tests

`verify: "python plugins/mill/unit_tests/run-all.py"` runs all 30+ unit tests including the updated `test-tasks-md.py` and the new `test-sidebar.py`. The suite is the complete regression gate. Individual test files can be run standalone (`python plugins/mill/unit_tests/test-sidebar.py`) during development.
