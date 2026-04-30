# Batch: skills-sweep

```yaml
task: 18 — par-E — Migrate Python invocation to `uv run`
batch: skills-sweep
cards: 11
verify: null
depends-on: [foundation]
```

## Batch Scope

Migrate every non-mill-setup SKILL.md from `python` to `uv run --project "${CLAUDE_PLUGIN_ROOT}" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-X.py"` (and `python -c "..."` to `uv run --project "${CLAUDE_PLUGIN_ROOT}" python -c "..."`), normalise all script paths to `${CLAUDE_PLUGIN_ROOT}/scripts/...` (no repo-relative `plugins/mill/scripts/...`), and audit helper-call shapes in prose against actual function signatures in `plugins/mill/scripts/_*.py` per issue #70.

Card 8 covers the 12 simple skills with a single uniform `Run it` block — they all share an identical mechanical transformation. Cards 9–17 cover the 9 complex skills individually because each has skill-specific details (multiple invocations, repo-relative paths, broken module references, PYTHONPATH hacks). Card 18 is the verification sweep — grep across all SKILL.md files to confirm no residual `python ` invocations or repo-relative paths or wrong helper shapes survive. `verify: null` because every change is documentation; correctness is checked structurally via the grep sweep in card 18.

## Cards

### Card 8: Migrate 12 simple skills uniformly

- **Reads:**
  - `plugins/mill/skills/mill-claim/SKILL.md`
  - `plugins/mill/skills/mill-inspect/SKILL.md`
  - `plugins/mill/skills/mill-abandon/SKILL.md`
  - `plugins/mill/skills/mill-fetch-issues/SKILL.md`
  - `plugins/mill/skills/mill-list/SKILL.md`
  - `plugins/mill/skills/mill-status/SKILL.md`
  - `plugins/mill/skills/mill-color/SKILL.md`
  - `plugins/mill/skills/mill-worktree/SKILL.md`
  - `plugins/mill/skills/mill-vscode/SKILL.md`
  - `plugins/mill/skills/mill-terminal/SKILL.md`
  - `plugins/mill/skills/mill-spawn/SKILL.md`
  - `plugins/mill/skills/mill-cleanup/SKILL.md`
  - `discussion.md`
- **Modifies:**
  - `plugins/mill/skills/mill-claim/SKILL.md`
  - `plugins/mill/skills/mill-inspect/SKILL.md`
  - `plugins/mill/skills/mill-abandon/SKILL.md`
  - `plugins/mill/skills/mill-fetch-issues/SKILL.md`
  - `plugins/mill/skills/mill-list/SKILL.md`
  - `plugins/mill/skills/mill-status/SKILL.md`
  - `plugins/mill/skills/mill-color/SKILL.md`
  - `plugins/mill/skills/mill-worktree/SKILL.md`
  - `plugins/mill/skills/mill-vscode/SKILL.md`
  - `plugins/mill/skills/mill-terminal/SKILL.md`
  - `plugins/mill/skills/mill-spawn/SKILL.md`
  - `plugins/mill/skills/mill-cleanup/SKILL.md`
- **Creates:** none
- **Requirements:** Each of these 12 skills has a `## Run it` (or similarly-named) section containing exactly one `python ${CLAUDE_PLUGIN_ROOT}/scripts/millpy-X.py [args]` invocation in a fenced bash block. Replace each invocation with `uv run --project "${CLAUDE_PLUGIN_ROOT}" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-X.py" [args]` — preserve all argument flags exactly. No other text changes per skill in this card. After edits, grep verification: `Grep -P 'python\s+\$\{CLAUDE_PLUGIN_ROOT\}'` across the 12 files returns zero matches.
- **Commit:** `mill-skills(simple): migrate to uv run`

### Card 9: Migrate `mill-go/SKILL.md` to uv run + helper-shape audit

- **Reads:**
  - `plugins/mill/skills/mill-go/SKILL.md`
  - `plugins/mill/scripts/_status.py`
  - `plugins/mill/scripts/_wiki.py`
  - `plugins/mill/scripts/_tasks_md.py`
  - `plugins/mill/scripts/_notify.py`
  - `discussion.md`
