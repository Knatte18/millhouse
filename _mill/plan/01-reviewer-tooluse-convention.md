# Batch: reviewer-tooluse-convention

```yaml
task: "Track _mill/briefs/ instead of gitignoring them"
batch: reviewer-tooluse-convention
number: 1
cards: 5
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-reviewers.py test-large-prompt-switch.py test-config.py
depends-on: []
```

## Batch Scope

Flip the reviewer naming convention across the whole catalogue and every consumer:
tool-use becomes the unsuffixed default (explicit `tooluse: true`), bulk becomes the
`_bulk`-suffixed opt-in (`tooluse: false`), and all `*_tool` names are retired. This
batch rewrites `mill-agents.yaml`, repoints all config roles, updates the test-registry
fixtures and the unit tests that assert on them, updates the integration-test configs,
and locks the convention with a catalogue test. It is one batch because every card is a
facet of a single rename and they share the same small set of config/registry files. No
production code logic changes — flipping reviewers to `tooluse: true` is what stops
bulking (the prepare stage already branches on mode), so the bulk code is reached only
via the new `_bulk` names.

## Cards

### Card 1: Rewrite mill-agents.yaml to the symmetric tool-use/_bulk scheme

- **Context:**
  - `plugins/mill/scripts/_reviewers.py`
- **Edits:**
  - `plugins/mill/templates/mill-agents.yaml`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Rewrite the catalogue so that for each distinct model/effort/provider
  combo currently present there are exactly two entries: an unsuffixed entry with an
  explicit `tooluse: true` (the tool-use default) and a `<name>_bulk` entry with
  `tooluse: false`. Remove every `*_tool` key (its behaviour is now the unsuffixed name).
  Preserve each entry's existing `model`, `provider`, `effort`, `timeout`, and
  `type: single` fields; only add the `tooluse` flag. The 10 combos to produce as
  `<name>` + `<name>_bulk` pairs: `g25flash`, `g25pro`, `g3flash_preview` (provider
  `gemini`); `haiku`; `opushigh`, `opusmax`, `opusmedium` (provider `claude`, model
  `claude-opus-4-7`, efforts high/max/medium); `sonnethigh`, `sonnetmax`, `sonnetmedium`
  (provider `claude`, model `claude-sonnet-4-6`, efforts high/max/medium). Result: 20
  entries. Keep the file's existing header comment, updating it to describe the new
  convention; in that comment note that `tooluse` is consumed only by reviewer dispatch
  and is irrelevant for entries used as implementer/fixer/merge models (e.g. `haiku`), so
  `tooluse: true` on such an entry is harmless and the convention still applies uniformly.
- **Commit:** `refactor(agents): make tool-use the default name, _bulk the suffixed exception`

### Card 2: Point reviewer roles and the schema example at tool-use names

- **Context:**
  - `plugins/mill/templates/mill-agents.yaml`
- **Edits:**
  - `plugins/mill/templates/mill-config.yaml`
  - `mill-config.yaml`
  - `plugins/mill/templates/review-output.schema.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In both `mill-config.yaml` files, repoint every reviewer role to a
  tool-use (unsuffixed) name: `roles.discussion-review.holistic.reviewer` `sonnetmax_tool`
  → `sonnetmax`; `roles.plan-review.holistic.reviewer` stays `sonnetmax` (now tool-use);
  `roles.plan-review.batch.reviewer` (if non-null in the template) likewise unsuffixed;
  `roles.code-review.holistic.reviewer` stays `sonnethigh`; `merge.model` stays
  `sonnethigh`. No role may reference a `*_tool` or `*_bulk` name. Keep the plugin template
  and the hub `mill-config.yaml` in sync per CLAUDE.md. In `review-output.schema.md`,
  update the `reviewer_model` metadata-fields table row (currently
  `(e.g. \`sonnetmax\`, \`sonnetmax_tool\`)`) to drop `sonnetmax_tool`, e.g.
  `(e.g. \`sonnetmax\`, \`sonnethigh\`)`. The line-14 example is already `sonnetmax` and
  needs no change. Confirm `grep sonnetmax_tool plugins/mill/templates/review-output.schema.md`
  returns nothing afterward.
- **Commit:** `refactor(config): point reviewer roles at tool-use names`

### Card 3: Update test-registry baseline and the assertions that depend on it

