# Batch: small-fixes

```yaml
task: 50 (A) — Bug-fix batch 5 (post-44 triage)
batch: small-fixes
number: 3
cards: 3
verify: python plugins/mill/unit_tests/test-no-unicode-arrow.py
depends-on: []
```

## Batch Scope

Cleanup batch for three doc / encoding tail-strands that don't fit
elsewhere: #237 `_review_plan.py` docstring + SCRIPTS.md regen, and #251
U+2192 `→` replacement in unit-test prints with a regression-guard test.

The new regression-guard test (`test-no-unicode-arrow.py`) doubles as this
batch's `verify:` because it covers Card 9's behaviour directly. Card 7's
docstring change has no test (docstrings are not unit-tested); Card 8's
SCRIPTS.md regen has no test either (the file is auto-generated from
`--help` output and the help strings were already migrated). Both are
reviewer-eye-on-diff.

Batch-local decisions:

- The arrow-replacement is purely textual: every literal `→` in every
  `plugins/mill/unit_tests/test-*.py` becomes `->`. No semantic change to
  any test assertion.
- The regression-guard test (`test-no-unicode-arrow.py`) scans
  `plugins/mill/unit_tests/test-*.py` files and reports any file containing
  the literal character U+2192. It excludes itself by filename so the test
  source can mention the character in a docstring.
- The SCRIPTS.md regen produces output that should match running each
  `millpy-*.py --help` against the existing source. The implementer runs
  the regen command from the SCRIPTS.md header verbatim, captures stdout
  for each script, and rewrites SCRIPTS.md preserving its existing top
  comment block.

## Cards

### Card 7: Fix stale config-schema docstring in `_review_plan.py`

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_review_plan.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `plugins/mill/scripts/_review_plan.py` line 280 (inside the docstring for the public `run` function), change `5. Holistic review (skipped if cfg.review.plan.holistic is None or no_holistic).` to `5. Holistic review (skipped if cfg["roles"]["plan-review"]["holistic"]["reviewer"] is None or no_holistic).`. Use the bracketed form (`cfg["roles"]["plan-review"]["holistic"]["reviewer"]`) — it matches every other reference to the same key inside the file (e.g. line 328: `if holistic_name is None or cfg["roles"]["plan-review"]["holistic"]["rounds"] == 0:`). No other line in the file changes.
- **Commit:** `fix(_review_plan): docstring uses roles.plan-review.holistic schema`

### Card 8: Regenerate `plugins/mill/SCRIPTS.md`

- **Context:**
  - `plugins/mill/scripts/millpy-review-code.py`
  - `plugins/mill/scripts/millpy-review-discussion.py`
  - `plugins/mill/scripts/millpy-review-plan.py`
- **Edits:**
  - `plugins/mill/SCRIPTS.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Regenerate `plugins/mill/SCRIPTS.md` from current `--help` output. The existing file's top comment block ("Auto-generated from `--help` output. Re-generate when CLI signatures change:" + the for-loop) MUST be preserved verbatim at the top of the regenerated file. For each `plugins/mill/scripts/millpy-*.py`, invoke `uv run --project plugins/mill <script> --help 2>/dev/null` and embed the stdout inside a code fence under a `## <script-basename>` heading (matching the existing file's structure). Sort script sections alphabetically by basename (matches current file order). The post-regen file MUST have zero occurrences of the literal strings `review.code.rounds`, `review.discussion.rounds`, or `review.plan.rounds` — those were the stale references the regen fixes. Verify by grep before committing.
- **Commit:** `chore(SCRIPTS): regenerate help reference (roles.* schema)`

### Card 9: Replace `→` with `->` in unit-test prints + regression guard

- **Context:** none
- **Edits:**
  - `plugins/mill/unit_tests/test-review-common.py`
- **Creates:**
  - `plugins/mill/unit_tests/test-no-unicode-arrow.py`
- **Deletes:** none
- **Requirements:**
  1. In `plugins/mill/unit_tests/test-review-common.py`, replace every literal U+2192 character (`→`) with the two-character ASCII sequence `->`. The file currently has 13 occurrences across both print-string content and comment text. The replacement is global and textual — no semantic change.
  2. Create `plugins/mill/unit_tests/test-no-unicode-arrow.py` as a standalone test script following the existing `test-*.py` style:

     ```python
     """Regression guard: no U+2192 arrow character in unit-test prints."""
     from __future__ import annotations
     import sys
     from pathlib import Path

     HERE = Path(__file__).resolve().parent
     SELF = Path(__file__).name


     def main() -> int:
         hits: list[str] = []
         for path in sorted(HERE.glob("test-*.py")):
             if path.name == SELF:
                 continue
             text = path.read_text(encoding="utf-8")
             if "→" in text:
                 hits.append(path.name)
         if hits:
             for name in hits:
                 print(f"FAIL: U+2192 arrow found in {name}", file=sys.stderr)
             return 1
         print("PASS: no U+2192 arrow in any test-*.py")
         return 0


     if __name__ == "__main__":
         sys.exit(main())
     ```

     The `SELF = Path(__file__).name` guard is the primary protection — the file's `glob` skips itself by filename, so the literal `→` in `if "→" in text:` is safe. The implementer MAY write the literal character (as shown in the code template above) OR may use `"→"` if they prefer an ASCII-only source — both are equally correct because the SELF guard prevents self-fail.
- **Commit:** `fix(tests): replace U+2192 with -> + add regression guard`

## Batch Tests

`verify: python plugins/mill/unit_tests/test-no-unicode-arrow.py` runs the
regression-guard test, asserting zero occurrences of `→` across all
`test-*.py` files. The 13 replacements in `test-review-common.py` are
mechanical; a manual diff plus `run-all.py` (which runs the full suite under
`PYTHONIOENCODING=utf-8`) confirms no behavioural regression.

The SCRIPTS.md regen and `_review_plan.py` docstring fix have no runnable
verifier — reviewer eyes on the diff catch any malformed output.
