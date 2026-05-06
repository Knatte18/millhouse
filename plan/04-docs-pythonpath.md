# Batch: PYTHONPATH documentation fix

```yaml
task: 19 (A) — mill-go + scripts infra fixes
batch: PYTHONPATH documentation fix
cards: 2
verify: null
depends-on: []
```

## Batch Scope

This batch fixes two documentation files that overstate the scope of PYTHONPATH inheritance. `CLAUDE.md` claims "CC inherits it automatically — no per-session export needed", which is only true for new sessions opened after mill-setup. `mill-setup SKILL.md` claims the inline prefix is "only required in mill-setup" and "all other skills … need no prefix", which also ignores the same-session case.

Both cards are one batch because they fix the same incorrect claim in two places. No code changes; pure docs.

Batch-local decisions: none beyond Shared Decisions.

## Cards

### Card 6: Fix PYTHONPATH claim in CLAUDE.md

- **Reads:**
  - `CLAUDE.md`
- **Modifies:**
  - `CLAUDE.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In the "Conventions worth carrying" section, find the sentence that begins "PYTHONPATH is set globally as a Windows user environment variable by `mill-setup` Phase 4.7; CC inherits it automatically — no per-session export needed." Replace the entire sentence (from "PYTHONPATH is set globally" through "no per-session export needed.") with:

  "PYTHONPATH is set globally as a Windows user environment variable by `mill-setup` Phase 4.7. This takes effect in **new shell sessions opened after mill-setup completes**. Within the same session, and on some Windows configurations, the Bash tool subshell may not inherit it — prefix inline `uv run python -c` calls with `PYTHONPATH=\"${CLAUDE_PLUGIN_ROOT}/scripts\"` if you see `ModuleNotFoundError`."

  Leave the following sentence ("Exception: `mill-setup` itself is the bootstrapper and uses an inline `PYTHONPATH=\"${CLAUDE_PLUGIN_ROOT}/scripts\"` prefix on each call.") unchanged.

- **Commit:** `docs(CLAUDE.md): correct PYTHONPATH inheritance scope`

### Card 7: Fix PYTHONPATH claim in mill-setup SKILL.md

- **Reads:**
  - `plugins/mill/skills/mill-setup/SKILL.md`
- **Modifies:**
  - `plugins/mill/skills/mill-setup/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In the "## How to invoke the helpers" section, find the sentence "This inline `PYTHONPATH=` prefix is **only** required in mill-setup. All other skills rely on the global Windows user env var set here and need no prefix." Replace it with:

  "This inline `PYTHONPATH=` prefix is required in mill-setup and in any skill invocation within the same CC session where mill-setup ran (before a new shell is opened). Skills running in a new CC session started after mill-setup completes rely on the global Windows user env var set by Phase 4.7 and need no prefix."

- **Commit:** `docs(mill-setup): clarify PYTHONPATH prefix scope to same-session vs new-session`

## Batch Tests

`verify: null` — docs-only changes with no runnable surface.
