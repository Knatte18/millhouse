# Verify-Fix Brief

The verify command `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-class-taxonomy.py test-review-common.py test-review-finalize.py` failed after a merge.
Your job is to diagnose the failures and fix the code so the verify command passes.

## Verify Output

```
PASS: ceiling table -- discussion (only design survives BLOCKING)
PASS: ceiling table -- plan (design+scope survive BLOCKING)
PASS: ceiling table -- code (all four classes survive BLOCKING)
PASS: ceiling never promotes a stated NIT
PASS: demotion rewrite -- heading mechanism, on disk
PASS: demotion rewrite -- yaml-only mechanism, on disk
PASS: demotion rewrite -- both mechanisms, one finding, both rewritten
PASS: re-read round trip reports demoted from marker alone
PASS: verdict derivation -- discussion scope-only BLOCKING approves
PASS: unknown class preserves stated severity and is ceiling-exempt
PASS: no double-count for NIT with unknown class
PASS: mixed-format document hides no finding
PASS: cross-mechanism dedup by title
PASS: duplicate title, same mechanism (headings), both survive and rewrite
PASS: duplicate title, same mechanism (yaml), both survive and rewrite
PASS: resolve_blocking_classes per-stage defaults
PASS: resolve_blocking_classes reads a configured value
PASS: resolve_blocking_classes never raises on missing/None levels
PASS: resolve_blocking_classes unrecognized review_type falls back to all classes
PASS: parse_verdict normalises GAPS_FOUND to REQUEST_CHANGES
All review-class-taxonomy unit tests passed.
[safe-rmtree] starting: path=/tmp/tmpou9pi0im allowed_root=/tmp/tmpou9pi0im
[safe-rmtree] removed: /tmp/tmpou9pi0im
[safe-rmtree] starting: path=/tmp/tmp2pd703zc allowed_root=/tmp/tmp2pd703zc
[safe-rmtree] removed: /tmp/tmp2pd703zc
[safe-rmtree] starting: path=/tmp/tmp0fgvyvm5 allowed_root=/tmp/tmp0fgvyvm5
[safe-rmtree] removed: /tmp/tmp0fgvyvm5
[safe-rmtree] starting: path=/tmp/tmpsnup5qq2 allowed_root=/tmp/tmpsnup5qq2
[safe-rmtree] removed: /tmp/tmpsnup5qq2
[safe-rmtree] starting: path=/tmp/tmpz08isj_4 allowed_root=/tmp/tmpz08isj_4
[safe-rmtree] removed: /tmp/tmpz08isj_4
[safe-rmtree] starting: path=/tmp/tmpgpay00gl allowed_root=/tmp/tmpgpay00gl
[safe-rmtree] removed: /tmp/tmpgpay00gl
[safe-rmtree] starting: path=/tmp/tmpdnog53it allowed_root=/tmp/tmpdnog53it
[safe-rmtree] removed: /tmp/tmpdnog53it
[safe-rmtree] starting: path=/tmp/tmpen50bkuo allowed_root=/tmp/tmpen50bkuo
[safe-rmtree] removed: /tmp/tmpen50bkuo
[safe-rmtree] starting: path=/tmp/tmpwhxvg_ub allowed_root=/tmp/tmpwhxvg_ub
[safe-rmtree] removed: /tmp/tmpwhxvg_ub
[_review_common] warning: finding has unknown or missing class -- unclassed blocking with unknown class
[_review_common] warning: finding has unknown or missing class -- bare blocking
[_review_common] warning: finding has unknown or missing class -- unclassed nit with unknown class
[_review_common] warning: finding has unknown or missing class -- bare nit
[safe-rmtree] starting: path=/tmp/tmplzpxp6k_ allowed_root=/tmp/tmplzpxp6k_
[safe-rmtree] removed: /tmp/tmplzpxp6k_
[_review_common] warning: finding has unknown or missing class -- cosmetic nit
[safe-rmtree] starting: path=/tmp/tmppzdigqsn allowed_root=/tmp/tmppzdigqsn
[safe-rmtree] removed: /tmp/tmppzdigqsn
[_review_common] warning: finding has unknown or missing class -- heading blocking unknown class
[_review_common] warning: finding has unknown or missing class -- yaml nit unknown class
[safe-rmtree] starting: path=/tmp/tmp2teuhm8q allowed_root=/tmp/tmp2teuhm8q
[safe-rmtree] removed: /tmp/tmp2teuhm8q
[safe-rmtree] starting: path=/tmp/tmpz_q_s8sz allowed_root=/tmp/tmpz_q_s8sz
[safe-rmtree] removed: /tmp/tmpz_q_s8sz
[safe-rmtree] starting: path=/tmp/tmp8hz7eo9k allowed_root=/tmp/tmp8hz7eo9k
[safe-rmtree] removed: /tmp/tmp8hz7eo9k
{"status": "success"}
PASS: review-code finalize does NOT call prepare()
{"status": "success"}
PASS: review-code finalize receives raw_text byte-identical (no unescape)
PASS: review-code finalize --round required
PASS: review-plan finalize does NOT call prepare()
{"type": "discussion", "round": 1, "verdict": "APPROVE", "blocking_count": 0, "nit_count": 0, "reviews": []}
PASS: review-discussion finalize does NOT call prepare()
{"type": "discussion", "round": 1, "verdict": "APPROVE", "blocking_count": 0, "nit_count": 0, "reviews": []}
PASS: review-discussion finalize receives raw_text byte-identical (no unescape)
{"type": "discussion", "round": 1, "verdict": "APPROVE", "blocking_count": 0, "nit_count": 0, "reviews": []}
PASS: review-discussion finalize auto-discovers round when --round absent
PASS: review-discussion finalize --actual-model override case
PASS: review-discussion finalize --actual-model omitted case
PASS: review-plan finalize --actual-model override case
PASS: review-plan finalize --actual-model omitted case
PASS: review-code finalize --actual-model override case
PASS: review-code finalize --actual-model omitted case
PASS: review-discussion finalize with missing agent-output returns verdict: ERROR on exit 0
PASS: review-discussion finalize with empty agent-output returns verdict: ERROR on exit 0
PASS: review-discussion finalize with whitespace-only agent-output returns verdict: ERROR on exit 0
PASS: review-plan finalize with missing agent-output returns verdict: ERROR on exit 0
PASS: review-plan finalize with empty agent-output returns verdict: ERROR on exit 0
PASS: review-plan finalize with whitespace-only agent-output returns verdict: ERROR on exit 0
PASS: review-code finalize with missing agent-output returns verdict: ERROR on exit 0
PASS: review-code finalize with empty agent-output returns verdict: ERROR on exit 0
PASS: review-code finalize with whitespace-only agent-output returns verdict: ERROR on exit 0
PASS: review-discussion stale .out.md does not survive a write_brief retry
PASS: review-plan stale .out.md does not survive a write_brief retry
PASS: review-code stale .out.md does not survive a write_brief retry
FAIL: review-plan finalize did not succeed via auto-discovery
FAIL: test 3b (catching classes that do not inherit from BaseException is not allowed)

2 test(s) FAILED
PASS: discover_round nonexistent dir returns 1
PASS: RE_SIMPLE matches plan-holistic before RE_BATCH could mis-identify
PASS: discover_round cross-type isolation (plan-batch ignored for discussion)
PASS: discover_round for plan with batch file: 3
PASS: discover_round plan holistic unaffected by batch file
PASS: discover_round plan other-batch unaffected by 01-setup file
PASS: discover_round per-scope discussion/holistic: 3
PASS: discover_round per-scope plan/holistic: 2
PASS: discover_round per-scope plan/batch-a: 3
PASS: discover_round per-scope plan/batch-b: 2
PASS: discover_round per-scope plan/batch-c (absent): 1
PASS: discover_round per-scope code/holistic: 2
PASS: discover_round per-scope code/batch-a: 2
PASS: discover_round per-scope code/batch-b (absent for code): 1
PASS: find_active_slug non-task branch -> ReviewError (MarkerError translation)
PASS: find_active_slug: 'my-task'
PASS: find_active_slug daemon-skip — confirmed on-disk marker -> 'my-task'
PASS: find_active_slug stale marker (branch mismatch) -> falls through to branch-derived slug
PASS: load_task_title with task_title in Home.md
PASS: load_task_title non-task branch -> fallback to slug
PASS: load_task_title daemon-skip — status.md present -> 'My On-Disk Title'
PASS: resolve_path('discussion.md', slug) -> worktree/discussion.md
PASS: resolve_path resolves without calling the daemon-backed _marker.slug_from_branch (skip_slug_validation=True)
PASS: resolve_path covers plan/, reviews/, nested reviews/r1/holistic.md
PASS: resolve_path stale <SLUG> template substituted (no literal segment)
PASS: resolve_path raises ActiveWorktreeSlugMismatch on branch mismatch
PASS: resolve_path M2 in-place (hub_rel='.') -> git_root/task/discussion.md
PASS: resolve_path M2+sub in-place (hub_rel='src/Models') -> git_root/src/Models/task/discussion.md
PASS: parse_verdict APPROVE
PASS: parse_verdict REQUEST_CHANGES
PASS: parse_verdict NEED_CONTEXT
PASS: parse_verdict yaml block not at top
PASS: parse_verdict no yaml block -> ReviewError
PASS: parse_verdict unclosed yaml block -> ReviewError
PASS: parse_verdict invalid verdict -> ReviewError
PASS: parse_verdict multiple yaml blocks (first wins)
PASS: parse_verdict trailing prose after yaml
PASS: parse_verdict yaml fence with trailing whitespace
PASS: parse_verdict prose preamble + yaml block
PASS: parse_verdict verdict with extra whitespace
PASS: write_review_file discussion: 20260808-191523-discussion-review-r1.md
PASS: write_review_file plan-batch: 20260808-191523-plan-review-01-setup-r1.md
PASS: write_review_file plan-holistic: 20260808-191523-plan-review-r1.md
PASS: write_review_file code-batch: 20260808-191523-code-review-foundation-r1.md
PASS: apply_actual_model_override rewrites existing reviewer_model line
PASS: apply_actual_model_override injects reviewer_model line after opening fence
PASS: apply_actual_model_override treats malformed reviewer_model line as not-found
PASS: apply_actual_model_override identity when actual_model is None
PASS: apply_actual_model_override leaves reviewer_self_id line untouched
PASS: write_review_file preserves reviewer_self_id line verbatim
PASS: finalize_scope applies actual_model override to written file
PASS: finalize_scope without actual_model reproduces unmodified behavior
PASS: bulk_files skips missing files
PASS: bulk_files END FILE delimiters present and ordered
PASS: bulk_files_with_diff END FILE delimiters present and ordered (start_sha=None)
PASS: render_prompt missing template -> FileNotFoundError
PASS: render_prompt with prior_nonblocking digest renders correctly
PASS: render_prompt round 1 with prior_nonblocking=(none) renders without KeyError
PASS: aggregate_verdict (incl. NEED_CONTEXT precedence)
PASS: build_tool_rule bulk + tool-use
PASS: build_tool_rule unknown mode -> ValueError
PASS: load_config loads repo config
PASS: load_config local override wins; other keys preserved
PASS: load_config missing config -> ReviewError
PASS: load_config stale review: overlay emits stderr warning with overlay path
PASS: load_config bare roles: does not crash; template roles: preserved
PASS: load_config hub_relative_path in config.local.yaml does not emit unknown-key warning
PASS: load_config delegation inherits _config.load_config's worktree-template cache-lag augmentation
PASS: parse_batch_refs multi-line bullet form returns both paths
PASS: parse_batch_refs sub-bullet keeps only leading token, drops prose backticks
PASS: parse_batch_refs 'none' token filtered
PASS: parse_batch_refs single-line form returns both paths
PASS: parse_batch_refs mixed single-line and multi-line fields
PASS: parse_batch_refs 'None' (capital N) filtered
PASS: parse_batch_refs 'NONE' (all caps) filtered
PASS: parse_batch_refs sub-bullet `None` filtered
PASS: parse_batch_refs backtick tokens win; trailing 'none' filtered
PASS: parse_batch_refs includes Deletes tokens alongside Context/Edits/Creates
PASS: resolve_ref_paths hit on disk returns resolved path
PASS: resolve_ref_paths creates_union suppresses missing path
PASS: resolve_ref_paths hard-fails with 'referenced path not found'
PASS: resolve_ref_paths wiki/ prefix resolved via wiki_root
PASS: resolve_ref_paths wiki/ without wiki_root raises ReviewError
PASS: resolve_ref_paths wiki path missing on disk hard-fails
PASS: resolve_ref_paths caller_label appears in error message
PASS: resolve_ref_paths defensive None skipped silently
PASS: resolve_ref_paths 'none' string skipped silently
PASS: resolve_ref_paths 'None' string skipped silently
PASS: resolve_ref_paths deletes_union suppresses missing path
PASS: resolve_ref_paths missing + in both unions -> silent suppress
PASS: resolve_ref_paths on-disk + in deletes_union -> resolved and included
PASS: resolve_ref_paths missing + not in deletes_union -> ReviewError
PASS: resolve_ref_paths caller_label in error with deletes_union present
PASS: resolve_ref_paths git_root fallback hit returns git_root path
PASS: resolve_ref_paths git_root fallback miss -> hard-fail ReviewError
PASS: resolve_ref_paths without git_root preserves current behavior
PASS: resolve_ref_paths creates_union suppresses even with git_root fallback
PASS: resolve_ref_paths wiki/ prefix ignores git_root fallback
PASS: resolve_ref_paths soft_fail_gitignored skips confirmed-ignored missing ref
PASS: resolve_ref_paths soft_fail_gitignored still hard-fails non-ignored missing ref
PASS: resolve_ref_paths hard-fails git-ignored missing ref when soft_fail_gitignored omitted
PASS: resolve_ref_paths hard-fails git-ignored missing ref when soft_fail_gitignored=False explicit
PASS: compute_creates_union nonexistent plan_dir returns empty set
PASS: compute_creates_union inline Creates returns set of tokens
PASS: compute_creates_union 'none' token filtered
PASS: compute_creates_union two batches -> union of Creates tokens
PASS: compute_creates_union 00-overview.md excluded
PASS: compute_creates_union 'None' (capital N) filtered
PASS: compute_deletes_union nonexistent plan_dir returns empty set
PASS: compute_deletes_union inline Deletes returns set of tokens
PASS: compute_deletes_union multi-line bullet form returns tokens
PASS: compute_deletes_union 'none' sentinel filtered
PASS: compute_deletes_union 'None' sentinel filtered
PASS: compute_deletes_union 'NONE' sentinel filtered
PASS: compute_deletes_union two batches with overlap -> de-duplicated
PASS: compute_deletes_union Deletes absent on some cards; present on others
PASS: compute_deletes_union 00-overview.md excluded
PASS: build_manifest_section empty input
PASS: build_manifest_section three-path input (heading + blank + bullets)
PASS: build_manifest_section no trailing newline
PASS: build_deletes_section empty list -> empty string
PASS: build_deletes_section single token -> heading + bullet
PASS: build_deletes_section multiple tokens preserve input order
PASS: build_deletes_section bullets have no backticks added
PASS: build_deletes_section no trailing newline
PASS: resolve_existing_paths path on disk returned
PASS: resolve_existing_paths missing path silently dropped
PASS: resolve_existing_paths wiki-prefixed path exists -> returned
PASS: resolve_existing_paths wiki-prefixed path missing -> silently dropped
PASS: resolve_existing_paths wiki/ with wiki_root=None -> silently dropped (no raise)
PASS: resolve_existing_paths None token silently dropped
PASS: resolve_existing_paths 'none'/'NONE'/'None' tokens silently dropped
PASS: resolve_existing_paths mixed input -> only existing paths returned
PASS: resolve_existing_paths git_root fallback hit returns git_root path
PASS: resolve_existing_paths git_root fallback miss silently drops (no error)
PASS: resolve_existing_paths without git_root preserves current behavior
PASS: resolve_ref_paths cwd==git_root with root set uses git_root/root/raw primary
PASS: resolve_existing_paths cwd==git_root/root returns single-prefixed git_root/root/raw (not doubled)
PASS: resolve_ref_paths git_root=None falls back to project_root/root/raw
PASS: resolve_existing_paths git_root=None falls back to project_root/root/raw
PASS: resolve_ref_paths wiki/ prefix routes through wiki_root unchanged
PASS: resolve_existing_paths wiki/ prefix routes through wiki_root unchanged
PASS: discover_round per-scope code/helper-modules after r1: 2
PASS: discover_round per-scope code/spawn-core (different batch, fresh count): 1
PASS: discover_round per-scope code/holistic independent after holistic r1: 2
PASS: discover_round per-scope code/helper-modules still independent of holistic: 2
PASS: parse_missing_context no heading -> []
PASS: parse_missing_context one path bullet -> ['a/b.py']
PASS: parse_missing_context two path bullets -> list in order
PASS: parse_missing_context empty section -> []
PASS: parse_missing_context stops at next ## heading
PASS: parse_missing_context bullet without backticks not captured
PASS: parse_missing_context `none` token filtered
PASS: parse_missing_context `None` token filtered
PASS: build_reattached_section empty input -> ''
PASS: build_reattached_section one path -> heading + FILE delimiter
PASS: build_reattached_section two paths -> both delimiters in order
PASS: parse_blocking_count empty string -> 0
PASS: parse_blocking_count one BLOCKING heading -> 1
PASS: parse_blocking_count two BLOCKINGs -> 2
PASS: parse_blocking_count one NIT -> 1
PASS: parse_blocking_count GAP severity -> 1
PASS: parse_blocking_count case-sensitive: lowercase blocking with BLOCKING severity -> 0
PASS: parse_blocking_count mid-line marker not counted -> 0
PASS: parse_blocking_count yaml-list BLOCKING -> 1
PASS: parse_blocking_count yaml-list mixed severities BLOCKING -> 1
PASS: parse_blocking_count yaml-list mixed severities NIT -> 2
PASS: parse_blocking_count heading>0 wins over yaml list
PASS: parse_blocking_count verdict-only yaml block -> 0
PASS: parse_blocking_count malformed yaml block -> 0, no crash
PASS: parse_blocking_count yaml severity is case-insensitive
PASS: count_unrecognized_severity_findings empty input -> 0
PASS: count_unrecognized_severity_findings one [MAJOR] heading -> 1
PASS: count_unrecognized_severity_findings [MEDIUM]/[HIGH]/[MINOR] each count as 1
PASS: count_unrecognized_severity_findings [BLOCKING] heading -> 0
PASS: count_unrecognized_severity_findings [NIT] heading -> 0
PASS: count_unrecognized_severity_findings mixed-case [Major]/[major] -> 0
PASS: count_unrecognized_severity_findings yaml-only MAJOR entry -> 1
PASS: count_unrecognized_severity_findings yaml-only lowercase 'major' entry -> 1
PASS: count_unrecognized_severity_findings finds [MAJOR] heading alongside a real [NIT] heading
PASS: count_unrecognized_severity_findings counts both a heading-only and a yaml-only unrecognized entry
PASS: count_unrecognized_severity_findings works for the GAP/NOTE severity pair
PASS: count_unrecognized_severity_findings double-counts a heading + mirroring yaml entry (accepted risk, not a bug)
PASS: finalize_scope folds unrecognized-severity findings into blocking_count
PASS: finalize_scope folds an isolated [MEDIUM]-only finding into blocking_count with zero recognized findings present
PASS: parse_blocking_count_warns_on_prose_divergence_numeric
PASS: parse_blocking_count_warns_on_prose_divergence_spelled
PASS: parse_blocking_count_silent_when_aligned
PASS: parse_blocking_count_silent_when_no_prose_count
PASS: parse_blocking_count_warns_for_gap_severity
PASS: parse_blocking_count divergence warning is ASCII-only (no mojibake)
PASS: _load_root_from_overview importable from _review_common
PASS: detect_resume_round nonexistent dir -> None
PASS: detect_resume_round empty dir -> None
PASS: detect_resume_round per-batch r1 + holistic r1 -> None
PASS: detect_resume_round per-batch r1 + no holistic -> 1
PASS: detect_resume_round per-batch r1+r2, holistic r1 only -> 2
PASS: detect_resume_round partial r2 batches, no holistic -> 2 (highest batch round)
PASS: detect_resume_round type isolation: plan files ignored for code
PASS: bulk_files_with_diff small diff -> DIFF delimiter
PASS: bulk_files_with_diff large diff -> FILE delimiter
PASS: bulk_files_with_diff empty diff (unchanged file) -> FILE delimiter
PASS: bulk_files_with_diff non-existent file skipped
PASS: bulk_files_with_diff git diff failure -> FILE delimiter fallback
PASS: _read_for_bulk code-cell-only notebook
PASS: _read_for_bulk markdown-cell-only notebook
PASS: _read_for_bulk mixed code + markdown
PASS: _read_for_bulk cell with list-form source
PASS: _read_for_bulk cell with string-form source
PASS: _read_for_bulk raw cell skipped
PASS: _read_for_bulk .py file returns text as-is
PASS: _read_for_bulk malformed JSON -> empty string + stderr warning
PASS: write_review_file UTC timestamp (code, no scope)
PASS: write_review_file UTC timestamp (code, scope=holistic)
PASS: write_review_file UTC timestamp (code, scope=batch)
PASS: write_review_file UTC timestamp (discussion)
PASS: write_review_file UTC timestamp (plan, scope=batch)
PASS: write_review_file holistic naming regression (#316)
PASS: find_active_slug glob fallback — one .active file -> 'my-task'
PASS: find_active_slug glob fallback — multiple .active files -> ReviewError with 'use --slug'
PASS: find_active_slug glob fallback — no _mill/ dir -> ReviewError
PASS: ReviewResult nit_count defaults to 0
PASS: ReviewResult.to_dict() includes nit_count field
PASS: ReviewResult nit_count non-default value round-trips through to_dict()
PASS: parse_verdict unfenced verdict line with leading whitespace normalises GAPS_FOUND to REQUEST_CHANGES
PASS: parse_verdict fenced block (primary path)
PASS: parse_verdict no verdict -> ReviewError
PASS: parse_verdict invalid fenced value raises (fallback not used)
PASS: _read_for_bulk directory path -> empty string + warning
PASS: bulk_files directory skipped, file included
PASS: tool-use omits bulked bodies and build_tool_rule grants tools
PASS: bulk inlines source content and build_tool_rule forbids tools
PASS: resolve_large_prompt_timeout under threshold -> default timeout
PASS: resolve_large_prompt_timeout over threshold + timeout key set -> override
PASS: resolve_large_prompt_timeout over threshold but key not set -> default
PASS: resolve_large_prompt_timeout no large_prompt key -> default
PASS: parse_blocking_count zero headings suppresses divergence warning
PASS: parse_blocking_count one heading + verdict: verdict line filtered from prose count
PASS: parse_blocking_count with headings still warns on divergence
PASS: parse_moves single pair returns list with one tuple
PASS: parse_moves multiple pairs returns all tuples in order
PASS: parse_moves inline 'none' sentinel returns []
PASS: parse_moves inline 'None' sentinel returns []
PASS: parse_moves inline 'NONE' sentinel returns []
PASS: parse_moves inline 'none' sentinel returns []
PASS: parse_moves Moves field mixed among other card fields
PASS: parse_moves malformed sub-bullet (one path only) is skipped without raising
PASS: parse_moves malformed sub-bullet (no arrow) is skipped without raising
PASS: parse_moves duplicate pairs deduplicated, first-seen order preserved
PASS: parse_deletes single-line inline form returns set of tokens
PASS: parse_deletes multi-line sub-bullet form returns set of tokens
PASS: parse_deletes 'none' sentinel returns empty set
PASS: parse_deletes 'None' sentinel returns empty set
PASS: parse_deletes 'NONE' sentinel returns empty set
PASS: parse_deletes Deletes field mixed among other card fields
PASS: parse_deletes malformed sub-bullet (no backtick path) tolerated without raising
PASS: compute_moves_union nonexistent plan_dir returns (set(), set())
PASS: compute_moves_union empty plan_dir returns (set(), set())
PASS: compute_moves_union single batch returns correct source/target split
PASS: compute_moves_union two batch files aggregates sources and targets
PASS: compute_moves_union 'none' batch contributes nothing to sets
PASS: compute_moves_union 00-overview.md excluded
PASS: parse_batch_refs does not return any token from a Moves: bullet (regression)
PASS: build_tool_rule bulk/tool-use x non-agent byte-identical to pinned literals
PASS: build_tool_rule agent_mode defaults to False (positional-callsite compatibility)
PASS: build_tool_rule bulk x agent avoids bare tool-call ban and grants exactly one Write
PASS: build_tool_rule tool-use x agent still grants Read/Grep/Glob and a Write carve-out
PASS: build_tool_rule both agent cells still forbid Edit, git, and bash
PASS: build_tool_rule unknown mode -> ValueError in both agent_mode states
All _review_common unit tests passed.
[safe-rmtree] starting: path=/tmp/tmpu_1e0y8o allowed_root=/tmp/tmpu_1e0y8o
[safe-rmtree] removed: /tmp/tmpu_1e0y8o
[safe-rmtree] starting: path=/tmp/tmp4_nuix4j allowed_root=/tmp/tmp4_nuix4j
[safe-rmtree] removed: /tmp/tmp4_nuix4j
[safe-rmtree] starting: path=/tmp/tmp9ss5z9fe allowed_root=/tmp/tmp9ss5z9fe
[safe-rmtree] removed: /tmp/tmp9ss5z9fe
[safe-rmtree] starting: path=/tmp/tmp_5silw9b allowed_root=/tmp/tmp_5silw9b
[safe-rmtree] removed: /tmp/tmp_5silw9b
[safe-rmtree] starting: path=/tmp/tmp2vj18li8 allowed_root=/tmp/tmp2vj18li8
[safe-rmtree] removed: /tmp/tmp2vj18li8
[safe-rmtree] starting: path=/tmp/tmphr88bf3a allowed_root=/tmp/tmphr88bf3a
[safe-rmtree] removed: /tmp/tmphr88bf3a
[safe-rmtree] starting: path=/tmp/tmpdoal4uzy allowed_root=/tmp/tmpdoal4uzy
[safe-rmtree] removed: /tmp/tmpdoal4uzy
[safe-rmtree] starting: path=/tmp/tmp62xzajpf allowed_root=/tmp/tmp62xzajpf
[safe-rmtree] removed: /tmp/tmp62xzajpf
[safe-rmtree] starting: path=/tmp/tmp_skb9xon allowed_root=/tmp/tmp_skb9xon
[safe-rmtree] removed: /tmp/tmp_skb9xon
[safe-rmtree] starting: path=/tmp/tmp7lj3l5_c allowed_root=/tmp/tmp7lj3l5_c
[safe-rmtree] removed: /tmp/tmp7lj3l5_c
[safe-rmtree] starting: path=/tmp/tmp0_c04onx allowed_root=/tmp/tmp0_c04onx
[safe-rmtree] removed: /tmp/tmp0_c04onx
[safe-rmtree] starting: path=/tmp/tmpw4om1fms allowed_root=/tmp/tmpw4om1fms
[safe-rmtree] removed: /tmp/tmpw4om1fms
[safe-rmtree] starting: path=/tmp/tmpgmlo76ch allowed_root=/tmp/tmpgmlo76ch
[safe-rmtree] removed: /tmp/tmpgmlo76ch
[safe-rmtree] starting: path=/tmp/tmpvtlquj82 allowed_root=/tmp/tmpvtlquj82
[safe-rmtree] removed: /tmp/tmpvtlquj82
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[safe-rmtree] starting: path=/tmp/tmpkjcczrt_ allowed_root=/tmp/tmpkjcczrt_
[safe-rmtree] removed: /tmp/tmpkjcczrt_
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[safe-rmtree] starting: path=/tmp/tmpxslr7zl8 allowed_root=/tmp/tmpxslr7zl8
[safe-rmtree] removed: /tmp/tmpxslr7zl8
[safe-rmtree] starting: path=/tmp/tmpljdezff5 allowed_root=/tmp/tmpljdezff5
[safe-rmtree] removed: /tmp/tmpljdezff5
[safe-rmtree] starting: path=/tmp/tmpk9u2emuw allowed_root=/tmp/tmpk9u2emuw
[safe-rmtree] removed: /tmp/tmpk9u2emuw
[safe-rmtree] starting: path=/tmp/tmpwh9jgjz8 allowed_root=/tmp/tmpwh9jgjz8
[safe-rmtree] removed: /tmp/tmpwh9jgjz8
[bulk_files] warning: /nonexistent/x.md not found or not readable, skipping
[safe-rmtree] starting: path=/tmp/tmp_ran3czf allowed_root=/tmp/tmp_ran3czf
[safe-rmtree] removed: /tmp/tmp_ran3czf
[safe-rmtree] starting: path=/tmp/tmpt45izimj allowed_root=/tmp/tmpt45izimj
[safe-rmtree] removed: /tmp/tmpt45izimj
[subprocess] spawn argv=['git', '-C', '/tmp/tmpx3b3s7mf', 'diff', 'None..HEAD', '--', 'a.py'] timeout=None
[subprocess] exit code=1 duration=0.001s
[bulk_files_with_diff] warning: git diff failed for /tmp/tmpx3b3s7mf/a.py (returncode=1), using full file
[subprocess] spawn argv=['git', '-C', '/tmp/tmpx3b3s7mf', 'diff', 'None..HEAD', '--', 'b.py'] timeout=None
[subprocess] exit code=1 duration=0.001s
[bulk_files_with_diff] warning: git diff failed for /tmp/tmpx3b3s7mf/b.py (returncode=1), using full file
[safe-rmtree] starting: path=/tmp/tmpx3b3s7mf allowed_root=/tmp/tmpx3b3s7mf
[safe-rmtree] removed: /tmp/tmpx3b3s7mf
[safe-rmtree] starting: path=/tmp/tmpv9uj50yc allowed_root=/tmp/tmpv9uj50yc
[safe-rmtree] removed: /tmp/tmpv9uj50yc
[safe-rmtree] starting: path=/tmp/tmps9fxpr1l allowed_root=/tmp/tmps9fxpr1l
[safe-rmtree] removed: /tmp/tmps9fxpr1l
[safe-rmtree] starting: path=/tmp/tmphquymtya allowed_root=/tmp/tmphquymtya
[safe-rmtree] removed: /tmp/tmphquymtya
[safe-rmtree] starting: path=/tmp/tmpefz9fvdm allowed_root=/tmp/tmpefz9fvdm
[safe-rmtree] removed: /tmp/tmpefz9fvdm
[safe-rmtree] starting: path=/tmp/tmphmwt0hpf allowed_root=/tmp/tmphmwt0hpf
[safe-rmtree] removed: /tmp/tmphmwt0hpf
[safe-rmtree] starting: path=/tmp/tmpexofim7l allowed_root=/tmp/tmpexofim7l
[safe-rmtree] removed: /tmp/tmpexofim7l
[safe-rmtree] starting: path=/tmp/tmp3zyj_g8t allowed_root=/tmp/tmp3zyj_g8t
[safe-rmtree] removed: /tmp/tmp3zyj_g8t
[safe-rmtree] starting: path=/tmp/tmp4c4dzp0v allowed_root=/tmp/tmp4c4dzp0v
[safe-rmtree] removed: /tmp/tmp4c4dzp0v
[safe-rmtree] starting: path=/tmp/tmpgwje8z0x allowed_root=/tmp/tmpgwje8z0x
[safe-rmtree] removed: /tmp/tmpgwje8z0x
[safe-rmtree] starting: path=/tmp/tmpntyqkl38 allowed_root=/tmp/tmpntyqkl38
[safe-rmtree] removed: /tmp/tmpntyqkl38
[safe-rmtree] starting: path=/tmp/tmp83w3droa allowed_root=/tmp/tmp83w3droa
[safe-rmtree] removed: /tmp/tmp83w3droa
[safe-rmtree] starting: path=/tmp/tmp1hhbaf2c allowed_root=/tmp/tmp1hhbaf2c
[safe-rmtree] removed: /tmp/tmp1hhbaf2c
[safe-rmtree] starting: path=/tmp/tmpd_i1km4l allowed_root=/tmp/tmpd_i1km4l
[safe-rmtree] removed: /tmp/tmpd_i1km4l
[safe-rmtree] starting: path=/tmp/tmp1gfbrmz2 allowed_root=/tmp/tmp1gfbrmz2
[safe-rmtree] removed: /tmp/tmp1gfbrmz2
[safe-rmtree] starting: path=/tmp/tmpkk2swi9e allowed_root=/tmp/tmpkk2swi9e
[safe-rmtree] removed: /tmp/tmpkk2swi9e
[safe-rmtree] starting: path=/tmp/tmph5o7g2sy allowed_root=/tmp/tmph5o7g2sy
[safe-rmtree] removed: /tmp/tmph5o7g2sy
[safe-rmtree] starting: path=/tmp/tmp6avorkyy allowed_root=/tmp/tmp6avorkyy
[safe-rmtree] removed: /tmp/tmp6avorkyy
[safe-rmtree] starting: path=/tmp/tmprh7_i4yg allowed_root=/tmp/tmprh7_i4yg
[safe-rmtree] removed: /tmp/tmprh7_i4yg
[safe-rmtree] starting: path=/tmp/tmpwfl5baq2 allowed_root=/tmp/tmpwfl5baq2
[safe-rmtree] removed: /tmp/tmpwfl5baq2
[safe-rmtree] starting: path=/tmp/tmppfd2t22g allowed_root=/tmp/tmppfd2t22g
[safe-rmtree] removed: /tmp/tmppfd2t22g
[safe-rmtree] starting: path=/tmp/tmpwkq2jsjr allowed_root=/tmp/tmpwkq2jsjr
[safe-rmtree] removed: /tmp/tmpwkq2jsjr
[safe-rmtree] starting: path=/tmp/tmpgoirg8n5 allowed_root=/tmp/tmpgoirg8n5
[safe-rmtree] removed: /tmp/tmpgoirg8n5
[safe-rmtree] starting: path=/tmp/tmphepnxgch allowed_root=/tmp/tmphepnxgch
[safe-rmtree] removed: /tmp/tmphepnxgch
[safe-rmtree] starting: path=/tmp/tmp0fs2fqyi allowed_root=/tmp/tmp0fs2fqyi
[safe-rmtree] removed: /tmp/tmp0fs2fqyi
[safe-rmtree] starting: path=/tmp/tmpp594dnx5 allowed_root=/tmp/tmpp594dnx5
[safe-rmtree] removed: /tmp/tmpp594dnx5
[safe-rmtree] starting: path=/tmp/tmp6ibo7ugb allowed_root=/tmp/tmp6ibo7ugb
[safe-rmtree] removed: /tmp/tmp6ibo7ugb
[safe-rmtree] starting: path=/tmp/tmp6nhd_ezf allowed_root=/tmp/tmp6nhd_ezf
[safe-rmtree] removed: /tmp/tmp6nhd_ezf
[safe-rmtree] starting: path=/tmp/tmpwtcbhax2 allowed_root=/tmp/tmpwtcbhax2
[safe-rmtree] removed: /tmp/tmpwtcbhax2
[safe-rmtree] starting: path=/tmp/tmpzox_y8lj allowed_root=/tmp/tmpzox_y8lj
[safe-rmtree] removed: /tmp/tmpzox_y8lj
[safe-rmtree] starting: path=/tmp/tmp5hddxg3p allowed_root=/tmp/tmp5hddxg3p
[safe-rmtree] removed: /tmp/tmp5hddxg3p
[safe-rmtree] starting: path=/tmp/tmplpdubr87 allowed_root=/tmp/tmplpdubr87
[safe-rmtree] removed: /tmp/tmplpdubr87
[safe-rmtree] starting: path=/tmp/tmp_9te6syu allowed_root=/tmp/tmp_9te6syu
[safe-rmtree] removed: /tmp/tmp_9te6syu
[safe-rmtree] starting: path=/tmp/tmptj0ykd0y allowed_root=/tmp/tmptj0ykd0y
[safe-rmtree] removed: /tmp/tmptj0ykd0y
[safe-rmtree] starting: path=/tmp/tmpf1bxvval allowed_root=/tmp/tmpf1bxvval
[safe-rmtree] removed: /tmp/tmpf1bxvval
[safe-rmtree] starting: path=/tmp/tmpshwfcqqj allowed_root=/tmp/tmpshwfcqqj
[safe-rmtree] removed: /tmp/tmpshwfcqqj
[safe-rmtree] starting: path=/tmp/tmpz41nobf_ allowed_root=/tmp/tmpz41nobf_
[safe-rmtree] removed: /tmp/tmpz41nobf_
[resolve_ref_paths] warning: skipping git-ignored Context: ref '.scratch/probe.md' (confirmed ignored under /tmp/tmpy44n8re8)
[safe-rmtree] starting: path=/tmp/tmpy44n8re8 allowed_root=/tmp/tmpy44n8re8
[safe-rmtree] removed: /tmp/tmpy44n8re8
[subprocess] spawn argv=['git', '-C', '/tmp/tmp9akipye7', 'check-ignore', '-q', '/tmp/tmp9akipye7/not_ignored_missing.py'] timeout=None
[subprocess] exit code=1 duration=0.002s
[subprocess] spawn argv=['git', '-C', '/tmp/tmp9akipye7', 'check-ignore', '-q', '/tmp/tmp9akipye7/not_ignored_missing.py'] timeout=None
[subprocess] exit code=1 duration=0.001s
[safe-rmtree] starting: path=/tmp/tmp9akipye7 allowed_root=/tmp/tmp9akipye7
[safe-rmtree] removed: /tmp/tmp9akipye7
[safe-rmtree] starting: path=/tmp/tmp4gap4emv allowed_root=/tmp/tmp4gap4emv
[safe-rmtree] removed: /tmp/tmp4gap4emv
[safe-rmtree] starting: path=/tmp/tmpnbg43tlh allowed_root=/tmp/tmpnbg43tlh
[safe-rmtree] removed: /tmp/tmpnbg43tlh
[safe-rmtree] starting: path=/tmp/tmpee5py6xi allowed_root=/tmp/tmpee5py6xi
[safe-rmtree] removed: /tmp/tmpee5py6xi
[safe-rmtree] starting: path=/tmp/tmptxuaffx0 allowed_root=/tmp/tmptxuaffx0
[safe-rmtree] removed: /tmp/tmptxuaffx0
[safe-rmtree] starting: path=/tmp/tmpxd3topqk allowed_root=/tmp/tmpxd3topqk
[safe-rmtree] removed: /tmp/tmpxd3topqk
[safe-rmtree] starting: path=/tmp/tmp7yr82lhh allowed_root=/tmp/tmp7yr82lhh
[safe-rmtree] removed: /tmp/tmp7yr82lhh
[safe-rmtree] starting: path=/tmp/tmp1nqdckur allowed_root=/tmp/tmp1nqdckur
[safe-rmtree] removed: /tmp/tmp1nqdckur
[safe-rmtree] starting: path=/tmp/tmpu4darr07 allowed_root=/tmp/tmpu4darr07
[safe-rmtree] removed: /tmp/tmpu4darr07
[safe-rmtree] starting: path=/tmp/tmp8x8ylf7i allowed_root=/tmp/tmp8x8ylf7i
[safe-rmtree] removed: /tmp/tmp8x8ylf7i
[safe-rmtree] starting: path=/tmp/tmp8ssawxtw allowed_root=/tmp/tmp8ssawxtw
[safe-rmtree] removed: /tmp/tmp8ssawxtw
[safe-rmtree] starting: path=/tmp/tmphn0sk2wv allowed_root=/tmp/tmphn0sk2wv
[safe-rmtree] removed: /tmp/tmphn0sk2wv
[safe-rmtree] starting: path=/tmp/tmp7ps47s_k allowed_root=/tmp/tmp7ps47s_k
[safe-rmtree] removed: /tmp/tmp7ps47s_k
[safe-rmtree] starting: path=/tmp/tmp6b897_mt allowed_root=/tmp/tmp6b897_mt
[safe-rmtree] removed: /tmp/tmp6b897_mt
[safe-rmtree] starting: path=/tmp/tmp7uebzu3x allowed_root=/tmp/tmp7uebzu3x
[safe-rmtree] removed: /tmp/tmp7uebzu3x
[safe-rmtree] starting: path=/tmp/tmpllb45uh1 allowed_root=/tmp/tmpllb45uh1
[safe-rmtree] removed: /tmp/tmpllb45uh1
[safe-rmtree] starting: path=/tmp/tmpeogttgax allowed_root=/tmp/tmpeogttgax
[safe-rmtree] removed: /tmp/tmpeogttgax
[safe-rmtree] starting: path=/tmp/tmp6vvtiofz allowed_root=/tmp/tmp6vvtiofz
[safe-rmtree] removed: /tmp/tmp6vvtiofz
[safe-rmtree] starting: path=/tmp/tmpuq7u4my8 allowed_root=/tmp/tmpuq7u4my8
[safe-rmtree] removed: /tmp/tmpuq7u4my8
[safe-rmtree] starting: path=/tmp/tmpvqlirxfx allowed_root=/tmp/tmpvqlirxfx
[safe-rmtree] removed: /tmp/tmpvqlirxfx
[safe-rmtree] starting: path=/tmp/tmpaqoc3nw8 allowed_root=/tmp/tmpaqoc3nw8
[safe-rmtree] removed: /tmp/tmpaqoc3nw8
[safe-rmtree] starting: path=/tmp/tmpu8hcnyf4 allowed_root=/tmp/tmpu8hcnyf4
[safe-rmtree] removed: /tmp/tmpu8hcnyf4
[safe-rmtree] starting: path=/tmp/tmp2c5tg3bk allowed_root=/tmp/tmp2c5tg3bk
[safe-rmtree] removed: /tmp/tmp2c5tg3bk
[safe-rmtree] starting: path=/tmp/tmpa0x6ms9o allowed_root=/tmp/tmpa0x6ms9o
[safe-rmtree] removed: /tmp/tmpa0x6ms9o
[safe-rmtree] starting: path=/tmp/tmp_5y3zc3p allowed_root=/tmp/tmp_5y3zc3p
[safe-rmtree] removed: /tmp/tmp_5y3zc3p
[safe-rmtree] starting: path=/tmp/tmpe3fse0vx allowed_root=/tmp/tmpe3fse0vx
[safe-rmtree] removed: /tmp/tmpe3fse0vx
[safe-rmtree] starting: path=/tmp/tmpnfmgmm0p allowed_root=/tmp/tmpnfmgmm0p
[safe-rmtree] removed: /tmp/tmpnfmgmm0p
[safe-rmtree] starting: path=/tmp/tmpxjqgou4f allowed_root=/tmp/tmpxjqgou4f
[safe-rmtree] removed: /tmp/tmpxjqgou4f
[safe-rmtree] starting: path=/tmp/tmp6u0r_g_q allowed_root=/tmp/tmp6u0r_g_q
[safe-rmtree] removed: /tmp/tmp6u0r_g_q
[safe-rmtree] starting: path=/tmp/tmprm45l2qz allowed_root=/tmp/tmprm45l2qz
[safe-rmtree] removed: /tmp/tmprm45l2qz
[safe-rmtree] starting: path=/tmp/tmpkls93_td allowed_root=/tmp/tmpkls93_td
[safe-rmtree] removed: /tmp/tmpkls93_td
[_review_common] warning: finding has unknown or missing class -- foo
[_review_common] warning: finding has unknown or missing class -- bar
[_review_common] warning: finding has unknown or missing class -- baz
[_review_common] warning: finding has unknown or missing class -- borderline concern
[safe-rmtree] starting: path=/tmp/tmp73t59yc5 allowed_root=/tmp/tmp73t59yc5
[safe-rmtree] removed: /tmp/tmp73t59yc5
[safe-rmtree] starting: path=/tmp/tmpbba66zxg allowed_root=/tmp/tmpbba66zxg
[safe-rmtree] removed: /tmp/tmpbba66zxg
[safe-rmtree] starting: path=/tmp/tmp08u_pjv3 allowed_root=/tmp/tmp08u_pjv3
[safe-rmtree] removed: /tmp/tmp08u_pjv3
[safe-rmtree] starting: path=/tmp/tmpd0sfuq2b allowed_root=/tmp/tmpd0sfuq2b
[safe-rmtree] removed: /tmp/tmpd0sfuq2b
[safe-rmtree] starting: path=/tmp/tmp5t3vw52f allowed_root=/tmp/tmp5t3vw52f
[safe-rmtree] removed: /tmp/tmp5t3vw52f
[safe-rmtree] starting: path=/tmp/tmpg3o_2xvd allowed_root=/tmp/tmpg3o_2xvd
[safe-rmtree] removed: /tmp/tmpg3o_2xvd
[safe-rmtree] starting: path=/tmp/tmpiz9jn5sg allowed_root=/tmp/tmpiz9jn5sg
[safe-rmtree] removed: /tmp/tmpiz9jn5sg
[safe-rmtree] starting: path=/tmp/tmpy73vndab allowed_root=/tmp/tmpy73vndab
[safe-rmtree] removed: /tmp/tmpy73vndab
[safe-rmtree] starting: path=/tmp/tmpjjsck744 allowed_root=/tmp/tmpjjsck744
[safe-rmtree] removed: /tmp/tmpjjsck744
[safe-rmtree] starting: path=/tmp/tmp9lwrda8a allowed_root=/tmp/tmp9lwrda8a
[safe-rmtree] removed: /tmp/tmp9lwrda8a
[bulk_files_with_diff] warning: /tmp/tmpexl8xl_i/nonexistent.py not found or not readable, skipping
[safe-rmtree] starting: path=/tmp/tmpexl8xl_i allowed_root=/tmp/tmpexl8xl_i
[safe-rmtree] removed: /tmp/tmpexl8xl_i
[subprocess] spawn argv=['git', '-C', '/tmp/tmpalmnixmq', 'diff', 'deadbeefdeadbeefdeadbeefdeadbeefdeadbeef..HEAD', '--', 'src/a.py'] timeout=None
[subprocess] exit code=128 duration=0.001s
[bulk_files_with_diff] warning: git diff failed for /tmp/tmpalmnixmq/src/a.py (returncode=128), using full file
[safe-rmtree] starting: path=/tmp/tmpalmnixmq allowed_root=/tmp/tmpalmnixmq
[safe-rmtree] removed: /tmp/tmpalmnixmq
[safe-rmtree] starting: path=/tmp/tmpixrklq1i allowed_root=/tmp/tmpixrklq1i
[safe-rmtree] removed: /tmp/tmpixrklq1i
[safe-rmtree] starting: path=/tmp/tmpww2g4ruy allowed_root=/tmp/tmpww2g4ruy
[safe-rmtree] removed: /tmp/tmpww2g4ruy
[safe-rmtree] starting: path=/tmp/tmpm5z93bkp allowed_root=/tmp/tmpm5z93bkp
[safe-rmtree] removed: /tmp/tmpm5z93bkp
[safe-rmtree] starting: path=/tmp/tmp6wu6bs3a allowed_root=/tmp/tmp6wu6bs3a
[safe-rmtree] removed: /tmp/tmp6wu6bs3a
[safe-rmtree] starting: path=/tmp/tmp5evhs3is allowed_root=/tmp/tmp5evhs3is
[safe-rmtree] removed: /tmp/tmp5evhs3is
[safe-rmtree] starting: path=/tmp/tmp3_5y08w7 allowed_root=/tmp/tmp3_5y08w7
[safe-rmtree] removed: /tmp/tmp3_5y08w7
[safe-rmtree] starting: path=/tmp/tmpl7bw29ro allowed_root=/tmp/tmpl7bw29ro
[safe-rmtree] removed: /tmp/tmpl7bw29ro
[safe-rmtree] starting: path=/tmp/tmprlp62jbo allowed_root=/tmp/tmprlp62jbo
[safe-rmtree] removed: /tmp/tmprlp62jbo
[safe-rmtree] starting: path=/tmp/tmpgx8bzvut allowed_root=/tmp/tmpgx8bzvut
[safe-rmtree] removed: /tmp/tmpgx8bzvut
[safe-rmtree] starting: path=/tmp/tmp5lqyb0o3 allowed_root=/tmp/tmp5lqyb0o3
[safe-rmtree] removed: /tmp/tmp5lqyb0o3
[safe-rmtree] starting: path=/tmp/tmpzb6bw1os allowed_root=/tmp/tmpzb6bw1os
[safe-rmtree] removed: /tmp/tmpzb6bw1os
[safe-rmtree] starting: path=/tmp/tmpluc09s3j allowed_root=/tmp/tmpluc09s3j
[safe-rmtree] removed: /tmp/tmpluc09s3j
[safe-rmtree] starting: path=/tmp/tmp4fbjw0zg allowed_root=/tmp/tmp4fbjw0zg
[safe-rmtree] removed: /tmp/tmp4fbjw0zg
[safe-rmtree] starting: path=/tmp/tmper1s_w0w allowed_root=/tmp/tmper1s_w0w
[safe-rmtree] removed: /tmp/tmper1s_w0w
[_read_for_bulk] warning: /tmp/tmpsqd6ra43/subdir is a directory, skipping
[safe-rmtree] starting: path=/tmp/tmpsqd6ra43 allowed_root=/tmp/tmpsqd6ra43
[safe-rmtree] removed: /tmp/tmpsqd6ra43
[safe-rmtree] starting: path=/tmp/tmpbxcebxlr allowed_root=/tmp/tmpbxcebxlr
[safe-rmtree] removed: /tmp/tmpbxcebxlr
[safe-rmtree] starting: path=/tmp/tmpzqkkiu4w allowed_root=/tmp/tmpzqkkiu4w
[safe-rmtree] removed: /tmp/tmpzqkkiu4w
[safe-rmtree] starting: path=/tmp/tmp2tt31mhb allowed_root=/tmp/tmp2tt31mhb
[safe-rmtree] removed: /tmp/tmp2tt31mhb
[safe-rmtree] starting: path=/tmp/tmp6tkojqq_ allowed_root=/tmp/tmp6tkojqq_
[safe-rmtree] removed: /tmp/tmp6tkojqq_
[safe-rmtree] starting: path=/tmp/tmpe1i2t7px allowed_root=/tmp/tmpe1i2t7px
[safe-rmtree] removed: /tmp/tmpe1i2t7px
[safe-rmtree] starting: path=/tmp/tmpnp3nplk5 allowed_root=/tmp/tmpnp3nplk5
[safe-rmtree] removed: /tmp/tmpnp3nplk5
[safe-rmtree] starting: path=/tmp/tmpa7hg0c_x allowed_root=/tmp/tmpa7hg0c_x
[safe-rmtree] removed: /tmp/tmpa7hg0c_x
[safe-rmtree] starting: path=/tmp/tmpba0s6sqo allowed_root=/tmp/tmpba0s6sqo
[safe-rmtree] removed: /tmp/tmpba0s6sqo
[safe-rmtree] starting: path=/tmp/tmpm35uul2p allowed_root=/tmp/tmpm35uul2p
[safe-rmtree] removed: /tmp/tmpm35uul2p
[safe-rmtree] starting: path=/tmp/tmp2ti7tzxn allowed_root=/tmp/tmp2ti7tzxn
[safe-rmtree] removed: /tmp/tmp2ti7tzxn
[safe-rmtree] starting: path=/tmp/tmps60zj6ob allowed_root=/tmp/tmps60zj6ob
[safe-rmtree] removed: /tmp/tmps60zj6ob
[safe-rmtree] starting: path=/tmp/tmpko_b3btn allowed_root=/tmp/tmpko_b3btn
[safe-rmtree] removed: /tmp/tmpko_b3btn
[safe-rmtree] starting: path=/tmp/tmpn3tiqwsj allowed_root=/tmp/tmpn3tiqwsj
[safe-rmtree] removed: /tmp/tmpn3tiqwsj
[safe-rmtree] starting: path=/tmp/tmpslwsgi0h allowed_root=/tmp/tmpslwsgi0h
[safe-rmtree] removed: /tmp/tmpslwsgi0h
[safe-rmtree] starting: path=/tmp/tmprxz4kotc allowed_root=/tmp/tmprxz4kotc
[safe-rmtree] removed: /tmp/tmprxz4kotc
[safe-rmtree] starting: path=/tmp/tmpeuqfq7nx allowed_root=/tmp/tmpeuqfq7nx
[safe-rmtree] removed: /tmp/tmpeuqfq7nx
[safe-rmtree] starting: path=/tmp/tmph1zilwyn allowed_root=/tmp/tmph1zilwyn
[safe-rmtree] removed: /tmp/tmph1zilwyn
[safe-rmtree] starting: path=/tmp/tmp2mf9o9zi allowed_root=/tmp/tmp2mf9o9zi
[safe-rmtree] removed: /tmp/tmp2mf9o9zi
[safe-rmtree] starting: path=/tmp/tmpjxmnhqmo allowed_root=/tmp/tmpjxmnhqmo
[safe-rmtree] removed: /tmp/tmpjxmnhqmo
[safe-rmtree] starting: path=/tmp/tmp02rjhg68 allowed_root=/tmp/tmp02rjhg68
[safe-rmtree] removed: /tmp/tmp02rjhg68
[safe-rmtree] starting: path=/tmp/tmpegaq6wuu allowed_root=/tmp/tmpegaq6wuu
[safe-rmtree] removed: /tmp/tmpegaq6wuu
[safe-rmtree] starting: path=/tmp/tmphjnit80i allowed_root=/tmp/tmphjnit80i
[safe-rmtree] removed: /tmp/tmphjnit80i
[safe-rmtree] starting: path=/tmp/tmp83_617rz allowed_root=/tmp/tmp83_617rz
[safe-rmtree] removed: /tmp/tmp83_617rz
[safe-rmtree] starting: path=/tmp/tmp_v29wrda allowed_root=/tmp/tmp_v29wrda
[safe-rmtree] removed: /tmp/tmp_v29wrda
[safe-rmtree] starting: path=/tmp/tmpb_fjtxwh allowed_root=/tmp/tmpb_fjtxwh
[safe-rmtree] removed: /tmp/tmpb_fjtxwh
[safe-rmtree] starting: path=/tmp/tmpstvvmo49 allowed_root=/tmp/tmpstvvmo49
[safe-rmtree] removed: /tmp/tmpstvvmo49
Running 3 tests across 12 worker(s).
--- PASS test-review-class-taxonomy.py (0.1s) ---
--- FAIL test-review-finalize.py (0.2s) ---
--- PASS test-review-common.py (0.4s) ---

Slowest 10:
     0.4s  test-review-common.py
     0.2s  test-review-finalize.py
     0.1s  test-review-class-taxonomy.py

FAIL -- 1 of 3 in 0.4s: ['test-review-finalize.py']
```

