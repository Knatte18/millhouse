# Discussion: 55 (A) — Fix hardcoded _mill/ paths and mill-setup junction/config bugs

```yaml
task: 55 (A) — Fix hardcoded _mill/ paths and mill-setup junction/config bugs
slug: mill-path-hardcodes
status: discussing
parent: main
```

## Problem

Mill SKILL.md files hardcode `_mill/` path strings directly — in Python expressions like `Path("_mill/status.md").resolve()` and in git commands like `git add _mill/status.md`, `git rm -r _mill/`. This breaks backward compatibility with in-flight worktrees created before the `task/` → `_mill/` rename: those worktrees have `task/status.md`, `task/plan/`, etc. The shim `_paths.resolve_task_path` exists to handle the fallback, but no SKILL.md instructions tell Claude to use it — they all hardcode the string.

Additionally, mill-setup has two related bugs:

- **#293 (Phase 4):** When `hub_relative_path != "."` (subdirectory-hub mode), Phase 4 passes `git rev-parse --show-toplevel` as `target_root` to `create_hub_links`. The git root is the repo root, not the hub directory. Junctions land in the wrong place.
- **#294 (Phase 3.1):** Phase 3.1 skips `config.yaml` entirely if the file exists, without validating that it contains required blocks. An existing config missing the `paths:` block causes a `KeyError` in mill-spawn downstream.

These are all in-repo SKILL.md / template edits — no Python helper changes except for the new unit test.

## Scope

**In:**
- mill-go/SKILL.md: add Path Setup block, replace hardcoded `_mill/` path strings with config-derived variables using `resolve_task_path` for reads and config-canonical for writes. **Exception:** the cleanliness snapshot path (`<worktree>/_mill/.cleanliness-snapshot-<batch_name>.txt`, SKILL.md line 136) must keep its `_mill/` literal and NOT be replaced with `task_dir`. `millpy-implement.py` writes this file unconditionally to `_mill/` and is out of scope — replacing only the SKILL.md read reference would cause a path mismatch on legacy `task/` worktrees, making `compute_new_dirt` silently treat pre-batch state as empty.
- mill-finalize/SKILL.md: same pattern; fix `git rm -r _mill/` to use resolved `task_dir`.
- mill-merge/SKILL.md: same pattern; fix `git rm -r _mill/` to use resolved `task_dir`.
- mill-start/SKILL.md: add Path Setup block, replace all `_mill/` references with config-derived paths; reads use `resolve_task_path`, new file creation uses config-canonical.
- mill-plan/SKILL.md: same pattern.
- mill-setup/SKILL.md Phase 4: change `target_root` from `<hub-path>` (= `git rev-parse --show-toplevel`) to `<cwd>`; update token documentation.
- mill-setup/SKILL.md Phase 3.1: after the skip-if-exists check, add block-level upsert logic to detect and fill missing required blocks (especially `paths:`) from the template.
- `plugins/mill/unit_tests/test-resolve-task-path.py`: new unit test covering the `resolve_task_path` compat fallback.

**Out:**
- No changes to `_paths.py` — `resolve_task_path` already exists and is correct.
- No changes to `_config.py`, `_status.py`, or any other Python helper.
- No changes to `wiki/config.yaml` or `templates/wiki-config.yaml` — paths already canonical.
- No changes to mill-spawn, mill-cleanup, mill-groom, or any other skill not listed above.
- No integration test for mill-setup Phase 4 subdir mode (complex environment setup).
- No changes to the `millpy-*.py` CLI scripts.

## Decisions

### Path setup block pattern

- **Decision:** Each affected SKILL.md gets a "Path Setup" sub-step in its Entry section that:
  1. Loads config via `_config.load_config(wiki_path, worktree_root)` (wiki_path and worktree_root already resolved at entry in every skill).
  2. Derives path variables:
     - `status_path = _paths.resolve_task_path(worktree_root, cfg['paths']['status_md'])`
     - `discussion_path = _paths.resolve_task_path(worktree_root, cfg['paths']['discussion_file'])` (mill-start only)
     - `plan_dir = _paths.resolve_task_path(worktree_root, cfg['paths']['plan_dir'])` (mill-go, mill-plan)
     - `reviews_dir = _paths.resolve_task_path(worktree_root, cfg['paths']['reviews_dir'])` (mill-go, mill-plan, mill-start)
     - `task_dir = status_path.parent` (mill-go, mill-finalize, mill-merge — for `git rm -r`)
     - `overview_path = plan_dir / "00-overview.md"` (mill-go, mill-plan — derived from plan_dir, not resolved separately)
  3. All subsequent path references in the skill use these variables. The cleanliness snapshot (`_mill/.cleanliness-snapshot-*`) in mill-go is the sole exception — keep its `_mill/` literal (see Scope).
