# Review: 59 (A) — Small infra fixes batch 8

```yaml
verdict: APPROVE
reviewer_model: sonnetmax_tool
reviewed_file: _mill/discussion.md
date: 2026-05-17
```

## Findings

### [NOTE] `sys.platform` vs `os.name` idiom inconsistency (#305)
**Section:** Decision — test-vscode-processes posix mocks on Windows
**Issue:** The existing skip in the same file (line 273) uses `os.name != "nt"`; the discussion proposes `sys.platform != "win32"` for the two new guards — two idioms in one file.
**Fix:** Plan should normalise to one idiom; `os.name != "nt"` matches the existing convention and is the natural inversion of the `os.name == "nt"` check the file already uses.

### [NOTE] `resolve_deps_as_names` API description slightly off (#303)
**Section:** Decision — `_plan_validate` depends-on cross-check / Technical context
**Issue:** The discussion says "using `resolve_deps_as_names` (which already accepts int-or-string lists)" but the function signature is `resolve_deps_as_names(batches: list[dict]) -> dict[str, list[str]]` — it takes fully-shaped batch dicts, not a bare deps list; number-to-name resolution comes from the `number:` fields in those dicts.
**Fix:** Implementation note: for the per-batch-file side of the comparison the plan writer will need to synthesise a batch-dict (or inline-resolve using the overview's `number_to_name` map) rather than calling the function with a raw `[1, 2]` list.

## Verdict

APPROVE — discussion is complete and technically accurate; two minor implementation-clarity notes, neither blocks plan writing.