# Discussion: _config.py / _treeguard.py: silently-ignored config keys and unguarded str-vs-Path args

```yaml
task: _config.py / _treeguard.py: silently-ignored config keys and unguarded str-vs-Path args
slug: shared-helper-script-validation-gaps
status: discussing
parent: main
```

## Problem

This task bundles two independent shared-helper validation gaps, filed as GitHub #1007 and #986.

**#1007 — `_config.py` silently ignores legacy round-cap keys.** `_config.load_config` (via `warn_unknown_keys`, `plugins/mill/scripts/_config.py:112-126`) treats `pipeline.max_review_rounds` and `pipeline.max_discussion_review_rounds` in `config.local.yaml` exactly like any other typo: it prints a generic `[config] unknown key: ...` line to stderr and drops the value. The keys never had any effect — the real round cap lives at `roles.<role>.<scope>.rounds` (confirmed against `plugins/mill/templates/mill-config.yaml:136-186`; there is no `pipeline.max_review_rounds` field anywhere in the schema). An operator who sets `pipeline.max_review_rounds: 3` believing it caps every review loop is silently overridden by whatever `roles.*.rounds` says, with no failure and only a low-signal warning that repeats on every `load_config` call.

**#986 — `_treeguard.check_and_restore` has no argument-type guard.** Its signature (`plugins/mill/scripts/_treeguard.py:37`) declares `worktree: Path` and `git_root: Path | None`, but nothing enforces it. The actual failure is asymmetric between the two arguments: `worktree.relative_to(git_root)` at line 75 calls `.relative_to()` on `worktree` itself, so a plain `str` `worktree` raises `AttributeError: 'str' object has no attribute 'relative_to'` there — but only when `git_root` is not `None` (the nested-hub branch); in the flat-layout case (`git_root is None`) a `str` `worktree` reaches `_rebase_onto_hub` and other string-indexing code that happens to also work on `str`, so the bug is latent rather than crashing outright. A plain `str` `git_root`, by contrast, does **not** crash at line 75 — `Path.relative_to()` accepts a str/PathLike argument and coerces it — so today's code tolerates a `str` `git_root` by accident. Either way, neither argument is validated against its declared `Path` type, and the one crash that does occur (`str` `worktree`, nested-hub layout) is a raw, unlabeled `AttributeError` deep inside the function, with no indication of which argument is wrong. `_status.py` already solved this exact class of bug for its own `status_path` argument via a `_require_path` guard (`plugins/mill/scripts/_status.py:57-74`) that raises a clear `TypeError` naming the function and the bad argument. `_treeguard.py` never got the equivalent treatment for either of its `Path`-typed arguments.

Both bugs were verified live against this worktree's current code before writing this file (not just the linked issues' historical repro).

## Scope

**In:**
- `_config.py`: `warn_unknown_keys` gains a small corrective-hint table for the two named legacy keys (`pipeline.max_review_rounds`, `pipeline.max_discussion_review_rounds`), so their warning names the correct replacement key instead of the generic "unknown key" message.
- `_treeguard.py`: `check_and_restore` gains explicit `isinstance` guards on `worktree` and `git_root` (when not `None`), raising `TypeError` in the `_status._require_path` style, before any attribute access on either.
- Unit tests for both, added to the existing `plugins/mill/unit_tests/test-config.py` and `plugins/mill/unit_tests/test-treeguard.py`.

