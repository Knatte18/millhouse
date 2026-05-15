# Discussion: Make implementer model configurable via config.yaml

```yaml
task: Make implementer model configurable via config.yaml
slug: implementer-model-config
status: discussing
parent: main
```

## Problem

`_implementer_sonnet.py` hardcodes both the module name ("sonnet") and the model ID (`claude-sonnet-4-6`). Switching to a cheaper model (Haiku for fast runs) or a stronger model (Opus for hard tasks) requires editing source code. Reviewer models have been configurable via named entries in `reviewers.yaml` since the beginning; the implementer never got the same treatment.

The prerequisite `sonnethigh` entry is already present in `reviewers.yaml`. This task wires up the same config-driven model selection for the implementer and, as a prerequisite, renames `reviewers.yaml` to `agents.yaml` so the shared registry isn't misleadingly named after only one consumer.

## Scope

**In:**
- Rename `_implementer_sonnet.py` → `_implementer_claude.py`; add `model` and `effort` parameters to `run()`
- Rename `wiki/reviewers.yaml` → `wiki/agents.yaml` (live wiki + `wiki-config.yaml` template)
- Update `_reviewers.py` to load from `agents.yaml` with fallback to `reviewers.yaml` for backward compatibility
- Update `_test_registry.py` to write `agents.yaml` instead of `reviewers.yaml`
- Add `haiku` entry to `wiki/agents.yaml` (no `effort` field)
- Add `roles.implementer.model: sonnethigh` to `wiki/config.yaml` and `wiki-config.yaml` template
- Update `millpy-implement.py`, `millpy-implement-holistic.py`, `millpy-merge-in-subagent.py` to read the named entry from config, resolve it via `_reviewers`, and pass `model` + `effort` to the implementer
- Extend `validate_role_refs` in `_reviewers.py` to also validate `roles.implementer.model`
- Update all unit tests: rename mock targets, update `_test_registry` usages, add model-from-config assertions

**Out:**
- Renaming the Python module `_reviewers.py` to `_agents.py` — only the YAML data file is renamed; the Python module rename is a separate task
- Non-Claude implementers (ollama, gemini, codex) — `_implementer_claude.py` is Claude-only; the naming makes room for future providers, but no other providers are implemented here
- Changes to existing named entries in `agents.yaml` (sonnetmax, sonnethigh, sonnetmedium, etc. stay as-is)
- Effort as a separate config key — effort is already encoded in the named entry (e.g. `sonnethigh` implies high effort)

## Decisions

### Module renamed to `_implementer_claude.py`