## Merge Diff

```diff
diff --git a/plugins/mill/scripts/_implementer_common.py b/plugins/mill/scripts/_implementer_common.py
index 483767f0..33a6c8f9 100644
--- a/plugins/mill/scripts/_implementer_common.py
+++ b/plugins/mill/scripts/_implementer_common.py
@@ -1787,25 +1787,34 @@ def _forward_output(
             print(json.dumps(_incomplete_envelope))
             return 0
 
-        result = _subprocess_util.run(
-            ["git", "rev-parse", "HEAD"],
-            cwd=project_root,
-        )
-        if result.returncode == 0 and _is_valid_commit_sha(result.stdout.strip()):
-            parsed["commit_sha"] = result.stdout.strip()
-            violations = _cleanliness.compute_scope_violations(project_root, git_root)
-            if violations:
-                parsed["scope_violations"] = violations
-            print(json.dumps(parsed))
+        # The corrective git rev-parse HEAD / _is_valid_commit_sha block below only ever
+        # applies to a self-reported status: success -- every other status (already-classified
+        # stuck/*, or anything else that reaches this point) must print through unchanged.
+        # Running the correction unconditionally here previously let an unrelated corrective-SHA
+        # failure silently corrupt an already-correct stuck/transient or stuck/verify report into
+        # stuck/logic (see the forward-output-stuck-passthrough postmortem).
+        if parsed.get("status") == "success":
+            result = _subprocess_util.run(
+                ["git", "rev-parse", "HEAD"],
+                cwd=project_root,
+            )
+            if result.returncode == 0 and _is_valid_commit_sha(result.stdout.strip()):
+                parsed["commit_sha"] = result.stdout.strip()
+                violations = _cleanliness.compute_scope_violations(project_root, git_root)
+                if violations:
+                    parsed["scope_violations"] = violations
+                print(json.dumps(parsed))
+            else:
+                # The corrective git rev-parse HEAD call failed or returned a malformed SHA -- never pass an agent's unvalidated self-reported commit_sha through on the success path (see #744 postmortem).
+                _correction_failure = {
+                    "status": "stuck",
+                    "stuck_type": "logic",
+                    "reason": "commit_sha correction failed: git rev-parse HEAD did not return a well-formed SHA",
+                    "session_id": session_id or parsed.get("session_id") or "unknown",
+                }
+                print(json.dumps(_correction_failure))
         else:
-            # The corrective git rev-parse HEAD call failed or returned a malformed SHA -- never pass an agent's unvalidated self-reported commit_sha through on the success path (see #744 postmortem).
-            _correction_failure = {
-                "status": "stuck",
-                "stuck_type": "logic",
-                "reason": "commit_sha correction failed: git rev-parse HEAD did not return a well-formed SHA",
-                "session_id": session_id or parsed.get("session_id") or "unknown",
-            }
-            print(json.dumps(_correction_failure))
+            print(json.dumps(parsed))
         return 0
     try:
         if (
diff --git a/plugins/mill/scripts/_plan_validate.py b/plugins/mill/scripts/_plan_validate.py
index 5a4a182b..b8827383 100644
--- a/plugins/mill/scripts/_plan_validate.py
+++ b/plugins/mill/scripts/_plan_validate.py
@@ -36,9 +36,9 @@ Checks performed (check keys):
     verify-unrelated-test-file — verify: --only test-file token untouched by its own batch and
         byte-identical to the parent branch
     verify-excludes-edited-tagged-test — Go-specific (gated on go.mod presence);
-        flags a batch whose Edits:-only _test.go files include a //go:build ...integration...-tagged
-            file when the batch's verify: command lacks a matching -tags ...integration...
-        flag
+        discovers each edited _test.go file's custom tag(s) from its own //go:build expression via
+        denylist (GOOS/GOARCH/reserved-word/release-version tags excluded), and flags every edited
+        tagged file independently whose batch verify: command lacks a matching -tags flag
     wiki-config-mutation — batch Edits:/Creates: contains mill-config.yaml (self-applying layout
         risk)
     plugin-manifest-context-missing — batch Creates:/Edits:/Deletes: touches plugins/mill/agents/
@@ -126,29 +126,33 @@ _REQUIRED_CARD_FIELDS = ["Context", "Edits", "Creates", "Deletes", "Moves", "Req
 def _parse_cards(batch_text: str) -> list[tuple[int, list[str]]]:
     """Return list of (card_number, card_lines) pairs.
 
-    Each card block starts at a ``### Card N:`` line and ends just before the next ``### `` heading
-    or at EOF.
+    Each card block starts at a ``### Card N:`` line and ends just before the next ``### ``
+    heading or at EOF. A ``### `` line inside a fenced code block (delimited by lines starting
+    with ``` ``` ```, toggled per ``_requirements_fence_aware_body``'s convention) never starts
+    or ends a card block.
     """
     lines = batch_text.splitlines()
     cards: list[tuple[int, list[str]]] = []
     current_num: int | None = None
     current_lines: list[str] = []
+    in_fence = False
 
     for line in lines:
-        m = re.match(r"^###\s+Card\s+(\d+)\s*:", line)
+        m = re.match(r"^###\s+Card\s+(\d+)\s*:", line) if not in_fence else None
         if m:
             if current_num is not None:
                 cards.append((current_num, current_lines))
             current_num = int(m.group(1))
             current_lines = [line]
         elif current_num is not None:
-            # Any other ### heading terminates the current card block.
-            if line.startswith("### "):
+            if not in_fence and line.startswith("### "):
                 cards.append((current_num, current_lines))
                 current_num = None
                 current_lines = []
             else:
                 current_lines.append(line)
+        if line.startswith("```"):
+            in_fence = not in_fence
 
     if current_num is not None:
         cards.append((current_num, current_lines))
@@ -1937,7 +1941,7 @@ def _check_verify_not_isolated(
 # ---------------------------------------------------------------------------
 
 # Matches a Go build-constraint comment line: "//go:build <expr>".
-# The captured expression is checked for the word "integration".
+# The captured expression's identifiers are extracted and filtered against the denylist below to discover custom tags.
 _RE_GO_BUILD_CONSTRAINT = re.compile(r"^//go:build\s+(?P<expr>.*)$")
 
 # Matches a -tags flag (space or = separated) and its value, which may be a quoted (comma/space-separated) list or a single bare (comma-separated) token.
@@ -1946,22 +1950,54 @@ _RE_VERIFY_TAGS_FLAG = re.compile(r"-tags[= ]+(\"[^\"]*\"|'[^']*'|\S+)")
 # Safety net bounding the //go:build header-comment scan well above real-world license-header lengths (Apache-2.0 ~15 lines, BSD-3-Clause ~25-27 lines), so a long copyright header never causes an unbounded scan.
 _GO_BUILD_TAG_SCAN_LINES = 40
 
-
-def _go_file_is_integration_tagged(path: Path) -> bool:
+# Standard Go build tags that are never "custom" -- discovering a GOOS/GOARCH/reserved/
+# release-version identifier in a //go:build expression must not require a matching -tags
+# flag (those tags are satisfied automatically, never via -tags).
+_GO_BUILD_DENYLIST_GOOS = frozenset({
+    "aix", "android", "darwin", "dragonfly", "freebsd", "hurd", "illumos", "ios", "js",
+    "linux", "nacl", "netbsd", "openbsd", "plan9", "solaris", "wasip1", "windows", "zos",
+})
+_GO_BUILD_DENYLIST_GOARCH = frozenset({
+    "386", "amd64", "amd64p32", "arm", "armbe", "arm64", "arm64be", "loong64", "mips",
+    "mipsle", "mips64", "mips64le", "mips64p32", "mips64p32le", "ppc", "ppc64", "ppc64le",
+    "riscv", "riscv64", "s390", "s390x", "sparc", "sparc64", "wasm",
+})
+_GO_BUILD_DENYLIST_RESERVED = frozenset({
+    "cgo", "race", "msan", "asan", "unix", "boringcrypto", "gc", "gccgo", "purego", "ignore",
+})
+# Release-version tags (e.g. "go1.21") are also never custom.
+_RE_GO_RELEASE_VERSION_TAG = re.compile(r"^go[1-9]\d*\.\d+$")
+
+# Deliberate divergence from _implementer_common.py's _GO_BUILD_TAG_GOOS/_GO_BUILD_TAG_GOARCH
+# (lines 1014-1017 there): that smaller set is safe only because its caller
+# (_go_build_tag_retiering_stuck) runs `go build -tags <tag>` downstream, so a
+# misclassified real GOOS/GOARCH value fails the compile and surfaces as stuck_type: verify
+# (fails closed). This check has no downstream compile step -- a misclassified value here
+# would silently create a new, never-corrected false positive, so it intentionally uses a
+# larger, more complete denylist and must not share a constant with that smaller set.
+
+
+def _go_file_custom_tags(path: Path) -> set[str]:
     """