- **Modifies:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Requirements:** (1) Replace `python plugins/mill/scripts/millpy-review-code.py …` (line ~96) with `uv run --project "${CLAUDE_PLUGIN_ROOT}" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-review-code.py" …`. Apply the same transformation to every other invocation in the file (line ~131 etc.). (2) Audit helper-call examples in prose against the real function signatures: `_status.append_phase(status_path, phase, timestamp)`, `_status.set_batch_field(...)`, `_wiki.write_commit_push(wiki_path, relative_paths, commit_msg)` (3-arg), `_wiki.acquire_lock(wiki_path, slug, timeout_seconds=30)`, `_wiki.release_lock(wiki_path)`, `_tasks_md.set_phase(home_path, slug, phase)`, `_notify.notify(...)`. Cross-check any helper-call example in mill-go SKILL.md prose against the actual signatures in `plugins/mill/scripts/_*.py`; fix any mismatches. (3) Replace any `plugins/mill/scripts/...` repo-relative path in invocation lines with `${CLAUDE_PLUGIN_ROOT}/scripts/...`. Prose mentions ("`_wiki.write_commit_push` is the canonical writer") stay as-is.
- **Commit:** `mill-go(skill): migrate to uv run + helper signature audit`

### Card 10: Migrate `mill-plan/SKILL.md` to uv run + helper-shape audit

- **Reads:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
  - `plugins/mill/scripts/_wiki.py`
  - `plugins/mill/scripts/_status.py`
  - `discussion.md`
- **Modifies:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Requirements:** (1) Replace `python plugins/mill/scripts/millpy-review-plan.py` (line ~98) with `uv run --project "${CLAUDE_PLUGIN_ROOT}" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-review-plan.py"`. Apply the same to every other invocation. (2) Verify `_wiki.write_commit_push(wiki_path, [f"active/{slug}/plan/"], …)` (line ~93) — note this is a 3-arg call (correct). Verify `_status.append_phase(...)` calls. Audit any other helper-call examples. (3) Replace repo-relative paths with `${CLAUDE_PLUGIN_ROOT}/scripts/...`.
- **Commit:** `mill-plan(skill): migrate to uv run + helper signature audit`

### Card 11: Migrate `mill-start/SKILL.md` to uv run + helper-shape audit

- **Reads:**
  - `plugins/mill/skills/mill-start/SKILL.md`
  - `plugins/mill/scripts/_status.py`
  - `plugins/mill/scripts/_wiki.py`
  - `discussion.md`
- **Modifies:**
  - `plugins/mill/skills/mill-start/SKILL.md`
- **Creates:** none
- **Requirements:** (1) Replace `python plugins/mill/scripts/millpy-review-discussion.py` (line ~73) with `uv run --project "${CLAUDE_PLUGIN_ROOT}" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-review-discussion.py"`. (2) Verify `_status.append_phase(status_path, "discussed", timestamp)` matches the real signature. Audit other helper-call examples. (3) Replace repo-relative paths.
- **Commit:** `mill-start(skill): migrate to uv run + helper signature audit`

### Card 12: Migrate `mill-add/SKILL.md` — remove PYTHONPATH hack + uv run

- **Reads:**
  - `plugins/mill/skills/mill-add/SKILL.md`
  - `discussion.md`
- **Modifies:**
  - `plugins/mill/skills/mill-add/SKILL.md`
- **Creates:** none
- **Requirements:** (1) Delete the `$env:PYTHONPATH = (Resolve-Path 'plugins/mill/scripts').Path` line (~line 89). The global PYTHONPATH env var (set by mill-setup) covers it. (2) Replace every `python plugins/mill/scripts/millpy-add.py …` invocation (lines ~90, ~106, ~132, ~161) with `uv run --project "${CLAUDE_PLUGIN_ROOT}" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-add.py" …` — preserve PowerShell line continuations (backtick-newline) and all flags exactly. (3) Audit helper-call examples (none expected; mill-add is a thin CLI wrapper) — but verify no examples remain that reference outdated signatures.
- **Commit:** `mill-add(skill): migrate to uv run, remove PYTHONPATH hack`

