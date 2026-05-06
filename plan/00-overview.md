# Plan: '5 (A) — mill-bg.py: project-lokal backgrounding'

```yaml
task: '5 (A) — mill-bg.py: project-lokal backgrounding'
slug: mill-bg-helper
approved: false
started: 20260506T072351Z
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - name: core-script
    file: 01-core-script.md
    depends-on: []
    verify: python plugins/mill/unit_tests/test-shortcut-wrapper.py
  - name: tests-and-skills
    file: 02-tests-and-skills.md
    depends-on: [core-script]
    verify: python plugins/mill/unit_tests/test-millpy-bg.py
```

## Shared Decisions

### Decision: stdlib-only throughout

- **Decision:** `millpy-bg.py` uses only Python stdlib — no mill helpers, no `pyyaml`. The worker path in particular must run without the `uv run` environment context (spawned directly via `sys.executable`), so zero non-stdlib imports are used anywhere in the file.
- **Rationale:** The worker is spawned by the launcher as a bare `sys.executable` call. If it imported mill helpers (`_paths`, `_timestamp`, `pyyaml`), it would silently fail on machines where `PYTHONPATH` does not include the mill scripts dir. stdlib is always available.
- **Applies to:** core-script

### Decision: argparse avoided for `--` splitting

- **Decision:** Instead of `argparse`, both launcher and worker modes locate `"--"` in `sys.argv` by index and split manually.
- **Rationale:** `argparse.REMAINDER` does not reliably handle `"--"` as a separator. Manual `argv.index("--")` is deterministic and simpler.
- **Applies to:** core-script

### Decision: no new template

- **Decision:** No new Jinja/render template for the SKILL.md additions. The implementer edits the SKILL.md files directly using the Edit tool.
- **Rationale:** SKILL.md files are freeform Markdown; templates are for repeatable structured artefacts (plan files, review files). Direct edits are simpler.
- **Applies to:** tests-and-skills

## All Files Touched

- `plugins/mill/scripts/_shortcuts.py`
- `plugins/mill/scripts/millpy-bg.py`
- `plugins/mill/skills/mill-go/SKILL.md`
- `plugins/mill/skills/mill-start/SKILL.md`
- `plugins/mill/unit_tests/test-millpy-bg.py`
- `plugins/mill/unit_tests/test-shortcut-wrapper.py`