-    Return True if a Go source file's leading //go:build constraint mentions "integration".
+    Return the set of custom build tags discovered in a Go source file's leading //go:build line.
 
     Scans from the top of the file, skipping blank lines and `//`-comment lines (a license/copyright
     header may precede the build-constraint line);
     the first line that is neither blank nor a `//`-comment ends the scan (e.g. `package foo` or a
     `/*` block comment opener).
     Bounded to the first `_GO_BUILD_TAG_SCAN_LINES` lines.
+    On the first scanned `//go:build` line, every identifier in its constraint expression is
+    extracted and the ones NOT in `_GO_BUILD_DENYLIST_GOOS`, `_GO_BUILD_DENYLIST_GOARCH`,
+    `_GO_BUILD_DENYLIST_RESERVED`, and not matching `_RE_GO_RELEASE_VERSION_TAG` (a
+    custom tag discovered from the file's own `//go:build` expression, GOOS/GOARCH/
+    reserved-word/release-version tags excluded via denylist) are returned.
 
     Args:
         path: Path to an existing Go source file on disk.
 
     Returns:
-        True if a scanned `//go:build` line's constraint expression contains the word "integration".
+        The set[str] of custom tags found on the first scanned `//go:build` line; empty when no such
+        line is found before the scan ends.
     """
     text = path.read_text(encoding="utf-8")
     for line in text.splitlines()[:_GO_BUILD_TAG_SCAN_LINES]:
@@ -1971,31 +2007,40 @@ def _go_file_is_integration_tagged(path: Path) -> bool:
         if not stripped.startswith("//"):
             break
         m = _RE_GO_BUILD_CONSTRAINT.match(stripped)
-        if m and re.search(r"\bintegration\b", m.group("expr")):
-            return True
-    return False
+        if m:
+            identifiers = re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", m.group("expr"))
+            return {
+                ident for ident in identifiers
+                if ident not in _GO_BUILD_DENYLIST_GOOS
+                and ident not in _GO_BUILD_DENYLIST_GOARCH
+                and ident not in _GO_BUILD_DENYLIST_RESERVED
+                and not _RE_GO_RELEASE_VERSION_TAG.match(ident)
+            }
+    return set()
 
 
-def _verify_command_has_integration_tag(command: str) -> bool:
+def _verify_command_has_any_tag(command: str, tags: set[str]) -> bool:
     """
