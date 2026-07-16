# Batch: fixer-tier-warning

```yaml
task: "Miscellaneous small tooling and doc/template accuracy gaps"
batch: "fixer-tier-warning"
number: 1
cards: 5
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-reviewers.py test-millpy-fix.py
depends-on: []
```

## Batch Scope

Closes GitHub #651: `roles.fixer.model` is a config key fully independent from
`roles.code-review.<scope>.reviewer`, so an operator escalating the reviewer mid-task can
silently leave the fixer on a weaker model. This batch adds a non-blocking stderr warning,
emitted from `millpy-fix.py` at fix-dispatch time, comparing the fixer's resolved tier
against the code-review reviewer's resolved tier for the scope being fixed — plus a short
documentation comment in the config template. `roles.fixer.model` is read only by
`millpy-fix.py`'s code-review fixer dispatch (confirmed in `_mill/discussion.md`); no other
role/scope is compared. External interface for later batches: none — this batch is
self-contained and does not export anything another batch consumes.

## Cards

### Card 1: add tier-rank comparison helpers to `_reviewers.py`

- **Context:**
  - `plugins/mill/scripts/_agent_dispatch.py`
  - `plugins/mill/templates/mill-agents.yaml`
- **Edits:**
  - `plugins/mill/scripts/_reviewers.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add `import _agent_dispatch` to the existing import block (alongside
  `import _paths` and `from _config import deep_merge, resolve_plugin_template_path`, at
  lines 25-33). Add two module-level rank dicts directly below the existing
  `_NAME_REGEX = re.compile(...)` line (line 35): `_TIER_RANK = {"haiku": 0, "sonnet": 1,
  "opus": 2}` and `_EFFORT_RANK = {"low": 0, "medium": 1, "high": 2, "max": 3}`. Add
  `def tier_rank(spec: dict) -> tuple[int, int] | None:` that: returns `None` immediately
  when `spec.get("type") != "single"` or `spec.get("provider") != "claude"` (cluster types
  and non-Claude providers — e.g. the `gemini`-provider entries in `mill-agents.yaml` — have
  no defined ordering); otherwise resolves the model family by calling
  `_agent_dispatch.model_to_tier(spec["model"])` inside a `try/except ValueError:
  return None` guard (an unrecognized model family is also "not comparable"); on success,
  returns `(_TIER_RANK[family], _EFFORT_RANK.get(spec.get("effort"), 0))` — the `.get(...,
  0)` default means a spec with no `"effort"` key at all (e.g. the shipped `haiku`/
  `haiku_bulk` entries in `mill-agents.yaml`, which carry no `effort:` field) ranks as `0`
  (same as `"low"`) rather than raising. Add
  `def fixer_weaker_than_reviewer_warning(fixer_spec: dict, reviewer_spec: dict, *,
  fixer_name: str, reviewer_name: str, scope: str) -> str | None:` that calls `tier_rank` on
  both specs, returns `None` if either call returns `None`, returns `None` if
  `reviewer_tier <= fixer_tier` (tuple comparison), and otherwise returns exactly:
  `f"[fixer-tier] roles.fixer.model={fixer_name!r} is weaker than "
  f"roles.code-review.{scope}.reviewer={reviewer_name!r} -- consider escalating "
  f"roles.fixer.model to match."`. Update the module docstring's "Public API" list (lines
  8-21) to add two entries in the same one-line style as the existing `resolve`/
  `resolve_role` entries, documenting `tier_rank` and `fixer_weaker_than_reviewer_warning`.
- **Commit:** `feat(reviewers): add fixer/reviewer tier-rank comparison helper`

### Card 2: wire the warning into `millpy-fix.py` at fixer dispatch time

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/millpy-fix.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Immediately after the existing block that resolves `fixer_spec` (the
  `try: registry = _reviewers.load(git_root); fixer_spec = _reviewers.resolve(registry,
  model_name) except _reviewers.ReviewerError as e: ...` block, currently ending around
  `fixer_model = fixer_spec["model"]`), add a lookup of the code-review reviewer configured
  for this invocation's `--scope`: `reviewer_name =
  cfg.get("roles", {}).get("code-review", {}).get(args.scope, {}).get("reviewer")`. When
  `reviewer_name is not None`, resolve it via `_reviewers.resolve(registry, reviewer_name)`
  inside a `try/except _reviewers.ReviewerError: pass` (an unresolvable reviewer name is
  `validate_role_refs`'s concern elsewhere, not this warning's — do not raise or exit here).
  On successful resolution, call
  `_reviewers.fixer_weaker_than_reviewer_warning(fixer_spec, reviewer_spec,
  fixer_name=model_name, reviewer_name=reviewer_name, scope=args.scope)`; if it returns a
  non-`None` string, `print(warning, file=sys.stderr)` (the module already imports `sys`).
  This check must never change `main`'s control flow, exit code, or the JSON report on any
  branch — it is advisory stderr output only, alongside the module's existing
  `[cleanliness]`/error-style stderr prints.
- **Commit:** `feat(fix): warn when fixer.model is weaker than the code-review reviewer it fixes for`

### Card 3: document the escalation relationship in the config template

- **Context:** none
- **Edits:**
  - `plugins/mill/templates/mill-config.yaml`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In the `fixer:` block (currently two lines: `fixer:` then
  `  model: haiku`), insert two comment lines directly above `model: haiku`, indented to
  match the block's existing style (compare the `merge:` block's `# model: LLM alias for the
  merge-in sub-agent (haiku is sufficient for conflict resolution)` comment a few lines
  below for the established comment format in this file): `# roles.fixer.model and
  roles.code-review.<scope>.reviewer should generally be escalated` and `# together --
  millpy-fix.py warns (stderr, non-blocking) when it detects this asymmetry.`. Do not change
  the `model: haiku` value.
- **Commit:** `docs(config): note fixer/reviewer escalation relationship in template`

### Card 4: unit tests for the new `_reviewers.py` helpers

- **Context:**
  - `plugins/mill/scripts/_reviewers.py`
  - `plugins/mill/templates/mill-agents.yaml`
- **Edits:**
  - `plugins/mill/unit_tests/test-reviewers.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add test functions in this file's existing `def test_*() -> None:` +
  `print("PASS: ...")`-on-success style (see e.g. `test_validate_role_refs_catches_bad_fixer_model`
  for the closest existing pattern) covering `tier_rank`: `test_tier_rank_single_claude_returns_family_and_effort_rank`
  — `{"type": "single", "provider": "claude", "model": "claude-opus-4-7", "effort": "high"}`
  returns `(2, 2)`; `test_tier_rank_missing_effort_defaults_to_zero` — a spec with no
  `"effort"` key at all (e.g. `{"type": "single", "provider": "claude", "model":
  "claude-haiku-4-5-20251001"}`) returns `(0, 0)`; `test_tier_rank_non_claude_provider_returns_none`
  — the same spec shape with `"provider": "gemini"` returns `None`;
  `test_tier_rank_cluster_type_returns_none` — a spec with `"type": "cluster"` returns
  `None`. And covering `fixer_weaker_than_reviewer_warning`:
  `test_fixer_weaker_than_reviewer_warning_fires_when_reviewer_stronger` — a haiku-family
  fixer spec vs. an opus/high reviewer spec returns a non-`None` string containing both the
  `fixer_name=` and `reviewer_name=` values passed in;
  `test_fixer_weaker_than_reviewer_warning_silent_when_equal` — identical tier specs on both
  sides returns `None`; `test_fixer_weaker_than_reviewer_warning_silent_when_fixer_stronger`
  — an opus fixer spec vs. a haiku reviewer spec returns `None`;
  `test_fixer_weaker_than_reviewer_warning_silent_when_either_not_comparable` — one side
  non-Claude-provider or cluster-type returns `None` regardless of the other side's tier.
