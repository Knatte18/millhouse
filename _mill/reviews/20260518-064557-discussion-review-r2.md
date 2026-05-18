I now have all the information needed for the review.

# Review: 64 (A) — Small infra fixes batch 9

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax_tool
reviewed_file: _mill/discussion.md
date: 2026-05-18
```

## Findings

### [GAP] spawn log fires before `proc` exists — "wrap both" is infeasible
**Section:** Technical context — `_subprocess_util.run()`
**Issue:** The spawn print at line 105 fires before `proc = subprocess.Popen(...)` at line 126. The technical context instruction "Wrap both in `if proc.returncode != 0:`" is wrong for the spawn line — `proc` doesn't exist yet, so `proc.returncode` is undefined at that call site. An implementer following this literally writes a `NameError`. The correct approach is to buffer the spawn message in a local variable and emit both lines post-hoc only when `proc.returncode != 0`; if `Popen` itself raises, the spawn line should also be emitted (no `returncode` to check).
**Fix:** Replace "Wrap both in `if proc.returncode != 0:`" with the buffering pattern: assign `_spawn_msg = f"[subprocess] spawn …"` before `Popen`, then after exit code is known emit `_spawn_msg` + exit line conditionally on `proc.returncode != 0`. Note the `Popen`-raises edge case too.

### [NOTE] DIFF path in `bulk_files_with_diff` not covered by END FILE decision
**Section:** Decisions — bulk_files END FILE delimiters; Technical context — `bulk_files_with_diff`
**Issue:** `bulk_files_with_diff` has four `parts.append(...)` branches: three use `--- FILE: {p} ---` (lines 778, 784, 791) and one uses `--- DIFF: {p} ---` (line 788). The decision says "add `--- END FILE: {p} ---` after each file's content" but does not state whether DIFF entries also get the delimiter. The attribution risk that motivates the fix applies equally to DIFF entries.
**Fix:** Clarify whether `--- END FILE: {p} ---` should also follow DIFF entries, or document why that path is intentionally exempt.

## Verdict

GAPS_FOUND  
One feasibility gap in the spawn-log technical context; one NOTE on DIFF-path delimiter coverage.