-    Return True if a verify: command's -tags flag value includes "integration".
+    Return True if a verify: command's -tags flag value includes any of `tags`.
 
-    Matches `-tags integration`, `-tags=integration`, and a quoted or bare comma-separated value
-    like `-tags "integration,other"` or `-tags integration,other`.
-    A value like `integrationtest` does not count -- the match requires "integration" as an exact
-    comma/whitespace-split token, not a substring.
+    Matches `-tags <tag>`, `-tags=<tag>`, and a quoted or bare comma-separated value like
+    `-tags "<tag>,other"` or `-tags <tag>,other`.
+    A value that merely contains a tag as a substring (e.g. `integrationtest` for tag
+    `integration`) does not count -- the match requires an exact comma/whitespace-split token,
+    not a substring.
 
     Args:
         command: The verify: command string (already normalized via `_plan_dag.parse_verify_field`).
+        tags: The set of custom tags to match against; the check passes if ANY of them appears.
 
     Returns:
-        True if any `-tags` flag in the command carries "integration" as one of its
+        True if any `-tags` flag in the command carries at least one of `tags` as one of its
         comma/whitespace-split values.
     """
     for m in _RE_VERIFY_TAGS_FLAG.finditer(command):
         value = m.group(1).strip("\"'")
         tokens = re.split(r"[,\s]+", value)
-        if "integration" in tokens:
+        if set(tokens) & tags:
             return True
     return False
 
@@ -2009,7 +2054,7 @@ def _check_verify_excludes_edited_tagged_test(
     git_root: Path | None = None,
 ) -> list[dict]:
     """
