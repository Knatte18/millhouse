# Layer 01 — Bootstrap

```yaml
depends-on: M0
delivers: working wiki + tasks list + .millhouse/ infrastructure
loc-budget: 450
status: in progress
```

Delivers the minimum viable infrastructure: wiki clone + tasks list + `.millhouse/` local state. After this layer, a user can initialise a fresh machine and add/list tasks. Nothing else.

**Full layer spec (v1 reuse, deliverables, design decisions, acceptance criteria):** [../layer-01-bootstrap.md](../layer-01-bootstrap.md). Read it before starting any milestone below.

## Progress

| ID | Milestone | Status |
|---|---|---|
| M1.1 | Lift v1 primitives | [x] done (commit `72af20b`) |
| M1.2 | `mill-setup` skill | [x] skill + templates written (runtime test deferred to M1.5) |
| M1.3 | `mill-add` script + `_sidebar.py` helper | [x] initial version done; **extension in progress** (new bracketed-slug format, sidebar regeneration, `--proposal-body`) |
| M1.3.5 | `mill-add/SKILL.md` — thin skill for long-discussion → split task | [ ] not started |
| M1.4 | `mill-list` script | [ ] not started |
| M1.5 | Layer 01 integration test | [ ] not started |

---

## M1.1 — Lift v1 primitives

**Depends on:** M0.

Carry over, strip, clean:

- [x] `_subprocess_util.py` (from `millpy/core/subprocess_util.py`)
- [x] `_junction.py` (from `millpy/core/junction.py`, incl. Python 3.10 fallback)
- [x] `_wiki.py` (from `millpy/tasks/wiki.py` — lock + commit/push helpers)
- [x] `_render.py` (new, ~20 LOC — template substitution helper)

### Exit criteria

- [x] All four files are in `plugins/mill/scripts/`
- [x] No imports reference `millpy.*`
- [x] Each file runs standalone if `python <file>.py` is called (prints a usage message at minimum)
- [x] Hand-test: create a junction, remove it; acquire wiki lock, release it; render a template

**Report:** [specs/_starter/m1.1-result.md](../_starter/m1.1-result.md). Committed in `72af20b`.

---

## M1.2 — mill-setup skill

**Depends on:** M1.1.

Write `plugins/mill/skills/mill-setup/SKILL.md`. Also write `plugins/mill/templates/config.local.yaml` and `plugins/mill/templates/Home.md`.

The skill tells Claude to:

1. Detect remote URL, derive wiki URL
2. Clone wiki if missing
3. Create `.millhouse/` + junction + config.local.yaml
4. Initialise Home.md if empty
5. Verify end-to-end

### Exit criteria

- [ ] Running `/mill-setup` from an empty `hub/` produces a working `.millhouse/` + `wiki/` junction *(verified end-to-end in M1.5 integration test)*
- [ ] Running it a second time is a no-op *(verified in M1.5)*
- [x] Skill file is under 200 lines *(143 lines)*

---

## M1.3 — mill-add script

**Depends on:** M1.2.

Write `plugins/mill/scripts/mill-add.py`. Under ~60 LOC. Uses `_wiki.py` for commit/push.

### Exit criteria

- [x] Initial `mill-add.py` appends to Home.md *(verified with real task `skills-index-rebuild` commit `e444de8`, old format `## <slug>`)*
- [x] Wiki gets commit pushed
- [x] Lock acquired/released *(verified happy-path and duplicate-reject path — lock released via `finally` in both)*

### Extension work (not yet done — resume here)

Format-discussion during this session produced a new Home.md task shape:
`## <Title> [<slug>]` (plain) or `## <Title> [[<slug>]](proposal-<slug>)` (linked when proposal exists).
Plus a `_Sidebar.md` regenerator and an optional `--proposal-body` flag for long-discussion splitting.

Specs are updated; code is not. To land the extension:

- [ ] Write `plugins/mill/scripts/_sidebar.py` — `parse_home_tasks`, `render_sidebar`, `regenerate` (see `layer-01-bootstrap.md` section "3. `_sidebar.py`")
- [ ] Rewrite `plugins/mill/scripts/mill-add.py` — new args (`--title`, `--summary`, `--proposal-body`), new heading format, call `_sidebar.regenerate()` after appending, commit all wiki files in one commit under one lock
- [ ] Update `plugins/mill/skills/mill-setup/SKILL.md` — Phase 6a to call `_sidebar.regenerate()` on fresh setup
- [ ] Write `plugins/mill/skills/mill-add/SKILL.md` — thin skill for long-discussion → split task (M1.3.5)
- [ ] Re-test against real wiki (wiki is **already manually updated** to the new format — `## Rebuild skills index [[skills-index-rebuild]](proposal-skills-index-rebuild)` + `proposal-skills-index-rebuild.md` + `_Sidebar.md`). Verify the new mill-add.py produces matching output when re-adding a task.
- [ ] Update exit criteria above to check boxes and add "heading format is `## <Title> [<slug>]` / `[[<slug>]](proposal-<slug>)`"

---

## M1.4 — mill-list script

**Depends on:** M1.2 (just needs wiki).

Write `plugins/mill/scripts/mill-list.py`. Under ~30 LOC.

### Exit criteria

- [ ] `python plugins/mill/scripts/mill-list.py` prints tasks, one per line

---

## M1.5 — Layer 01 integration test

**Depends on:** M1.1, M1.2, M1.3, M1.4.

Write `plugins/mill/integration_tests/test-bootstrap.ps1`. Sets up fake wiki in temp dir, runs setup + add + list, checks output.

### Exit criteria

- [ ] Test passes
- [ ] Total Python LOC for Layer 01 is under 450

⛔ **Gate 1:** stop here and evaluate. Can you add/list tasks reliably? If yes, Layer 01 is done — tag `layer-01-done`. If no, fix before continuing.
