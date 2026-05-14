# Batch: setup

```yaml
task: "(A) -- Benchmark Gemini single-reviewers vs sonnetmax baseline"
batch: setup
number: 1
cards: 2
verify: "PYTHONPATH=plugins/mill/scripts python -c \"from _reviewers import load; from pathlib import Path; load(Path('.wiki'))\""
depends-on: []
```

## Batch Scope

This batch adds four new reviewer registry entries to `wiki/reviewers.yaml` and creates the code-review fixture used by the bench script. After this batch, `_reviewers.load()` resolves `g3flash_preview`, `g3flash_preview_tool`, `g25pro`, and `g25pro_tool` without error, and `integration_tests/fixtures/sample-code.py` exists for use as the code-holistic artefact. The bench-script batch (batch 02) depends on both.

## Cards

### Card 1: Add Gemini reviewer registry entries

- **Context:**
  - `plugins/mill/scripts/_reviewers.py`
- **Edits:**
  - `.wiki/reviewers.yaml`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add four entries to `wiki/reviewers.yaml`, immediately after the existing `g25flash_tool:` block. Use `_paths.resolve_wiki_path(git_root)` to obtain the real wiki path; commit via `_wiki.write_commit_push`. Do NOT write to `.wiki/reviewers.yaml` (junction path) from Python. Entries to add verbatim:

  ```yaml
  g3flash_preview:
    type: single
    provider: gemini
    model: gemini-3-flash-preview

  g3flash_preview_tool:
    type: single
    provider: gemini
    model: gemini-3-flash-preview
    tooluse: true

  g25pro:
    type: single
    provider: gemini
    model: gemini-2.5-pro

  g25pro_tool:
    type: single
    provider: gemini
    model: gemini-2.5-pro
    tooluse: true
  ```

  No `effort:` field — Gemini CLI ignores it. After writing, call `_reviewers.load(wiki_path)` in-process to confirm no YAML parse error before returning.
- **Commit:** `feat(reviewers): add g3flash_preview, g3flash_preview_tool, g25pro, g25pro_tool`

### Card 2: Create sample-code.py code-review fixture

- **Context:**
  - `plugins/mill/integration_tests/fixtures/sample-plan/00-overview.md`
  - `plugins/mill/integration_tests/fixtures/sample-plan/01-core.md`
- **Edits:** none
- **Creates:**
  - `plugins/mill/integration_tests/fixtures/sample-code.py`
- **Deletes:** none
- **Requirements:** Write `plugins/mill/integration_tests/fixtures/sample-code.py` as the code artefact for bench-script code-holistic reviews. The file represents a completed implementation of what the sample-plan specifies — adding `render_cached()` to the `_render.py` template-rendering module. Plant the following bug: `render_cached()` uses `str.replace` in a loop over `values.items()` for substitution, which (a) silently leaves unresolved `<TOKEN>` placeholders when a key is absent from `values` (rather than raising `KeyError` as `render()` does), and (b) duplicates the `_TOKEN_RE.sub` machinery already in `render()`. This is the primary finding reviewers should catch. Write the file with this exact content:

  ```python
  """
  Single template-substitution helper used by every mill artefact format.

  Per the v2 format-discipline rules, every artefact type lives as a `.md`
  template in `plugins/mill/templates/` with `<PLACEHOLDER>` tokens.

  Public API:
      render(template_path, values)
      render_cached(template_path, values)
  """
  from __future__ import annotations

  import functools
  import re
  from pathlib import Path

  _TOKEN_RE = re.compile(r"<([A-Z][A-Z0-9_]*)>")


  def _strip_leading_comment(text: str) -> str:
      stripped = text.lstrip()
      if not stripped.startswith("<!--"):
          return text
      close = stripped.find("-->")
      if close == -1:
          return text
      after = stripped[close + len("-->"):].lstrip("\r\n")
      return after


  @functools.lru_cache(maxsize=None)
  def _read_template(path: Path) -> str:
      return _strip_leading_comment(path.read_text(encoding="utf-8"))


  def render(template_path: Path, values: dict[str, str]) -> str:
      text = _strip_leading_comment(template_path.read_text(encoding="utf-8"))
      missing: list[str] = []

      def replace(match: re.Match[str]) -> str:
          name = match.group(1)
          if name not in values:
              missing.append(name)
              return match.group(0)
          return values[name]

      rendered = _TOKEN_RE.sub(replace, text)
      if missing:
          raise KeyError(f"Unresolved template tokens: {sorted(set(missing))}")
      return rendered


  def render_cached(template_path: Path, values: dict[str, str]) -> str:
      """Cached variant of render() -- file read is memoised via lru_cache."""
      text = _read_template(template_path)
      result = text
      for name, val in values.items():
          result = result.replace(f"<{name}>", val)
      return result
  ```
- **Commit:** `feat(fixtures): add sample-code.py code-review fixture`

## Batch Tests

`verify:` runs `_reviewers.load(Path('.wiki'))` — passes if the four new entries parse without error. Card 2 has no runnable test; `sample-code.py` is a static fixture; visual inspection of the planted bug suffices.
