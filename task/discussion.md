# Discussion: Replace uv-run-project with direct venv Python in SKILL.md invocations

```yaml
task: Replace uv-run-project with direct venv Python in SKILL.md invocations
slug: skills-direct-venv-invocation
status: discussing
parent: main
```

## Problem

Every SKILL.md bash block that invokes a mill Python script or helper currently uses `uv run --project "${CLAUDE_PLUGIN_ROOT}"` to activate the plugin venv and run the script. This adds uv's project-resolution and venv-check overhead to every single mill CLI call made by an agent. Since agents invoke mill scripts many times per task (spawn, review, implement, cleanup, etc.) this overhead compounds.

Commit 3c9f955 already replaced `uv run --project` with `uv run --active` in the generated `.millhouse/*.ps1` shortcut wrappers. The SKILL.md bash blocks were not updated. This task makes the same change for SKILL.md invocations, using direct venv Python (`"${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe"`) rather than `uv run --active`, because the Bash subshell in Claude Code's Bash tool does not have the mill venv activated.

## Scope

**In:**
- All `uv run --project "${CLAUDE_PLUGIN_ROOT}"` invocations in `plugins/mill/skills/*/SKILL.md` files — both script calls and `python -c "..."` inline forms.
- mill-go's `PLUGIN_ROOT` fallback block — the fallback itself keeps `uv run --project`; the comment is updated to explain why.
- `CLAUDE.md` at the repo root — update the "Mill scripts are invoked via `uv run`" paragraph to document the new pattern.

**Out:**
- Source-tree forms (`uv run --project plugins/mill ...`) in mill-add and mill-setup SKILL.md — these are the documented exception per CLAUDE.md; they stay as `uv run --project`.
- mill-setup's bootstrap-phase invocations (`uv run --project plugins/mill ...`) — same reason.
- Any `.py` script files — no changes to the scripts themselves.
- Unit and integration tests — they run via pytest or explicit uv invocations and are unaffected.
- Codeguide plugin SKILL.md files — no `uv run --project` in those files.

## Decisions

### New invocation form: direct venv Python binary

- **Decision:** Replace `uv run --project "${CLAUDE_PLUGIN_ROOT}" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-X.py"` with `PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-X.py"`.
- **Rationale:** The venv is guaranteed to exist in the plugin cache. Invoking the Python binary directly avoids uv's project-resolution, venv-presence-check, and subprocess-wrap overhead on every call.
- **Rejected:** `uv run --active` — requires the mill venv to be activated in the Bash subshell. The Bash tool in Claude Code has `VIRTUAL_ENV=C:\Program Files\Python313` set (a different Python), and mill-setup Phase 4.8 only activates for PowerShell (`$PROFILE`), not Bash.
- **Rejected:** `uv run --python <venv-path>` — still invokes uv; only partially eliminates overhead.

### Always prefix PYTHONPATH

- **Decision:** Every invocation gets an explicit `PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts"` prefix, including script calls that previously omitted it.
- **Rationale:** CLAUDE.md documents that the global Windows user env var for PYTHONPATH "may not be inherited" in Bash subshells. The inline `python -c "..."` calls already used the prefix. Applying it universally is consistent and eliminates intermittent `ModuleNotFoundError` for the 18 scripts that don't self-add their directory to `sys.path`.
- **Rejected:** Relying on the inherited global PYTHONPATH — too fragile; observed to fail in VS Code's integrated terminal Bash subshells on Windows.

### Windows-only venv path

- **Decision:** Use `.venv/Scripts/python.exe` (Windows path convention). No cross-platform OS detection.
- **Rationale:** All mill operators run Windows 11. Adding `if [ ! -f "$MILL_PYTHON" ]; then ...` boilerplate to every skill for a hypothetical Linux/Mac operator violates YAGNI.
- **Rejected:** Cross-platform wrapper with OS detection — unnecessary complexity.

### Source-tree forms and fallbacks stay as `uv run --project`

- **Decision:** Leave all `uv run --project plugins/mill ...` forms unchanged. Leave mill-go's `PLUGIN_ROOT` fallback using `uv run --project` (add a comment explaining why).
- **Rationale:** Source-tree paths are the documented exception in CLAUDE.md. The fallback fires when `CLAUDE_PLUGIN_ROOT` is unset, which only happens in developer scenarios where the plugin venv may not exist yet — `uv run` handles venv creation on demand.
- **Rejected:** Updating the fallback too — would fail silently when the source-tree venv doesn't exist.

### Update CLAUDE.md

- **Decision:** Update the "Mill scripts are invoked via `uv run`, not `python`" paragraph in CLAUDE.md to document the new `"${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe"` pattern.
- **Rationale:** CLAUDE.md is loaded on every session start. If it still describes `uv run --project` as "the pattern", agents will revert to the old form.
- **Rejected:** Leaving CLAUDE.md unchanged — creates documented pattern contradicting actual practice.

## Technical context

**Invocation patterns to replace (cache form only):**