### Card 13: Migrate `mill-ghissues-to-tasks/SKILL.md` to uv run

- **Reads:**
  - `plugins/mill/skills/mill-ghissues-to-tasks/SKILL.md`
  - `plugins/mill/scripts/_wiki.py`
  - `plugins/mill/scripts/_paths.py`
  - `discussion.md`
- **Modifies:**
  - `plugins/mill/skills/mill-ghissues-to-tasks/SKILL.md`
- **Creates:** none
- **Requirements:** (1) Replace every `PYTHONPATH=$CLAUDE_PLUGIN_ROOT/scripts python -c "..."` (lines ~25, ~39, ~125) with `uv run --project "${CLAUDE_PLUGIN_ROOT}" python -c "..."` — drop the inline `PYTHONPATH=` because the global env var handles it. (2) Audit helper-call examples: `_wiki.write_commit_push` (3-arg), `_paths.resolve_*` calls. (3) No repo-relative paths to fix in this file (it already uses `$CLAUDE_PLUGIN_ROOT`).
- **Commit:** `mill-ghissues-to-tasks(skill): migrate to uv run`

### Card 14: Migrate `mill-groom/SKILL.md` to uv run + helper-shape audit

- **Reads:**
  - `plugins/mill/skills/mill-groom/SKILL.md`
  - `plugins/mill/scripts/_wiki.py`
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/scripts/_tasks_md.py`
  - `discussion.md`
- **Modifies:**
  - `plugins/mill/skills/mill-groom/SKILL.md`
- **Creates:** none
- **Requirements:** (1) Replace every `PYTHONPATH=$CLAUDE_PLUGIN_ROOT/scripts python -c "..."` (lines ~21, ~28, ~49, ~195, ~206) with `uv run --project "${CLAUDE_PLUGIN_ROOT}" python -c "..."`. (2) Audit `_wiki.write_commit_push(wiki, relative_paths, commit_msg)` signature in the prose example at line ~199 (verify it's 3-arg) and any other helper-call examples. Fix any mismatches.
- **Commit:** `mill-groom(skill): migrate to uv run + helper signature audit`

### Card 15: Fix `mill-resume/SKILL.md` — remove broken module ref + uv run

- **Reads:**
  - `plugins/mill/skills/mill-resume/SKILL.md`
  - `plugins/mill/scripts/_sidebar.py`
  - `discussion.md`
- **Modifies:**
  - `plugins/mill/skills/mill-resume/SKILL.md`
- **Creates:** none
- **Requirements:** (1) Replace the broken `PYTHONPATH=<scripts-dir> python -m millpy.entrypoints.regenerate_sidebar` (line ~147) with `uv run --project "${CLAUDE_PLUGIN_ROOT}" python -c "from pathlib import Path; import _sidebar; _sidebar.regenerate(Path(r'<wiki-dir>').resolve())"`. The `millpy.entrypoints` module does not exist in the codebase — confirmed by grep. The replacement uses `_sidebar.regenerate` directly (the actual API). (2) Migrate any other invocations in the file to `uv run --project "${CLAUDE_PLUGIN_ROOT}" …`. (3) Audit helper-call examples; verify `_sidebar.regenerate(wiki_path)` is the real signature.
- **Commit:** `mill-resume(skill): fix broken module ref + migrate to uv run`

### Card 16: Migrate `mill-skills-index/SKILL.md` to uv run

- **Reads:**
  - `plugins/mill/skills/mill-skills-index/SKILL.md`
  - `discussion.md`
- **Modifies:**
  - `plugins/mill/skills/mill-skills-index/SKILL.md`
- **Creates:** none
- **Requirements:** Replace `python plugins/mill/scripts/millpy-skills-index.py` (line ~23) with `uv run --project "${CLAUDE_PLUGIN_ROOT}" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-skills-index.py"`. Replace any other repo-relative path with `${CLAUDE_PLUGIN_ROOT}/...`.
- **Commit:** `mill-skills-index(skill): migrate to uv run`

