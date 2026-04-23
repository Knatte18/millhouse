# unit_tests

Unit tests for every `_*.py` helper in `plugins/mill/scripts/`. One
`test-<name>.py` per helper. Tests import the helper module directly
and drive it with in-memory fixtures or `tempfile` scratch dirs —
never real git, never real LLM calls. Those live in
`plugins/mill/integration_tests/`.

## Running

```bash
python plugins/mill/unit_tests/run-all.py
```

Runs every `test-*.py` in this directory. Exits 0 when all pass, non-zero
on any failure. Individual files are also executable on their own:

```bash
python plugins/mill/unit_tests/test-plan-dag.py
```

## Why separate from the helper files

Helper files under `plugins/mill/scripts/` used to end with an
`if __name__ == "__main__":` block carrying the same assertions. That
made fixtures read like production data to anyone browsing the module;
the separation here keeps production files strictly about production
behaviour.