-    Flag a batch whose verify: command silently skips an edited integration-tagged Go test.
+    Flag a batch whose verify: command silently skips an edited custom-tagged Go test.
 
     Go-specific: gated on `(project_root / "go.mod").exists()`, fail-open for every non-Go project
     -- mirrors `_check_verify_not_isolated`'s `is_python_project` gate.
@@ -2017,16 +2062,19 @@ def _check_verify_excludes_edited_tagged_test(
     For each batch, collects `Edits:`-only tokens ending in `_test.go` (via `_parse_edits_only`,
     filtered to that suffix). `Creates:` tokens are deliberately excluded from this collection: a
     `Creates:` target does not exist on disk at plan-validation time (this codebase's established
-    convention), so `resolve_existing_paths` would never confirm it as integration-tagged anyway --
-    an accepted, documented limitation, not a bug (see the Card 6 `(h)` regression scenario).
-
-    Each resolved edited test file is scanned via `_go_file_is_integration_tagged`.
-    When a batch has at least one edited integration-tagged test, its `verify:` command (normalized
-    via `_plan_dag.parse_verify_field`; a malformed `{cwd, command}` mapping raises `ValueError` --
-    caught and skipped here since `_check_verify_malformed_cwd` is the sole reporter for that) must
-    carry a `-tags` flag whose value includes "integration" (`_verify_command_has_integration_tag`);
-    otherwise this check reports the batch with one finding naming the first (sorted) tagged token
-    found.
+    convention), so `resolve_existing_paths` would never confirm it as custom-tagged anyway -- an
+    accepted, documented limitation, not a bug (see the Card 6 `(h)` regression scenario).
+
+    Each resolved edited test file is scanned via `_go_file_custom_tags`, which discovers custom
+    tags from the file's own `//go:build` expression (GOOS/GOARCH/reserved-word/release-version
+    tags excluded via denylist). Every edited tagged file is checked independently -- not just the
+    first -- so a batch editing multiple custom-tagged test files gets one finding per untested
+    file. The batch's `verify:` command (normalized once per batch via `_plan_dag.parse_verify_field`;
+    a malformed `{cwd, command}` mapping raises `ValueError` -- caught and skipped here since
+    `_check_verify_malformed_cwd` is the sole reporter for that) must carry a `-tags` flag whose
+    value includes at least one of a file's discovered tags (`_verify_command_has_any_tag`);
+    otherwise this check reports one finding for that file, naming the alphabetically-first
+    (`sorted(tags)[0]`) discovered tag for determinism.
 
     Error dict shape: ``{check, batch, card, path, message}``.
 