- **Rationale:** Single config-load per skill; explicit variable names; compat shim applied consistently. Mirrors how other skills already handle config at entry.
- **Rejected:** Inline `resolve_task_path` at each use site — verbose, easy to miss one site. Minimal fix (Python-only, leave git strings) — leaves `git add _mill/status.md` broken on `task/` worktrees.

### Read vs. write path strategy

- **Decision:** For reading existing task state, use `resolve_task_path` (tries `_mill/`, falls back to `task/` if that exists and `_mill/` does not). For creating new task state (mill-start writing `discussion.md`, mill-plan creating `_mill/plan/`), use the config-canonical path directly: `worktree_root / cfg['paths']['discussion_file']`. No compat fallback on write paths.
- **Rationale:** Writing new state to a legacy `task/` path would permanently embed the old layout. All new output should land in the config-canonical `_mill/` location. Read-time compat handles the transition for in-flight worktrees.
- **Rejected:** Use `resolve_task_path` for writes too — would write to `task/` on old worktrees and perpetuate the legacy layout.

### git rm -r task_dir

- **Decision:** Replace `git rm -r _mill/` (in mill-finalize and mill-merge) with `git -C <worktree> rm -r <task_dir>`, where `task_dir = status_path.parent`. Since `status_path` is already resolved via `resolve_task_path`, its parent is the actual task directory — `_mill/` or `task/` as appropriate.
- **Rationale:** The relative path `_mill/` would fail if the worktree uses `task/`. The resolved parent is the correct compat-aware path.
- **Rejected:** Hardcode both `git rm -r _mill/ || git rm -r task/` — fragile double-try pattern.

### mill-setup Phase 4: target_root = cwd

- **Decision:** In the Phase 4 `create_hub_links` call, change `target_root=Path(r'<hub-path>').resolve()` to `target_root=Path(r'<cwd>').resolve()`. Update the token documentation: `<hub-path>` description changes from "`git rev-parse --show-toplevel`" to "`cwd` — the hub directory (same as `<cwd>` for mill-setup; use `cwd`, not git rev-parse)". The `HUB_PATH` token in the tokens dict also changes to `r'<cwd>'` since no junction target in the current config references `<HUB_PATH>`, making the value immaterial to correctness, but it should be accurate for future templates.
- **Rationale:** `cwd` is already the hub directory at Phase 4 time (mill-setup is invoked from the hub). In subdir-hub mode, `git rev-parse --show-toplevel` returns the repo root, not the hub subdirectory. Phase 4.9 computes `hub_relative_path` by comparing cwd to git-root, proving cwd != git-root in this mode.
- **Rejected:** Compute `git_toplevel / hub_relative_path` — would require reading `hub_relative_path` from config before Phase 4.9 writes it; ordering hazard. Using cwd is simpler and correct by construction.

### mill-setup Phase 3.1: block-level upsert

- **Decision:** When `<wiki-dir>/config.yaml` exists (i.e. the skip-if-exists path fires), add a validation step:
  1. Load existing `config.yaml` as YAML.
  2. Load the template from `${CLAUDE_PLUGIN_ROOT}/templates/wiki-config.yaml`.
  3. For each required top-level key missing from the existing config (`paths`, `llm`, `pipeline`, `roles`, `notify`, `spawn`, `groom`), copy it verbatim from the template.
  4. If any blocks were added, write the merged YAML back to `config.yaml`, commit, and push via `_wiki.write_commit_push`.
  5. Log which blocks were added so the operator can see the diff.
- **Rationale:** Handles partial configs from old mill-setup versions or manual edits without requiring operator intervention. Idempotent: if all blocks present, no write occurs. The `paths:` block is the critical one (causes `KeyError` in mill-spawn), but upsert-all avoids future issues with other required blocks.
- **Rejected:** Hard halt on missing block — forces operator to manually fix config, poor UX for a recoverable gap. Warning only — doesn't fix the KeyError.

### Unit test scope

- **Decision:** Add `plugins/mill/unit_tests/test-resolve-task-path.py` with in-memory / tempfile fixtures (no real git, no real LLM). Covers:
  1. `_mill/status.md` exists → returns the `_mill/` path.
  2. `task/status.md` exists, `_mill/status.md` does not → returns the `task/` path (compat).
  3. Neither exists → returns `_mill/status.md` (config-canonical default).
  4. Both exist → returns `_mill/` path (primary wins).
  5. Non-`_mill/` config path (e.g. `custom/status.md`) → no fallback attempted; returns the config path.
- **Rationale:** `resolve_task_path` is the compat shim that all SKILL.md changes depend on. A unit test pins the behavior and catches regressions if the function is edited.
- **Rejected:** Integration test for mill-setup Phase 4 subdir mode — would require a real git repo, subdir setup, and junction creation; significant fixture complexity for a one-line SKILL.md fix.

## Technical context

