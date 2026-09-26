# Batch: fixer-parent-guidance

```yaml
task: Ask the parent session when stuck (parent_thread)
batch: fixer-parent-guidance
number: 2
cards: 1
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-millpy-fix.py
depends-on: []
```

## Batch Scope

Adds the free-text channel the holistic fixer needs for parent guidance: an optional `--parent-guidance <path>` flag on `millpy-fix.py` and a `<PARENT_GUIDANCE>` token in `fixer-holistic-brief.md`, the only template `millpy-fix.py` renders.
Batch 4's `go-holistic-cap` and `go-handoff-nits` retries pass this flag.
It mirrors `--prior-blocking` exactly and is independent of every other batch.

## Cards

### Card 5: `millpy-fix.py --parent-guidance` and `<PARENT_GUIDANCE>` token

- **Context:**
  - `plugins/mill/scripts/_render.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-fix.py`
  - `plugins/mill/templates/fixer-holistic-brief.md`
  - `plugins/mill/unit_tests/test-millpy-fix.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - In `millpy-fix.py` `main`, add `parser.add_argument("--parent-guidance", default=None, help=...)` directly after the `--prior-blocking` argument.
    Help text: path to a file holding operator-level guidance from the task's parent session (written by mill-go after a parent escalation); rendered into the fixer brief; omit when there is none.
  - Bind `parent_guidance_path = Path(args.parent_guidance) if args.parent_guidance else None` next to the existing `prior_blocking_path` binding.
  - Next to the `prior_blocking_text` computation, compute `parent_guidance_text` with the identical rule: the file's text when the path is not `None`, `is_file()`, and its text is non-empty after `strip()`; otherwise `"(none)"`.
  - Pass `"PARENT_GUIDANCE": parent_guidance_text` in the `_render.render` token dict, after `"PRIOR_BLOCKING"`.
  - Add `--parent-guidance PATH` to the module docstring's `Flags:` list.
  - In `fixer-holistic-brief.md`: add `<PARENT_GUIDANCE>` to the leading comment's token list (after `<PRIOR_BLOCKING>`, described as operator-level guidance from the parent session, `"(none)"` when there is none).
    Add a `## Parent guidance` section directly after the `## Prior BLOCKING findings` section (before `## Fix discipline`) whose body is two lines — `This is operator-level direction from the session that spawned this task. Where it conflicts with your own judgment or a finding, follow it.` — then a blank line, then `<PARENT_GUIDANCE>`.
    `_render.render` raises `KeyError` on any unsubstituted body token, so the dict entry and the template token land in this one card.
  - Tests in `test-millpy-fix.py`, mirroring the three existing `--prior-blocking` tests (`test_stage_prepare_holistic_scope_prior_blocking_threaded_into_render`, `test_prior_blocking_omitted_renders_as_none`, `test_prior_blocking_empty_file_renders_as_none`) and placed directly after them: a non-empty `--parent-guidance` file's exact text reaches `mock_render.call_args[0][1]["PARENT_GUIDANCE"]`;
    the flag omitted renders `"(none)"`;
    an empty file renders `"(none)"`.
    Add one more test that renders the real `fixer-holistic-brief.md` through `_render.render` with every token `millpy-fix.py` passes (build the dict from the same keys, e.g. by capturing `mock_render.call_args[0][1]` from a prepare run and calling the real `_render.render(template_path, captured_dict)`) and asserts the output contains the guidance text and no literal `<PARENT_GUIDANCE>`.
- **Commit:** `feat(fix): add --parent-guidance flag and PARENT_GUIDANCE brief token`

## Batch Tests

`verify:` runs `test-millpy-fix.py`, which holds the new flag tests beside the existing `--prior-blocking` tests plus a real-template render check proving no `<PARENT_GUIDANCE>` token is left unsubstituted.
