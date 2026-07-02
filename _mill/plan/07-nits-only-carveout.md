# Batch: nits-only-carveout

```yaml
task: "Fix agent-mode dispatch races and pipeline gaps"
batch: nits-only-carveout
number: 7
cards: 3
verify: null
depends-on: []
```

## Batch Scope

Fixer-brief templates unconditionally forbid a zero-new-commit `success` report in two separate sentences each, contradicting `_implementer_common.py`'s existing `nits_only` guard (`:894-899`) that already permits exactly this for a legitimate `--nits-only` no-op pass. This batch adds a `NITS_ONLY_CARVEOUT` render token — computed once in `millpy-fix.py` from `args.nits_only` (already parsed, already threaded to the runtime guard via `nits_only=args.nits_only` at `:253` and `:476`) — and restructures both templates' two strict sentences to consume it, so the brief text and the runtime guard's actual behavior can never diverge. Self-contained: touches only `millpy-fix.py` and the two templates it renders; no dependency on any other batch.

## Cards

### Card 14: millpy-fix.py — compute the NITS_ONLY_CARVEOUT token

- **Context:**
  - `_mill/discussion.md`
  - `plugins/mill/scripts/_implementer_common.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-fix.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Immediately before the `if args.scope == "batch":` branch (`millpy-fix.py:260`), add:
  ```python
  nits_only_carveout = (
      ", unless every finding was a legitimate --nits-only no-op requiring no code change."
      if args.nits_only
      else "."
  )
  ```
  Add `"NITS_ONLY_CARVEOUT": nits_only_carveout,` to the batch-scope token dict passed to `_render.render(template_path, {...})` (`millpy-fix.py:321-336`) and to the holistic-scope token dict (`millpy-fix.py:386-397`) — one new key in each of the two existing dicts, no other change to either dict's contents. The value carries its own leading punctuation/conjunction and terminal period in both branches so the templates (Cards 15-16) never hardcode sentence-ending punctuation after the token — this is what prevents a dangling "unless ." or a missing terminal period in either branch.
- **Commit:** `feat(millpy-fix): compute NITS_ONLY_CARVEOUT render token from --nits-only`

### Card 15: fixer-holistic-brief.md — consume the carve-out token

- **Context:**
  - `_mill/discussion.md`
  - `plugins/mill/scripts/millpy-fix.py`
- **Edits:**
  - `plugins/mill/templates/fixer-holistic-brief.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Two edits, both in the `## Report` section:
  1. `fixer-holistic-brief.md:71` currently ends "...never report `success` when HEAD equals the baseline (no new commit was made). Run `git -C <PROJECT_ROOT> status --porcelain --untracked-files=no`. ..." — replace `(no new commit was made).` with `(no new commit was made)<NITS_ONLY_CARVEOUT>` (remove the literal trailing period; the token supplies it). The rest of the sentence/paragraph is unchanged.
  2. `fixer-holistic-brief.md:84` currently reads "**`commit_sha` MUST be a real new content commit distinct from the holistic fix housekeeping commit.** A fixer that made edits but did not commit must report `status: stuck` (`stuck_type: logic`) instead." — change to "**`commit_sha` MUST be a real new content commit distinct from the holistic fix housekeeping commit**<NITS_ONLY_CARVEOUT> A fixer that made edits but did not commit must report `status: stuck` (`stuck_type: logic`) instead." — the closing `**` moves to immediately after "commit" (before the token, so the bold emphasis covers the core rule and not the conditionally-empty trailing clause), and the literal period before `**` is removed (the token supplies the terminal punctuation for whichever branch renders).

  Also add `<NITS_ONLY_CARVEOUT>` to the template's tokens comment block at the top of the file (`fixer-holistic-brief.md:4-19`), in the same one-line style as the other listed tokens (e.g. `  <NITS_ONLY_CARVEOUT>   — trailing clause after the zero-commit rules; empty-punctuation "." for a normal pass, or a --nits-only exception clause`).
- **Commit:** `feat(fixer-holistic-brief): carve out legitimate --nits-only zero-commit success`

### Card 16: fixer-batch-brief.md — consume the carve-out token

- **Context:**
  - `_mill/discussion.md`
  - `plugins/mill/scripts/millpy-fix.py`
- **Edits:**
  - `plugins/mill/templates/fixer-batch-brief.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Two edits, both in the `## Report` section, mirroring Card 15's holistic-template edits exactly (same rule, per-batch scope instead of holistic):
  1. `fixer-batch-brief.md:65` currently ends "...never report `success` when HEAD equals the baseline (no new commit was made). Run `git -C <PROJECT_ROOT> status --porcelain --untracked-files=no`. ..." — replace `(no new commit was made).` with `(no new commit was made)<NITS_ONLY_CARVEOUT>`.
  2. `fixer-batch-brief.md:78` currently reads "**`commit_sha` MUST be a real new content commit distinct from the fix-round housekeeping commit.** A fixer that made edits but did not commit must report `status: stuck` (`stuck_type: logic`) instead." — change to "**`commit_sha` MUST be a real new content commit distinct from the fix-round housekeeping commit**<NITS_ONLY_CARVEOUT> A fixer that made edits but did not commit must report `status: stuck` (`stuck_type: logic`) instead." (note this template says "fix-round housekeeping commit", not "holistic fix housekeeping commit" — preserve that existing wording difference, only move the bold-close and swap the trailing period for the token exactly as in Card 15).

  Also add `<NITS_ONLY_CARVEOUT>` to this template's tokens comment block (`fixer-batch-brief.md:4-19`), same one-line style as Card 15.
- **Commit:** `feat(fixer-batch-brief): carve out legitimate --nits-only zero-commit success`

## Batch Tests

`verify: null` — these are prose template + one small token-computation change with no runnable surface of its own. Per `_mill/discussion.md`'s Testing section, this is a documentation-only change relying on `_implementer_common.py`'s existing `nits_only` guard tests (Cases 56-58 in `test-implementer-common.py`, already covering `#582`) as the ground truth for correct runtime behavior — the templates must not drift from that guard's actual semantics. Validate by re-reading the four edited sentences for a clean, complete sentence in BOTH the `nits_only=True` and `nits_only=False` render (no dangling "unless ." and no missing terminal period).