- **Context:**
  - `plugins/mill/scripts/_reviewers.py`
- **Edits:**
  - `plugins/mill/scripts/_test_registry.py`
  - `plugins/mill/unit_tests/_test_registry.py`
  - `plugins/mill/unit_tests/test-reviewers.py`
  - `plugins/mill/unit_tests/test-large-prompt-switch.py`
  - `plugins/mill/unit_tests/test-config.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In both `_test_registry.py` copies, change `make_minimal_registry`'s
  baseline so it contains `sonnetmax` with explicit `tooluse: True` (tool-use) and a new
  `sonnetmax_bulk` entry with `tooluse: False`; remove the `sonnetmax_tool` key. Update the
  docstring line "Contains sonnetmax (bulk) and sonnetmax_tool (tool-use)..." to match.
  Then fix the consumers so each assertion still tests its original intent:
  in `test-reviewers.py`, the inline-YAML registry test that asserts
  `registry["sonnetmax_tool"]["tooluse"] is True` → rename the fixture key to a tool-use
  name and assert against it; the resolver test asserting `resolve(registry, "sonnetmax")`
  yields `tooluse is False  # defaulted` → point it at a spec that OMITS `tooluse`
  entirely (construct an inline no-`tooluse` spec) so it still verifies the default-False
  path, since baseline `sonnetmax` now sets `tooluse: true` explicitly. In
  `test-large-prompt-switch.py` and `test-config.py`, replace `sonnetmax_tool` with
  `sonnetmax`, and use `sonnetmax_bulk` wherever the test's intent is a bulk/`tooluse:false`
  reviewer. After editing, confirm `grep sonnetmax_tool plugins/mill/unit_tests` returns
  no remaining references.
- **Commit:** `test(reviewers): update fixtures and assertions to the new reviewer naming`

### Card 4: Update integration-test reviewer configs

- **Context:**
  - `plugins/mill/templates/mill-agents.yaml`
- **Edits:**
  - `plugins/mill/integration_tests/test-review-code.py`
  - `plugins/mill/integration_tests/test-review-discussion.py`
  - `plugins/mill/integration_tests/test-review-plan.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In each integration test's inline `_CONFIG_YAML`, update reviewer
  names to the new convention: `discussion.holistic: sonnetmax_tool` → `sonnetmax`;
  `plan.batch: sonnetmax`, `plan.holistic: sonnetmax`, and `code.reviewer: sonnetmax`
  stay `sonnetmax` (now tool-use). If a test deliberately exercises bulk behaviour, use
  `sonnetmax_bulk` instead; otherwise tool-use `sonnetmax`. Every referenced name must
  exist in the catalogue after Card 1.
- **Commit:** `test(integration): update reviewer names to the tool-use convention`

### Card 5: Lock the catalogue naming convention with a test

- **Context:**
  - `plugins/mill/templates/mill-agents.yaml`
  - `plugins/mill/scripts/_reviewers.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-reviewers.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add a test (e.g. `test_agents_catalogue_naming_convention`) that loads
  `plugins/mill/templates/mill-agents.yaml` (resolve the path via the module's existing
  `HUB` root pattern) and asserts every entry obeys the convention: a key that does NOT
  end in `_bulk` has `tooluse` present and `True`; a key ending in `_bulk` has `tooluse`
  present and `False`; and no key ends in `_tool`. Follow the existing test style in the
  file (return int error count or assert-based, matching siblings). Add a short comment in
  the test noting that `tooluse` is reviewer-only and the convention is applied uniformly,
  so entries used as implementer/merge models (e.g. `haiku`) still assert `tooluse: True`
  by design — this is not an oversight.
- **Commit:** `test(agents): lock the tool-use/_bulk naming convention`

## Batch Tests

`verify` runs `test-reviewers.py`, `test-large-prompt-switch.py`, and `test-config.py`
via `run-all.py --only` — the three unit suites that consume the test-registry baseline
or reference reviewer names and are affected by Cards 3 and 5. The integration tests
(`test-review-*.py`) invoke a real LLM and are NOT part of `verify`; Card 4 keeps their
configs internally consistent and is validated by review. `mill-agents.yaml`,
`mill-config.yaml`, and `review-output.schema.md` are data/doc files with no direct unit
test beyond the Card 5 convention test (which runs inside `test-reviewers.py`).
