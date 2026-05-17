Now I have all I need. Writing the review:

---

# Review: 51 (D) — Config infra: env interpolation + agents.yaml inheritance

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax_tool
reviewed_file: _mill/discussion.md
date: 2026-05-17
```

## Findings

### [GAP] extends step-2 validation infeasible for multi-level chains
**Section:** Technical context — Modification plan for `_reviewers.load()`, step 2
**Issue:** Step 2 says "target must be type=single," but for a 3-level chain `c → b → a`, `b`'s raw YAML has no `type:` field (it inherits it from `a`). The check is therefore unresolvable from raw form when intermediate links omit `type:`. As written, step 2 would incorrectly reject valid `c extends b` because `b` has no raw `type: single`.
**Fix:** Clarify whether (a) the step-2 check is "target must not declare `type: cluster`" (checkable on raw) with the full type=single guarantee deferred to step 5, or (b) intermediate links in a multi-level chain must explicitly re-declare `type: single`. The discussion allows multi-level chains but leaves this invariant unresolved.

### [NOTE] ConfigError does not exist in `_config.py`
**Section:** Decisions — Unset var without default: hard error
**Issue:** The decision says raise "ConfigError (eller eksisterende exception-klasse i `_config`)", but reading `_config.py` confirms there is no existing exception class there at all.
**Fix:** Drop the hedge; the plan should simply say "create and raise a new `ConfigError(ValueError)` class in `_config.py`."

### [NOTE] Lowercase env var names pass through silently
**Section:** Technical context — `_substitute_string(s)` (ny)
**Issue:** The regex `[A-Z_][A-Z0-9_]*` only matches uppercase names; `${my_var}` produces no match and no error — it passes through as literal text. This is asymmetric with the hard-error behavior for uppercase unset vars.
**Fix:** Call this out explicitly as intended behaviour (POSIX convention; lowercase names are not supported and are treated as literal strings). Add a `test_interp_lowercase_name_passthrough` test case or a comment in the regex documenting the boundary.

## Verdict

GAPS_FOUND  
The multi-level extends validation ordering is internally contradictory and must be resolved before plan writing.