### Card 17: Migrate `mill-skills-from-scripts/SKILL.md` to uv run

- **Reads:**
  - `plugins/mill/skills/mill-skills-from-scripts/SKILL.md`
  - `discussion.md`
- **Modifies:**
  - `plugins/mill/skills/mill-skills-from-scripts/SKILL.md`
- **Creates:** none
- **Requirements:** Replace `python ${CLAUDE_PLUGIN_ROOT}/scripts/millpy-<X>.py …` (line ~51) with `uv run --project "${CLAUDE_PLUGIN_ROOT}" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-<X>.py" …`. Same for `python ${CLAUDE_PLUGIN_ROOT}/scripts/millpy-skills-index.py` (line ~61). The `<X>` is a meta-token in the skill prose (not a real shell variable) — preserve it.
- **Commit:** `mill-skills-from-scripts(skill): migrate to uv run`

### Card 18: API audit verification sweep across all SKILL.md

- **Reads:**
  - `plugins/mill/skills/*/SKILL.md` (all)
  - `plugins/mill/scripts/_config.py`
  - `plugins/mill/scripts/_wiki.py`
  - `plugins/mill/scripts/_status.py`
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/scripts/_tasks_md.py`
  - `plugins/mill/scripts/_notify.py`
  - `plugins/mill/scripts/_sidebar.py`
  - `plugins/mill/scripts/_active.py`
  - `discussion.md`
- **Modifies:** any `plugins/mill/skills/*/SKILL.md` that fails one of the verification greps below
- **Creates:** none
- **Requirements:** Run grep verification across `plugins/mill/skills/*/SKILL.md` to confirm the migration is complete and consistent. For each grep that returns hits, fix the file in place; iterate until all greps return zero hits in invocation contexts (commentary mentions of `_wiki` etc. are not invocations and stay).
  - Grep `^\s*python\s+\$\{?CLAUDE_PLUGIN_ROOT\}?` → must be zero. Indicates a missed `python` → `uv run` substitution.
  - Grep `\bPYTHONPATH=` → must be zero outside mill-setup/SKILL.md (mill-setup is the only skill that uses inline PYTHONPATH).
  - Grep `python\s+plugins/mill/scripts/` → must be zero. Indicates a missed repo-relative path.
  - Grep `python\s+-m\s+millpy\.` → must be zero. The `millpy` package does not exist; mill-resume's broken reference is the only one and is fixed in card 15.
  - Grep `_config\.load\(` → if any hits, fix to `_config.load_config(wiki_path, git_root)`.
  - Grep `_wiki\.write_commit_push\(` → for each hit, verify the call has 3 args (`wiki_path, relative_paths, commit_msg`); fix 2-arg shapes.
  - Grep `_status\.set_phase\(` → if any hits, this is wrong — there is no `_status.set_phase`; the real API is `_status.append_phase(status_path, phase, timestamp)`. Fix.
  Document the verification result inline in this card's commit message (e.g., "audit pass: 0 residual python invocations, 0 wrong-shape helper calls").
- **Commit:** `mill-skills(audit): verify uv migration + helper signatures across all SKILL.md`

## Batch Tests

`verify: null` — these are SKILL.md (documentation) changes; no runnable surface in the batch itself. Card 18 is the structural test: grep-based verification across the entire SKILL.md surface ensures no regressions slip through. Semantic correctness is verified end-to-end when an operator runs each affected skill in a real session post-merge — the changes are pure invocation rewrites and helper-call audits, so any regression would surface immediately on first invocation. The 22 SKILL.md files affected by this batch are listed in the cards above; card 18's grep covers the full skill set (40+ files) including the workflow/conversation/etc. style files that don't have invocations but might contain helper-call examples in prose.
