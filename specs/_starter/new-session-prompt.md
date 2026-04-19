# Starter prompt for new CC session in mill-v2 hub/

Copy-paste this into a fresh Claude Code session opened in `C:\Code\millhouse\hub\`.

---

You're starting fresh in `C:\Code\millhouse\hub\` — the home for mill-v2, a disciplined rewrite of the mill plugin. Old version is at `C:\Code\millhouse-legacy\` for reference only.

Before writing any code, read these in order:

1. `specs/00-overview.md` — principles and constraints
2. `specs/01-roadmap.md` — build order, M0 → M4.6 with stop gates
3. `specs/ref-v1-reuse.md` — what to lift from legacy, what to rewrite
4. `specs/ref-legacy-index.md` — file-level navigation into legacy (do NOT scan or grep the legacy repo broadly — use the index)

Hard discipline rules:

- Max 300 LOC per file. Over that, stop and show me the structure.
- No package structure. Flat files. No `__init__.py`, no Protocol, no ABC.
- No pytest. Integration tests are PowerShell only.
- No inline prompt strings — prompts live in `plugins/mill/templates/`.
- Total Python LOC budget for v2.0: < 1500.
- Lift v1 code before writing new. Use `ref-v1-reuse.md` and `ref-legacy-index.md`.
- If you want to exceed spec scope: propose a spec change first, don't just write the code.

Start with M0 from the roadmap (decision gates), then M1.1.

First reply: confirm you've read the 4 specs above, list any M0 decisions you think need clarification, then ask before proceeding.
