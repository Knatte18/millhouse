# Plan: 16 (A) — Autonomous bug-fix pipeline (mill-autofix)

```yaml
task: 16 (A) — Autonomous bug-fix pipeline (mill-autofix)
slug: mill-autofix-bugs
approved: true
started: 20260507-105737
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
    name: Core Python helpers
    file: 01-core-python-helpers.md
    depends-on: []
    verify: python plugins/mill/unit_tests/run-all.py

  - number: 2
    name: Config and autonomous-mode wiring
    file: 02-config-autonomous-mode.md
    depends-on: []
    verify: null

  - number: 3
    name: Mill-autofix skill
    file: 03-mill-autofix-skill.md
    depends-on: [1, 2]
    verify: python plugins/mill/unit_tests/run-all.py
```

## Shared Decisions

_Cross-cutting decisions every batch inherits._

### Decision: wiki-config-write-pattern

- **Decision:** Changes to `wiki/config.yaml` are made by resolving the wiki path via `_paths.resolve_wiki_path(_paths.resolve_git_root())`, editing the file at `<wiki_path>/config.yaml`, then committing and pushing the wiki repo directly: `git -C <wiki_path> add config.yaml && git -C <wiki_path> commit -m "..." && git -C <wiki_path> push`. The `.wiki` junction is never used as a code path.
- **Rationale:** The wiki is a separate git repo. Junction paths are IDE/terminal convenience only (CLAUDE.md path invariants).
- **Applies to:** Batch 2 (Card 5).

### Decision: unit-test-style

- **Decision:** Unit tests follow the existing pattern in `test-gh-issues.py`: a `main() -> int` function running numbered cases with `PASS:`/`FAIL:` print statements and a final `return 0` / `return 1`. Import the module under test via direct `sys.path.insert` at the file top (matching the existing `HUB / "plugins" / "mill" / "scripts"` pattern). No third-party test framework.
- **Rationale:** Consistency with existing unit test suite.
- **Applies to:** Batches 1 and 3.

### Decision: slug-algorithm

- **Decision:** `slug_from_title` in `_autofix.py` implements: lowercase → replace non-`[a-z0-9]` with `-` → collapse consecutive `-` → strip leading/trailing `-` → truncate to 30 chars at last `-` boundary → if result in `existing_slugs`: append `-<issue_number>`.
- **Rationale:** Matches the discussion decision exactly (§slug-derivation).
- **Applies to:** Batch 1 (Card 1), Batch 3 (Card 8).

## All Files Touched

_Full union of every `Creates:` / `Edits:` across every batch._

- `SKILLS.md`
- `plugins/mill/scripts/_autofix.py`
- `plugins/mill/scripts/_gh_issues.py`
- `plugins/mill/skills/mill-autofix/SKILL.md`
- `plugins/mill/skills/mill-go/SKILL.md`
- `plugins/mill/skills/mill-plan/SKILL.md`
- `plugins/mill/unit_tests/test-autofix.py`
- `plugins/mill/unit_tests/test-gh-issues.py`
