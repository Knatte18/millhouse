# Plan: Fix millpy-implement.py finalize to accept (or not require) --session-id/--start-sha

```yaml
task: "Fix millpy-implement.py finalize to accept (or not require) --session-id/--start-sha"
slug: implement-finalize-session-id
approved: true
started: "20260615-104103"
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
    name: accept-session-start-sha-flags
    file: 01-accept-session-start-sha-flags.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-millpy-implement.py
```

## Shared Decisions

### Decision: accept-but-ignore (status.md is source of truth)

- **Decision:** The two new flags `--session-id` and `--start-sha` are added to
  `millpy-implement.py`'s argparse purely for CLI-shape parity with `millpy-fix.py` and the generic
  agent-dispatch loop. The `--stage finalize` branch is NOT modified — it keeps reading the
  authoritative `start_sha` and `implementer_session` values from `status.md`. The new args are
  parsed and discarded.
- **Rationale:** `millpy-implement.py` persists both values in `status.md` at prepare time
  (`millpy-implement.py:202`) and reads them back at finalize (`millpy-implement.py:174,177`). The
  CLI-passed value and the `status.md` value are identical (the SKILL got `session_id` from the same
  prepare envelope that wrote `status.md`), so reading from `status.md` is robust and unchanged.
  See `_mill/discussion.md` "Decisions" for the rejected alternatives (full fix.py parity; narrow
  the SKILL).
- **Applies to:** all batches

### Decision: ASCII-only help text

- **Decision:** The argparse `help=` strings and any new code comment use plain ASCII only (no
  em-dash, no `->` glyphs).
- **Rationale:** Project CLAUDE.md constraint — Windows cp1252 stdout crashes on non-ASCII; argparse
  `--help` prints to stdout.
- **Applies to:** all batches

## All Files Touched

- `plugins/mill/scripts/millpy-implement.py`
- `plugins/mill/unit_tests/test-millpy-implement.py`
