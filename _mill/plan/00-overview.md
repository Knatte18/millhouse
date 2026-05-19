# Plan: Silence verbose review log lines cluttering orchestrator output

```yaml
task: Silence verbose review log lines cluttering orchestrator output
slug: review-log-noise
approved: false
started: 20260519-063410
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
    name: Python noise removal
    file: 01-python-noise-removal.md
    depends-on: []
    verify: "uv run --project plugins/mill python unit_tests/run-all.py"
  - number: 2
    name: SKILL.md extraction commands
    file: 02-skill-extraction-commands.md
    depends-on: []
    verify: null
```

## Shared Decisions

### Decision: remove-prints-entirely

- **Decision:** Delete the noisy `print(..., file=sys.stderr)` lines entirely — no debug flag, no log level.
- **Rationale:** `_subprocess_util.py` (task 64) established the model: only emit to stderr on error. The "starting" and "returned N chars" lines are pure progress noise; error paths already surface the diagnostic info. A debug flag adds complexity and would still flood the bg log since reviewers run as subprocesses.
- **Applies to:** Batch 1 (Python noise removal)

### Decision: bash-grep-extraction

- **Decision:** Replace vague extraction prose with `grep '^{' <log-path> | tail -1` in all SKILL.md poll steps.
- **Rationale:** SKILL.md files already use bash-style syntax; the Bash tool is available in every orchestrator session. `^{` matches JSON object lines unambiguously; `tail -1` is defensive for any future multi-match edge case. PowerShell `Select-String` is inconsistent with existing SKILL.md style.
- **Applies to:** Batch 2 (SKILL.md extraction commands)

## All Files Touched

- `plugins/mill/scripts/_llm_claude.py`
- `plugins/mill/scripts/_review_code.py`
- `plugins/mill/scripts/_review_discussion.py`
- `plugins/mill/skills/mill-go/SKILL.md`
- `plugins/mill/skills/mill-plan/SKILL.md`
- `plugins/mill/skills/mill-start/SKILL.md`
