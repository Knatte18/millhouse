# Plan: mill-merge-in SKILL.md: _plan_dag helper calls missing signature lines

```yaml
task: 'mill-merge-in SKILL.md: _plan_dag helper calls missing signature lines'
slug: mill-merge-in-plan-dag-signature-docs
approved: false
started: 20260802-101327
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
    name: add-signature-lines
    file: 01-add-signature-lines.md
    depends-on: []
    verify: null
```

## Shared Decisions

### Decision: signature-line placement and format

- **Decision:** Add two standalone `signature:` lines directly after the
  step-4 paragraph in `plugins/mill/skills/mill-merge-in/SKILL.md`
  (currently line 95), each on its own line, in the same call order as
  the prose sentence (`_read_batch_frontmatter` first, `parse_verify_field`
  second). Exact text:
  ```
  `signature: _plan_dag._read_batch_frontmatter(batch_path: Path) -> dict`
  `signature: _plan_dag.parse_verify_field(frontmatter: dict, hub_root: Path, git_root: Path) -> tuple[str | None, Path | None]`
  ```
- **Rationale:** Matches the established convention for a prose sentence
  naming multiple helper calls, following the closer structural
  precedent at `mill-go/SKILL.md:434-437` — standalone, unindented
  `signature:` lines following plain prose, not a numbered-list-item
  continuation. `parse_verify_field`'s return type is verified against
  the actual current source (`plugins/mill/scripts/_plan_dag.py:366-368`
  in this task worktree), not either source issue's prose — issue #768's
  `-> str | None` claim is stale/wrong; issue #762's
  `-> tuple[str | None, Path | None]` claim matches the real source.
- **Applies to:** all batches (single batch)

## All Files Touched

- `plugins/mill/skills/mill-merge-in/SKILL.md`
