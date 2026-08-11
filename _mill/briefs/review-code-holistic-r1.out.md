MILL_REVIEW_BEGIN
# Review: mill-go: quality-gate coverage gaps (NIT-fix regressions, missing lint gate) — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewed_file: plan/ + source
date: 2026-08-11
```

## Findings

None. Verified all four batches against their cards and the overview's Shared Decisions:

- **Batch 1** (`_prior_blocking.py` + `test-prior-blocking.py`): `build_digest` signature, `_BLOCKING_HEADING_RE` (byte-identical to `_review_common._RE_FINDING_HEADING`), the RE_SIMPLE-before-RE_BATCH classification order, `BLOCKING_SEVERITY` comparison, demoted-finding exclusion (implicit via sev filter, matching `rewrite_demoted_findings`'s on-disk rewrite), and the ASCII-fold convention (matches `_treeguard.py:114-115` exactly) are all correctly implemented per `digest-scans-current-disk-state-no-round-boundary`. All 9 required test cases present and correctly targeted; import style mirrors `test-nit-gate.py`.
- **Batch 2** (`millpy-fix.py`, both fixer-brief templates, `test-millpy-fix.py`): `--prior-blocking` flag placed immediately after `--nits-only`; `prior_blocking_path` resolved alongside `review_file`; the existence+non-empty-after-strip check (`empty-digest-file-reads-as-none`) is implemented exactly as specified, correctly distinguished from `_review_code.py`'s `prior_notes.is_file()`-only check (verified at `_review_code.py:357`). `PRIOR_BLOCKING` token wired into both batch and holistic render-token dicts. Both templates carry the documented token comment and the `## Prior BLOCKING findings` section in the correct position. All 4 new unit tests present and asserting the correct `call_args` values (the tests set `mock_render.return_value` while still inspecting `call_args`, which satisfies the card's functional intent — a bare `Mock()` without a string return value would break `millpy-fix.py`'s `len(prompt_text)` max-chars check).
- **Batch 3** (`mill-go/SKILL.md`): all three dispatch sites (per-batch `## Execute` step 4, holistic `## Holistic code review` step 4, and the Handoff nit-enforcement self-resolve) carry the "Prior-blocking digest." block with correct `scope=`/`batch_name=` arguments and file-naming convention, and `--prior-blocking <path>` is appended after `--nits-only` in both the Agent-mode arg string and the subprocess/psmux bash invocation at each in-flow site. The Handoff site correctly remains a textual pointer per Card 8, with the amendment sentence present.
- **Batch 4** (`mill-plan/SKILL.md`, both `mill-config.yaml` files): lint-command names (`golangci-lint run`, `ruff check .`) match `golang-build`/`python-build`'s own Build Commands sections verbatim; the csharp-build "no lint command" claim matches its own Convention note verbatim. Both `mill-config.yaml` `done_gate:` comment lines are byte-identical between hub and template.

No out-of-plan files, no cross-batch contract violations, no duplicated helpers, no language pitfalls (mutable defaults, import side effects, path-sep/CRLF issues) observed.

## Verdict

APPROVE
All four batches match their plan cards and Shared Decisions precisely; no defects found.
MILL_REVIEW_END
