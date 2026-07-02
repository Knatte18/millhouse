I have reviewed all four batches holistically against the plan and each other. My findings are below.

MILL_REVIEW_BEGIN
# Review: Fix daemon health-check race, finalize env-var delivery, skills-index drop, and encoding crash — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewed_file: plan/ + source
date: 2026-07-02
```

## Findings

None. All four independent (Layer A) batches are fully realized, cross-checked against each other and the overview.

Verified:
- `wiki/_client.py:160-190` — `_dispatch()` splits `ConnectionRefusedError` (respawns via `_ensure_daemon()` when `attempt < 3`, propagates `WikiStartupError` uncaught) from `TimeoutError`/`ConnectionResetError` (unchanged sleep-retry), exactly per Card 1. `test-wiki-client-retry.py` cases 9-11 cover respawn-success, no-respawn-on-timeout, and respawn-failure-is-terminal with correct call/sleep-count assertions; existing cases 1-8 remain compatible (mocked `_ensure_daemon` return values don't break under the new extra invocation).
- `git-pr/SKILL.md:36-38,46-73,87` and `mill-finalize/SKILL.md:96,101` — env-var contract fully replaced by `--skip-task-branch-guard` token-walk (`case " $ARGUMENTS " in *" ... "*`); base-branch resolution strips the flag first; no leftover `MILL_FINALIZE_PR_CLEANUP` references anywhere in `plugins/`. `## Usage` and `argument-hint` left untouched, matching the "stay undocumented" requirement.
- `millpy-skills-index.py:25-43,56-77,102-115` — new `FrontmatterParseError(path, original_exc)` raised from `_extract_frontmatter`'s `except yaml.YAMLError`, caught in `_scan()` with a distinct stderr message, while the missing-frontmatter branch is untouched. `test-skills-index.py` reproduces the #589 unquoted-colon case and asserts the two stderr messages are mutually exclusive.
- `millpy-wiki-migrate.py:38-49,77` — `_ensure_utf8_stdout()` added verbatim as specified, called as the first statement in `main()` before `argparse.ArgumentParser`. `test-wiki-migrate-print.py` reproduces the cp1252 precondition and the exact `#588` repro character.
- No out-of-plan files, no duplicated helpers (`_ensure_utf8_stdout` has no sibling implementation elsewhere), all `verify:` commands correctly carry the `PYTHONPATH= ` isolation prefix per the Shared Decision (batch 02 correctly `null`).

## Verdict

APPROVE
All four batches match their cards, tests cover the new behavior, no out-of-plan files or duplication found.
MILL_REVIEW_END