**Out:**
- Turning the generic unknown-key warning into a hard failure (`ConfigError`/`SystemExit`). Rejected below under Decisions — stays a warning for every key except the two explicitly named ones, which get a better message, not a different severity.
- "Honoring" `pipeline.max_review_rounds` by wiring it to actually set a round cap. Rejected below — there are five independent `roles.<role>.<scope>.rounds` settings (discussion-review, plan-review.holistic, plan-review.batch, code-review.holistic, code-review.batch); a single `pipeline.max_review_rounds` key cannot map onto one of them unambiguously.
- Adding the same `isinstance` guard to `check_and_restore`'s `tracked_root` parameter. It's typed `str` (not `Path`), and neither #986 nor the current code shows any str/Path confusion risk for it — only `worktree` and `git_root` are `Path`-typed and un-guarded.
- Any other shared helper in `plugins/mill/scripts/` beyond these two files (this task's own title scopes it to `_config.py` / `_treeguard.py`).
- The "warning prints twice per `load_config` call" noise mentioned in #1007 as an observation — that's a caller-side effect of the orchestrating skill calling `load_config` more than once per invocation, not a `_config.py` bug; out of scope for this file-scoped task.

## Decisions

### Legacy-key hint table, not auto-mapping and not a hard failure

- Decision: Add a module-level `RENAMED_KEY_HINTS: dict[str, str]` mapping the dotted legacy path to a one-line hint string (e.g. `"pipeline.max_review_rounds": "round caps now live at roles.<role>.<scope>.rounds, e.g. roles.plan-review.holistic.rounds -- this key has no effect"`). In `warn_unknown_keys`, when an unknown path is a key in this table, append the hint to the existing warning line instead of the bare `[config] unknown key: ...` text; every other unknown key keeps today's generic message unchanged. The module-level placement mirrors `ENV_REGISTRY` (`_config.py:44-51`), which is module-level; `deprecated_keys` (`_config.py:121`) is a function-local variable inside `warn_unknown_keys`, not module-level, so it's cited here only for the narrower point both share — a small, explicit table of known special-cased dotted paths, not a generic mechanism — not for placement.
- Rationale: The issue names three options (honor the key, fail loudly, or name the correct key in the warning) and picks none of them as mandatory, leaving it to this discussion. Naming the correct key is the only one of the three that doesn't require a judgment call this codebase can't make on the operator's behalf, and it directly satisfies the issue's own "Expected" text.
- Rejected: **Honor the key** — a single `pipeline.max_review_rounds` would have to fan out to some subset of five distinct `roles.*.rounds` settings; there's no non-arbitrary choice, and guessing wrong would be worse than the current silent-drop because it would look like it worked. **Fail loudly (raise on any unknown key)** — this function is deliberately permissive elsewhere (the `deprecated_keys` allowlist exists precisely because unknown-but-harmless keys are tolerated by design); turning the whole check into a hard error is a much bigger behavior change than this bug warrants and risks breaking existing installs with unrelated stale/typo'd keys that today are silently ignored.

### `_treeguard.py` gets its own module-local `_require_path`-style guard

- Decision: In `_treeguard.py`, at the top of `check_and_restore`, add inline `isinstance` checks:
  ```python
  if not isinstance(worktree, Path):
      raise TypeError(f"check_and_restore: worktree must be a pathlib.Path, got {type(worktree).__name__}")
  if git_root is not None and not isinstance(git_root, Path):
      raise TypeError(f"check_and_restore: git_root must be a pathlib.Path, got {type(git_root).__name__}")
  ```
  placed before the `_pygit2_util.status_porcelain(worktree, ...)` call (line 69), so a bad argument fails immediately rather than 6 lines later at the `.relative_to()` call. This is a small inline guard, not a shared cross-module helper.
- Rationale: `_status.py`'s `_require_path(status_path, fn_name)` is private (module-local, leading underscore) and issue #986 explicitly asks for "the same `_require_path`-style guard `_status.py` already uses" — style, not the literal function. `_treeguard.py:16-34`'s own `_rebase_onto_hub` docstring already documents and accepts this exact convention in this codebase: reimplementing a private helper locally rather than importing another module's underscore-prefixed internal. The message format (`"{fn}: {arg} must be a pathlib.Path, got {type}"`) is copied verbatim from `_status._require_path` for consistency across the two modules' error text. Both arguments get the guard even though only `worktree` can actually crash today (see Problem section above) — `git_root`'s current tolerance of `str` is an implementation accident of `Path.relative_to()`'s coercion, not a documented contract, and the declared signature says `Path | None` either way; guarding both closes the gap between the signature and its enforcement, not just the one crash path.
- Rejected: **Extracting a shared `_require_path` into a new common module** (e.g. `_argcheck.py`) and having both `_status.py` and `_treeguard.py` import it. Rejected as disproportionate to a two-argument, two-call-site fix, and it would touch `_status.py` (outside this task's scope) to refactor its existing, working private helper for a single new caller. **A single combined guard function taking both args** — rejected in favor of two separate `isinstance` checks so the `TypeError` message can name the exact offending parameter, matching `_status._require_path`'s one-argument-at-a-time precision.

## Technical context

- `plugins/mill/scripts/_config.py` — `warn_unknown_keys` (lines 112-126) is the only call site that needs to change; `walk_unknown_keys` (lines 88-109) and `load_config`'s call to `warn_unknown_keys` (line 322) are unaffected. The existing `deprecated_keys` frozenset-in-function pattern (line 121) is the direct precedent for where `RENAMED_KEY_HINTS` should live and how it should be consulted.
- `plugins/mill/scripts/_treeguard.py` — `check_and_restore` (lines 37-130) is the only function in this module; the guard goes at its top, before line 69's `_pygit2_util.status_porcelain(worktree, ...)` call. `Path` is already imported at the top of the file (line 5), so no new import is needed.
- `plugins/mill/scripts/_status.py:57-74` — `_require_path` is the reference pattern for both the guard shape and the exact `TypeError` message wording (`"{fn}: {arg} must be a pathlib.Path, got {type}"`).
- Every call site of `check_and_restore` across the skills (`mill-start/SKILL.md`, `mill-plan/SKILL.md`, `mill-go-base/SKILL.md`) already passes `worktree_root` and `git_root` as `Path` objects resolved via `_paths.py`; this fix does not require touching any call site — it only makes a future mistake fail clearly instead of confusingly (crashing for `str` `worktree` in the nested-hub case, or silently tolerating `str` `git_root` today) per #986's own framing ("easy to accidentally pass `str`... fail fast with a clear message instead of an opaque traceback").
- `plugins/mill/unit_tests/test-config.py:590-615` (`test_unknown_key_warning_emitted`) is the existing pattern for asserting stderr content from `warn_unknown_keys`/`load_config` — new tests for the hint table should follow this same tempdir + `mock_stderr` shape.
- `plugins/mill/unit_tests/test-treeguard.py` already imports `check_and_restore` directly (line 15) and calls it with a mix of positional and `git_root=` keyword forms (e.g. line 220, line 238); new type-guard tests slot in alongside the existing ones, calling with a plain `str` in place of `worktree`/`git_root` and asserting the `TypeError` and its message.

## Constraints

None beyond the codebase's standing conventions already covered under Technical context and Decisions (module-local guard duplication over cross-module extraction; warnings stay non-fatal; ASCII-only stderr — both new messages here are already plain ASCII, no `->`/em-dash substitution needed).

## Testing

- **`_config.py` (TDD candidate):** a new unit test asserting that setting `pipeline.max_review_rounds` (and separately `pipeline.max_discussion_review_rounds`) in `config.local.yaml` produces a stderr warning whose text names `roles.<role>.<scope>.rounds` (or the specific hint string chosen), following the `test_unknown_key_warning_emitted` shape. A second test confirms an unrelated unknown key (e.g. `pipeline.some_unrecognized_key`, as already covered by the existing test) still gets the plain generic message, not a hint — proving the hint table is scoped to exactly the two named keys and doesn't change behavior for anything else.
- **`_treeguard.py` (TDD candidate):** two new unit tests — one calling `check_and_restore("/some/str/path", "_mill")` (a plain `str` for `worktree`) and asserting `TypeError` with a message containing `"worktree"` and `"pathlib.Path"`; one calling `check_and_restore(<real Path>, "_mill", git_root="/some/str/path")` and asserting the same for `git_root`. Both should assert on the exact message shape (function name + arg name + `got <type>`), not just the exception type, so a future regression that changes the message silently is still caught.
- Both existing test files already have git/tempdir fixtures; no new fixture infrastructure is needed. Verify command (per CLAUDE.md's `PYTHONPATH=` prefix rule and `mill-plan/SKILL.md`'s per-batch `--only` scoping for a focused multi-file batch): `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-config.py test-treeguard.py`.

## Q&A log

- **Q:** Issue #1007 offers three options (honor the key, fail loudly, or name the correct key) with no operator present to choose. **A:** [auto-pick] Name the correct key via a small hint table, matching the issue's own "Expected" text and the codebase's existing `deprecated_keys`/`ENV_REGISTRY` precedent for special-cased dotted paths. **Why:** honoring the key is ambiguous (five candidate `roles.*.rounds` targets, no non-arbitrary pick) and failing loudly is a bigger, riskier behavior change than a two-issue bug-fix task warrants, given the function's existing deliberately-permissive design.
- **Q:** Should `_treeguard.py`'s new guard import `_status._require_path` directly, or reimplement it locally? **A:** [auto-pick] Reimplement locally as two inline `isinstance` checks. **Why:** `_require_path` is a private (underscore-prefixed) helper in `_status.py`; `_treeguard.py:16-34`'s own docstring already documents and follows this exact "reimplement the private helper locally" convention in this codebase (`_rebase_onto_hub` vs. `_cleanliness`'s private closure), so this fix follows established precedent rather than introducing a new cross-module coupling.
