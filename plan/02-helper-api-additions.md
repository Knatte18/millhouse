# Batch: helper-api-additions

```yaml
task: 6 — mill-go SKILL.md prose + lock-API + lock-coverage + Builder-oppførsel
batch: helper-api-additions
cards: 4
verify: uv run --project "plugins/mill" python "plugins/mill/unit_tests/run-all.py"
depends-on: []
```

## Batch Scope

Four small, independent helper-API improvements that B04 depends on for the mill-go SKILL.md rewrite:

1. `_tasks_md.set_phase_at(path, slug, phase) -> None` wrapper so the orchestrator skill can flip a Home.md phase in one call instead of three (closes #28 / #49 / #51 / #61 / #76 / #98 — six independent TypeError sightings).
2. `_render.render` strips a leading HTML comment from any template before substitution, saving ~600 tokens per implementer call (closes #91).
3. `_llm_claude.run_implementer` adds `Skill` to its allowed-tools list so the implementer can invoke `@git-commit` (closes #97).
4. `implementer-brief.md` tightens the `## Report` section's `session_id` requirement to require literal echo of the `--session-id` UUID (closes #71 / #89 / #105 — four sightings; mill-go does not validate, fix is contract-only).

The external interface that B04 will consume:

- `_tasks_md.set_phase_at(path: Path, slug: str, phase: str | None) -> None` — does read → `set_phase` → write internally.
- `_render.render(template_path, values)` — auto-strips a leading `<!-- ... -->` block before substitution.
- `_llm_claude.run_implementer` — same Python signature, but the spawned implementer can now call `@git-commit` and any other skills.
- `implementer-brief.md` — unchanged structurally; the `## Report` section's `session_id` line is tightened.

## Cards

### Card 9: Add `_tasks_md.set_phase_at(path, slug, phase) -> None` wrapper

- **Reads:**
  - `plugins/mill/scripts/_tasks_md.py`
  - `plugins/mill/unit_tests/test-tasks-md.py`
- **Modifies:**
  - `plugins/mill/scripts/_tasks_md.py`
  - `plugins/mill/unit_tests/test-tasks-md.py`
- **Creates:** none
- **Requirements:** In `_tasks_md.py`, add `set_phase_at(path: Path, slug: str, phase: str | None) -> None` defined as: read `path` as UTF-8 → call existing `set_phase(text, slug, phase)` → write the result back to `path` as UTF-8. Update the module docstring's "Public API" block to list `set_phase_at` alongside `set_phase`. Keep pure `set_phase(text, ...)` unchanged so tests and any caller that already has the text in hand continue to work. In `test-tasks-md.py`, add tests for: (a) `set_phase_at` happy path — given a tempfile with a known Home.md heading, calling `set_phase_at(path, slug, "done")` rewrites the heading and writes it back; (b) `set_phase_at` raises `ValueError` on unknown slug (delegates to `set_phase`); (c) `set_phase_at` raises `ValueError` on invalid phase; (d) round-trip with `phase=None` strips an existing marker.
- **Commit:** `feat(_tasks_md): add set_phase_at path-taking wrapper`

### Card 10: `_render.render` strips a leading HTML comment

- **Reads:**
  - `plugins/mill/scripts/_render.py`
  - `plugins/mill/scripts/_status.py`
  - `plugins/mill/unit_tests/test-render.py`
- **Modifies:**
  - `plugins/mill/scripts/_render.py`
  - `plugins/mill/unit_tests/test-render.py`
- **Creates:** none
- **Requirements:** In `_render.py`, add a private `_strip_leading_comment(text: str) -> str` helper that mirrors the implementation in `_status._strip_leading_comment` (`_status.py:52-68`): drop a leading `<!-- ... -->` block at the very start of `text` (after `lstrip()` for whitespace tolerance), preserve mid-template comments verbatim, return `text` unchanged when no leading comment is present. Apply the strip inside `render()` after reading `template_path` and before token substitution (so unresolved-token detection runs against the post-strip body). Update the module docstring to document the auto-strip behaviour. In `test-render.py`, add tests for: (a) leading `<!-- doc -->` comment is removed before render; (b) mid-template `<!-- inline -->` comment is preserved verbatim; (c) template that is ONLY a comment (no body after `-->`) renders to empty string; (d) tokens inside the leading comment are NOT substituted (they are stripped first); (e) tokens after the leading comment ARE substituted as before.
- **Commit:** `feat(_render): strip leading HTML comment from templates`

### Card 11: Add `Skill` to `_llm_claude.run_implementer` allowed tools

- **Reads:**
  - `plugins/mill/scripts/_llm_claude.py`
  - `plugins/mill/unit_tests/test-llm-claude.py`
- **Modifies:**
  - `plugins/mill/scripts/_llm_claude.py`
  - `plugins/mill/unit_tests/test-llm-claude.py`
- **Creates:** none
- **Requirements:** In `_llm_claude.py`, change `run_implementer`'s `allowed_tools` literal from `"Read,Edit,Write,Bash,Grep,Glob"` to `"Read,Edit,Write,Bash,Grep,Glob,Skill"`. Update the function's docstring to list `Skill` alongside the other tools and explain why: "Skill is added so the implementer can invoke `@git-commit` (per implementer-brief.md) and any other skills the brief instructs." In `test-llm-claude.py`, find the existing test that asserts `run_implementer`'s argv contains `--allowedTools` followed by the tool list; update the expected string to include `Skill`. If no such test exists, add one that calls `run_implementer` with a patched `_subprocess_util.run` and asserts the captured argv contains `"--allowedTools"` immediately followed by `"Read,Edit,Write,Bash,Grep,Glob,Skill"`.
- **Commit:** `feat(_llm_claude): add Skill tool to run_implementer`

### Card 12: Tighten `implementer-brief.md` `session_id` contract

- **Reads:**
  - `plugins/mill/templates/implementer-brief.md`
- **Modifies:**
  - `plugins/mill/templates/implementer-brief.md`
- **Creates:** none
- **Requirements:** In `implementer-brief.md`'s `## Report` section, find the description of the `session_id` field in the JSON shape (currently a placeholder `"session_id":"<this-session-id>"`). Add an explicit one-paragraph requirement immediately after the JSON example: "**`session_id` MUST be the exact UUID passed to you via the `--session-id` flag (you can read it from your own command-line arguments or echo it as given). Do not invent or paraphrase the value. mill-go uses this field to correlate the report with the spawned session.**" Apply the same wording in the "stuck" JSON example block. Do not remove the existing leading HTML documentation comment — Card 10 makes `_render.render` strip it automatically; the comment stays in source for human readers. Do remove the line "Strip this HTML comment before the prompt is sent." since the strip is now automatic; replace it with "(`_render.render` strips this comment automatically.)".
- **Commit:** `docs(implementer-brief): tighten session_id literal-echo requirement`

## Batch Tests

`verify:` runs the full unit-test suite. Every code change in this batch ships with paired unit-test extensions (Cards 9, 10, 11). Card 12 is a template-prose change with no automated test — coverage is provided by the next mill-go integration run (the implementer-brief is rendered every batch) and by the `_render` strip test in Card 10 (which exercises the brief template indirectly via the leading-comment-strip test).
