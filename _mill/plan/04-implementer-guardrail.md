# Batch: implementer-guardrail

```yaml
task: Fix unit test suite failures, spurious review warning, and implementer verify-gate gaps
batch: implementer-guardrail
number: 4
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-guards.py
depends-on: []
```

## Batch Scope

#492: a weak-tier implementer was caught silently weakening test assertions
(adding `ExcludedPropertyNames` entries, downgrading conformance asserts) to
make `verify:` pass instead of fixing the underlying bug. No mechanical gate can
distinguish a legitimate test edit from a gutting edit, so the lever is the
implementer's instructions. This batch adds an explicit anti-weakening guardrail
to the per-batch brief template (`implementer-brief.md`) and the
`mill-implementer` agent definition, and adds a guard test asserting the
guardrail text is present in both files so it cannot be silently dropped. To
keep the guard test simple, both prose edits embed one exact marker sentence
(defined in card 8) that card 10 asserts on.

## Cards

### Card 8: Add the anti-weakening guardrail to the implementer brief template (#492)

- **Context:** none
- **Edits:**
  - `plugins/mill/templates/implementer-brief.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add a short guardrail to `implementer-brief.md` (a new
  subsection near the `## Verify` section is the natural anchor). It MUST contain
  this exact marker sentence verbatim so the guard test can assert it:
  `Never weaken, relax, exclude, downgrade, or delete test assertions, conformance checks, or allowlist entries to make verify pass.`
  Follow it with the rule that when `verify:` fails because a test or harness is
  itself buggy, the implementer fixes the test/harness or the code under test,
  and if it cannot, reports `stuck_type: logic` -- it never weakens coverage to
  go green. Keep the wording ASCII-only.
- **Commit:** `docs(implementer): forbid weakening tests to pass verify (#492)`

### Card 9: Add the same guardrail to the mill-implementer agent definition (#492)

- **Context:**
  - `plugins/mill/templates/implementer-brief.md`
- **Edits:**
  - `plugins/mill/agents/mill-implementer.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add the same anti-weakening rule to `mill-implementer.md`,
  including the identical exact marker sentence verbatim:
  `Never weaken, relax, exclude, downgrade, or delete test assertions, conformance checks, or allowlist entries to make verify pass.`
  One or two sentences is enough; keep it ASCII-only and consistent with the
  brief wording from card 8.
- **Commit:** `docs(implementer): add anti-weakening rule to mill-implementer agent (#492)`

### Card 10: Guard test asserting the guardrail is present in both files (#492)

- **Context:**
  - `plugins/mill/templates/implementer-brief.md`
  - `plugins/mill/agents/mill-implementer.md`
- **Edits:**
  - `plugins/mill/unit_tests/test-guards.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add a new check function to `test-guards.py` (e.g.
  `_check_anti_weakening_guardrail() -> int`, returning 0 on PASS / 1 on FAIL like
  the existing checks) that reads `plugins/mill/templates/implementer-brief.md`
  and `plugins/mill/agents/mill-implementer.md` and FAILs if either file does not
  contain the exact marker sentence
  `Never weaken, relax, exclude, downgrade, or delete test assertions, conformance checks, or allowlist entries to make verify pass.`
  Resolve those paths relative to the repo root using the same path-derivation
  pattern the existing checks use (do not hard-code an absolute path). Wire the
  new check into `main()`'s return-code aggregation (`rc |= _check_...()`) and add
  a one-line entry to the module docstring's check list. Keep all strings
  ASCII-only.
- **Commit:** `test(guards): assert anti-weakening guardrail present (#492)`

## Batch Tests

`verify:` runs `run-all.py --only test-guards.py`. The batch's runnable surface
is the new guard check (card 10), which asserts the card 8/9 prose edits are in
place; `test-guards.py` also re-runs its existing checks (including
`no_unicode_arrow`) to confirm the prose edits introduce no ASCII violations.
The brief/agent files themselves have no executable tests beyond this presence
check.
