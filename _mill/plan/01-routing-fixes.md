# Batch: routing-fixes

```yaml
task: 'mill-go-base SKILL.md: resume phase branch, entry routing, and undocumented flags'
batch: routing-fixes
number: 1
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-mill-go-base-agent-only.py test-skill-helper-drift.py
depends-on: []
```

## Batch Scope

Closes the two remaining live gaps from #837 and #840 in `mill-go-base`'s routing prose (`SKILL.md`'s "### Mid-execution phase-gate widening" table and `resume.md` step 1). Both cards are self-contained markdown-prose edits to orchestrator instructions with no corresponding Python logic — no Python file is touched and no signature changes. There is no external interface between the two cards: each closes its own independent routing gap in its own file (see the overview's "no shared helper between the two fixes" Shared Decision), so there is nothing for one card to hand off to the other.

## Cards

### Card 1: `approved-{batch_name}` liveness check before Execute-loop continuation

- **Context:**
  - `plugins/mill/skills/mill-go-base/resume.md`
  - `plugins/mill/skills/mill-go-base/holistic-review.md`
- **Edits:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `SKILL.md`'s `### Mid-execution phase-gate widening` section, locate the `approved-{batch_name}` bullet, whose text today reads exactly (byte-exact excerpt, no added indentation):

```
- `approved-{batch_name}` — fires *between* batches: the just-finished batch is `state: approved`, every other batch is either already `approved` or still `pending`, so no batch entry is `running`/`reviewing`/`fixing` and Resume's (`plugins/mill/skills/mill-go-base/resume.md`) step 1 has nothing to match.
  Route instead to `## Execute — sequential loop`, continuing from the next `pending` batch in `order` — the same continuation the normal in-flow path already takes after a batch approves.
  **Edge case:** if the just-approved batch was the last one in `order` (zero `pending` batches remain), route to `## Holistic code review` (`plugins/mill/skills/mill-go-base/holistic-review.md`) instead, mirroring the normal in-flow transition from the end of the Execute loop into that section.
```

  Insert a new paragraph between the bullet's first sentence (ending "...has nothing to match.") and the "Route instead to..." sentence, so the bullet reads (byte-exact excerpt, no added indentation):

```
- `approved-{batch_name}` — fires *between* batches: the just-finished batch is `state: approved`, every other batch is either already `approved` or still `pending`, so no batch entry is `running`/`reviewing`/`fixing` and Resume's (`plugins/mill/skills/mill-go-base/resume.md`) step 1 has nothing to match.
  **Liveness check first.** Starting a batch's implementer (dispatching, setting `state: running`, recording `start_sha`/`implementer_session`) does not call `_status.append_phase`, so an interruption right after dispatching the next batch can leave `phase:` on-disk still reading `approved-{batch_name}` even though the next batch is genuinely mid-implementation. Before applying the assumption above, call `_status.read_batches(status_path)` and check whether any entry's `state` is `running`, `reviewing`, or `fixing`. If one is found, route to `## Resume` (`plugins/mill/skills/mill-go-base/resume.md`) instead — its step 1 will correctly locate and resume that batch.
  Only when no entry is non-terminal does the following apply, unchanged:
  Route instead to `## Execute — sequential loop`, continuing from the next `pending` batch in `order` — the same continuation the normal in-flow path already takes after a batch approves.
  **Edge case:** if the just-approved batch was the last one in `order` (zero `pending` batches remain), route to `## Holistic code review` (`plugins/mill/skills/mill-go-base/holistic-review.md`) instead, mirroring the normal in-flow transition from the end of the Execute loop into that section.
```

  This mirrors the existing `self-resolved-verify-logic` bullet in the same table (a few lines below, read-only reference — no separate Context: entry needed since it is inside the same `Edits:` file), which already does exactly this kind of `_status.read_batches(status_path)` liveness check to disambiguate before routing — match that bullet's phrasing style. Do not change any other bullet in the "### Mid-execution phase-gate widening" section, and do not change the phase-gate table above it (the `implementing`/`reviewing`/`fixing` row's action text is unrelated to this fix).
- **Commit:** `docs(mill-go-base): add batch-liveness check to approved-{batch_name} routing (#837)`

### Card 2: `resume.md` step 1 fallback for zero non-terminal batch entries

- **Context:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
  - `_mill/status.md`
- **Edits:**
  - `plugins/mill/skills/mill-go-base/resume.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `resume.md`, step 1 today reads exactly (byte-exact excerpt, no added indentation):

```
1. Read `_mill/status.md`;
   locate the current batch entry (the single entry whose `state` is non-terminal: `running`, `reviewing`, or `fixing`).
```

  Append an explicit fallback paragraph directly after it, so step 1 reads (byte-exact excerpt, no added indentation):

```
1. Read `_mill/status.md`;
   locate the current batch entry (the single entry whose `state` is non-terminal: `running`, `reviewing`, or `fixing`).
   **Fallback — no non-terminal entry found.** If `_status.read_batches(status_path)` finds no entry with a non-terminal state, this is the narrow window between Prepare's bare `implementing` phase-append and Execute's dispatch of the first batch — every batch entry is still `state: pending`. Skip the rest of this Resume file entirely and fall through directly to `plugins/mill/skills/mill-go-base/SKILL.md`'s `## Execute — sequential loop`, starting at the first `pending` batch in `order`.
```

  `SKILL.md`'s `## Execute — sequential loop` heading (read-only reference, listed in Context: above) is the exact target heading text to cite verbatim — do not paraphrase it. `_mill/status.md` (also listed in Context: above) is cited only as the file `_status.read_batches` reads — this card does not edit it. Do not renumber or otherwise change steps 2–4 of `resume.md`; this card only appends the new fallback paragraph to step 1.
- **Commit:** `docs(mill-go-base): add resume.md step-1 fallback for zero non-terminal batches (#840)`

## Batch Tests

`verify:` runs `test-mill-go-base-agent-only.py` and `test-skill-helper-drift.py` via `run-all.py --only` — these are the exact two existing tests `_mill/discussion.md`'s "Testing" section names as covering the structural invariants (companion-file cross-references, no dead literals, drift/consistency) that a careless prose edit to either file could break. No new unit tests are added: both cards are prose-only edits to orchestrator instructions with no corresponding Python logic to unit-test. Beyond the automated `verify:`, the implementer should also manually confirm the new text in each file is internally consistent with the rest of that file's routing table/step numbering (phase-string literals and cross-references to `## Resume` / `## Execute — sequential loop` / `## Holistic code review` match exactly), per the discussion's stated verification approach.