- Decision: rename `_implementer_sonnet.py` to `_implementer_claude.py`.
- Rationale: provider-named mirrors `_llm_claude.py`; leaves room for `_implementer_ollama.py` and `_implementer_gemini.py` as parallel files later.
- Rejected: `_implementer.py` (doesn't indicate provider; ambiguous when multiple providers exist); keeping the old name (misleads readers into thinking the model is fixed to Sonnet).

### `reviewers.yaml` renamed to `agents.yaml`

- Decision: rename `wiki/reviewers.yaml` to `wiki/agents.yaml`. The shared registry holds named model profiles used by both reviewers and implementers.
- Rationale: `reviewers.yaml` is misleading when implementer entries also live there. A separate `implementers.yaml` would be structurally identical — pure duplication.
- Rejected: separate `implementers.yaml` (acknowledged duplication, wrong long-term shape).

### `_reviewers.py` Python module NOT renamed

- Decision: `_reviewers.py` keeps its name; only the YAML data file changes.
- Rationale: renaming `_reviewers.py` touches all review scripts and all review-related unit tests — a larger refactor than this task warrants.
- Follow-up: a dedicated rename task can do it cleanly once this task is merged.

### Named entries instead of raw model IDs in config

- Decision: `roles.implementer.model: sonnethigh` — a name that resolves in `agents.yaml`, not a raw model ID string.
- Rationale: consistent with how reviewer models are configured; model version pinning happens in one place (`agents.yaml`); no duplication of model strings across config.
- Rejected: `roles.implementer.model: claude-sonnet-4-6` (raw ID in config; must be updated in two places when models change).

### Effort is implicit in the named entry, not a separate key

- Decision: effort is a field inside the named `agents.yaml` entry (e.g. `sonnethigh` has `effort: high`). There is no separate `roles.implementer.effort` key.
- Rationale: effort and model are tightly coupled; the name encodes the combination. Separating them creates a config surface where `model: sonnethigh` + `effort: low` produces contradictory config.
- Rejected: `roles.implementer.effort` alongside `model` (redundant and ambiguous).

### Haiku: effort silently absent

- Decision: the `haiku` entry in `agents.yaml` has no `effort` field. `_implementer_claude.run()` receives `effort=None`; `_llm_claude.run_implementer` already handles `effort=None` by omitting `--effort` from the Claude CLI invocation.
- Rationale: Haiku does not support extended thinking; the named entry simply lacks the field. No model-sniffing required.
- Rejected: detect "haiku" in the model name and skip effort (adds model-sniffing logic, brittle).

### Backward compatibility via fallback in `_reviewers.load()`

- Decision: `_reviewers.load()` tries `agents.yaml` first; if absent, falls back to `reviewers.yaml` with a deprecation note in the error path.
- Rationale: existing external hubs won't break after `update-plugins`. The user's own wiki is renamed as part of this task's implementation batch (wiki is locked during the rename commit).
- Rejected: hard rename with no fallback (breaks every external hub immediately after plugin update).

### `validate_role_refs` extended to cover implementer

- Decision: add a check for `roles.implementer.model` inside `validate_role_refs` so config errors are caught at startup rather than at dispatch time.
- Rationale: consistent with how reviewer role refs are validated; catches typos in the named entry before a batch starts.
- Implementation note: the implementer check is structurally different from reviewer checks (it reads `.model` not `.reviewer`), so the new check is a dedicated code path, not a fold into the existing loop.

## Technical context

### Files changed

| File | Change |
|---|---|
| `plugins/mill/scripts/_implementer_sonnet.py` | Delete (replaced by `_implementer_claude.py`) |
| `plugins/mill/scripts/_implementer_claude.py` | New file — same structure as old, `run()` accepts `model` and `effort` as required kwargs |
| `plugins/mill/scripts/_reviewers.py` | `load()` path: `agents.yaml` with fallback; `validate_role_refs` extended for implementer |
| `plugins/mill/scripts/_test_registry.py` | `write_to()` writes `agents.yaml` instead of `reviewers.yaml` |
| `plugins/mill/scripts/millpy-implement.py` | Import `_implementer_claude`; read `roles.implementer.model`; resolve spec; pass `model`+`effort` |
| `plugins/mill/scripts/millpy-implement-holistic.py` | Same pattern as above |
| `plugins/mill/scripts/millpy-merge-in-subagent.py` | Same pattern as above |
| `plugins/mill/templates/wiki-config.yaml` | Add `roles.implementer.model: sonnethigh`; update comments referencing `reviewers.yaml` → `agents.yaml` |
| `wiki/config.yaml` (live wiki) | Add `roles.implementer.model: sonnethigh` |
| `wiki/agents.yaml` (live wiki, renamed from `reviewers.yaml`) | Add `haiku` entry; rename commit with wiki lock |
| Unit tests (4 files) | Update mock targets and fixture writes; add model-from-config assertions |

### `_implementer_claude.py` API

```python
def run(
    prompt_text: str,
    *,
    model: str,          # required: model ID from resolved agents.yaml entry
    effort: str | None,  # required: effort string or None (omits --effort flag)
    session_id: str | None = None,
    resume: bool = False,
    cwd: Path | str | None = None,
    timeout: int = 1800,
) -> tuple[str, str]:
    return run_implementer(prompt_text, model=model, effort=effort, ...)
```

Both `model` and `effort` are required kwargs (not defaulted) so callers can't accidentally use a stale default.

### Config reading in the three CLI scripts

Pattern to add after `timeout` is read (same in all three scripts):

```python
implementer_cfg = cfg.get("roles", {}).get("implementer", {})
model_name = implementer_cfg.get("model", "sonnethigh")
registry = _reviewers.load(wiki_path)
impl_spec = _reviewers.resolve(registry, model_name)
impl_model = impl_spec["model"]
impl_effort = impl_spec.get("effort")
```

Then replace **every** `_implementer_sonnet.run(...)` call with `_implementer_claude.run(..., model=impl_model, effort=impl_effort)`. Note that `millpy-implement.py` has **two** call sites (initial dispatch and fix-cycle resume), `millpy-merge-in-subagent.py` has **two** call sites (conflicts mode and verify-fix mode), and `millpy-implement-holistic.py` has **one** call site. All must be updated.

### `_reviewers.load()` fallback logic

```python
path = wiki_root / "agents.yaml"
if not path.exists():
    path = wiki_root / "reviewers.yaml"
if not path.exists():
    raise ReviewerError(f"Missing registry at {wiki_root / 'agents.yaml'}")
```

### `validate_role_refs` extension

After the existing reviewer-walking loop, add:

```python
impl_model = cfg.get("roles", {}).get("implementer", {}).get("model")
if impl_model is not None:
    try:
        resolve(registry, impl_model)
    except ReviewerError as exc:
        errors.append(f"roles.implementer.model={impl_model!r}: {exc}")
```

### `agents.yaml` haiku entry

```yaml
haiku:
  type: single
  provider: claude
  model: claude-haiku-4-5-20251001
```

No `effort` field. All existing entries (sonnetmax, sonnetmax_tool, sonnetmedium, opusmax, sonnethigh) carry over unchanged.

### Wiki lock requirement

The `wiki/reviewers.yaml` → `wiki/agents.yaml` rename must happen inside a wiki-lock window (acquired via `_wiki.wiki_lock`). The implementer batch that touches the live wiki should commit `agents.yaml` (added) and delete `reviewers.yaml` in a single `git -C <wiki_path> commit` so no window exists where both or neither file is present.

### `_test_registry.py` update

`write_to()` changes from `wiki_root / "reviewers.yaml"` to `wiki_root / "agents.yaml"`. All tests that call `_test_registry.write_to(wiki_root)` continue to work unchanged — the path is encapsulated in the helper. Tests in `test-reviewers.py` that write directly to `wiki_root / "reviewers.yaml"` must be updated to write `wiki_root / "agents.yaml"` instead.

## Testing

### `test-millpy-implement.py`

- Update all mock targets: `millpy_implement._implementer_sonnet` → `millpy_implement._implementer_claude`
- Add mocks for `_reviewers.load` (returns a registry dict) and `_reviewers.resolve` (returns a resolved spec with `model` and `effort`) — consistent with how all other external I/O is mocked in these tests. Do NOT call `_test_registry.write_to()` here; the implement test files never set up a file-based wiki fixture.
- Update the mock config (returned by `mock_load_config`) to include `roles.implementer.model: sonnethigh` alongside the existing keys
- Add: verify that `_implementer_claude.run` receives the correct `model` and `effort` values from the resolved spec
- Add: config missing `roles.implementer.model` → falls back to `sonnethigh` default (test with a config that omits the key)

### `test-millpy-implement-holistic.py`

- Same mock target update, same `_reviewers.load` + `_reviewers.resolve` mock pattern, same model-from-config assertion

### `test-millpy-merge-in-subagent.py`

- Same mock target update, same `_reviewers.load` + `_reviewers.resolve` mock pattern

### `test-reviewers.py`

- Update all direct `wiki / "reviewers.yaml"` writes to `wiki / "agents.yaml"`
- Add: `load()` raises when neither `agents.yaml` nor `reviewers.yaml` exists
- Add: `load()` succeeds when only `reviewers.yaml` exists (backward compat fallback)
- Add: `validate_role_refs()` catches a bad `roles.implementer.model` reference

### `test-review-cli.py`

- Update the one direct `reviewers.yaml` write to `agents.yaml`

## Q&A log

- **Q:** What to name the renamed implementer module? **A:** `_implementer_claude.py` — provider-named, mirrors `_llm_claude.py`, leaves room for future provider variants.
- **Q:** Should `millpy-merge-in-subagent.py` be updated alongside the two implement scripts? **A:** Yes — it also imports `_implementer_sonnet` and must be updated.
- **Q:** Should `effort` be separately configurable in config? **A:** Yes, but it's implicit in the named entry — `sonnethigh` encodes both model and effort; no separate key needed.
- **Q:** Raw model IDs or named entries (like reviewers) for the implementer? **A:** Named entries from a shared registry — same pattern as reviewers.
- **Q:** Should `reviewers.yaml` be renamed since implementers would use it too? **A:** Yes, rename to `agents.yaml`. A separate `implementers.yaml` with identical structure is pure duplication.
- **Q:** Should `_reviewers.py` also be renamed to `_agents.py`? **A:** No — deferred to a follow-up task. Only the YAML data file is renamed in this task.
- **Q:** What happens if someone configures `haiku` with an effort setting? **A:** The `haiku` entry in `agents.yaml` has no `effort` field, so `impl_effort` is `None` regardless of anything else. No model-sniffing required.
- **Q:** Backward compatibility for external hubs that still have `reviewers.yaml`? **A:** `_reviewers.load()` falls back to `reviewers.yaml` if `agents.yaml` is absent.