### Key modules

- `plugins/mill/scripts/_paths.py` — `resolve_task_path(worktree_root, cfg_relative_path)` at lines 448–461. Already exported in `__all__`. `status_path(worktree_root, cfg)` at lines 463–470 already calls `resolve_task_path` — but no SKILL.md instruction tells Claude to use it.
- `plugins/mill/scripts/_config.py` — `load_config(wiki_path, worktree_root)` deep-merges shared and local config. All affected skills already call this or have access to its output.
- `plugins/mill/scripts/_setup.py` — `create_hub_links(target_root, wiki_path, tokens)` at lines 35–118. `target_root` is the directory where junctions/hardlinks are created. All junction link paths are `target_root / junction_rel` (line 98).

### SKILL.md entry patterns (before fix)

mill-go, line 45: `status_path = Path("_mill/status.md").resolve()`
mill-go, line 62: `plan_dir = Path("_mill/plan/").resolve()`
mill-plan, lines 61/65: same two patterns
mill-finalize, line 49: `git add _mill/status.md`; line 58: `git rm -r _mill/`
mill-merge, line 82: `git rm -r _mill/`; line 142: `git add _mill/status.md`
mill-start, line 94: `git -C <worktree> add _mill/discussion.md`

### wiki/config.yaml paths block (authoritative)

```yaml
paths:
  discussion_file: _mill/discussion.md
  plan_dir:        _mill/plan/
  reviews_dir:     _mill/reviews/
  status_md:       _mill/status.md
```

These are the canonical values. `resolve_task_path` uses these as the primary target and falls back to the `task/` equivalent only if the primary is absent.

### mill-setup Phase 4 (before fix)

```python
result = _setup.create_hub_links(
    target_root=Path(r'<hub-path>').resolve(),   # BUG: should be cwd
    wiki_path=Path(r'<wiki-dir>').resolve(),
    tokens={
        'HUB_PATH':       r'<hub-path>',         # should be cwd
        'CWD_PATH':       r'<cwd>',
        ...
    },
)
```

Token doc says `<hub-path>` = `git rev-parse --show-toplevel`. Fix: replace both occurrences with `r'<cwd>'` and update the token doc.

### mill-setup Phase 3.1 (before fix)

```
1. If <wiki-dir>/config.yaml exists: skip.
2. Otherwise: copy template → config.yaml ...
```

Fix: when the file exists, add a validation sub-step (see Decisions above).

### PYTHONPATH for mill-setup upsert inline Python

Use the same form as other Phase 3.1 inline calls:
```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe" -c "..."
```

For loading YAML in the validation sub-step, `import yaml` is available in the mill venv.

### Unit test location and runner

New test file: `plugins/mill/unit_tests/test-resolve-task-path.py`.
Runner: `python plugins/mill/unit_tests/run-all.py` — auto-discovers `test-*.py` in the directory.
Pattern: use `tempfile.TemporaryDirectory()` for fixtures; create/skip files to control which path exists.

## Testing

- `test-resolve-task-path.py` covers all five compat scenarios (see Decisions above). Run via `run-all.py`.
- Manual smoke test of mill-go on an in-flight worktree that uses `task/` layout (if one is available) to verify the compat fallback fires.
- Mill-setup Phase 4 fix verified by re-running `/mill-setup` with `hub_relative_path != "."` and confirming junctions land in `<cwd>`, not in git-root.
- Mill-setup Phase 3.1 fix verified by running `/mill-setup` against a wiki with an existing config.yaml that lacks the `paths:` block and confirming it is added and committed.

## Q&A log

- **Q:** Which approach for the path-hardcode fix pattern in SKILL.md files? **A:** [auto-pick] Dedicated "Path Setup" block at skill entry that loads config and defines all path variables; replace hardcoded `_mill/` strings throughout with those variables. **Why:** Centralizes config loading once per skill; consistent; ensures every downstream reference uses the compat-aware variable.
- **Q:** Should reads and writes use the same path strategy? **A:** [auto-pick] Reads use `resolve_task_path` (compat fallback); writes use config-canonical path directly. **Why:** Writing to a legacy `task/` path propagates the old layout; new state always lands in `_mill/`.
- **Q:** For mill-setup Phase 3.1 validation, what level of fix? **A:** [auto-pick] Block-level upsert — add missing required blocks from template. **Why:** Idempotent; handles partial configs without operator intervention.
- **Q:** For mill-setup Phase 4, which source for target_root? **A:** [auto-pick] Use `cwd` directly instead of `git rev-parse --show-toplevel`. **Why:** `cwd` is the hub by construction; simpler; no extra subprocess.
- **Q:** What unit tests to add? **A:** [auto-pick] `test-resolve-task-path.py` for the compat fallback. **Why:** Pure in-memory + tempfile; validates the shim that all SKILL.md changes depend on.
