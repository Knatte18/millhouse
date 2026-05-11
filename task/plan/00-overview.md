# Plan: '47 (A) — mill-merge-in: allowlist for known-broken pre-existing test failures'

```yaml
task: '47 (A) — mill-merge-in: allowlist for known-broken pre-existing test failures'
slug: verify-skip-known-broken
approved: true
started: 20260511-181206
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
    name: skill-and-schema
    file: 01-skill-and-schema.md
    depends-on: []
    verify: null
```

## Shared Decisions

### Decision: SKILL.md is the only behavioural surface

- **Decision:** All allowlist logic lives in `plugins/mill/skills/mill-merge-in/SKILL.md`. No new Python helper is added.
- **Rationale:** The check is a config-read plus a string-contains over the existing `iter_batch_verifies` output. An LLM-directed skill already loops over those pairs, so an inline pre-check is the smallest possible change. Adding a Python helper for a one-liner would be premature abstraction.
- **Applies to:** all batches

### Decision: Substring match, skip entire verify command

- **Decision:** A verify command `cmd` is skipped when any entry `p` in `cfg["verify"]["skip_known_broken"]` satisfies `p in cmd` (Python `str.__contains__`). The entire command is bypassed; the command string is not mutated.
- **Rationale:** Plan-author-controlled verify strings name test files literally. Substring is correct and zero-dependency. Per-runner flag injection (`--ignore`, `--deselect`) would require framework coupling.
- **Applies to:** all batches

### Decision: Config key is `verify.skip_known_broken`, values live in local config only

- **Decision:** The schema is documented in `plugins/mill/templates/wiki-config.yaml` (commented, empty list default) under a new top-level `verify:` section. Operators set actual values only in `.millhouse/config.local.yaml`. The production `C:/Code/millhouse/wiki/config.yaml` is mirrored to match the template's documentation per the CLAUDE.md mirror invariant.
- **Rationale:** Known-broken tests vary per machine; the shared wiki config is the wrong place for values. Documenting the schema in the template (and production wiki/config.yaml) makes the key discoverable without forcing anyone to set it.
- **Applies to:** all batches

### Decision: Log format and Step 6 Report

- **Decision:** When a verify command is skipped, log on stdout: `[verify] skipped <allowlisted-path> (allowlisted as known-broken)` where `<allowlisted-path>` is the specific entry that matched. Step 6 Report extends to `Verify: <M> batch tests ran, <K> skipped (allowlisted as known-broken).` when `K >= 1`; the existing `Verify: <M> batch tests ran.` format is unchanged when `K == 0`.
- **Rationale:** Exact spec text for the per-skip line. The Step 6 extension keeps the count unambiguous without churning the format when no skip happened.
- **Applies to:** all batches

## All Files Touched

- `C:/Code/millhouse/wiki/config.yaml`
- `plugins/mill/skills/mill-merge-in/SKILL.md`
- `plugins/mill/templates/wiki-config.yaml`
