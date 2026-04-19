# Starter prompt for new CC session in mill-v2 hub/

Copy-paste this into a fresh Claude Code session opened in `C:\Code\millhouse\hub\`.

---

You're starting fresh in `C:\Code\millhouse\hub\` — the home for mill-v2, a disciplined rewrite of the mill plugin. Old version is at `C:\Code\millhouse-legacy\` for reference only.

## Load full spec context upfront

Before any exploration, read the entire `specs/` tree (except `specs/_starter/`). It is ~35k tokens total — trivial for your context window, and essential for every decision that follows. The specs were written by a prior Opus instance with deep analysis; defer to them, don't re-derive.

Read in this order:

1. **Principles:** `specs/00-overview.md`
2. **Roadmap index (status):** `specs/roadmap/README.md` — find the current position in the status table, then open the matching `specs/roadmap/M*.md`
3. **Layer specs (HOW for the current layer):** `specs/layer-01-bootstrap.md`, `specs/layer-02-review.md`, `specs/layer-03-orchestration.md`, `specs/layer-04-extras.md`
4. **Reference:** `specs/ref-code-scope.md`, `specs/ref-formats.md`, `specs/ref-workflows.md`, `specs/ref-dev-loop.md`, `specs/ref-v1-reuse.md`, `specs/ref-legacy-index.md`

**Do NOT** scan or grep `C:\Code\millhouse-legacy\` broadly. Use `ref-legacy-index.md` for exact file paths. Touch legacy only via the index.

**Do NOT** read files inside `specs/_starter/` — those are per-session hand-off prompts and result reports, not canonical spec content.

## Hard discipline rules (from 00-overview.md)

- Max 300 LOC per file. If you're about to generate >100 lines for one file, stop and ask for a "minimum version".
- Flat files under `plugins/mill/scripts/`. No `__init__.py`, no subpackages, no `Protocol`, no ABC.
- No pytest. Integration tests are PowerShell under `plugins/mill/integration_tests/`.
- No inline prompt strings — prompts live in `plugins/mill/templates/` and are rendered via `_render.py`.
- Total Python LOC budget for v2.0: **< 1500**.
- Lift v1 code before writing new. Follow `ref-v1-reuse.md` + `ref-legacy-index.md` — strip `millpy.*` imports, replace v1 logging with `print(..., file=sys.stderr)`.
- If you want to exceed spec scope: propose a spec change first, then code. Never silently drift.

## Finding your current position

`specs/roadmap/README.md` has a status table showing which layer is in progress and which `M*.md` file owns the sub-milestones. Open that file to see which exit criteria are ticked and which are next. Then open the matching `specs/layer-0N-*.md` for the full detail on the milestone you're about to work on.

Rule of thumb: **roadmap = WHAT and WHEN; layer spec = HOW.**

## First reply

Confirm you've read the specs above, summarise the current position (which layer, which M, which exit criteria are open), flag anything in the specs that looks stale or contradictory, then ask before writing any code.