- **Commit:** `test(reviewers): cover tier_rank and fixer_weaker_than_reviewer_warning`

### Card 5: wiring test in `test-millpy-fix.py`

- **Context:**
  - `plugins/mill/scripts/millpy-fix.py`
  - `plugins/mill/scripts/_reviewers.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-millpy-fix.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add a test that extends this file's existing fixture config string
  (currently `"roles:\n  implementer:\n    self_fix_rounds: 2\n  fixer:\n    model:
  haiku\n"`, used by the happy-path tests) with a `code-review:` block naming a
  strictly-stronger reviewer for the scope under test, e.g.
  `"roles:\n  implementer:\n    self_fix_rounds: 2\n  fixer:\n    model: haiku\n
  code-review:\n    batch:\n      reviewer: opushigh\n"` for a `--scope batch` invocation
  (match whichever scope the existing happy-path fixture already dispatches — mirror
  `test_batch_happy_path`'s end-to-end `millpy_fix.main` invocation and stderr-capture
  pattern). Assert the captured stderr contains `"[fixer-tier]"`. Add a second test using a
  config where `roles.code-review.<scope>.reviewer` is absent (matching today's default
  fixture) and assert `"[fixer-tier]"` does NOT appear in captured stderr — the
  no-reviewer-configured case must stay silent.
- **Commit:** `test(fix): cover fixer-tier warning wiring in millpy-fix.py`

## Batch Tests

`verify:` runs `test-reviewers.py` and `test-millpy-fix.py` — the two files this batch adds
tests to (card 4 and card 5). Scoped via `run-all.py --only`, not the unbounded full suite.
