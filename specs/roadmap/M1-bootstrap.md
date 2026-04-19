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
| M1.3 | `mill-add` script | [ ] not started |
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

- [ ] `python plugins/mill/scripts/mill-add.py foo --description "do foo"` appends to Home.md
- [ ] Wiki gets commit pushed
- [ ] Lock acquired/released

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
