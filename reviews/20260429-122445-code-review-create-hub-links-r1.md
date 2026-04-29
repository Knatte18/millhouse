# Review: 11 — par-C — Container layout overhaul + cwd-as-hub everywhere + gitignore-split — create-hub-links

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnetmax
reviewed_file: create-hub-links
date: 2026-04-29
```

## Findings

### [BLOCKING] Missing idempotent re-claim test in test-millpy-claim.py
**Location:** `plugins/mill/unit_tests/test-millpy-claim.py` (no such test exists)
**Issue:** Card 9 plan requirements explicitly enumerate four test cases `(a)–(d)`; case `(b)` "idempotent re-claim (re-running claim on the same slug doesn't error and is a no-op)" is absent. The three-state portal check in `millpy-claim.py` (exists+same-target → skip) has no test coverage.
**Fix:** Add a test that mocks `portal_link.exists()`/`is_symlink()` True and `os.path.realpath` returning equal strings, asserts `_junction.create` is not called a second time and exit code is 0.

### [BLOCKING] wiki/config.yaml junctions comment contradicts new junctions-block-semantic decision
**Location:** `wiki/config.yaml:68-71`
**Issue:** The "Scope is INFERRED from token presence" paragraph still says "Target contains `<SLUG>` → per-worktree, created by mill-spawn / Target has no `<SLUG>` → hub + worktrees, created by mill-setup" — the exact old behavior the Shared Decision `junctions-block-semantic` replaces. Card 10 explicitly requires updating the comment; the new `.others` entry is not mentioned in the narrative either.
**Fix:** Replace the "Scope is INFERRED" paragraph with the new semantic: `<SLUG>` parameterizes the target, not scope; all entries are created in every worktree via `_setup.create_hub_links`; entries with absent tokens are silently skipped by the token-scope filter.

### [NIT] `import os` inline inside main() in millpy-claim.py
**Location:** `plugins/mill/scripts/millpy-claim.py:~195`
**Issue:** `import os` is placed inside the `elif` branch rather than at module level; violates project style and hinders static analysis.
**Fix:** Move `import os` to the top of the file with the other stdlib imports.

### [NIT] Redundant `elif` condition in portal entry handling
**Location:** `plugins/mill/scripts/millpy-claim.py:~192-200`
**Issue:** `elif (portal_link.exists() or portal_link.is_symlink()):` is always True when reached (it is the exact negation of the `if` guard); reads as if there is a reachable third branch when there is none.
**Fix:** Replace `elif (portal_link.exists() or portal_link.is_symlink()):` with `else:`.

### [NIT] Unused `is_dirty` parameter in `_make_stub_map`
**Location:** `plugins/mill/unit_tests/test-millpy-claim.py:~70`
**Issue:** `is_dirty: bool = False` is declared in the signature but never read inside the function body; dirty-tree behaviour is patched at the test level instead.
**Fix:** Remove the unused parameter from the signature.

## Verdict

REQUEST_CHANGES
Two BLOCKINGs: missing idempotent re-claim test; wiki/config.yaml comment contradicts approved shared decision.