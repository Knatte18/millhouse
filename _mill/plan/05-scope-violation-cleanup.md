# Batch: scope-violation-cleanup

```yaml
task: "Fix nit-enforcement gate, Windows verify false-positive, reviewer oscillation, and scope-violation handling"
batch: scope-violation-cleanup
number: 5
cards: 4
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-cleanliness.py
depends-on: [4]
```

## Batch Scope

Fixes #523 — a `-cover` verify run leaves `coverage.out` (untracked, out-of-scope) at the repo root, surfaced as `scope_violations` but never handled, requiring manual cleanup. Adds `_cleanliness.clean_ephemeral_scope_violations(worktree)` which auto-removes a conservative allowlist of build artifacts and reports anything else as blocking; wires it into mill-go's Handoff terminal gate and documents `scope_violations` handling in the fix paths; adds a non-enforced mill-plan note steering `-cover` to a scratch coverprofile. Depends on batch 4 (shared `mill-go/SKILL.md` write ordering — last in the chain). No downstream consumer.

## Cards

### Card 16: clean_ephemeral_scope_violations helper

- **Context:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Edits:**
  - `plugins/mill/scripts/_cleanliness.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add `clean_ephemeral_scope_violations(worktree: Path) -> tuple[list[str], list[str]]` to `_cleanliness.py`. It calls the existing `compute_scope_violations(worktree)`, partitions the returned untracked out-of-scope paths by a conservative allowlist — basename `coverage.out`, or suffix in `{.test, .test.exe, .prof, .cover}` — removing allowlisted files from disk (via `os.remove`, swallowing already-gone errors) and returning `(removed_paths, blocking_paths)` where `blocking_paths` are the non-allowlisted violations. Pure helper: it never deletes anything off the allowlist. Resolve nothing through junctions. ASCII-only.
- **Commit:** `feat(cleanliness): auto-clean ephemeral scope violations on an allowlist`

### Card 17: mill-go terminal gate + scope_violations handling

- **Context:**
  - `plugins/mill/scripts/_cleanliness.py`
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `mill-go/SKILL.md`'s Handoff terminal cleanliness gate, after the existing `compute_terminal_dirt` check, add a step that calls `_cleanliness.clean_ephemeral_scope_violations(worktree_root)`; log the removed allowlisted artifacts (ASCII) and, if `blocking_paths` is non-empty, BLOCK Handoff with a message listing them (`BLOCKED: out-of-scope untracked file(s): <list>`). Additionally, in the per-batch and holistic fix paths, document that a `scope_violations` field in the fixer JSON envelope is read and surfaced to the orchestrator (it is already folded into the generic `stuck_type: logic` envelope; note that the terminal gate is the authoritative cleanup point). ASCII-only.
- **Commit:** `feat(mill-go): terminal gate auto-cleans ephemeral scope violations`

### Card 18: mill-plan -coverprofile guidance note

- **Context:**
  - `plugins/mill/scripts/_cleanliness.py`
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `mill-plan/SKILL.md`, near the existing "Verify command scope" guidance, add a one-line, non-enforced note: a `verify:` command that collects coverage should write to a scratch path (e.g. `-coverprofile=.scratch/coverage.out`) so it does not leave an untracked `coverage.out` at the repo root; the Handoff terminal gate auto-cleans the common artifacts as a backstop. This is guidance only — not a validator rule. ASCII-only.
- **Commit:** `docs(mill-plan): note scratch coverprofile for -cover verify commands`

### Card 19: tests for clean_ephemeral_scope_violations

- **Context:**
  - `plugins/mill/scripts/_cleanliness.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-cleanliness.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `test-cleanliness.py`, add cases (reuse the existing tempfile-git-repo fixture): (a) an allowlisted artifact (`coverage.out`, and one suffix case like `foo.test.exe`) placed untracked at the worktree root is removed and reported in `removed`, leaving the tree clean; (b) a non-allowlisted untracked out-of-scope file (e.g. `notes.txt`) is NOT removed and appears in `blocking`; (c) an in-scope untracked file under `_mill/` is neither removed nor reported (compute_scope_violations already excludes it). Assert the function never deletes off-allowlist files.
- **Commit:** `test(cleanliness): cover ephemeral scope-violation auto-clean`

## Batch Tests

`verify:` runs `test-cleanliness.py` — the suite covering `_cleanliness.py`. The two SKILL.md edits (mill-go terminal gate wiring, mill-plan note) have no unit surface and are plan-reviewer validated. Key scenarios: allowlist remove vs block vs in-scope-ignore in card 19.
