# Batch: regression-guard

```yaml
task: 'mill-go-base: remove subprocess/psmux dispatch branches'
batch: 'regression-guard'
number: 1
cards: 1
verify: null
depends-on: []
```

## Batch Scope

Writes the single new test this task adds: a content-assertion guard over `mill-go-base`'s SKILL and its three future companion files.
It is written first, deliberately red, so the strip that follows has something to turn green.
The external interface every later batch consumes is the set of literals and path references this test pins: the three banned strings, the three companion filenames, and the mandatory-read directive shape at each reference site.

Batch-local decision: this batch's `verify:` is `null` because the test it creates is expected to fail until batch 4.
See `## Batch Tests`.

## Cards

### Card 1: Regression guard for the agent-only mill-go-base skill

- **Context:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
  - `plugins/mill/unit_tests/test-mill-go-variants.py`
  - `plugins/mill/unit_tests/run-all.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/unit_tests/test-mill-go-base-agent-only.py`
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Create a standalone test module following the conventions of `plugins/mill/unit_tests/test-mill-go-variants.py`: module docstring, `from __future__ import annotations`, a module-level `HUB = Path(__file__).resolve().parent.parent.parent.parent`, a `SKILLS = HUB / "plugins" / "mill" / "skills"` constant, one `_check_*() -> list[str]` helper per concern returning failure strings, and a `main() -> int` that runs every check, prints `FAIL: …` lines to stderr, and returns 1 if any check produced failures.
  Guard it with `if __name__ == "__main__": sys.exit(main())`.
  Define module-level constants `BASE_DIR = SKILLS / "mill-go-base"`, `COMPANIONS = ("resume.md", "holistic-review.md", "handoff.md")`, and `BANNED_LITERALS = ("psmux", "millpy-bg", "dispatch == subprocess")`.
  Implement exactly four checks:
  1. `_check_no_dead_dispatch_literals` — for `SKILL.md` and for each name in `COMPANIONS`, read the file and assert none of `BANNED_LITERALS` appears in its text.
     A missing companion file is itself a failure here, reported as such rather than silently skipped.
  2. `_check_companion_files_exist` — assert each `BASE_DIR / name` exists for every name in `COMPANIONS`.
  3. `_check_companions_referenced_by_repo_relative_path` — assert `SKILL.md` contains the literal substring `plugins/mill/skills/mill-go-base/<name>` for every name in `COMPANIONS`.
  4. `_check_mandatory_read_directive_at_each_reference_site` — for every name in `COMPANIONS`, assert `SKILL.md` matches the case-insensitive regex `` Read\s+`plugins/mill/skills/mill-go-base/<escaped-name>` `` .
     Assert on that read-instruction shape only; do not assert on any surrounding prose, adjectives, or sentence ordering, so the wording at the three sites can be revised without breaking the guard.
  Use only ASCII in every string literal, docstring, and printed message, and use no `->` U+2192 arrow character anywhere in the file — `test-guards.py` fails any `test-*.py` containing one.
- **Commit:** `test(mill-go-base): add agent-only dispatch regression guard`

## Batch Tests

`verify: null`.
The one test this batch creates is a TDD guard written against the *post-strip* end state: it asserts three companion files exist that batch 4 creates, and that three literals are absent that batch 2 removes.
It therefore fails by design from the moment it is written until batch 4 completes, which is the point of writing it first.

Coverage is not deferred to nothing in the meantime: batches 2 and 3 gate on `test-guards.py`, `test-mill-go-variants.py`, and `test-skill-helper-drift.py`, the three existing tests that read `mill-go-base/SKILL.md`.
From batch 4 onward `test-mill-go-base-agent-only.py` joins that `--only` list and stays in it.