```bash
# Script call — old
uv run --project "${CLAUDE_PLUGIN_ROOT}" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-X.py" [args]

# Script call — new
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-X.py" [args]

# Inline python — old
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" uv run --project "${CLAUDE_PLUGIN_ROOT}" python -c "..."

# Inline python — new
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe" -c "..."

# Inline python without PYTHONPATH prefix — old (some skills omit it)
uv run --project "$CLAUDE_PLUGIN_ROOT" python -c "..."

# Same — new (add PYTHONPATH prefix)
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe" -c "..."
```

**Variable naming in SKILL.md files:**
- Most skills use `${CLAUDE_PLUGIN_ROOT}` with double-quotes.
- `mill-go` uses `$PLUGIN_ROOT` (set from `${CLAUDE_PLUGIN_ROOT}` at the top of its Step 0 block). Its fallback stays as `uv run --project`.
- Some older skills use `"$CLAUDE_PLUGIN_ROOT"` without braces — normalise to `"${CLAUDE_PLUGIN_ROOT}"` when touching that line anyway.

**Files with the most changes (by occurrence count):**
- `plugins/mill/skills/mill-go/SKILL.md` — 22 occurrences
- `plugins/mill/skills/mill-setup/SKILL.md` — 17 occurrences (mix of source-tree and cache forms; only cache forms change)
- `plugins/mill/skills/mill-autofix/SKILL.md` — 14 occurrences
- `plugins/mill/skills/mill-add/SKILL.md` — 6 occurrences (some are source-tree forms; skip those)
- 16 other SKILL.md files with 1–5 occurrences each

**Source-tree forms to leave unchanged** (do NOT convert):
```bash
uv run --project plugins/mill plugins/mill/scripts/millpy-X.py ...
PYTHONPATH="plugins/mill/scripts" uv run --project plugins/mill python -c "..."
```

**mill-go PLUGIN_ROOT fallback block (keep `uv run --project`, add comment):**
```bash
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT}"
if [ -z "$PLUGIN_ROOT" ]; then
    PLUGIN_ROOT="$(git rev-parse --show-toplevel)/plugins/mill"
    echo "[mill-go] CLAUDE_PLUGIN_ROOT unset; resolved to: $PLUGIN_ROOT"
fi
# Note: subsequent calls use uv run --project for the fallback path because
# the source-tree venv may not exist yet; uv creates it on demand.
```

**CLAUDE.md paragraph to update:**
```
## Conventions worth carrying (excerpt)
> **Mill scripts are invoked via `uv run`, not `python`.** All SKILL.md examples use
> `uv run --project "${CLAUDE_PLUGIN_ROOT}" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-X.py" [args]`
```

New text should state:
- Cache-path SKILL.md blocks use `PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-X.py"`.
- Inline helpers use `PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe" -c "..."`.
- Source-tree forms (`plugins/mill/...`) still use `uv run --project` — this remains the documented exception.
- The exception caveat about `${CLAUDE_PLUGIN_ROOT}` being empty in some shells is retained.

## Testing

No new logic is being introduced — this is a mechanical text substitution across SKILL.md files and one CLAUDE.md paragraph. There are no unit tests for SKILL.md content.

**Manual verification steps for mill-plan to include in the plan:**
1. After editing, grep for any remaining `uv run --project "${CLAUDE_PLUGIN_ROOT}"` lines in `plugins/mill/skills/*/SKILL.md` — result must be zero (source-tree forms are `plugins/mill`, not `${CLAUDE_PLUGIN_ROOT}`).
2. Grep for `uv run --project plugins/mill` — these should remain; count should match the pre-edit count.
3. Spot-check the CLAUDE.md paragraph to ensure both the new pattern and the source-tree exception are documented.
4. Optionally: run one of the updated SKILL.md invocations in a fresh shell to confirm the direct Python binary resolves and runs correctly.

## Q&A log

- **Q:** What invocation form should replace `uv run --project "${CLAUDE_PLUGIN_ROOT}"`? **A:** [auto-pick] Direct venv Python binary. **Why:** venv exists in plugin cache; avoids all uv overhead; `uv run --active` unavailable because Bash tool doesn't activate the mill venv.
- **Q:** Should PYTHONPATH always be prefixed explicitly? **A:** [auto-pick] Yes, always prefix `PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts"`. **Why:** Bash subshells sometimes don't inherit the Windows user env var; inline python calls already used the prefix; consistent.
- **Q:** Windows-only or cross-platform? **A:** [auto-pick] Windows-only (`.venv/Scripts/python.exe`). **Why:** all operators run Windows 11; cross-platform detection is YAGNI.
- **Q:** How to handle mill-go's source-tree `PLUGIN_ROOT` fallback? **A:** [auto-pick] Keep `uv run --project` for the fallback; add a comment explaining why. **Why:** source-tree venv may not exist; `uv run` creates it on demand.
- **Q:** Should source-tree forms (`uv run --project plugins/mill ...`) be updated? **A:** [auto-pick] No, keep as-is. **Why:** documented exception in CLAUDE.md; changing them adds no practical value and risks breakage when venv doesn't exist.
- **Q:** Should CLAUDE.md be updated? **A:** [auto-pick] Yes. **Why:** CLAUDE.md is loaded on every session start; stale pattern docs cause wrong invocations.
