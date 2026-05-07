# Plan fixer report — round 4 holistic — rename-hub-junctions

```yaml
date: 2026-05-07T05:53:08Z
round: 4
note: holistic-only re-review (per-batch reviews from r3 are now stale; their findings were addressed in plan-fix-r4)
```

## Fixed

### From holistic-r3 (20260507-055135)

- **[BLOCKING-1] Card 8 req 1: `test_write_initial_status` git log path filter** (Card 8 Req 1)
  Updated Card 8 Req 1 to also change the git log path-filter argument from `"status.md"` to `"task/status.md"`. Card 4 changes the committed file path; the path filter must match.

- **[BLOCKING-2] Card 8 req 2: error-message substring check** (Card 8 Req 2)
  Updated Card 8 Req 2 from "no change needed" to update the error-substring check from `"git add status.md failed"` to `"git add task/status.md failed"`.

- **[NIT-1] Card 11 req 4e: `_build_tokens` is a dead branch** (Card 11 Req 4e)
  Removed the "if exposed, or replicate the dict here" wording. `_build_tokens` lives in `millpy-spawn.py` (a dash-named script not importable as a module); the only valid path is to replicate the dict inline.

- **[NIT-2] Card 9 req 3: both standard claim fixtures need distinct hub mock** (Card 9 Req 3)
  Updated Card 9 Req 3 to specify that both fixture blocks (lines ~83/88 and ~136/141) must change `resolve_hub_path` to return a distinct path. Removed the conditional language.

- **[NIT-3] Card 4: module-level public API docstring entry for `recreate_active_junction`** (Card 4 Req 5 added)
  Added new requirement to update the line ~51 module-level Public API docstring entry from the stale `(wiki_path, slug, mill_dir)` signature to the new `(slug, hub_root, container_path) -> None` signature.

## Pushed Back

None.

## Notes on stale per-batch reviews

The CLI's resumption logic re-ran only the holistic for round 3 (since round 3's holistic had errored out). The per-batch r3 review files (02, 03) are stale — their reported BLOCKINGs have been addressed in plan-fix-r3 and plan-fix-r4. The `blocking_count: 2` in the CLI's JSON envelope reflects those stale findings, not new ones.
