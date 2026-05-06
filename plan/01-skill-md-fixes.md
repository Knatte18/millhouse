# Batch: skill-md-fixes

```yaml
task: 17 (A) — SKILL.md API accuracy audit + implementer-brief contract fixes
batch: skill-md-fixes
cards: 4
verify: null
depends-on: []
```

## Batch Scope

Fix three API documentation bugs in four SKILL.md files. Issue A: `_paths.resolve_git_root()` is incorrectly called with a `Path.cwd()` positional argument in mill-go, mill-plan, mill-start, and mill-resume — the function takes no arguments. Issue B: mill-plan SKILL.md option B in the max-rounds escape omits the `--max-rounds` CLI flag, making that escape non-functional. Issue C: mill-go SKILL.md documents `_status.read_full()` as returning a bare `dict` without showing the nested `{"yaml": dict, "timeline": list[str]}` structure, causing the phase-gate to use the wrong key. All changes are targeted string replacements; no file is created or deleted. This batch has no external interface for the next batch to consume.

## Cards

### Card 1: mill-go/SKILL.md — fix resolve_git_root arg and read_full signature

- **Reads:**
  - `plugins/mill/skills/mill-go/SKILL.md`
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/scripts/_status.py`
- **Modifies:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**

  **Fix 1 — resolve_git_root arg (line 14):**
  Find the line in the Entry section that reads:
  ```
  2. Resolve the wiki path: `wiki_path = _paths.resolve_wiki_path(_paths.resolve_git_root(Path.cwd()))`. Sync the wiki clone: `_wiki.sync_pull(wiki_path, slug=slug)`.
  ```
  Replace `_paths.resolve_git_root(Path.cwd())` with `_paths.resolve_git_root()` (remove the `Path.cwd()` argument). The rest of the line is unchanged.

  **Fix 2 — read_full signature and phase access (lines 24–25):**
  Find the block in Entry step 5 that currently reads:
  ```
  5. **Entry phase gate.** Set `status_path = Path("status.md").resolve()` and inspect the phase via `_status.read_full(status_path)`.
     `signature: _status.read_full(status_path: Path) -> dict`
  ```
  Replace it with:
  ```
  5. **Entry phase gate.** Set `status_path = Path("status.md").resolve()` and inspect the phase:
     ```python
     status = _status.read_full(status_path)
     phase = status["yaml"]["phase"]
     blocked_reason = status["yaml"].get("blocked_reason")
     ```
     `signature: _status.read_full(status_path: Path) -> {"yaml": dict, "timeline": list[str]}`
  ```
  Verify in `_status.py` that `read_full` returns `{"yaml": dict, "timeline": list[str]}` and that all YAML fields (phase, blocked_reason, etc.) live under the `"yaml"` key.

- **Commit:** `docs(mill-go): fix resolve_git_root arg and document read_full nested structure`

### Card 2: mill-plan/SKILL.md — fix resolve_git_root arg and document --max-rounds option B

- **Reads:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/scripts/millpy-review-plan.py`
- **Modifies:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**

  **Fix 1 — resolve_git_root arg (line 12):**
  Find the line in the Entry section that reads:
  ```
  1. Resolve the wiki path via `_paths.resolve_wiki_path(_paths.resolve_git_root(Path.cwd()))` and call `_wiki.sync_pull(wiki_path, slug="mill-plan")`.
  ```
  Replace `_paths.resolve_git_root(Path.cwd())` with `_paths.resolve_git_root()`. The rest of the line is unchanged.

  **Fix 2 — option B in max-rounds escape (step 6):**
  Find the max-rounds escape block (step 6) which contains this blockquote:
  ```
     > A) Deep problems — rethink approach. Go back to mill-start and revise discussion.
     > B) Shallow — one more review round.
     > C) Override — accept findings and proceed to mill-go anyway.
  ```
  Update the option B line to:
  ```
     > B) Shallow — one more review round. Invoke: `uv run --project "${CLAUDE_PLUGIN_ROOT}" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-review-plan.py" --max-rounds {N+1}` (the `--max-rounds` flag overrides the configured cap; without it the script re-reads config and exits at the same cap again).
  ```
  Then find the sentence that ends step 6:
  ```
     Wait for the user's choice. A → halt and tell user to check out fresh after they revise. B → run one more round (ignore the max). C → set `approved: true` and proceed to Handoff.
  ```
  Replace `B → run one more round (ignore the max).` with `B → invoke `millpy-review-plan.py --max-rounds {N+1}` where `{N}` is the round count just reported (one extra round beyond the configured max).`

  Verify in `millpy-review-plan.py` that `--max-rounds` is a valid argument (it is, defined around line 31–36).

- **Commit:** `docs(mill-plan): fix resolve_git_root arg and document --max-rounds for option B escape`

### Card 3: mill-start/SKILL.md — fix resolve_git_root arg

- **Reads:**
  - `plugins/mill/skills/mill-start/SKILL.md`
  - `plugins/mill/scripts/_paths.py`
- **Modifies:**
  - `plugins/mill/skills/mill-start/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  Find the line in the Entry section (step 1) that reads:
  ```
  1. Resolve the wiki path via `_paths.resolve_wiki_path(_paths.resolve_git_root(Path.cwd()))` and call `_wiki.sync_pull(wiki_path, slug="mill-start")`.
  ```
  Replace `_paths.resolve_git_root(Path.cwd())` with `_paths.resolve_git_root()`. The rest of the line is unchanged.

- **Commit:** `docs(mill-start): fix resolve_git_root call — takes 0 args not 1`

### Card 4: mill-resume/SKILL.md — fix both resolve_git_root args

- **Reads:**
  - `plugins/mill/skills/mill-resume/SKILL.md`
  - `plugins/mill/scripts/_paths.py`
- **Modifies:**
  - `plugins/mill/skills/mill-resume/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  There are two occurrences of `_paths.resolve_git_root(Path.cwd())` in this file (the skill lists them at lines 14 and 40). Both must be fixed.

  **Occurrence 1** — in the preamble "Sync invariant" note (near line 14):
  Find:
  ```
  where `wiki_path = _paths.resolve_wiki_path(_paths.resolve_git_root(Path.cwd()))`.
  ```
  Replace `_paths.resolve_git_root(Path.cwd())` with `_paths.resolve_git_root()`.

  **Occurrence 2** — in Phase 2: Sync wiki (near line 40):
  Find:
  ```
  Call `_wiki.sync_pull(wiki_path, slug="mill-resume")` (where `wiki_path = _paths.resolve_wiki_path(_paths.resolve_git_root(Path.cwd()))`) to refresh
  ```
  Replace `_paths.resolve_git_root(Path.cwd())` with `_paths.resolve_git_root()`.

  After both edits, confirm no remaining `resolve_git_root(Path.cwd())` occurrences exist in this file.

- **Commit:** `docs(mill-resume): fix both resolve_git_root calls — function takes 0 args`

## Batch Tests

`verify: null` — all changes are documentation only. No runnable surface exists. Verify manually that `resolve_git_root(Path.cwd())` no longer appears in any of the four SKILL.md files after completing the cards.
