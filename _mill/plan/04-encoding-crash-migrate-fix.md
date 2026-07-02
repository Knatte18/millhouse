# Batch: encoding-crash-migrate-fix

```yaml
task: Fix daemon health-check race, finalize env-var delivery, skills-index drop, and encoding crash
batch: encoding-crash-migrate-fix
number: 4
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-wiki-migrate-print.py
depends-on: []
```

## Batch Scope

Fixes the remaining scope of #588: mill-start's own Phase: Select / Phase: Explore encoding crash is already fixed on this branch (both call sites already carry `PYTHONIOENCODING=utf-8`; verified via `grep -rn PYTHONIOENCODING plugins/mill/skills/` — no plan changes needed there). `millpy-wiki-migrate.py`'s `_print_task_brief()` has the same unguarded-print vulnerability: it prints raw `title`/`brief` strings (externally-authored wiki content that can legitimately contain non-ASCII characters) via plain `print(f"...")`, which crashes with `UnicodeEncodeError` on a Windows cp1252 console — the same bug class as #588, just not yet triggered/reported for this script. This batch closes that gap with an in-script `sys.stdout.reconfigure()` guard rather than a `PYTHONIOENCODING=utf-8` invocation-prefix convention, because this script has no SKILL.md/wrapper invocation site to attach such a convention to — it is run manually and, separately, exercised by one integration test (`plugins/mill/integration_tests/test-wiki-migrate.py`), so there is no reliable place for a human to remember an invocation prefix.

## Cards

### Card 7: Guard `millpy-wiki-migrate.py` stdout against non-ASCII content

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/millpy-wiki-migrate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add a new module-level function `_ensure_utf8_stdout() -> None` in `millpy-wiki-migrate.py` (placed immediately before `_print_task_brief`), whose body is exactly `sys.stdout.reconfigure(encoding="utf-8", errors="replace")`. Call `_ensure_utf8_stdout()` as the first statement inside `main()`, before the `parser = argparse.ArgumentParser(...)` line. This guards `_print_task_brief()`'s raw `title`/`brief` pass-through against `UnicodeEncodeError` on a Windows cp1252 console. `sys` is already imported at module level — no new import needed.
- **Commit:** `fix(wiki-migrate): guard stdout against non-ASCII task content on cp1252 consoles (#588)`

### Card 8: Add `test-wiki-migrate-print.py` covering the stdout guard

- **Context:**
  - `plugins/mill/scripts/millpy-wiki-migrate.py`
  - `plugins/mill/unit_tests/test-abandon.py`
- **Creates:**
  - `plugins/mill/unit_tests/test-wiki-migrate-print.py`
- **Deletes:** none
- **Moves:** none
- **Requirements:** Using the `importlib.util.spec_from_file_location` pattern from `test-abandon.py` to load `millpy-wiki-migrate.py` as a module (hyphenated filename, cannot be `import`ed directly), write a unit test file with a `main()` entry point using the `ok()`/`fail()` harness pattern from `test-wiki-client-retry.py`, with one test case **"non-ASCII print survives on a simulated cp1252 stdout"**: save the original `sys.stdout`; replace `sys.stdout` with a fresh `io.TextIOWrapper(io.BytesIO(), encoding="cp1252")` (simulating a Windows cp1252 console, reproducing #588's precondition); call the loaded module's `_ensure_utf8_stdout()`; then `print("test: →")` (the exact character from #588's original repro) inside a `try`/`except UnicodeEncodeError` and assert no exception is raised; also assert `sys.stdout.encoding.lower() == "utf-8"` after the `_ensure_utf8_stdout()` call. Restore the original `sys.stdout` in a `finally` block regardless of test outcome.
- **Commit:** `test(wiki-migrate): verify _ensure_utf8_stdout guards non-ASCII console output (#588)`

## Batch Tests

`verify:` runs `test-wiki-migrate-print.py` (new, single-file scope) — directly reproduces #588's cp1252 precondition and confirms Card 7's guard prevents the crash.
