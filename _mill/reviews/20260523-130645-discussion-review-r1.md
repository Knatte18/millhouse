# Review: Migrate wiki task store to TinyDB

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax_tool
reviewed_file: _mill/discussion.md
date: 2026-05-23
```

## Findings

### [GAP] Migration steps omit group extraction logic
**Section:** Technical context → Migration logic (on_start)
**Issue:** Steps 2–3 say "parse with `_tasks_md.parse()`" but `Task` (line 63–69 of `_tasks_md.py`) exposes only `slug`, `title`, `phase`, `has_proposal`, `heading_line_no` — no group. Section headers (`# Layer D (isolated — run alone)`) are plain `#` headings; `_HEADING_RE` only matches `##` headings, so `parse()` discards them entirely. The migration steps make no mention of how `group` is assigned to each task document.
**Fix:** Add a migration sub-step describing how to walk raw Home.md text to attribute each task to its nearest preceding `# Layer <letter>` header (or `group=None` if none precedes it).

### [GAP] `status="blocked"` breaks `_tasks_md.parse()` round-trip
**Section:** Technical context → Data model; Testing → Unit tests
**Issue:** The data model includes `"blocked"` as a valid `status` value. `_tasks_md._VALID_PHASES` (line 56) is `(None, "s", "active", "ready-to-merge", "pr-pending", "done", "abandoned")` — `"blocked"` is absent. `_HEADING_RE` won't match `[slug] [blocked]`, so the unit test "Rendered Home.md parses cleanly with `_tasks_md.parse()`" would fail for any blocked task.
**Fix:** Either remove `"blocked"` from the stored `status` enum (map it to `None` on render, same as `"s"`) or note that `render()` omits the status marker for unrecognised values, and update the round-trip test to cover this case.

### [NOTE] `brief` extraction mechanism not described
**Section:** Technical context → Migration logic (on_start), step 3
**Issue:** `_tasks_md.parse()` returns heading metadata only — no body paragraphs. Extracting `brief` from "first non-empty paragraph of body text" requires a separate raw-text walk (from end-of-slug-line to next `##` heading), distinct from calling `parse()`.
**Fix:** Clarify in the migration steps that body/brief extraction is a raw markdown scan independent of `_tasks_md.parse()`, so a plan writer does not conflate the two.

## Verdict

GAPS_FOUND
Two incompatibilities between the spec and source: missing group-extraction logic in migration steps, and `"blocked"` status breaking the stated `_tasks_md.parse()` round-trip test.