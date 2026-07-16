MILL_REVIEW_BEGIN
# Review: Miscellaneous small tooling and doc/template accuracy gaps — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: opushigh
reviewed_file: plan/
date: 2026-07-16
```

## Findings

### [BLOCKING] Card 5 test cannot fire the [fixer-tier] warning as specified
**Location:** Batch 1 / Card 5 (test-millpy-fix.py)
**Issue:** The card says to extend the fixture config string `"roles:...fixer:\n    model: haiku\n"` "used by the happy-path tests", but that string is written to `wiki/config.yaml`, which is NOT read — `_review_common.load_config` is mocked in setUp to a hardcoded dict with no `code-review` key; additionally `_reviewers.resolve` is mocked with a fixed `return_value` (the haiku spec) regardless of name, so the reviewer resolves to haiku too and `reviewer_tier <= fixer_tier` keeps the warning silent. Implemented literally, `assertIn("[fixer-tier]")` fails.
**Fix:** Have the card override `self.mock_load_config.return_value` to include `roles.code-review.<scope>.reviewer` AND give `mock_reviewers_resolve` a name-aware `side_effect` returning an opus/high spec for the reviewer name vs. the haiku spec for the fixer.

### [NIT] Card 1 adds a module-level import cycle
**Location:** Batch 1 / Card 1 (_reviewers.py)
**Issue:** `import _agent_dispatch` at module top closes a cycle `_reviewers -> _agent_dispatch -> _review_common -> _reviewers`. It resolves safely today only because every cross-reference sits in a function body (`_review_common` binds `_reviewers` but uses it only inside functions), so it is fragile against any future top-level use.
**Fix:** Consider a function-local `import _agent_dispatch` inside `tier_rank` instead of a top-level import.

## Verdict

REQUEST_CHANGES
Card 5's prescribed test wiring cannot exercise the new warning; fix the mock overrides.
MILL_REVIEW_END
