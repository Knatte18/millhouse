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
- mill-go's `PLUGIN_ROOT` body calls (22 occurrences) — converted to use `MILL_PYTHON` variable; Step 0 block updated to set `MILL_PYTHON` after the fallback check; fallback note added.
- `CLAUDE.md` at the repo root — update the "Mill scripts are invoked via `uv run`" paragraph to document the new pattern.
- mill-setup SKILL.md "How to invoke the helpers" prose section (lines ~57–69) — the "unique inline-prefix form" framing is outdated after conversion; update to reflect that all skills now use direct Python with an explicit PYTHONPATH prefix.

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

### Source-tree forms stay as `uv run --project`; mill-go body calls are converted via `MILL_PYTHON`

- **Decision:** Leave all `uv run --project plugins/mill ...` forms in mill-add and mill-setup unchanged (source-tree exception). Convert mill-go's 22 body calls to use a `MILL_PYTHON` variable that is set after the fallback check. Add a note in the fallback block that the source-tree venv must already exist.
- **Rationale:** mill-go uses `$PLUGIN_ROOT` (not `${CLAUDE_PLUGIN_ROOT}`) for all its calls. Converting those calls requires deriving the Python binary from `$PLUGIN_ROOT` too. The fallback fires only when `CLAUDE_PLUGIN_ROOT` is unset — a dev-only scenario. In that case, the source-tree venv is expected to exist (created by any prior `uv run --project plugins/mill` invocation). Leaving mill-go's 22 body calls unconverted would forfeit the largest performance gain (mill-go has the most invocations of any skill).
- **Rejected:** Leaving mill-go entirely as `uv run --project` — forfeits the bulk of the performance benefit; mill-go is the most frequently invoked orchestration skill.
- **Rejected:** A runtime existence check (`if [ ! -f "$MILL_PYTHON" ]`) that falls back to `uv run` — adds branching complexity to every call site; the note in the fallback block is sufficient for the dev edge case.

The Step 0 block in mill-go SKILL.md becomes:
```bash
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT}"
if [ -z "$PLUGIN_ROOT" ]; then
    PLUGIN_ROOT="$(git rev-parse --show-toplevel)/plugins/mill"
    echo "[mill-go] CLAUDE_PLUGIN_ROOT unset; resolved to: $PLUGIN_ROOT"
    echo "[mill-go] NOTE: source-tree venv must exist at $PLUGIN_ROOT/.venv — run 'uv sync --project $PLUGIN_ROOT' if not."
fi
MILL_PYTHON="${PLUGIN_ROOT}/.venv/Scripts/python.exe"
```

All 22 body calls change from `uv run --project "$PLUGIN_ROOT" "$PLUGIN_ROOT/scripts/..."` to `PYTHONPATH="${PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${PLUGIN_ROOT}/scripts/..."`.

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
1. After editing, grep for any remaining `uv run --project "${CLAUDE_PLUGIN_ROOT}"` (or `"$CLAUDE_PLUGIN_ROOT"`) in `plugins/mill/skills/*/SKILL.md` — result must be zero.
2. Grep for `uv run --project.*PLUGIN_ROOT` in `plugins/mill/skills/mill-go/SKILL.md` — result must be zero (all 22 body calls converted).
3. Grep for `uv run --project plugins/mill` — these should remain (source-tree exception forms in mill-add, mill-setup); count should match the pre-edit count.
4. Spot-check the CLAUDE.md paragraph to ensure both the new pattern and the source-tree exception are documented.
5. Spot-check mill-setup SKILL.md lines ~57–69 to confirm "unique inline-prefix form" prose is updated.
6. Optionally: run one of the updated SKILL.md invocations in a fresh shell to confirm the direct Python binary resolves and runs correctly.

## Q&A log

- **Q:** What invocation form should replace `uv run --project "${CLAUDE_PLUGIN_ROOT}"`? **A:** [auto-pick] Direct venv Python binary. **Why:** venv exists in plugin cache; avoids all uv overhead; `uv run --active` unavailable because Bash tool doesn't activate the mill venv.
- **Q:** Should PYTHONPATH always be prefixed explicitly? **A:** [auto-pick] Yes, always prefix `PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts"`. **Why:** Bash subshells sometimes don't inherit the Windows user env var; inline python calls already used the prefix; consistent.
- **Q:** Windows-only or cross-platform? **A:** [auto-pick] Windows-only (`.venv/Scripts/python.exe`). **Why:** all operators run Windows 11; cross-platform detection is YAGNI.
- **Q:** How to handle mill-go's `PLUGIN_ROOT` body calls and fallback? **A:** [auto-pick, revised after review r1] Convert the 22 body calls via a `MILL_PYTHON` variable set in Step 0; add fallback note that source-tree venv must exist. **Why:** leaving body calls unconverted forfeits the largest performance gain; the fallback is dev-only and source-tree venv is expected to already exist.
- **Q:** Should source-tree forms (`uv run --project plugins/mill ...`) be updated? **A:** [auto-pick] No, keep as-is. **Why:** documented exception in CLAUDE.md; changing them adds no practical value and risks breakage when venv doesn't exist.
- **Q:** Should CLAUDE.md be updated? **A:** [auto-pick] Yes. **Why:** CLAUDE.md is loaded on every session start; stale pattern docs cause wrong invocations.
