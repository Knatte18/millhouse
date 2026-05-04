# Batch: validate-plan-typeerror

```yaml
task: 6 — mill-go SKILL.md prose + lock-API + lock-coverage + Builder-oppførsel
batch: validate-plan-typeerror
cards: 1
verify: uv run --project "c:/Code/millhouse/wts/millhouse/plugins/mill" python "c:/Code/millhouse/wts/millhouse/plugins/mill/unit_tests/run-all.py"
depends-on: []
```

## Batch Scope

A one-card fix for #101: `millpy-validate-plan.py:32` calls `resolve_path(cfg["paths"]["plan_dir"], slug, wiki_root)` with three arguments, but the imported `_review_common.resolve_path` signature is `(path_tmpl, slug)`. The standalone CLI (`uv run ... millpy-validate-plan.py`) crashes with `TypeError: resolve_path() takes 2 positional arguments but 3 were given`. The fix is mechanical — drop the third arg — and ships with a new `test-millpy-validate-plan.py` that exercises the standalone CLI path so this signature drift is caught the next time `_review_common.resolve_path`'s shape changes.

## Cards

### Card 13: Fix `millpy-validate-plan.py` `resolve_path` call + add CLI test

- **Reads:**
  - `plugins/mill/scripts/millpy-validate-plan.py`
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/unit_tests/test-plan-validate.py`
- **Modifies:**
  - `plugins/mill/scripts/millpy-validate-plan.py`
- **Creates:**
  - `plugins/mill/unit_tests/test-millpy-validate-plan.py`
- **Requirements:** In `millpy-validate-plan.py:32`, change `resolve_path(cfg["paths"]["plan_dir"], slug, wiki_root)` to `resolve_path(cfg["paths"]["plan_dir"], slug)` (drop `wiki_root`). The local `wiki_root` variable on line 27 is still needed for `_plan_validate.run(plan_dir, project_root, wiki_root=wiki_root)` — leave that call shape unchanged. Verify by running the standalone CLI manually against a fixture plan dir: it must exit 0 + JSON envelope on success and exit 1 + errors envelope on validator findings. Create `test-millpy-validate-plan.py` that invokes the CLI's `main()` function in-process (not as a subprocess) against a `tempfile.TemporaryDirectory` fixture: build a minimal valid plan dir layout (overview + one batch file, both passing the validator), call `main()`, capture stdout via `contextlib.redirect_stdout`, assert exit code 0 and JSON envelope `{"errors": [], "summary": "no findings"}`. Add a second test fixture with a known validator violation (e.g. a card with no Reads field) and assert the CLI returns exit 1 and the JSON envelope contains the expected error type. **Do NOT use `monkeypatch.chdir` — the test suite uses plain Python with no pytest runner.** Instead, change cwd via `os.chdir(str(fixture_root))` wrapped in a `try/finally` that restores the original cwd: `orig = os.getcwd(); os.chdir(str(fixture_root)); try: ...; finally: os.chdir(orig)`. **Patch the helpers that `main()` calls before reaching `_plan_validate.run` — these do not work in a bare tempdir:** use `unittest.mock.patch('_paths.resolve_git_root', return_value=fixture_root)`, `unittest.mock.patch('_paths.resolve_wiki_path', return_value=fixture_root / 'wiki')`, `unittest.mock.patch('_review_common.load_config', return_value={...minimal config dict...})`, `unittest.mock.patch('_review_common.find_active_slug', return_value=slug)`, and `unittest.mock.patch('_review_common.resolve_path', return_value=fixture_plan_dir)`. This lets `main()` reach `_plan_validate.run(plan_dir, ...)` with real plan files constructed in the fixture. Follow `test-plan-validate.py`'s structural style for plan-fixture construction.
- **Commit:** `fix(millpy-validate-plan): correct resolve_path arity + add CLI test`

## Batch Tests

`verify:` runs the full unit-test suite, which now includes `test-millpy-validate-plan.py`. The test exercises both the success path and a validator-failure path of the standalone CLI; it also implicitly catches any future signature drift in `_review_common.resolve_path` that would re-break the CLI. No integration test is added — `_plan_validate`'s behaviour is already covered by `test-plan-validate.py`; this batch only fixes the wrapper CLI.
