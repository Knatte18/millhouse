# Plan: Wiki daemon error-log leak and stale plugin-cache config validation produce misleading noise

```yaml
task: "Wiki daemon error-log leak and stale plugin-cache config validation produce misleading noise"
slug: "mill-background-noise-and-stale-config"
approved: true
started: "2026-07-25T12:07:50Z"
parent: "hanf/linux-port-more"
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
    name: daemon-noise-fixes
    file: 01-daemon-noise-fixes.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-wiki-daemon.py
  - number: 2
    name: review-common-load-config-dedup
    file: 02-review-common-load-config-dedup.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-common.py test-config.py
```

## Shared Decisions

_Cross-cutting decisions every batch inherits: naming conventions,
error-handling posture, test frameworks, style/lint constraints. One
subsection per decision. Batch-local decisions live in each batch file._

### Decision: test style matches existing file

- **Decision:** New test cases follow the exact ok()/fail()-wrapped, try/except-per-case
  flat-script style already used throughout `test-wiki-daemon.py` and
  `test-review-common.py` — no pytest, no new test framework, no helper
  abstractions beyond what each file already imports.
- **Rationale:** Both files are hand-rolled flat scripts run via `run-all.py`; introducing
  a different style in only the new cases would fragment the file for no benefit.
- **Applies to:** all batches

### Decision: no behavior change beyond documented scope

- **Decision:** Every edit in this plan implements exactly one of the four
  `discussion.md` §Scope-In items (daemon exception classification, daemon stdio
  redirection, daemon logger consolidation, `_review_common.load_config` dedup).
  No incidental refactors, renames, or cleanups beyond what each decision requires.
- **Rationale:** `discussion.md` §Scope-Out explicitly excludes wire-protocol changes,
  `resolve_plugin_template_path` changes, and cache-refresh-timing changes — staying
  inside the four decisions keeps the diff reviewable against that boundary.
- **Applies to:** all batches

## All Files Touched

_Full union of every `Creates:` / `Edits:` / `Moves:` **target** path
across every batch, sorted alphabetically (Move **source** paths are
excluded — they disappear, like `Deletes:` tokens). Cards are the
source of truth; this section is the input `_plan_validate.py`'s
`all-files-touched-mismatch` check cross-references against the derived
union of every card's `Edits:`/`Creates:`/Move-target paths, to catch
drift between the hand/agent-maintained list here and that derived
union._

- `plugins/mill/scripts/_daemon.py`
- `plugins/mill/scripts/_review_common.py`
- `plugins/mill/scripts/wiki/_client.py`
- `plugins/mill/scripts/wiki/_server.py`
- `plugins/mill/unit_tests/test-review-common.py`
- `plugins/mill/unit_tests/test-wiki-daemon.py`
