# mill-spawn (script)

```yaml
type: script
layer: 03
v1_ref: plugins/mill/scripts/spawn_task.py + skills/mill-spawn/
status: done — merged to main 2026-04-22 (branch impl/02-mill-spawn)
note: "No skill wrapper. All logic is mechanical and lives in mill-spawn.py."
```

**Implementation notes:** `mill-spawn.py` implemented with flags `--slug`, `--dry-run`. Supporting modules: `_tasks_md.py` (Home.md parse/claim), `_status.py` (renderer), `_worktree.py` (git worktree + .millhouse copy), plus `_wiki.sync_pull()`. Per-worktree VS Code title-bar colour via the existing `_vscode.py` + an 8-colour palette local to `mill-spawn.py` (green reserved for the hub). Config lives under `spawn:` in `wiki/config.yaml` (`branch_prefix`, `worktrees_dir` with `<CONTAINER_PATH>`/`<REPO>` tokens); developer-specific `branch_prefix` override goes in `.millhouse/config.local.yaml`. Tested by `integration_tests/test-spawn.py` (end-to-end against an isolated hub+bare-wiki pair in `.millhouse/scratch/`) and `integration_tests/test-spawn-units.py` (pure-function coverage of `pick_task` + `pick_worktree_color`). Empty Home.md path verified against the live wiki (exits 0 with a "no pickable tasks" message).

## Purpose

Claim one task from the wiki's Home.md, create a git worktree for it, and set up the per-task state under `wiki/active/<slug>/`.

## Decisions

- **Claim flow**: Beholder `[s]` marker fra v1.
  - Hvis minst én `[s]` finnes: claim første.
  - Hvis ingen `[s]`: list nummererte valgbare tasks, les tall fra stdin, marker valgt som claimed.
- **Worktree**: `git worktree add -b <prefix>/<slug> <worktrees-dir>/<slug>`
  - `prefix` fra config. Default `~` betyr: ingen prefix (branch = `<slug>`).
  - Typisk verdi: `hanf`.
- **`.active/` junction**: Opprettes i ny worktree, peker til `wiki/active/<slug>/`.
- **Wiki junction**: Allerede etablert av `mill-setup`. Følger med via copy-on-spawn (se under).
- **Junction-lokasjon**: Både `.active` og wiki-junction skal være **konfigurerbar** — enten cwd-root eller under `.millhouse/`. Les fra wiki-config. (Åpent design-punkt, se under.)
- **Copy-on-spawn**: Kopier `.millhouse/` fra parent worktree til ny worktree, men dropp `scratch/`. (v1 droppet også `task/` og `children/` — disse finnes ikke lenger i v2.)
- **`status.md`**: Opprett i `wiki/active/<slug>/status.md` ved spawn. Format følger v1 (YAML-blokk med `phase:`, `task:`, timeline). Discussion.md er ikke tilstrekkelig — status.md er eneste autoritative state-fil.

## Flow

1. `wiki.sync_pull(cfg)` — hent nyeste wiki.
2. Acquire wiki-lock.
3. Les `Home.md`. Finn `[s]`-task ELLER prompt bruker med nummerert picker.
4. Derive slug fra tittel.
5. Marker task `[active]` i Home.md; commit+push.
6. Release wiki-lock.
7. `git worktree add -b <branch> <worktrees-dir>/<slug>`.
8. Copy-on-spawn: kopier `.millhouse/` (minus `scratch/`) til ny worktree.
9. Opprett `.active/` junction i ny worktree → `wiki/active/<slug>/`.
10. Render `templates/status-discussing.md` til `wiki/active/<slug>/status.md`.
11. Commit+push til wiki: `active/<slug>/status.md`.
12. Regenerate sidebar.
13. Print worktree-path og branch.

## Backend

**New:**
- `mill-spawn.py` — CLI entrypoint.
- `_worktree.py` — `create()`, `remove()`, `copy_millhouse()`. Gjenbruker mye fra v1 `worktree.py`.
- `_status.py` — render + read status.md. Rendre initial template, senere phase-transitions.
- `_tasks_md.py` — parse/render Home.md, finn `[s]`/unmarked, skriv `[active]`.

**Reused / already exists:**
- `_junction.py` — create junction.
- `_wiki.py` — sync_pull, write_commit_push, lock.
- `_sidebar.py` — regenerate.
- `_render.py` — template substitusjon.

## Templates

- `templates/status-discussing.md` — initial `status.md` ved spawn. Tokens: `<TASK_TITLE>`, `<TASK_DESCRIPTION>`, `<TIMESTAMP>`. (Eksisterer i v1 og kan kopieres inn direkte.)

## Out of scope vs v1

- Ingen `.millhouse/children/` registry — erstattet av wiki's `active/<slug>/`.
- Ingen copy av `task/` eller `children/` — de finnes ikke.
- Ingen v3 DAG-specific state — plan er linear (avgjort).

## Open design points

- **Junction-lokasjon som config**: skal leses fra wiki (`config.yaml`). `mill-setup` leser config fra wiki FØR junctions opprettes. Krever at selve wiki-lokasjonen er bootstrappet fra `config.local.yaml` (wiki-url → real path). Avklares i neste runde.
- **Invariant**: `.active/` og wiki-junction skal **aldri brukes som path** av andre scripts — alltid resolve til faktisk lokasjon (wiki-repo på disk). Må dokumenteres i skill-guide eller CLAUDE.md.