@@ -2042,8 +2090,8 @@ def _check_verify_excludes_edited_tagged_test(
         git_root: Optional repo root, threaded to `resolve_existing_paths`.
 
     Returns:
-        List of error dicts, one per batch with an edited integration-tagged test file whose verify:
-        command lacks a matching -tags flag.
+        List of error dicts, one per edited custom-tagged test file whose batch verify: command
+        lacks a matching -tags flag.
     """
     if not (project_root / "go.mod").exists():
         return []
@@ -2056,19 +2104,6 @@ def _check_verify_excludes_edited_tagged_test(
         if not edited_test_tokens:
             continue
 
-        tagged_token: str | None = None
-        for token in edited_test_tokens:
-            resolved = resolve_existing_paths(
-                [token], project_root, root, wiki_root=wiki_root, git_root=git_root,
-            )
-            if not resolved:
-                continue
-            if _go_file_is_integration_tagged(resolved[0]):
-                tagged_token = token
-                break
-        if tagged_token is None:
-            continue
-
         try:
             frontmatter = _plan_dag._read_batch_frontmatter(batch_path)
             command, _cwd = _plan_dag.parse_verify_field(
@@ -2078,18 +2113,26 @@ def _check_verify_excludes_edited_tagged_test(
             # _check_verify_malformed_cwd is the sole reporter for this.
             continue
 
-        if command is None or not _verify_command_has_integration_tag(command):
-            errors.append({
-                "check": "verify-excludes-edited-tagged-test",
-                "batch": batch_path.stem,
-                "card": None,
-                "path": tagged_token,
-                "message": (
-                    f"batch '{batch_path.stem}' edits integration-tagged test "
-                    f"'{tagged_token}' but its verify: command lacks a matching "
-                    "-tags ...integration... flag"
-                ),
-            })
+        for token in edited_test_tokens:
+            resolved = resolve_existing_paths(
+                [token], project_root, root, wiki_root=wiki_root, git_root=git_root,
+            )
+            if not resolved:
+                continue
+            tags = _go_file_custom_tags(resolved[0])
+            if not tags:
+                continue
+            if command is None or not _verify_command_has_any_tag(command, tags):
+                errors.append({
+                    "check": "verify-excludes-edited-tagged-test",
+                    "batch": batch_path.stem,
+                    "card": None,
+                    "path": token,
+                    "message": (
+                        f"batch '{batch_path.stem}' edits custom-tagged test '{token}' but its "
+                        f"verify: command lacks a matching -tags flag naming '{sorted(tags)[0]}'"
+                    ),
+                })
 
     return errors
 
diff --git a/plugins/mill/skills/mill-plan/SKILL.md b/plugins/mill/skills/mill-plan/SKILL.md
index e0f5dfb6..ae36f512 100644
--- a/plugins/mill/skills/mill-plan/SKILL.md
+++ b/plugins/mill/skills/mill-plan/SKILL.md
@@ -296,7 +296,7 @@ Each round:
    | requirements-quote-indent-drift | Locate the card's `Requirements:` fence identified by the error payload's `message` (its fence index and the reported strip amount `N` — the message carries no content snippet). Strip exactly `N` leading space characters from each line of the fence body (not necessarily to column 0 — preserve whatever baseline indentation remains after the strip) so its content is a literal byte-exact substring of the target `Edits:` file named in the payload's `path` field. |
    | verify-not-isolated            | Open the per-batch file named by the error payload's `batch:` field (resolve `_mill/plan/<batch>.md`). Read the offending command from the payload's `path:` field. Replace the frontmatter line `verify: <original>` with `verify: PYTHONPATH= <original>` (literal `PYTHONPATH=`, single space, original command). One row, one prepend. |
    | verify-unrelated-test-file     | Remove the named token (the payload's `path:` field) from the offending batch's `verify:` command frontmatter (identified by the payload's `batch:` field). Log what was dropped and why in the validator-fix commit message, so the drop is auditable rather than silent. |
-   | verify-excludes-edited-tagged-test | Open the offending batch's verify: command (payload's batch/path fields name the batch and the tagged test file). If a -tags flag already exists, append ,integration to its value; otherwise append " -tags integration" to the command. |
+   | verify-excludes-edited-tagged-test | Open the offending batch's verify: command (payload's batch/path fields name the batch and the tagged test file; the payload's message field names the missing tag in its trailing "naming '<tag>'" fragment). If a -tags flag already exists, append ,<tag> to its value; otherwise append " -tags <tag>" to the command. |
    | wiki-config-mutation           | This check cannot be fixed by editing plan files — the batch intentionally modifies `mill-config.yaml`. To proceed, verify one of two conditions: (a) a bootstrap card is present — a card whose body explains why the mill-config.yaml change is safe mid-flight for the currently-shipping task; or (b) the modified keys are provably unused — meaning key *removal or rename* where zero grep hits across `scripts/` and `skills/` confirm no existing code references them. (For key *addition* where consuming code is also being added in the same plan, zero grep hits does NOT satisfy condition (b); use (a) or halt.) If either condition holds: document the justification in the validator-fix commit message and re-run the CLI with `--skip-check wiki-config-mutation`. If `wiki-config-mutation` co-occurs with other fixable validator errors, fix those first per their rows, then re-run with `--skip-check wiki-config-mutation`. If neither condition holds: halt — the plan requires redesign. |
    | batch-oversized                | Halt — the batch exceeds `pipeline.max_cards_per_batch` cards and/or the `pipeline.max_batch_context_tokens` context estimate. Splitting a batch is a structural change, not a mechanical fix; the planner must re-split at Phase: Plan. Not auto-fixable. |
    | out-of-worktree-target         | Halt — an `Edits:`/`Creates:` target resolves outside the worktree (home-dir or absolute path). The operator must handle such edits manually; the implementer can never be pointed at them. Not auto-fixable. |
diff --git a/plugins/mill/unit_tests/test-agent-mode-dispatch.py b/plugins/mill/unit_tests/test-agent-mode-dispatch.py
index 2210462d..6f025df8 100644
--- a/plugins/mill/unit_tests/test-agent-mode-dispatch.py
+++ b/plugins/mill/unit_tests/test-agent-mode-dispatch.py
@@ -195,7 +195,7 @@ class TestImplementerModeParity(unittest.TestCase):
         # All other git calls (config, branch, add, commit, push, log) return a sensible default CompletedProcess so prepare's commit sequence succeeds.
         self._in_finalize = False
         self._prepare_head_sha = "abc1234"
-        self._finalize_head_sha = "def5678"
+        self._finalize_head_sha = "d" * 40
 
         def _git_side_effect(*args, **kwargs):
             argv = args[0] if args else kwargs.get("args", [])
diff --git a/plugins/mill/unit_tests/test-bg-json-contract.py b/plugins/mill/unit_tests/test-bg-json-contract.py
index 754cd2de..748a4ba6 100644
--- a/plugins/mill/unit_tests/test-bg-json-contract.py
+++ b/plugins/mill/unit_tests/test-bg-json-contract.py
@@ -123,7 +123,7 @@ class TestJsonContractEmitter(unittest.TestCase):
                 # Mock git rev-parse HEAD
                 mock_run_result = unittest.mock.MagicMock()
                 mock_run_result.returncode = 0
-                mock_run_result.stdout = "new_sha_123\n"
+                mock_run_result.stdout = "a" * 40 + "\n"
                 mock_run.return_value = mock_run_result
                 with unittest.mock.patch.object(
                     _implementer_common._cleanliness, "compute_scope_violations", return_value=[]
@@ -211,6 +211,35 @@ class TestJsonContractEmitter(unittest.TestCase):
         except json.JSONDecodeError as e:
             self.fail(f"_forward_output did not emit valid JSON fallback: {emitted!r}, error: {e}")
 
+    def test_forward_output_stuck_verify_passthrough_survives_bad_corrective_sha(self) -> None:
+        """An already-classified stuck/verify envelope must pass through unchanged even when
+        the corrective ``git rev-parse HEAD`` call would return a malformed SHA -- the
+        commit-SHA correction block only ever runs on the status: success path, so this
+        mocked malformed-SHA return is never even consulted here."""
+        agent_output = (
+            "some log output\n"
+            '{"status": "stuck", "stuck_type": "verify", "session_id": "fake-session"}\n'
+        )
+        project_root = Path(__file__).resolve().parent.parent.parent.parent
+        output_buffer = StringIO()
+        with contextlib.redirect_stdout(output_buffer):
+            with unittest.mock.patch.object(_implementer_common._subprocess_util, "run") as mock_run:
+                mock_run_result = unittest.mock.MagicMock()
+                mock_run_result.returncode = 0
+                mock_run_result.stdout = "not-a-sha\n"
+                mock_run.return_value = mock_run_result
+                with unittest.mock.patch.object(
+                    _implementer_common._cleanliness, "compute_scope_violations", return_value=[]
+                ):
+                    _implementer_common._forward_output(agent_output, project_root)
+        emitted = output_buffer.getvalue().strip()
+        try:
+            parsed = json.loads(emitted)
+            self.assertEqual(parsed["status"], "stuck")
+            self.assertEqual(parsed["stuck_type"], "verify")
+        except json.JSONDecodeError as e:
+            self.fail(f"_forward_output did not emit valid JSON: {emitted!r}, error: {e}")
+
 
 if __name__ == "__main__":
     unittest.main()
diff --git a/plugins/mill/unit_tests/test-claude-sub.py b/plugins/mill/unit_tests/test-claude-sub.py
index a68bee2f..1275ab26 100644
--- a/plugins/mill/unit_tests/test-claude-sub.py
+++ b/plugins/mill/unit_tests/test-claude-sub.py
@@ -289,6 +289,7 @@ def main() -> int:
                      mock.patch("_psmux.kill_session") as m_kill, \
                      mock.patch.object(mod, "_wait_for_marker_in_pane", return_value=True), \
                      mock.patch.object(mod, "_wait_for_idle_prompt", side_effect=mock_wait_for_idle_fails), \
+                     mock.patch.object(mod, "_wait_for_idle_stable", return_value=False), \
                      mock.patch("_paths.resolve_git_root", return_value=tmpdir_path), \
                      mock.patch("_config.load_config", return_value={}), \
                      mock.patch("sys.stdout", new_callable=io.StringIO), \
diff --git a/plugins/mill/unit_tests/test-millpy-claim.py b/plugins/mill/unit_tests/test-millpy-claim.py
index c4604d9f..e9744cf8 100644
--- a/plugins/mill/unit_tests/test-millpy-claim.py
+++ b/plugins/mill/unit_tests/test-millpy-claim.py
@@ -65,6 +65,11 @@ def _load_claim_module(stub_map: dict) -> object:
         saved[name] = sys.modules.get(name)
         sys.modules[name] = stub
     spec.loader.exec_module(mod)
+    # 'from wiki import _client as wiki' can resolve via a real '_client' attribute already
+    # cached on the 'wiki' package object by an earlier test in this process, bypassing the
+    # sys.modules["wiki._client"] injection above. Bind mod.wiki directly so every scenario
+    # reaches the stub instead of the real wiki._client module.
+    mod.wiki = stub_map["wiki._client"]
     return mod, saved
 
 
@@ -104,6 +109,10 @@ def _make_stub_map(
         "_junction": MagicMock(),
         "_config": config_mod,
         "_sibling": types.ModuleType("_sibling"),
+        # millpy-claim.py resolves 'from wiki import _client as wiki' via this sys.modules
+        # key; without it, every scenario's mod.main() reaches the real wiki._client code
+        # against the fake '/fake/wiki' path and hangs in _ensure_daemon's spawn-poll loop.
+        "wiki._client": MagicMock(),
     }
 
 
@@ -258,6 +267,7 @@ def test_main_happy_path_calls_spawn_core_helpers() -> None:
             patch.object(mod, "_is_dirty", return_value=False),
             patch.object(Path, "exists", return_value=True),
             patch.object(Path, "read_text", return_value="# Home\n"),
+            patch.object(Path, "mkdir", return_value=None),
         ):
             exit_code = mod.main(["--slug", "my-task"])
     finally:
@@ -367,6 +377,7 @@ def test_main_dirty_tree_stash_invokes_git_stash() -> None:
             patch.object(mod, "_prompt_dirty_tree", return_value=1),
             patch.object(Path, "exists", return_value=True),
             patch.object(Path, "read_text", return_value="# Home\n"),
+            patch.object(Path, "mkdir", return_value=None),
         ):
             exit_code = mod.main(["--slug", "my-task"])
     finally:
@@ -431,6 +442,7 @@ def test_main_multi_path_skips_claim_in_wiki() -> None:
             patch.object(mod, "_is_dirty", return_value=False),
             patch.object(Path, "exists", return_value=True),
             patch.object(Path, "read_text", return_value="# Home\n"),
+            patch.object(Path, "mkdir", return_value=None),
         ):
             exit_code = mod.main([])
     finally:
@@ -656,6 +668,7 @@ def test_main_hub_title_flip_when_cwd_is_hub() -> None:
             patch.object(mod, "_is_dirty", return_value=False),
             patch.object(Path, "exists", return_value=True),
             patch.object(Path, "read_text", return_value=green_settings),
+            patch.object(Path, "mkdir", return_value=None),
         ):
             exit_code = mod.main(["--slug", "my-task"])
     finally:
@@ -711,6 +724,7 @@ def test_hub_paths_use_cwd_not_git_root() -> None:
             patch.object(mod, "_is_dirty", return_value=False),
             patch.object(Path, "exists", return_value=True),
             patch.object(Path, "read_text", return_value="# Home\n"),
+            patch.object(Path, "mkdir", return_value=None),
         ):
             exit_code = mod.main(["--slug", "my-task"])
     finally:
diff --git a/plugins/mill/unit_tests/test-millpy-merge-in-subagent.py b/plugins/mill/unit_tests/test-millpy-merge-in-subagent.py
index bf47d9a9..bfc9cad3 100644
--- a/plugins/mill/unit_tests/test-millpy-merge-in-subagent.py
+++ b/plugins/mill/unit_tests/test-millpy-merge-in-subagent.py
@@ -40,7 +40,9 @@ def _clean_gate_side_effect(argv, **kwargs):
     contains neither "conflict marker" nor any of the test's input filenames.
     """
     if "rev-parse" in argv:
-        return subprocess.CompletedProcess(args=argv, returncode=0, stdout="abc1234\n", stderr="")
+        return subprocess.CompletedProcess(
+            args=argv, returncode=0, stdout="a" * 40 + "\n", stderr=""
+        )
     return subprocess.CompletedProcess(args=argv, returncode=0, stdout="", stderr="")
 
 
diff --git a/plugins/mill/unit_tests/test-millpy-spawn.py b/plugins/mill/unit_tests/test-millpy-spawn.py
index f694c3b2..c2ec0131 100644
--- a/plugins/mill/unit_tests/test-millpy-spawn.py
+++ b/plugins/mill/unit_tests/test-millpy-spawn.py
@@ -196,9 +196,19 @@ def _run_main_with_mocks(
     for name, stub in stub_map.items():
         saved[name] = sys.modules.get(name)
         sys.modules[name] = stub
+    # millpy-spawn.py resolves 'from wiki import _client as wiki' via this sys.modules key
+    # (the "_wiki" entry above is a dead stub for a module name it never imports). Without
+    # this, main() reaches the real wiki._client code against the fake '/fake/wiki' path.
+    wiki_client_mock = MagicMock()
+    saved_wiki_client = sys.modules.get("wiki._client")
+    sys.modules["wiki._client"] = wiki_client_mock
 
     try:
         spec.loader.exec_module(mod)
+        # 'from wiki import _client as wiki' can resolve via a real '_client' attribute
+        # already cached on the 'wiki' package object by an earlier test in this process,
+        # bypassing the sys.modules injection above. Bind mod.wiki directly as a fallback.
+        mod.wiki = wiki_client_mock
 
         # Patch config-loading and worktrees-dir resolution so main() doesn't hit the real filesystem.
         fake_cfg = {"spawn": {"branch_prefix": ""}}
@@ -217,6 +227,10 @@ def _run_main_with_mocks(
                 sys.modules.pop(name, None)
             else:
                 sys.modules[name] = original
+        if saved_wiki_client is None:
+            sys.modules.pop("wiki._client", None)
+        else:
+            sys.modules["wiki._client"] = saved_wiki_client
 
     return exit_code, spawn_core_mock, wiki_mock
 
@@ -330,9 +344,18 @@ def test_write_settings_uses_short_name_and_slug() -> None:
     for name, stub in stub_map.items():
         saved[name] = sys.modules.get(name)
         sys.modules[name] = stub
+    # millpy-spawn.py resolves 'from wiki import _client as wiki' via this sys.modules key
+    # (the "_wiki" entry above is a dead stub for a module name it never imports).
+    wiki_client_mock = MagicMock()
+    saved_wiki_client = sys.modules.get("wiki._client")
+    sys.modules["wiki._client"] = wiki_client_mock
 
     try:
         spec.loader.exec_module(mod)
+        # 'from wiki import _client as wiki' can resolve via a real '_client' attribute
+        # already cached on the 'wiki' package object by an earlier test in this process,
+        # bypassing the sys.modules injection above. Bind mod.wiki directly as a fallback.
+        mod.wiki = wiki_client_mock
         fake_cfg = {"spawn": {"branch_prefix": ""}}
         with (
             patch.object(mod, "_load_config", return_value=fake_cfg),
@@ -350,6 +373,10 @@ def test_write_settings_uses_short_name_and_slug() -> None:
                 sys.modules.pop(name, None)
             else:
                 sys.modules[name] = original
+        if saved_wiki_client is None:
+            sys.modules.pop("wiki._client", None)
+        else:
+            sys.modules["wiki._client"] = saved_wiki_client
 
     if exit_code != 0:
         raise AssertionError(f"expected exit 0, got {exit_code}")
@@ -422,8 +449,17 @@ def test_main_backlog_empty_exits_zero() -> None:
     for name, stub in stub_map.items():
         saved[name] = sys.modules.get(name)
         sys.modules[name] = stub
+    # millpy-spawn.py resolves 'from wiki import _client as wiki' via this sys.modules key
+    # (the "_wiki" entry above is a dead stub for a module name it never imports).
+    wiki_client_mock = MagicMock()
+    saved_wiki_client = sys.modules.get("wiki._client")
+    sys.modules["wiki._client"] = wiki_client_mock
     try:
         spec.loader.exec_module(mod)
+        # 'from wiki import _client as wiki' can resolve via a real '_client' attribute
+        # already cached on the 'wiki' package object by an earlier test in this process,
+        # bypassing the sys.modules injection above. Bind mod.wiki directly as a fallback.
+        mod.wiki = wiki_client_mock
         fake_cfg = {"spawn": {}}
         with (
             patch.object(mod, "_load_config", return_value=fake_cfg),
@@ -439,6 +475,10 @@ def test_main_backlog_empty_exits_zero() -> None:
                 sys.modules.pop(name, None)
             else:
                 sys.modules[name] = original
+        if saved_wiki_client is None:
+            sys.modules.pop("wiki._client", None)
+        else:
+            sys.modules["wiki._client"] = saved_wiki_client
 
     if exit_code != 0:
         raise AssertionError(f"empty mode should produce exit 0, got {exit_code}")
@@ -544,9 +584,18 @@ def test_create_hub_links_called_after_portal_creation() -> None:
     for name, stub in stub_map.items():
         saved[name] = sys.modules.get(name)
         sys.modules[name] = stub
+    # millpy-spawn.py resolves 'from wiki import _client as wiki' via this sys.modules key
+    # (the "_wiki" entry above is a dead stub for a module name it never imports).
+    wiki_client_mock = MagicMock()
+    saved_wiki_client = sys.modules.get("wiki._client")
+    sys.modules["wiki._client"] = wiki_client_mock
 
     try:
         spec.loader.exec_module(mod)
+        # 'from wiki import _client as wiki' can resolve via a real '_client' attribute
+        # already cached on the 'wiki' package object by an earlier test in this process,
+        # bypassing the sys.modules injection above. Bind mod.wiki directly as a fallback.
+        mod.wiki = wiki_client_mock
         fake_cfg = {"spawn": {"branch_prefix": ""}}
         with (
             patch.object(mod, "_load_config", return_value=fake_cfg),
@@ -569,6 +618,10 @@ def test_create_hub_links_called_after_portal_creation() -> None:
                 sys.modules.pop(name, None)
             else:
                 sys.modules[name] = original
+        if saved_wiki_client is None:
+            sys.modules.pop("wiki._client", None)
+        else:
+            sys.modules["wiki._client"] = saved_wiki_client
 
     if exit_code != 0:
         raise AssertionError(f"expected exit 0, got {exit_code}")
@@ -1118,10 +1171,12 @@ def test_spawn_aborts_when_origin_branch_already_exists() -> None:
     paths_mock.resolve_main_worktree_root.return_value = Path("/fake/repo")
     paths_mock.status_path.return_value = Path("/fake/worktrees/my-task/_mill/status.md")
 
+    wiki_mock = MagicMock()
+
     stub_map = {
         "_spawn_core": spawn_core_mock,
         "_setup": MagicMock(),
-        "_wiki": MagicMock(),
+        "_wiki": wiki_mock,
         "_junction": junction_mock,
         "_tasks_md": MagicMock(),
         "_vscode": MagicMock(),
@@ -1134,9 +1189,18 @@ def test_spawn_aborts_when_origin_branch_already_exists() -> None:
     for name, stub in stub_map.items():
         saved[name] = sys.modules.get(name)
         sys.modules[name] = stub
+    # millpy-spawn.py resolves 'from wiki import _client as wiki' via this sys.modules key
+    # (the "_wiki" entry above is a dead stub for a module name it never imports).
+    wiki_client_mock = MagicMock()
+    saved_wiki_client = sys.modules.get("wiki._client")
+    sys.modules["wiki._client"] = wiki_client_mock
 
     try:
         spec.loader.exec_module(mod)
+        # 'from wiki import _client as wiki' can resolve via a real '_client' attribute
+        # already cached on the 'wiki' package object by an earlier test in this process,
+        # bypassing the sys.modules injection above. Bind mod.wiki directly as a fallback.
+        mod.wiki = wiki_client_mock
         fake_cfg = {"spawn": {"branch_prefix": ""}}
         with (
             patch.object(mod, "_load_config", return_value=fake_cfg),
@@ -1153,6 +1217,10 @@ def test_spawn_aborts_when_origin_branch_already_exists() -> None:
                 sys.modules.pop(name, None)
             else:
                 sys.modules[name] = original
+        if saved_wiki_client is None:
+            sys.modules.pop("wiki._client", None)
+        else:
+            sys.modules["wiki._client"] = saved_wiki_client
 
     # Spawn must exit non-zero (return 1) when origin branch already exists.
     if exit_code != 1:
diff --git a/plugins/mill/unit_tests/test-plan-validate.py b/plugins/mill/unit_tests/test-plan-validate.py
index 66dcf07c..9566d2a4 100644
--- a/plugins/mill/unit_tests/test-plan-validate.py
+++ b/plugins/mill/unit_tests/test-plan-validate.py
@@ -5271,6 +5271,102 @@ def test_check_cards_legend_in_comment_not_parsed_as_refs() -> int:
             return 1
 
 
+def test_check_card_missing_field_fence_guard_clean() -> int:
+    """Issue #776's exact repro: a fenced ### heading in Requirements: must not truncate the card."""
+    with tempfile.TemporaryDirectory() as tmpdir:
+        tmp = Path(tmpdir)
+        plan_dir = tmp / "plan"
+        project_root = tmp / "project"
+
+        existing_file = project_root / "src" / "a.py"
+        existing_file.parent.mkdir(parents=True)
+        existing_file.write_text("# placeholder", encoding="utf-8")
+
+        requirements = (
+            "  Write the following exact heading into the target file:\n"
+            "  ```markdown\n"
+            "  ### Some Heading\n"
+            "  ```\n"
+        )
+        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
+        batch_text = _make_batch_file("alpha", edits=["src/a.py"], requirements=requirements)
+        _write_plan(plan_dir, overview, [("01-alpha.md", batch_text)])
+
+        result = _plan_validate.run(plan_dir, project_root)
+        check = [e for e in result if e["check"] == "card-missing-field"]
+        try:
+            assert check == [], (
+                f"expected no card-missing-field findings for a fenced ### heading "
+                f"in Requirements:, got: {check}"
+            )
+            print("PASS test_check_card_missing_field_fence_guard_clean")
+            return 0
+        except AssertionError as exc:
+            print(f"FAIL test_check_card_missing_field_fence_guard_clean: {exc}", file=sys.stderr)
+            return 1
+
+
+def test_check_card_missing_field_fence_guard_real_boundary_still_detected() -> int:
+    """Regression guard: the fence guard must not over-suppress a genuine card boundary."""
+    with tempfile.TemporaryDirectory() as tmpdir:
+        tmp = Path(tmpdir)
+        plan_dir = tmp / "plan"
+        project_root = tmp / "project"
+        project_root.mkdir()
+
+        frontmatter = (
+            "```yaml\n"
+            "task: test\nbatch: alpha\ncards: 2\nverify: null\ndepends-on: []\n"
+            "```\n\n"
+        )
+        card1 = (
+            "### Card 1: example\n\n"
+            "- **Context:** none\n"
+            "- **Edits:** none\n"
+            "- **Creates:** none\n"
+            "- **Deletes:** none\n"
+            "- **Moves:** none\n"
+            "- **Requirements:**\n"
+            "  Write the following exact heading into the target file:\n"
+            "  ```markdown\n"
+            "  ### Not A Real Heading\n"
+            "  ```\n"
+            "- **Commit:** feat(alpha): card 1\n"
+        )
+        card2 = (
+            "### Card 2: card 2\n\n"
+            "- **Context:** none\n"
+            "- **Edits:** none\n"
+            "- **Creates:** none\n"
+            "- **Deletes:** none\n"
+            "- **Moves:** none\n"
+            "- **Requirements:**\n  See scope.\n"
+            "- **Commit:** feat(alpha): card 2\n"
+        )
+        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
+        batch_text = (
+            "# Batch: alpha\n\n" + frontmatter
+            + "## Cards\n\n" + card1 + "\n" + card2
+        )
+        _write_plan(plan_dir, overview, [("01-alpha.md", batch_text)])
+
+        result = _plan_validate.run(plan_dir, project_root)
+        missing_field_hits = [e for e in result if e["check"] == "card-missing-field"]
+        numbering_hits = [e for e in result if e["check"] == "card-numbering"]
+        try:
+            assert missing_field_hits == [], (
+                f"expected no card-missing-field findings, got: {missing_field_hits}"
+            )
+            assert numbering_hits == [], (
+                f"expected no card-numbering findings, got: {numbering_hits}"
+            )
+            print("PASS test_check_card_missing_field_fence_guard_real_boundary_still_detected")
+            return 0
+        except AssertionError as exc:
+            print(f"FAIL test_check_card_missing_field_fence_guard_real_boundary_still_detected: {exc}", file=sys.stderr)
+            return 1
+
+
 # ---------------------------------------------------------------------------
 # verify-excludes-edited-tagged-test check (#724)
 # ---------------------------------------------------------------------------
@@ -5281,6 +5377,12 @@ _INTEGRATION_TAGGED_TEST_GO = "//go:build integration\n\npackage foo\n"
 
 _UNTAGGED_TEST_GO = "package foo\n\nfunc TestFoo(t *testing.T) {}\n"
 
+_SCOUT_TAGGED_TEST_GO = "//go:build scout\n\npackage foo\n"
+_SMOKE_TAGGED_TEST_GO = "//go:build smoke\n\npackage foo\n"
+_GOOS_ONLY_TAGGED_TEST_GO = "//go:build linux\n\npackage foo\n"
+_SCOUT_AND_SMOKE_TAGGED_TEST_GO = "//go:build scout && smoke\n\npackage foo\n"
+_LINUX_AND_SCOUT_TAGGED_TEST_GO = "//go:build linux && scout\n\npackage foo\n"
+
 _HEADER_COMMENT_INTEGRATION_TAGGED_TEST_GO = (
     "// Copyright 2024 Foo Corp.\n"
     "// Licensed under the Apache License, Version 2.0 (the \"License\");\n"
@@ -5554,6 +5656,317 @@ def test_verify_excludes_edited_tagged_test_creates_only_clean() -> int:
             return 1
 
 
+def test_verify_excludes_edited_tagged_test_scout_tag_no_tags_flag_dirty() -> int:
+    """Custom "scout" tag, verify: has no -tags -> one finding naming "scout"."""
+    with tempfile.TemporaryDirectory() as tmpdir:
+        tmp = Path(tmpdir)
+        plan_dir = tmp / "plan"
+        project_root = tmp / "project"
+        project_root.mkdir()
+        (project_root / "go.mod").write_text(_GO_MOD_TEXT, encoding="utf-8")
+        test_file = project_root / "pkg" / "foo_test.go"
+        test_file.parent.mkdir(parents=True, exist_ok=True)
+        test_file.write_text(_SCOUT_TAGGED_TEST_GO, encoding="utf-8")
+
+        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
+        batch_text = _make_verify_only_batch_text(
+            "alpha", "PYTHONPATH= go test ./...", edits=["pkg/foo_test.go"],
+        )
+        _write_plan(plan_dir, overview, [("01-alpha.md", batch_text)])
+
+        result = _plan_validate.run(plan_dir, project_root)
+        check = [e for e in result if e["check"] == "verify-excludes-edited-tagged-test"]
+        try:
+            assert len(check) == 1, f"expected 1 finding, got {len(check)}: {check}"
+            e = check[0]
+            assert e["path"] == "pkg/foo_test.go", f"wrong path: {e['path']!r}"
+            assert "scout" in e["message"], f"message missing 'scout': {e['message']!r}"
+            print("PASS test_verify_excludes_edited_tagged_test_scout_tag_no_tags_flag_dirty")
+            return 0
+        except AssertionError as exc:
+            print(f"FAIL test_verify_excludes_edited_tagged_test_scout_tag_no_tags_flag_dirty: {exc}", file=sys.stderr)
+            return 1
+
+
+def test_verify_excludes_edited_tagged_test_scout_tag_tags_scout_clean() -> int:
+    """Custom "scout" tag, verify: has -tags scout -> zero findings."""
+    with tempfile.TemporaryDirectory() as tmpdir:
+        tmp = Path(tmpdir)
+        plan_dir = tmp / "plan"
+        project_root = tmp / "project"
+        project_root.mkdir()
+        (project_root / "go.mod").write_text(_GO_MOD_TEXT, encoding="utf-8")
+        test_file = project_root / "pkg" / "foo_test.go"
+        test_file.parent.mkdir(parents=True, exist_ok=True)
+        test_file.write_text(_SCOUT_TAGGED_TEST_GO, encoding="utf-8")
+
+        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
+        batch_text = _make_verify_only_batch_text(
+            "alpha", "PYTHONPATH= go test ./... -tags scout", edits=["pkg/foo_test.go"],
+        )
+        _write_plan(plan_dir, overview, [("01-alpha.md", batch_text)])
+
+        result = _plan_validate.run(plan_dir, project_root)
+        check = [e for e in result if e["check"] == "verify-excludes-edited-tagged-test"]
+        try:
+            assert check == [], f"expected no findings, got: {check}"
+            print("PASS test_verify_excludes_edited_tagged_test_scout_tag_tags_scout_clean")
+            return 0
+        except AssertionError as exc:
+            print(f"FAIL test_verify_excludes_edited_tagged_test_scout_tag_tags_scout_clean: {exc}", file=sys.stderr)
+            return 1
+
+
+def test_verify_excludes_edited_tagged_test_smoke_tag_no_tags_flag_dirty() -> int:
+    """Custom "smoke" tag, verify: has no -tags -> one finding naming "smoke"."""
+    with tempfile.TemporaryDirectory() as tmpdir:
+        tmp = Path(tmpdir)
+        plan_dir = tmp / "plan"
+        project_root = tmp / "project"
+        project_root.mkdir()
+        (project_root / "go.mod").write_text(_GO_MOD_TEXT, encoding="utf-8")
+        test_file = project_root / "pkg" / "foo_test.go"
+        test_file.parent.mkdir(parents=True, exist_ok=True)
+        test_file.write_text(_SMOKE_TAGGED_TEST_GO, encoding="utf-8")
+
+        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
+        batch_text = _make_verify_only_batch_text(
+            "alpha", "PYTHONPATH= go test ./...", edits=["pkg/foo_test.go"],
+        )
+        _write_plan(plan_dir, overview, [("01-alpha.md", batch_text)])
+
+        result = _plan_validate.run(plan_dir, project_root)
+        check = [e for e in result if e["check"] == "verify-excludes-edited-tagged-test"]
+        try:
+            assert len(check) == 1, f"expected 1 finding, got {len(check)}: {check}"
+            assert "smoke" in check[0]["message"], f"message missing 'smoke': {check[0]['message']!r}"
+            print("PASS test_verify_excludes_edited_tagged_test_smoke_tag_no_tags_flag_dirty")
+            return 0
+        except AssertionError as exc:
+            print(f"FAIL test_verify_excludes_edited_tagged_test_smoke_tag_no_tags_flag_dirty: {exc}", file=sys.stderr)
+            return 1
+
+
+def test_verify_excludes_edited_tagged_test_smoke_tag_tags_smoke_clean() -> int:
+    """Custom "smoke" tag, verify: has -tags smoke -> zero findings."""
+    with tempfile.TemporaryDirectory() as tmpdir:
+        tmp = Path(tmpdir)
+        plan_dir = tmp / "plan"
+        project_root = tmp / "project"
+        project_root.mkdir()
+        (project_root / "go.mod").write_text(_GO_MOD_TEXT, encoding="utf-8")
+        test_file = project_root / "pkg" / "foo_test.go"
+        test_file.parent.mkdir(parents=True, exist_ok=True)
+        test_file.write_text(_SMOKE_TAGGED_TEST_GO, encoding="utf-8")
+
+        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
+        batch_text = _make_verify_only_batch_text(
+            "alpha", "PYTHONPATH= go test ./... -tags smoke", edits=["pkg/foo_test.go"],
+        )
+        _write_plan(plan_dir, overview, [("01-alpha.md", batch_text)])
+
+        result = _plan_validate.run(plan_dir, project_root)
+        check = [e for e in result if e["check"] == "verify-excludes-edited-tagged-test"]
+        try:
+            assert check == [], f"expected no findings, got: {check}"
+            print("PASS test_verify_excludes_edited_tagged_test_smoke_tag_tags_smoke_clean")
+            return 0
+        except AssertionError as exc:
+            print(f"FAIL test_verify_excludes_edited_tagged_test_smoke_tag_tags_smoke_clean: {exc}", file=sys.stderr)
+            return 1
+
+
+def test_verify_excludes_edited_tagged_test_goos_only_no_tags_flag_clean() -> int:
+    """Denylist-correctness regression guard: a plain //go:build linux file never needs -tags linux."""
+    with tempfile.TemporaryDirectory() as tmpdir:
+        tmp = Path(tmpdir)
+        plan_dir = tmp / "plan"
+        project_root = tmp / "project"
+        project_root.mkdir()
+        (project_root / "go.mod").write_text(_GO_MOD_TEXT, encoding="utf-8")
+        test_file = project_root / "pkg" / "foo_test.go"
+        test_file.parent.mkdir(parents=True, exist_ok=True)
+        test_file.write_text(_GOOS_ONLY_TAGGED_TEST_GO, encoding="utf-8")
+
+        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
+        batch_text = _make_verify_only_batch_text(
+            "alpha", "PYTHONPATH= go test ./...", edits=["pkg/foo_test.go"],
+        )
+        _write_plan(plan_dir, overview, [("01-alpha.md", batch_text)])
+
+        result = _plan_validate.run(plan_dir, project_root)
+        check = [e for e in result if e["check"] == "verify-excludes-edited-tagged-test"]
+        try:
+            assert check == [], f"expected no findings for a GOOS-only build tag, got: {check}"
+            print("PASS test_verify_excludes_edited_tagged_test_goos_only_no_tags_flag_clean")
+            return 0
+        except AssertionError as exc:
+            print(f"FAIL test_verify_excludes_edited_tagged_test_goos_only_no_tags_flag_clean: {exc}", file=sys.stderr)
+            return 1
+
+
+def test_verify_excludes_edited_tagged_test_multi_file_batch_untested_second_file_dirty() -> int:
+    """Two tagged files in one batch, verify: only covers the first -> one finding for the second."""
+    with tempfile.TemporaryDirectory() as tmpdir:
+        tmp = Path(tmpdir)
+        plan_dir = tmp / "plan"
+        project_root = tmp / "project"
+        project_root.mkdir()
+        (project_root / "go.mod").write_text(_GO_MOD_TEXT, encoding="utf-8")
+        foo_file = project_root / "pkg" / "foo_test.go"
+        foo_file.parent.mkdir(parents=True, exist_ok=True)
+        foo_file.write_text(_SCOUT_TAGGED_TEST_GO, encoding="utf-8")
+        bar_file = project_root / "pkg" / "bar_test.go"
+        bar_file.write_text(_SMOKE_TAGGED_TEST_GO, encoding="utf-8")
+
+        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
+        batch_text = _make_verify_only_batch_text(
+            "alpha", "PYTHONPATH= go test ./... -tags scout",
+            edits=["pkg/foo_test.go", "pkg/bar_test.go"],
+        )
+        _write_plan(plan_dir, overview, [("01-alpha.md", batch_text)])
+
+        result = _plan_validate.run(plan_dir, project_root)
+        check = [e for e in result if e["check"] == "verify-excludes-edited-tagged-test"]
+        try:
+            assert len(check) == 1, f"expected 1 finding, got {len(check)}: {check}"
+            e = check[0]
+            assert e["path"] == "pkg/bar_test.go", f"wrong path: {e['path']!r}"
+            assert "smoke" in e["message"], f"message missing 'smoke': {e['message']!r}"
+            print("PASS test_verify_excludes_edited_tagged_test_multi_file_batch_untested_second_file_dirty")
+            return 0
+        except AssertionError as exc:
+            print(f"FAIL test_verify_excludes_edited_tagged_test_multi_file_batch_untested_second_file_dirty: {exc}", file=sys.stderr)
+            return 1
+
+
+def test_verify_excludes_edited_tagged_test_multi_file_batch_both_tags_clean() -> int:
+    """Two tagged files in one batch, verify: covers both tags -> zero findings."""
+    with tempfile.TemporaryDirectory() as tmpdir:
+        tmp = Path(tmpdir)
+        plan_dir = tmp / "plan"
+        project_root = tmp / "project"
+        project_root.mkdir()
+        (project_root / "go.mod").write_text(_GO_MOD_TEXT, encoding="utf-8")
+        foo_file = project_root / "pkg" / "foo_test.go"
+        foo_file.parent.mkdir(parents=True, exist_ok=True)
+        foo_file.write_text(_SCOUT_TAGGED_TEST_GO, encoding="utf-8")
+        bar_file = project_root / "pkg" / "bar_test.go"
+        bar_file.write_text(_SMOKE_TAGGED_TEST_GO, encoding="utf-8")
+
+        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
+        batch_text = _make_verify_only_batch_text(
+            "alpha", "PYTHONPATH= go test ./... -tags scout,smoke",
+            edits=["pkg/foo_test.go", "pkg/bar_test.go"],
+        )
+        _write_plan(plan_dir, overview, [("01-alpha.md", batch_text)])
+
+        result = _plan_validate.run(plan_dir, project_root)
+        check = [e for e in result if e["check"] == "verify-excludes-edited-tagged-test"]
+        try:
+            assert check == [], f"expected no findings, got: {check}"
+            print("PASS test_verify_excludes_edited_tagged_test_multi_file_batch_both_tags_clean")
+            return 0
+        except AssertionError as exc:
+            print(f"FAIL test_verify_excludes_edited_tagged_test_multi_file_batch_both_tags_clean: {exc}", file=sys.stderr)
+            return 1
+
+
+def test_verify_excludes_edited_tagged_test_multi_composed_tag_single_file_no_tags_dirty() -> int:
+    """One file composed of two custom tags, no -tags flag -> one finding naming the alphabetically-first tag."""
+    with tempfile.TemporaryDirectory() as tmpdir:
+        tmp = Path(tmpdir)
+        plan_dir = tmp / "plan"
+        project_root = tmp / "project"
+        project_root.mkdir()
+        (project_root / "go.mod").write_text(_GO_MOD_TEXT, encoding="utf-8")
+        test_file = project_root / "pkg" / "baz_test.go"
+        test_file.parent.mkdir(parents=True, exist_ok=True)
+        test_file.write_text(_SCOUT_AND_SMOKE_TAGGED_TEST_GO, encoding="utf-8")
+
+        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
+        batch_text = _make_verify_only_batch_text(
+            "alpha", "PYTHONPATH= go test ./...", edits=["pkg/baz_test.go"],
+        )
+        _write_plan(plan_dir, overview, [("01-alpha.md", batch_text)])
+
+        result = _plan_validate.run(plan_dir, project_root)
+        check = [e for e in result if e["check"] == "verify-excludes-edited-tagged-test"]
+        try:
+            assert len(check) == 1, f"expected 1 finding, got {len(check)}: {check}"
+            e = check[0]
+            assert e["path"] == "pkg/baz_test.go", f"wrong path: {e['path']!r}"
+            assert "scout" in e["message"], f"message missing 'scout': {e['message']!r}"
+            assert "smoke" not in e["message"], f"message unexpectedly contains 'smoke': {e['message']!r}"
+            print("PASS test_verify_excludes_edited_tagged_test_multi_composed_tag_single_file_no_tags_dirty")
+            return 0
+        except AssertionError as exc:
+            print(f"FAIL test_verify_excludes_edited_tagged_test_multi_composed_tag_single_file_no_tags_dirty: {exc}", file=sys.stderr)
+            return 1
+
+
+def test_verify_excludes_edited_tagged_test_multi_composed_tag_single_file_second_tag_only_clean() -> int:
+    """Same composed-tag file, verify: names only the second/non-first tag -> zero findings (ANY-tag rule)."""
+    with tempfile.TemporaryDirectory() as tmpdir:
+        tmp = Path(tmpdir)
+        plan_dir = tmp / "plan"
+        project_root = tmp / "project"
+        project_root.mkdir()
+        (project_root / "go.mod").write_text(_GO_MOD_TEXT, encoding="utf-8")
+        test_file = project_root / "pkg" / "baz_test.go"
+        test_file.parent.mkdir(parents=True, exist_ok=True)
+        test_file.write_text(_SCOUT_AND_SMOKE_TAGGED_TEST_GO, encoding="utf-8")
+
+        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
+        batch_text = _make_verify_only_batch_text(
+            "alpha", "PYTHONPATH= go test ./... -tags smoke", edits=["pkg/baz_test.go"],
+        )
+        _write_plan(plan_dir, overview, [("01-alpha.md", batch_text)])
+
+        result = _plan_validate.run(plan_dir, project_root)
+        check = [e for e in result if e["check"] == "verify-excludes-edited-tagged-test"]
+        try:
+            assert check == [], f"expected no findings, got: {check}"
+            print("PASS test_verify_excludes_edited_tagged_test_multi_composed_tag_single_file_second_tag_only_clean")
+            return 0
+        except AssertionError as exc:
+            print(f"FAIL test_verify_excludes_edited_tagged_test_multi_composed_tag_single_file_second_tag_only_clean: {exc}", file=sys.stderr)
+            return 1
+
+
+def test_verify_excludes_edited_tagged_test_goos_and_custom_composed_dirty() -> int:
+    """GOOS + custom tag composed in one expression -> denylist strips "linux", custom "scout" still discovered."""
+    with tempfile.TemporaryDirectory() as tmpdir:
+        tmp = Path(tmpdir)
+        plan_dir = tmp / "plan"
+        project_root = tmp / "project"
+        project_root.mkdir()
+        (project_root / "go.mod").write_text(_GO_MOD_TEXT, encoding="utf-8")
+        test_file = project_root / "pkg" / "foo_test.go"
+        test_file.parent.mkdir(parents=True, exist_ok=True)
+        test_file.write_text(_LINUX_AND_SCOUT_TAGGED_TEST_GO, encoding="utf-8")
+
+        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
+        batch_text = _make_verify_only_batch_text(
+            "alpha", "PYTHONPATH= go test ./...", edits=["pkg/foo_test.go"],
+        )
+        _write_plan(plan_dir, overview, [("01-alpha.md", batch_text)])
+
+        result = _plan_validate.run(plan_dir, project_root)
+        check = [e for e in result if e["check"] == "verify-excludes-edited-tagged-test"]
+        try:
+            assert len(check) == 1, f"expected 1 finding, got {len(check)}: {check}"
+            e = check[0]
+            assert e["path"] == "pkg/foo_test.go", f"wrong path: {e['path']!r}"
+            assert "scout" in e["message"], f"message missing 'scout': {e['message']!r}"
+            assert "linux" not in e["message"], f"message unexpectedly contains 'linux': {e['message']!r}"
+            print("PASS test_verify_excludes_edited_tagged_test_goos_and_custom_composed_dirty")
+            return 0
+        except AssertionError as exc:
+            print(f"FAIL test_verify_excludes_edited_tagged_test_goos_and_custom_composed_dirty: {exc}", file=sys.stderr)
+            return 1
+
+
 # ---------------------------------------------------------------------------
 # Runner
 # ---------------------------------------------------------------------------
@@ -5713,6 +6126,8 @@ def main() -> int:
         test_check_verify_unrelated_test_files_no_only_segment_no_findings,
         # Cards field-legend HTML-comment regression guard (#734)
         test_check_cards_legend_in_comment_not_parsed_as_refs,
+        test_check_card_missing_field_fence_guard_clean,
+        test_check_card_missing_field_fence_guard_real_boundary_still_detected,
         # verify-excludes-edited-tagged-test check (#724)
         test_verify_excludes_edited_tagged_test_no_tags_flag_dirty,
         test_verify_excludes_edited_tagged_test_tags_integration_clean,
@@ -5722,6 +6137,16 @@ def main() -> int:
         test_verify_excludes_edited_tagged_test_malformed_verify_no_crash,
         test_verify_excludes_edited_tagged_test_header_comment_scan_dirty,
         test_verify_excludes_edited_tagged_test_creates_only_clean,
+        test_verify_excludes_edited_tagged_test_scout_tag_no_tags_flag_dirty,
+        test_verify_excludes_edited_tagged_test_scout_tag_tags_scout_clean,
+        test_verify_excludes_edited_tagged_test_smoke_tag_no_tags_flag_dirty,
+        test_verify_excludes_edited_tagged_test_smoke_tag_tags_smoke_clean,
+        test_verify_excludes_edited_tagged_test_goos_only_no_tags_flag_clean,
+        test_verify_excludes_edited_tagged_test_multi_file_batch_untested_second_file_dirty,
+        test_verify_excludes_edited_tagged_test_multi_file_batch_both_tags_clean,
+        test_verify_excludes_edited_tagged_test_multi_composed_tag_single_file_no_tags_dirty,
+        test_verify_excludes_edited_tagged_test_multi_composed_tag_single_file_second_tag_only_clean,
+        test_verify_excludes_edited_tagged_test_goos_and_custom_composed_dirty,
     ]
 
     errors = 0

```

## Instructions

1. Read the failing tests and the source files they exercise.
2. Fix the root cause of the failures.
   Do not modify tests unless they are genuinely wrong due to the merge (e.g. a test asserted against a value that the merge legitimately changed).
3. Re-run `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-class-taxonomy.py test-review-common.py test-review-finalize.py` after each fix attempt using `git -C /home/knatte/Code/millhouse/wts/review-gap-classification-by-kind` for git commands.
4. Commit each fix attempt with a clear commit message.
5. Self-fix up to `3` times.
   If the verify command still fails after `3` attempts, stop and report stuck.

## Report

Your last output line MUST be a bare JSON object (no code fence, no backticks):

**`commit_sha` MUST be the full SHA from `git rev-parse HEAD` -- never the abbreviated form (`git rev-parse --short HEAD`) or a `git log --oneline` hash.**

On success:

{"status":"success","commit_sha":"<last-HEAD-sha>"}

After exhausting fix rounds:

{"status":"stuck","stuck_type":"verify","reason":"<one-line description of what still fails>","commit_sha":"<last-HEAD-sha>"}

Anything other than this JSON object on the last line is a protocol violation;
the merge-in dispatcher treats that as stuck_type: logic with reason "no structured report" — your work is lost.
Do not wrap the JSON in a code fence;
do not add commentary after it.

## Tools

Available: Read, Edit, Write, Bash, Grep, Glob.
Use `git -C /home/knatte/Code/millhouse/wts/review-gap-classification-by-kind` for git commands;
do not `cd`.
Worktree cwd is `/home/knatte/Code/millhouse/wts/review-gap-classification-by-kind`.
