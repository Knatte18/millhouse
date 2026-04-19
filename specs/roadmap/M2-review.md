# Layer 02 — Review

```yaml
depends-on: Layer 01
delivers: mill-review with Claude + Gemini providers
loc-budget: 750
status: not started
```

Single-shot review on demand. Given a file and a model name, produce a review artefact with a clear verdict and findings.

**Full layer spec (v1 reuse, deliverables, design decisions, acceptance criteria):** [../layer-02-review.md](../layer-02-review.md). Read it before starting any milestone below.

## Progress

| ID | Milestone | Status |
|---|---|---|
| M2.1 | Review CLI skeleton + dispatcher | [ ] not started |
| M2.2 | Claude provider (stream-json) | [ ] not started |
| M2.3 | Review-prompt templates | [ ] not started |
| M2.4 | Gemini provider (tool-use) | [ ] not started |
| M2.5 | Layer 02 integration tests | [ ] not started |

---

## M2.1 — Review CLI skeleton + dispatcher

**Depends on:** Layer 01 done.

Write `plugins/mill/scripts/mill-review.py` — arg parsing, template loading, dispatch stub (no providers yet, just raises NotImplementedError). ~80 LOC.

### Exit criteria

- [ ] `python plugins/mill/scripts/mill-review.py --type plan --file foo.md --model fake-model` exits 2 (unknown model) with clear error
- [ ] Config loading works

---

## M2.2 — Claude provider (stream-json)

**Depends on:** M2.1.

Write `plugins/mill/scripts/providers/claude.py`. Spawn `claude.exe`, parse stream-json, extract verdict. Handle both tool-use and free-text responses. ~200 LOC.

### Exit criteria

- [ ] `mill-review --type plan --model sonnet --file sample-plan.md` completes
- [ ] Verdict extracted correctly from tool-use response
- [ ] Timeout handling works (force a hang, verify wrapper kills it)

---

## M2.3 — Review-prompt templates

**Depends on:** M2.1.

Lift and clean from `millpy/doc/prompts/plan-review.md`, `code-review.md`, `discussion-review.md`:

- [ ] `templates/review-prompt-plan.md`
- [ ] `templates/review-prompt-code.md`
- [ ] `templates/review-prompt-discussion.md`
- [ ] `templates/review-output.md`

Plus schemas (only where validation matters — `review-output.md`).

### Exit criteria

- [ ] Each template has clear `<PLACEHOLDER>` tokens
- [ ] Substitution via `_render.py` works
- [ ] No inline prompts in Python

---

## M2.4 — Gemini provider (tool-use)

**Depends on:** M2.2 (proves provider pattern works first).

- [ ] Write `plugins/mill/scripts/providers/gemini.py`. API client, tool-use loop, function declarations for Read/Write. ~250 LOC.
- [ ] Write `plugins/mill/scripts/providers/_tools.py` — shared tool implementations. ~60 LOC.

### Exit criteria

- [ ] `mill-review --type discussion --model gemini-3-pro --file sample.md` completes via tool-use
- [ ] Agent can Read/Write files via declared tools
- [ ] Tool-use loop terminates cleanly (max-turns cap works)

---

## M2.5 — Layer 02 integration tests

**Depends on:** M2.2 and M2.4.

Three test scripts, one per combo:

- [ ] `test-review-plan-claude.ps1`
- [ ] `test-review-code-claude.ps1`
- [ ] `test-review-discussion-gemini.ps1`

### Exit criteria

- [ ] All three pass
- [ ] Total Python LOC for Layer 02 is under 750

⛔ **Gate 2:** stop and evaluate. Can you review a plan file with Claude AND with Gemini? Do the outputs look useful? Tag `layer-02-done`.
