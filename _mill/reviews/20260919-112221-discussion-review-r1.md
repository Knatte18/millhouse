MILL_REVIEW_BEGIN
# Review: _config.py / _treeguard.py: silently-ignored config keys and unguarded str-vs-Path args

```yaml
duration_s: 185.0
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5 (per environment metadata; self-assessed)
reviewed_file: _mill/discussion.md
date: 2026-09-19
```

## Findings

### [BLOCKING:design] AttributeError-at-line-75 claim is false for `git_root`
**Section:** Problem (#986) / Decision 2 rationale / Technical context line 60
**Issue:** Discussion claims passing either `worktree` or `git_root` as `str` "raises a raw AttributeError ... at line 75". Verified against `_treeguard.py:75` (`worktree.relative_to(git_root)`): `Path.relative_to()` accepts a plain `str` argument without error, so a `str` `git_root` never raises there (at most a `ValueError` if it isn't a real prefix, and only when `git_root is not None`). Only a `str` `worktree` can hit that line's `AttributeError`, and only in the nested-hub branch (`git_root` not `None`) — in the flat-layout case the function would silently "work" on a `str` worktree.
**Fix:** Correct the Problem/rationale text to describe the asymmetric, conditional failure mode (or re-verify and restate precisely which argument/layout combination actually crashes) before this becomes the plan's stated justification.

### [NIT:consistency] Testing section's verify-command guidance omits required `PYTHONPATH=` prefix and `--only` scoping
**Demoted-from:** BLOCKING
**Section:** Testing (final bullet)
**Issue:** States "Run via `plugins/mill/unit_tests/run-all.py` under `uv run --project plugins/mill` per this repo's Python-project verify-command convention" — no `PYTHONPATH= ` prefix and no `--only <files>` scoping. CLAUDE.md's Verify-command-shape rule requires `PYTHONPATH=` (empty) for Python-project `verify:` commands, `_plan_validate.py`'s `verify-not-isolated`/`verify-full-suite` checks enforce both (confirmed against `_plan_validate.py:3212-3219` and `test-plan-validate.py`'s literal `"PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only ..."` fixtures), and `mill-plan/SKILL.md:230-232` mandates `--only` for a focused multi-file batch like this one (exactly two touched test files).
**Fix:** State the verify command literally as `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-config.py test-treeguard.py` so a plan writer doesn't have to reverse-engineer the required shape.

### [NIT:consistency] RENAMED_KEY_HINTS precedent citation conflates two different scopes
**Section:** Decision 1 rationale
**Issue:** Claims the new module-level `RENAMED_KEY_HINTS` "mirrors the existing `deprecated_keys` set in the same function" — but `deprecated_keys` (`_config.py:121`) is a function-local variable, not module-level; only `ENV_REGISTRY` (lines 44-51) is actually module-level. The placement decision follows `ENV_REGISTRY`'s precedent, not `deprecated_keys`'s.
**Fix:** Attribute the module-level placement to `ENV_REGISTRY` specifically, and keep the `deprecated_keys` comparison scoped to "small explicit table of special-cased dotted paths" only.

## Verdict

REQUEST_CHANGES
Two BLOCKING findings: a false verified-behavior claim underpinning the guard rationale, and a verify-command convention contradiction.
_Note: 1 finding(s) demoted from BLOCKING to NIT by the stage's blocking-class ceiling; current blocking_count is 1._
MILL_REVIEW_END
