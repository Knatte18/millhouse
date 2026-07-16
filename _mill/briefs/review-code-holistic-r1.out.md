MILL_REVIEW_BEGIN
# Review: Batch verify/baseline/completeness gates produce false positives or time out — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewed_file: plan/ + source
date: 2026-07-16
```

## Findings

### [BLOCKING] millpy-review-plan.py prepare-stage can crash uncaught on TaskHubError
**Location:** `plugins/mill/scripts/millpy-review-plan.py:132` (also `:177` for the except clause)
**Issue:** Card 12 adds `status_path = _paths.require_status_path(project_root, cfg)` inside the `--stage prepare` branch, but that branch's enclosing `try` (line 127) only has `except ReviewError as exc:` (line 177) — `TaskHubError` (a distinct, unrelated exception class per `_paths.py:360`) propagates uncaught out of `main()` instead of producing the standard JSON error envelope every other failure path in this CLI uses. The `full`-stage branch's identical new call (line 226) happens to be safe only because that branch has a broader `except Exception as exc:` at line 264 — an inconsistency between the two new call sites doing the same thing.
**Fix:** Report only — wrap the prepare-stage `require_status_path` call (or the resolution block) in its own try/except that also catches `TaskHubError`, or add a catch-all `except Exception` to the prepare branch matching the `full` branch's existing pattern.

### [BLOCKING] `cards_done` field name reused with conflicting types across envelopes
**Location:** `plugins/mill/templates/implementer-brief.md:70` vs `:105,113,118`
**Issue:** The pre-existing `status: incomplete` self-report envelope uses `"cards_done":N` as an **integer count** (line 70, unchanged by this plan). Card 5 introduces a new `status: success` envelope field with the **same name** `cards_done` but as a **JSON array of card-number integers** (lines 105/113/118). Both shapes appear in the same brief document an implementer LLM reads. If a model emits an int under `status: success` (following the sibling field's shape it just read), `_cards_incomplete_reason`'s `{int(x) for x in cards_done}` raises `TypeError` (int not iterable) and silently falls back to the old raw-commit-count heuristic — degrading, on that dispatch, exactly back to the #660 bug this batch exists to fix. It fails safe (no crash) but silently defeats the fix's purpose for that turn.
**Fix:** Report only — rename one of the two fields (e.g. `cards_completed_count` for the incomplete envelope, or `cards_done_ids` for the success envelope) so the two incompatible shapes are not addressable by implementer confusion under one identical key.

### [NIT] Hub's own mill-config.yaml documents a `done_gate` key that isn't present
**Location:** `mill-config.yaml:20`
**Issue:** Card 15 says to add `done_gate_baseline_preflight` "immediately below the existing `done_gate: null` line" in both files. The template (`plugins/mill/templates/mill-config.yaml:123-124`) has both keys; this hub's own `mill-config.yaml` has only `done_gate_baseline_preflight` (line 20) with a comment "see done_gate above" pointing at a key that does not exist in this file. Functionally harmless (`cfg.get` defaults to `None`), but the comment is misleading for anyone reading this file in isolation.
**Fix:** Report only — either add the missing `done_gate: null` line to this hub's config for consistency with the template, or reword the comment to not imply a sibling key is present here.

### [NIT] Same-directory removed-tag transitions with differing tag values silently pick one
**Location:** `plugins/mill/scripts/_implementer_common.py:1039-1042`
**Issue:** `removed_dirs.setdefault(dir_str, {"tag": tag, "files": []})` keeps only the first-seen tag per directory. If two files in the same package directory each remove a *different* single custom `//go:build` tag in the same batch, the second file's actual removed tag is silently dropped from the compile check (only the first file's tag is used for `go build -tags <tag>`). Not addressed by the plan's spec, and no test covers this multi-file/differing-tag case.
**Fix:** Report only — either run one compile check per distinct (dir, tag) pair, or detect the mismatch and skip with a logged reason.

### [NIT] `_done_gate.run_preflight` only guards `OSError`, narrower than the "never raise" wording
**Location:** `plugins/mill/scripts/_done_gate.py:71-79`
**Issue:** Card 14 requires "any unexpected failure ... also degrades to a stuck/blocked dict rather than propagating." The implementation catches only `OSError` around `subprocess.run(..., shell=True, ...)`. In practice launch failures under `shell=True` are almost always `OSError` subclasses, so this is low risk, but it's narrower than the stated contract.
**Fix:** Report only — broaden to `except Exception` to fully match the Shared Decision's "never raise" wording.

## Verdict

REQUEST_CHANGES
Two BLOCKING integration/design gaps (uncaught TaskHubError path; colliding `cards_done` field semantics) plus minor doc/edge-case NITs.
MILL_REVIEW_END
