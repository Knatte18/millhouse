# Batch: finalize-completeness-and-baseline-robustness

```yaml
task: mill-go/mill-merge-in orchestration robustness gaps, round 2
batch: finalize-completeness-and-baseline-robustness
number: 1
cards: 4
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-implementer-common.py test-verify-baseline.py
depends-on: []
```

## Batch Scope

Fixes four robustness gaps in the shared finalize/baseline-classification code path in
`_implementer_common.py` and `_verify_baseline.py` (`_mill/discussion.md` Decisions
`baseline-signature-extraction-non-test-failure` #1060, `fixer-incomplete-recovery-ancestor-check`
#1104, `self-resolve-finalize-full-history-fallback` #1061, `baseline-preflight-lazy-already-landed`
#1089). All four touch the same failure-classification/completeness machinery inside
`_forward_output`/`_run_verify_gates`, so they are one batch. External interface: no public function
signature loses backward compatibility — every new parameter is optional/keyword with a default that
preserves today's behavior for every existing caller that doesn't pass it.

## Cards

### Card 1: synthesize a signature for a non-test-format verify failure

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_implementer_common.py`
  - `plugins/mill/scripts/_verify_baseline.py`
  - `plugins/mill/unit_tests/test-implementer-common.py`
  - `plugins/mill/unit_tests/test-verify-baseline.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  `_implementer_common._extract_failure_signatures(output: str) -> list[str]` only recognizes four
  test-runner failure shapes via `_FAILURE_MARKER_PREFIXES` (`"--- FAIL:", "FAIL\t", "FAILED ", "---
  FAIL ", "FAIL -- "`). A verify command chaining a non-test tool ahead of tests (e.g. `go vet ./...
  && go test ./...`) that fails at the non-test stage produces zero matching lines, so today the
  function returns `[]` even though the command's own exit code is non-zero.
  Add a new keyword parameter `returncode: int | None = None` to
  `_extract_failure_signatures`. After computing the existing `matches = [line for line in
  output.splitlines() if line.startswith(_FAILURE_MARKER_PREFIXES)]`, when `returncode` is not `None`
  and not `0` and `matches` is empty, append exactly one synthetic signature line built from the
  first non-empty line of `output` (stripped, truncated to 200 characters) in the fixed, clearly-synthetic
  form `f"NONZERO_EXIT: exit {returncode}: {first_line}"` — pick a prefix that does not collide with
  any entry in `_FAILURE_MARKER_PREFIXES` and is easy to recognize as synthetic in a status.md dump.
  When `output` has no non-empty line, use the literal string `"(no output)"` for `first_line`. Return
  `matches` unchanged (do not append) when `returncode` is `None` or `0`, or when `matches` is
  already non-empty — the synthetic signature exists only to give an otherwise-empty signature set
  something comparable for the subset-diff waiver in `_run_verify_gates`; a command that already
  produces recognized FAIL-format lines needs no synthetic addition.
  Known limitation, accepted rather than engineered around: `_verify_baseline._signatures_for_pair`
  unions two runs' `_extract_failure_signatures` output via exact-string dedup, so if the embedded
  `first_line` differs between the two corroboration runs (possible for an intrinsically
  non-deterministic failure), the two runs produce two distinct persisted entries instead of one.
  This is a non-issue for the target class this card fixes (a compiler/linter diagnostic like `go
  vet` is deterministic across runs on identical content — its first output line does not vary), and
  a broader failure class already has no stronger baseline-comparison guarantee today. Document this
  explicitly in `## Batch Tests` rather than adding cross-run normalization logic.
  Update both authoritative call sites to pass the known return code: in `_run_verify_gate` (this
  same file), the call at the line reading `signatures = _extract_failure_signatures(output)` runs
  inside the `if result.returncode != 0:` block (and after the optional dotnet-lock retry, whose own
  `retry_result.returncode` is the correct value at that point) — pass `returncode=result.returncode`
  (or `retry_result.returncode` when the retry branch ran). Do NOT change the second call in the same
  function, `fail_lines = _extract_failure_signatures(omitted)[:20]` (the truncated-output display
  excerpt) — leave it with no `returncode` argument, since it is a display-only summary of the
  omitted portion, not the authoritative signature set the baseline/waiver logic compares.
  In `_verify_baseline.py`'s `_signatures_for_pair`, the loop already captures `rc, output =
  _run_verify_in(...)` — pass `returncode=rc` to its `_extract_failure_signatures(output)` call so
  the on-demand and eager-shared baseline computation paths gain the same synthetic-signature
  behavior as the live replay.
  Update `_extract_failure_signatures`'s docstring to document the new parameter and its synthesis
  rule, and update the module docstring of `_verify_baseline.py` if it references
  `_extract_failure_signatures`'s return contract.
- **Commit:** `fix(implementer-common): synthesize a signature for a non-test-format verify failure (#1060)`

### Card 2: ancestor/clean-tree override for a self-reported fixer `stuck_type: logic`

- **Context:**
  - `plugins/mill/scripts/_status.py`
  - `plugins/mill/scripts/_subprocess_util.py`
  - `plugins/mill/scripts/millpy-fix.py`
  - `plugins/mill/scripts/millpy-merge-in-subagent.py`
- **Edits:**
  - `plugins/mill/scripts/_implementer_common.py`
  - `plugins/mill/unit_tests/test-implementer-common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `_forward_output`, the final `else: print(json.dumps(parsed)); return 0` branch (reached after
  the `parsed.get("status") == "incomplete"` early-return and after the `parsed.get("status") ==
  "success"` block, for every other self-reported status including `stuck`) passes a well-formed
  self-reported `stuck_type: logic` JSON straight through unchanged. Add a new check immediately
  before that final `else`, gated on `card_ids is None` (the implementer always passes `card_ids`,
  so this guard naturally excludes it) and on a real prior commit existing (`start_sha is not
  None`). This combination is satisfied only by `millpy-fix.py`'s `finalize_from_output` call, which
  passes `start_sha=args.start_sha` and never passes `card_ids` — confirmed by reading both callers:
  `millpy-merge-in-subagent.py`'s `verify-fix` mode never calls `finalize_from_output`/
  `_forward_output` at all (it hand-rolls its own JSON in the `--stage finalize` early-exit branch),
  and its `conflicts` mode's `finalize_from_output` call hardcodes `start_sha=None`, so this new
  check can never fire for either merge-in mode — it is fixer-only, matching #1104's own incident
  (a holistic fix-round crash in `millpy-fix.py`), and this card does not extend it to merge-in:
  ```python
  if (
      parsed.get("status") == "stuck"
      and parsed.get("stuck_type") == "logic"
      and card_ids is None
      and start_sha is not None
  ):
      _override = _fixer_logic_ancestor_override(
          project_root,
          start_sha,
          verify_cmd,
          module_wide_verify_cmd,
          git_root=git_root,
          module_verify_baseline=module_verify_baseline,
          cwd_override=cwd_override,
          module_wide_cwd_override=module_wide_cwd_override,
          batch_verify_baseline=batch_verify_baseline,
          status_path=status_path,
          batch_name=batch_name,
          git_name=git_name,
          git_email=git_email,
          session_id=session_id or parsed.get("session_id"),
      )
      if _override is not None:
          print(json.dumps(_override))
          return 0
  ```
  Add a new function `_fixer_logic_ancestor_override(project_root: Path, start_sha: str,
  verify_cmd: str | None, module_wide_verify_cmd: str | None, *, git_root: Path | None = None,
  module_verify_baseline: str | None = None, cwd_override: Path | None = None,
  module_wide_cwd_override: Path | None = None, batch_verify_baseline: list[str] | None = None,
  status_path: Path | None = None, batch_name: str | None = None, git_name: str | None = None,
  git_email: str | None = None, session_id: str | None = None) -> dict | None`, placed immediately
  above `_forward_output`. It mirrors the ancestor/clean-tree pattern the no-JSON inference branches
  already use (the `elif start_sha is not None and snapshot_path is None:` block later in this same
  function): (1) `if _content_commit_count(project_root, start_sha) in (None, 0): return None` — no
  real prior commit exists, so the self-report stands. (2) run `git -C <project_root> status
  --porcelain --untracked-files=no` via `_subprocess_util.run`; a non-empty result means the tree is
  dirty (a genuine unresolved logic problem) — `return None`. (3) When both checks pass, call
  `_run_verify_gates(project_root, verify_cmd, module_wide_verify_cmd, git_root=git_root,
  module_verify_baseline=module_verify_baseline, cwd_override=cwd_override,
  module_wide_cwd_override=module_wide_cwd_override, batch_verify_baseline=batch_verify_baseline,
  start_sha=start_sha, status_path=status_path, batch_name=batch_name, git_name=git_name,
  git_email=git_email)` — a non-`None` result means verify still fails, so `return None` (the
  self-reported `logic` stuck is not overridden; a genuinely still-broken batch must not be silently
  waved through). (4) Otherwise, resolve `head = _subprocess_util.run(["git", "rev-parse", "HEAD"],
  cwd=project_root).stdout.strip()` and return `{"status": "success", "commit_sha": head,
  "session_id": session_id or "unknown", "inferred": True}`.
  This mechanizes the manual `git merge-base --is-ancestor` / `git status --porcelain` check the
  Builder performed by hand in the #1104 incident, without inventing a new `incomplete`-style
  classification the fixer has no card concept to resume against.
- **Commit:** `fix(implementer-common): ancestor/clean-tree override for self-reported fixer logic-stuck (#1104)`

### Card 3: full-batch-history fallback for a self-resolve re-fire's completeness recount

- **Context:**
  - `plugins/mill/scripts/_plan_dag.py`
  - `plugins/mill/scripts/_plan_validate.py`
  - `plugins/mill/scripts/_subprocess_util.py`
- **Edits:**
  - `plugins/mill/scripts/_plan_dag.py`
  - `plugins/mill/scripts/_implementer_common.py`
  - `plugins/mill/scripts/millpy-implement.py`
  - `plugins/mill/unit_tests/test-implementer-common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  `_plan_dag.py` already has `_CARD_COMMIT_RE = re.compile(r"^-\s*\*\*Commit:\*\*(?P<inline>.*)$",
  re.MULTILINE)`, used by `parse_commit_none_card_ids`. Add a new function
  `parse_card_commit_messages(batch_text: str) -> dict[int, str]` to `_plan_dag.py`, placed adjacent
  to `parse_commit_none_card_ids`: split `batch_text` into cards the same way
  `parse_commit_none_card_ids` already does in this same file (a `### Card N:` heading starts a
  card, the next `### ` heading or EOF ends it — this is NOT fence-aware, unlike
  `_plan_validate._parse_cards`'s own splitting, which toggles on ` ``` ` lines; mirror
  `parse_commit_none_card_ids`'s actual splitting loop, not `_parse_cards`'s), then for each card
  apply `_CARD_COMMIT_RE` to its own text and
  return `{card_number: inline.strip()}` for every card whose `Commit:` value is present and not the
  literal `none` (case-insensitive) — a `Commit: none` card has nothing to search for in git log by
  definition and is excluded from the returned dict.
  In `_implementer_common.py`, add a new keyword parameter `card_commit_messages: dict[int, str] |
  None = None` to `_forward_output` (and thread it through `finalize_from_output`'s identical
  parameter, forwarded unchanged to its own `_forward_output` call). Before the two existing
  "no content commit" demotions in the explicit `status: success` branch — the `HEAD == start_sha`
  block and the `_is_only_start_batch_commit` block, both currently gated on `start_sha is not None
  and not nits_only` — add one more guard clause ahead of both: when `card_commit_messages` is
  truthy (non-`None`, non-empty) and `card_ids` is truthy, run `git -C <project_root> log --oneline
  --all` via `_subprocess_util.run` once and check whether **every** value in
  `card_commit_messages` appears as a substring of that log output. Reuse `card_ids` to scope the
  check to this batch's own cards (`card_commit_messages` may legitimately contain other batches'
  entries if the caller ever passes a whole-plan dict — this batch's callers only ever construct it
  from the current batch's own file, so this is a defensive, not load-bearing, cross-check). When
  every message is found: skip both existing demotions entirely and instead build `_success =
  {"status": "success", "session_id": session_id or parsed.get("session_id") or "unknown",
  "inferred": True}`, call `_attach_commit_sha(_success, project_root)` (the existing helper every
  sibling success/stuck path in this function already uses to resolve the actual current HEAD — do
  NOT hardcode `start_sha` as `commit_sha`: in the `_is_only_start_batch_commit` bypass case HEAD is
  one housekeeping commit ahead of `start_sha`, so `start_sha` would be stale), then `print
  (json.dumps(_success))` and `return 0`. When the full-history scan is
  inconclusive (any message missing), fall through to the existing two demotions unchanged — this
  fallback only ever prevents a false-negative demotion, never a false-positive success.
  In `millpy-implement.py`'s `main()`, wherever the batch's own text is already read to compute
  `card_ids` (the `### Card N:` heading scan), also compute `card_commit_messages =
  _plan_dag.parse_card_commit_messages(batch_text)` and thread it into BOTH call sites that already
  pass `card_ids=card_ids`: the `--stage finalize` branch's `finalize_from_output(...)` call, and the
  `--stage full` branch's direct `_forward_output(...)` call — both must gain
  `card_commit_messages=card_commit_messages` alongside their existing `card_ids=card_ids` argument,
  since both are live entry points into the same self-resolve-remint false-negative this card exists
  to close.
  This directly targets the gap in `millpy-implement.py`'s own `_prepare_reuse_entry`/
  `_self_resolve_remint_ts` mechanism (added 2026-09-04): the first re-fire after a
  `self-resolved-verify-logic` marker deliberately fresh-mints a new `start_sha`, so when every card
  was already committed before that self-resolve, the SHA-range recount alone can never see them —
  read that existing mechanism in full before touching this card; do not alter its one-remint
  bookkeeping.
- **Commit:** `fix(implementer-common): full-batch-history fallback for self-resolve completeness recount (#1061)`

### Card 4: progress line for on-demand baseline computation

- **Context:**
  - `plugins/mill/scripts/_verify_baseline.py`
- **Edits:**
  - `plugins/mill/scripts/_implementer_common.py`
  - `plugins/mill/unit_tests/test-implementer-common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `_run_verify_gates`'s on-demand-compute prelude — the block guarded by `if (not
  batch_verify_baseline and replay_signatures and status_path is not None and verify_cmd is not
  None):` — immediately before the call to `_verify_baseline.compute_batch_baseline_on_demand(...)`,
  add one ASCII-only progress line: `print(f"[baseline] computing on-demand baseline for
  {batch_name or 'batch'}...")`. This is the only attributable log line for the rare case where the
  lazy on-demand baseline computation (landed via the already-merged `mill-infra-reliability-misc-r2`
  task's #1102 resolution) actually fires and takes as long as a full verify run — without it, the
  wait is indistinguishable from a generic `[mill-bg] HEARTBEAT` line. Use `--` and `->` (never an
  em-dash or Unicode arrow) per this codebase's ASCII-only `print()`/`_log()` output convention. Do
  not add any per-batch "N of M" counter — the lazy path computes at most one batch's baseline at a
  time, on demand, so there is no total count to report.
- **Commit:** `feat(implementer-common): progress line for on-demand baseline computation (#1089)`

## Batch Tests

Extends `test-implementer-common.py` with: (1) a case asserting `_extract_failure_signatures`
returns a non-empty, stable synthetic signature for a non-zero `returncode` with no recognized
FAIL-format lines, and an unchanged empty list for `returncode=0`; (2) a case driving
`_fixer_logic_ancestor_override` with `card_ids=None`, a real commit since `start_sha`, a clean
`git status --porcelain`, and a passing verify — asserts the override fires; a second case with a
dirty tree or a still-failing verify asserts it returns `None` (self-report passes through
unchanged); (3) a case for the full-batch-history fallback: a fixture where every declared card's
`Commit:` message appears in `git log --oneline --all` predating a synthetic fresh `start_sha` —
asserts `_forward_output` reports `success` instead of the `HEAD == start_sha` logic demotion; a
case with one missing message asserts the existing demotion still fires. Extends
`test-verify-baseline.py` with a case asserting `_signatures_for_pair` threads `returncode` into
`_extract_failure_signatures` for both runs, and a case documenting the accepted limitation that two
corroboration runs of a non-deterministic non-test failure can persist two distinct synthetic
signatures rather than deduping to one (no cross-run normalization is added for this — see Card 1's
Requirements for why the target class, deterministic compiler/linter diagnostics, is unaffected).
Runs via `run-all.py --only test-implementer-common.py test-verify-baseline.py` — both files are
directly touched by this batch's cards.
