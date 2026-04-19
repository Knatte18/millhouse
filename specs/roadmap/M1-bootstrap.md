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
| M1.2 | `mill-setup` skill | [x] skill + templates + `_vscode.py` helper done; all 8 phases verified end-to-end against real wiki + hub (commits `d81d74c`, `06b1497`) |
| M1.3 | `mill-add` script + `_sidebar.py` helper | [x] done; bracketed-slug format + `_sidebar.regenerate` + `--proposal-body` landed; end-to-end push against real wiki still pending |
| M1.3.5 | `mill-add/SKILL.md` — thin skill for long-discussion → split task | [x] done |
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

Committed in `72af20b`.

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

- [x] Running `/mill-setup` from an empty `hub/` produces a working `.millhouse/` + `wiki/` junction *(verified against real wiki: cloned to `C:\Code\millhouse\wiki`, junction created at `.millhouse/wiki`, Home.md normalised from GitHub-default, VS Code green applied correctly)*
- [x] Running it a second time is a no-op *(verified via `.millhouse/scratch/m1.2-idempotency-test.ps1` — all phases SKIP or pull-no-op on re-run)*
- [x] Skill file is under 200 lines *(186 lines after `_vscode.py` refactor and spec-driven extensions — still under the 200-line cap)*
- [x] `.millhouse/config.local.yaml` exists *(template copied)*
- [x] `.vscode/settings.json` exists with `titleBar.activeBackground == "#2d7d46"` *(pre-existing green detected by regex, SKIP fired correctly)*

**Note:** Phase 6a (regenerate `_Sidebar.md` via `_sidebar.regenerate`) is now implemented alongside M1.3 — the SKILL.md describes it and the helper exists.

---

## M1.3 — mill-add script

**Depends on:** M1.2.

Write `plugins/mill/scripts/mill-add.py`. Under ~60 LOC. Uses `_wiki.py` for commit/push.

### Exit criteria

- [x] Initial `mill-add.py` appends to Home.md *(verified with real task `skills-index-rebuild` commit `e444de8`, old format `## <slug>`)*
- [x] Wiki gets commit pushed
- [x] Lock acquired/released *(verified happy-path and duplicate-reject path — lock released via `finally` in both)*
- [x] Heading format is `## <Title> [<slug>]` (plain) or `## <Title> [[<slug>]](proposal-<slug>)` (linked) — single regex parses both
- [x] `_sidebar.py` helper exists (`parse_home_tasks`, `render_sidebar`, `regenerate`) and regenerates `_Sidebar.md` idempotently
- [x] `mill-add` accepts `--title`, `--summary`, `--proposal-body`; writes `proposal-<slug>.md` at wiki root when `--proposal-body` is given
- [x] `mill-add` commits Home.md + `_Sidebar.md` (+ proposal when present) in **one commit** under **one** `_wiki.acquire_lock` acquisition
- [x] `mill-setup/SKILL.md` has Phase 6a calling `_sidebar.regenerate()`
- [x] `mill-add/SKILL.md` exists (thin skill for long-discussion → split task — M1.3.5)
- [x] End-to-end re-test against real wiki *(added `m1-4-mill-list` task, commit `7355e2c` pushed to `origin/master` — `Home.md` + `_Sidebar.md` in a single commit; proposal code path verified in unit smoke test)*

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
