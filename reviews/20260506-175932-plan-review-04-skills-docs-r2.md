# Review: 12 (C) — Restructure hub junction layout — 04-skills-docs

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnetmax
reviewed_file: 04-skills-docs
date: 2026-05-06
```

## Findings

### [BLOCKING] Card 14 req 3 scope too narrow — mill-setup "When to invoke" retains `.millhouse/wiki`

**Step:** Card 14, requirement 3
**Issue:** Req 3 says "Update any junction **diagram** in the SKILL.md" — but mill-setup/SKILL.md "When to invoke" has a prose bullet `"When `.millhouse/wiki` junction is missing or broken"`, not a diagram. A literal reading of the requirement leaves this bullet unchanged; post-implementation the SKILL.md will still say `.millhouse/wiki` when it should say `.wiki`.
**Fix:** Change req 3 scope to "Update any **reference** in the SKILL.md" (or add an explicit sub-bullet for the "When to invoke" item).

### [NIT] Card 14 req 5 scope misses mill-spawn description paragraph

**Step:** Card 14, requirement 5
**Issue:** Req 5 says "If any **bullet list** in the SKILL.md references `status.md` at root…". The mill-spawn/SKILL.md description paragraph (not a bullet list) ends with "writes the initial `status.md`". After the batch this remains `status.md` instead of `task/status.md`.
**Fix:** Broaden req 5 to "any reference" (or add a sentence: "Also update the description paragraph's `status.md` reference to `task/status.md`").

### [NIT] Card 17 req 6 omits `discussion.md` → `task/discussion.md` from Board discipline

**Step:** Card 17, requirement 6
**Issue:** Req 6 lists `status.md`, `plan/`, `reviews/` for the Board discipline update but skips `discussion.md`. Current mill-merge Board discipline reads "Task state (`status.md`, `discussion.md`, `plan/`, `reviews/`)"; `discussion.md` will remain without a `task/` prefix.
**Fix:** Add `discussion.md` → `task/discussion.md` to req 6's list, or note that `task/` replaces all four paths.

## Verdict

REQUEST_CHANGES
One BLOCKING scope gap in Card 14 req 3 that would leave `.millhouse/wiki` in mill-setup's "When to invoke" bullet unchanged.