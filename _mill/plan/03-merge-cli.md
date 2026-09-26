# Batch: merge-cli

```yaml
task: 'mill-merge: run the deterministic path as one script'
batch: merge-cli
number: 3
cards: 1
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-merge.py test-millpy-merge.py
depends-on: [2]
```

## Batch Scope

Adds the thin CLI `plugins/mill/scripts/millpy-merge.py` over `_merge.run_merge` and its tests.
Batch 4's rewritten `SKILL.md` invokes this CLI and documents its flags.

## Cards

### Card 7: millpy-merge.py CLI

- **Context:**
  - `plugins/mill/scripts/_merge.py`
  - `plugins/mill/scripts/millpy-spawn.py`
  - `plugins/mill/unit_tests/test-merge.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/scripts/millpy-merge.py`
  - `plugins/mill/unit_tests/test-millpy-merge.py`
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Create `plugins/mill/scripts/millpy-merge.py` with a module docstring (usage, flags, exit codes, one-line JSON contract summary pointing at `_merge.run_merge`).
  `main(argv: list[str] | None = None) -> int`:
  argparse with `--merged-in` (store_true), `--confirm-parent <branch>`, `--parent <branch>`;
  build `_merge.MergeOptions`;
  `result = _merge.run_merge(opts)`;
  print `json.dumps(result)` as the only stdout line (default `ensure_ascii=True`);
  return 0.
  No `try/except` around `run_merge`: an unexpected exception propagates, so the process exits non-zero with a traceback on stderr and prints no JSON (discussion Decision `script-shape`).
  Progress lines, if any, go to stderr.
  `if __name__ == "__main__": sys.exit(main())`.

  Create `plugins/mill/unit_tests/test-millpy-merge.py` (same harness shape as `plugins/mill/unit_tests/test-merge.py`), loading the CLI via `importlib.util.spec_from_file_location` because of the hyphenated filename:
  import smoke test;
  flag parsing — patch `_merge.run_merge` with a fake that captures `opts`, then assert `--merged-in`, `--confirm-parent X`, `--parent Y` map onto `MergeOptions` fields;
  stdout carries exactly one line that `json.loads` parses, for a `halt` result, and `main` returns 0;
  a `run_merge` fake raising `RuntimeError` makes `main` raise (the crash path), with nothing written to stdout.
- **Commit:** `feat(mill-merge): add millpy-merge.py CLI`

## Batch Tests

`verify:` runs `test-merge.py` and `test-millpy-merge.py`: the CLI tests plus a re-run of the core tests the CLI depends on.
