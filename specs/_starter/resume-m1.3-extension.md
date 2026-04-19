# Resume prompt — M1.3 extension (and onward through M1.5)

Written by an Opus 4.7 session on 2026-04-19 after the original M1.3 landed (`e444de8`) but before the format-discussion extensions. Morning-session continues from here.

## Where you are

Current commit on `main` and `origin/main`: `8d6dfe3` "Spec: lock in Home.md format, _Sidebar.md, flat proposals, mill-spawn UX".

Wiki (`origin/master` on `millhouse.wiki.git`): Home.md is **already manually edited** to the new format during the previous session. It contains one real task (`skills-index-rebuild`) with a proposal file (`proposal-skills-index-rebuild.md`) and a `_Sidebar.md`. The code in `plugins/mill/scripts/mill-add.py` was written for the **old** format (`## <slug>` heading) — it has not been rewritten to match the wiki.

So: wiki is ahead of code. Your job is to catch the code up, verify the whole loop, then proceed to M1.4 and M1.5.

## What's already done

- [x] **M1.1** — `_subprocess_util.py`, `_junction.py`, `_wiki.py`, `_render.py`. Commit `72af20b`.
- [x] **M1.2** — `mill-setup` skill + templates (`Home.md`, `config.local.yaml`, `vscode-settings.json`) + `_vscode.py` helper. Commits `d81d74c` (initial), `06b1497` (helper refactor).
- [x] **M1.3 initial** — `mill-add.py` (old `## <slug>` format). Commit `e444de8`. Works end-to-end but uses the format we have since retired.
- [x] **Design spec for everything below** — all locked in commit `8d6dfe3`. Read the updated spec files before writing code (see "Key reading" below).

## What's left in M1

- [ ] **M1.3 extension** — bring code up to the new spec:
  1. Write `plugins/mill/scripts/_sidebar.py` (~60 LOC) — `parse_home_tasks(home_path) -> list[dict]`, `render_sidebar(tasks) -> str`, `regenerate(wiki_path) -> None`. Navigation section first, Tasks section after. Tasks linked when a matching `proposal-<slug>.md` exists at wiki root; plain text otherwise.
  2. Rewrite `plugins/mill/scripts/mill-add.py`:
     - New CLI: `<slug> --title "..." [--summary "..."] [--proposal-body "..."]`
     - Heading: `## <Title> [<slug>]` (plain) or `## <Title> [[<slug>]](proposal-<slug>)` (when `--proposal-body` given)
     - When `--proposal-body` given: write `<wiki>/proposal-<slug>.md` with the body content
     - Always: call `_sidebar.regenerate(wiki_path)` after Home.md write
     - Commit Home.md + _Sidebar.md (+ proposal-<slug>.md) in ONE commit under ONE `_wiki.acquire_lock` acquisition
     - Duplicate-slug detection regex: `^##\s+.+?\s+\[\[?([a-z][a-z0-9-]*)\]?\](?:\([^)]+\))?\s*$`
  3. Update `plugins/mill/skills/mill-setup/SKILL.md` — add Phase 6a: "Initialise `_Sidebar.md` via `_sidebar.regenerate()`". Idempotent: regenerator is safe to re-run; it just rewrites the file from current state.
- [ ] **M1.3.5** — new thin skill `plugins/mill/skills/mill-add/SKILL.md`. Takes a user discussion, derives slug/title/summary (and optionally proposal-body if the discussion is substantial, heuristic ~150 words), calls `mill-add.py`. Judgment-heavy; script is mechanical.
- [ ] **M1.4** — `plugins/mill/scripts/mill-list.py` (~30–60 LOC). Parses Home.md for task headings, prints one line per task. Use the same regex as mill-add's duplicate detection. Consider showing whether a task has a proposal (e.g., `[P]` marker) in the output.
- [ ] **M1.5** — `plugins/mill/integration_tests/test-bootstrap.ps1`. Sets up a fake wiki in `$env:TEMP`, runs `mill-add` + `mill-list` against it, asserts outputs. End-to-end verification. Also: verify total Python LOC for Layer 01 is under 450.
- [ ] **Tag `layer-01-done`** once all M1 exit criteria land.

## Key reading before coding

In order:

1. `specs/00-overview.md` — discipline rules (LOC cap, flat files, no abstractions before use).
2. `specs/roadmap/README.md` — current status table.
3. `specs/roadmap/M1-bootstrap.md` — M1.3 "Extension work (not yet done — resume here)" section is the direct task list.
4. `specs/layer-01-bootstrap.md` — full Layer 01 spec including the new mill-add args, `_sidebar.py` API, mill-setup Phase 6a, and mill-add/SKILL.md outline.
5. `specs/ref-formats.md` — Home.md new format (`## Title [[slug]](proposal-slug)`), `_Sidebar.md` shape, flat-namespace rationale ("Why flat namespace for proposals").
6. `specs/ref-v1-reuse.md` — lifting protocol. Most of what you need is already in `plugins/mill/scripts/_*.py` from M1.1.

Do NOT re-read all of `specs/` unless you're a fresh session — if you've already loaded them at session start per `_starter/new-session-prompt.md`, skip to the M1-specific ones.

## Key decisions locked in the previous session (do not re-litigate)

- **Home.md heading format:** `## <Title> [<slug>]` or `## <Title> [[<slug>]](proposal-<slug>)`. Single regex parses both.
- **Proposal file location:** flat namespace at wiki root, `proposal-<slug>.md` prefix. GitHub Wiki does NOT render subdirectory pages reliably — we verified by pushing `proposals/foo.md` and clicking the link; it returned raw `.md` view. So flat it is.
- **Sidebar:** Navigation section first, Tasks section after. Regenerated by every wiki-mutating command via `_sidebar.py`.
- **Naming:** `slug` (kebab-case machine ID), `repo.short-name` (e.g. "MH" — deferred to M2, lives in wiki/config.yaml), per-task `short-name` (e.g. "Py-skills" — used for VS Code title, deferred to M3.1 mill-spawn). Today's work touches none of these — `_vscode.py` still uses last-URL-segment heuristic and is fine for now.
- **mill-spawn (M3.1) interactive mode:** when called without a slug, lists tasks numbered and prompts. Kept in the script (not a separate skill) because numbered-pick is mechanical. Your M1 work doesn't touch mill-spawn; noted here for context.
- **Don't sacrifice readability for LOC targets.** The roadmap's "~60 LOC for mill-add" is sizing guidance, not a contract. Named helpers with Google-style docstrings are expected per `plugins/python/skills/python-comments`.

## Current wiki state (manually edited last session)

Clone is at `C:\Code\millhouse\wiki\`. Three files touched:

- `Home.md` — one real task `## Rebuild skills index [[skills-index-rebuild]](proposal-skills-index-rebuild)` under `# Tasks` header + the template HTML comment
- `proposal-skills-index-rebuild.md` — full background for the task
- `_Sidebar.md` — Navigation section with `[Home](Home)`, Tasks section with linked skills-index-rebuild

This state was hand-written to prove the design before code landed. When you run the rewritten `mill-add.py` against the wiki, the output should match what's already there. Don't panic if you see "slug already exists" — that just confirms the manual entry matches.

## First actions when you resume

1. Read the Key Reading list above.
2. Run `git -C c:/Code/millhouse/hub status` — should show clean working tree on `main` at `8d6dfe3`.
3. Run `git -C c:/Code/millhouse/wiki log --oneline -5` — last three commits should be wiki-related (sidebar ordering, cleanup-to-flat, the initial `add task: skills-index-rebuild` and earlier preview commits).
4. Start with `_sidebar.py` (no dependencies, pure function on Home.md text). Write tests by running it against the real Home.md — output should match the existing `_Sidebar.md`.
5. Then rewrite `mill-add.py`. Test end-to-end by adding a second real task — perhaps `m1-4-mill-list` as a meta-backlog item to plan M1.4 work.
6. Update mill-setup Phase 6a last (small change).
7. Write mill-add/SKILL.md.
8. Commit. Move to M1.4.

## Scratch directory

`.millhouse/scratch/` contains the PowerShell verification scripts from last session:

- `m1.2-test-phase4.ps1` — junction create test
- `m1.2-test-phase7.ps1` — VS Code regex match test
- `m1.2-test-vscode-helper.ps1` — `_vscode` helper dry-render
- `m1.2-test-render.ps1` — `_render` smoke
- `m1.2-idempotency-test.ps1` — mill-setup full walkthrough
- `m1.2-fix-wiki-home.ps1` — Home.md GitHub-default replacement (has run; wiki already updated)
- `m1.3-preview-*.ps1`, `m1.3-cleanup-and-flat-demo.ps1`, `m1.3-fix-sidebar-order.ps1` — format-decision history

These are reference material, not required reading. The user cleans scratch periodically. Feel free to add more as you verify your own work.

## After M1 is done

Tag `layer-01-done`, update `roadmap/README.md` status table, then move on to Layer 02 in a fresh session (per our convention of one M layer per thread).
