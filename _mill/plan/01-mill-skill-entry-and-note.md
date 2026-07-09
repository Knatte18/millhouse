# Batch: mill-skill-entry-and-note

```yaml
task: Fix mill-start instruction gaps, baseline long-path on Windows, and language skill tooling reliability
batch: mill-skill-entry-and-note
number: 1
cards: 2
verify: null
depends-on: []
```

## Batch Scope

Two instruction-correctness fixes in the mill orchestration SKILLs. Card 1 (#618) reorders the `## Entry` steps in both `mill-start` and `mill-plan` so config is loaded — and the `git_root`/`wiki_path` variables are bound — before the slug read that consumes them, eliminating the literal-execution `AttributeError`. Card 2 (#613) adds `[NOTE]`-finding handling to `mill-start`'s interactive GAPS_FOUND branch so NOTEs returned alongside gaps are applied rather than silently dropped. Both cards edit `mill-start/SKILL.md`; card 1 additionally edits `mill-plan/SKILL.md`. No external interface is produced. This is a pure-documentation batch: `verify: null`.

## Cards

### Card 1: Reorder Entry to load config and bind path vars before the slug read

- **Context:**
  - `plugins/mill/scripts/_marker.py`
  - `plugins/mill/scripts/_paths.py`
- **Edits:**
  - `plugins/mill/skills/mill-start/SKILL.md`
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In the `## Entry` section of BOTH `mill-start/SKILL.md` and `mill-plan/SKILL.md`, reorder the three numbered steps so the ordering becomes: (1) resolve and BIND the path variables — replace the inline `_paths.resolve_wiki_path(_paths.resolve_git_root())` with two bound assignments, `git_root = _paths.resolve_git_root()` then `wiki_path = _paths.resolve_wiki_path(git_root)`, keeping the existing `signature:` annotation lines; (2) the existing "Load config — deep-merge ..." step that assigns `cfg` and reads the `rounds` value; (3) the existing slug read `_marker.slug_from_branch(git_root, wiki_path, cfg)` with its `MarkerError` handling. The slug read (now step 3) must reference only already-bound names (`git_root`, `wiki_path`, `cfg`). Renumber the three steps to 1/2/3 in the new order and audit the `## Entry` block (including the `**Path Setup**` note that follows) for any "step 2"/"step 3" cross-references that must be updated to match. `_marker.slug_from_branch` genuinely requires `cfg` (it reads `cfg.get("spawn", {})` at `_marker.py:79`) — do NOT change its call signature; the fix is ordering plus binding only. Leave the `**Path Setup**` derivations themselves unchanged except for any step-number references.
- **Commit:** `fix(mill-start,mill-plan): load config and bind path vars before slug read in Entry`

### Card 2: Add [NOTE] handling to mill-start GAPS_FOUND branch

- **Context:**
  - `plugins/mill/skills/mill-receiving-review/SKILL.md`
- **Edits:**
  - `plugins/mill/skills/mill-start/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `mill-start/SKILL.md`, `### Phase: Discussion Review`, step 5 (the `On GAPS_FOUND` branch that currently instructs "read the review file and enumerate each `[GAP]` finding"), add explicit handling for `[NOTE]` findings that arrive in the same GAPS_FOUND round: each `[NOTE]` is applied via the `mill-receiving-review` fix-everything default (edited into the same in-memory `discussion.md` copy as the gap resolutions) and folded into the SAME `discussion-gap-fix` commit — no separate commit, no separate fixer report, and the Q&A log is not used for NOTEs. State that this mirrors the auto-mode rule already documented earlier in the SKILL ("every gap AND every NOTE returned by the reviewer is treated as FIX"). Do not alter the existing gap batching, the in-memory-copy-then-write-at-end-of-round mechanic, or the commit/push/round-increment flow — only add the NOTE-handling clause.
- **Commit:** `fix(mill-start): handle [NOTE] findings in GAPS_FOUND discussion-review branch`

## Batch Tests

`verify: null` — both cards edit `SKILL.md` prose only. No automated test asserts mill-start/mill-plan `## Entry` step ordering or GAPS_FOUND NOTE handling; the existing skill-structure tests (`test-skills-index.py`, `test-skill-helper-drift.py`) validate index/helper consistency, not instruction content, so they would neither exercise nor catch these edits. Correctness is established by the plan reviewer's read of the reordered Entry (config + path binding before the slug call) and the added NOTE clause, and confirmed at merge time by human read-through.
