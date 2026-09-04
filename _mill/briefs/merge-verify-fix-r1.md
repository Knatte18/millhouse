# Verify-Fix Brief

The verify command `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-plan-flow.py` failed after a merge.
Your job is to diagnose the failures and fix the code so the verify command passes.

## Verify Output

```
PASS test1a: first run — all scopes r1
PASS test1b: second run — per-batch carryforward (r1), holistic fresh (r2)
PASS test2: partial re-invocation — alpha r2, beta/gamma r1, holistic r2 (independent per-scope)
PASS test3: creates_union suppresses missing cross-batch ref in parallel plan review (#60)
PASS test4: per-batch ReviewError -> ERROR entry, aggregate REQUEST_CHANGES (#41)
PASS test5: holistic resolve_ref_paths raises ReviewError, reviewer never called (#41)
PASS test6: per-batch NEED_CONTEXT retry -> APPROVE, holistic unaffected
PASS test7: holistic NEED_CONTEXT retry -> APPROVE
PASS test7b: holistic NEED_CONTEXT no-resolve branch — no retry, counters finalized from first response
PASS test8: skip-approved happy path — 01-a/03-c carryforward, 02-b/holistic fresh, blocking/nit counts correct
PASS test9: all approved — stub fires once (holistic only), holistic-only result (bug C fix #184)
PASS test10: malformed prior review -> 01-a treated as not-approved, all 4 scopes fire
PASS test11: holistic_only=True — stub fires once (holistic only)
PASS test12: no_holistic=True — stub fires twice (per-batch only)
PASS test13: holistic_only+no_holistic raises ReviewError (mutually exclusive)
PASS test14: aggregate blocking_count == 3 (2 + 1 + 0), nit_count == 1
PASS test14b: holistic-normal site's own blocking_count/nit_count == 1/1
PASS test15a: round 4 raises ReviewError without max_rounds kwarg
PASS test15b: max_rounds=5 -> holistic r4 succeeds -> 20260904-172627-plan-review-r4.md
PASS test16: all-ERROR run returns ReviewResult(ERROR) rather than raising (#84, #228)
PASS test17: mid-round resume — stub fires once (holistic only), holistic-only result (bug C fix #184)
PASS test18: deletes surface — '## Intentionally deleted' in per-batch prompt
PASS test19: timeout plumbing — bulk_timeout=900 -> per-batch, holistic_timeout=1800 -> holistic
PASS test20: holistic parse_verdict failure -> ERROR entry, no ReviewError raised (#185)
PASS test6a: batch=null — holistic fires, per-batch skipped
PASS test6b: batch=null + holistic=null raises ReviewError
PASS test21: holistic parse_verdict failure emits ERROR envelope (#315)
PASS test22: max_rounds=0 kwarg disables holistic + batch=null -> ReviewError
PASS test23: large_prompt.timeout override wires to holistic run call
PASS test24: prepare CLI entry point rejects plan with validator errors, no brief written
PASS test25: prepare CLI entry point accepts clean plan, writes brief file
PASS test26: Moves: source appears in both per-batch and holistic plan-review prompts
PASS test27: move targets suppressed in per-batch and holistic plan-review path checks
PASS: plan-review briefs_dir resolves under resolve_active_hub's value, not resolve_hub_path's decoy
PASS test29: unrecognized [MAJOR] severity fail-loud in synchronous per-batch dispatch, nit_count == 1
PASS test30: #720 MEDIUM-fold-in on the holistic dispatch path
PASS test31a: prepare() holistic reviewer_override drives resolution, not config's reviewer
PASS test31b: prepare() holistic reviewer_override unknown name raises ReviewError
PASS test31c: prepare() holistic reviewer_override cluster raises ReviewError
PASS test31d: prepare() holistic reviewer_override survives large_prompt auto-switch untouched
PASS test31e: prepare() reviewer_override is a no-op outside holistic scope
PASS test32a: run() holistic_only reviewer_override dispatches named override
PASS test32b: run() holistic_only reviewer_override unknown name raises ReviewError
PASS test32c: run() holistic_only reviewer_override dispatches non-Claude (Gemini) reviewer
PASS test32d: run() holistic_only reviewer_override skips large-prompt auto-switch, effort forwarded
PASS test33: --max-rounds override forces holistic dispatch despite rounds:0
PASS test34: top-level findings == concatenation of per-scope findings, counts consistent
PASS test35: [BLOCKING:consistency] demoted to NIT, [BLOCKING:scope] survives (plan-stage ceiling)
PASS test36: _scan_approved_batches counts match for demoted vs plain headings (no second ceiling)
PASS test37: carryforward + aggregation -- carried-forward findings reach the top-level list
PASS test38: prepare() reviews_subdir namespaces reviews_dir; default omission leaves it unchanged
PASS test39: run() reviews_subdir discovers rounds independently of the bare reviews_dir; default omission still uses it
PASS test40: per-batch prepare() soft-skips a git-ignored missing Context: ref
PASS test41: holistic prepare() soft-skips a git-ignored missing Context: ref
PASS test42 (per-batch): missing, non-ignored Context: ref still hard-fails
PASS test42 (holistic): missing, non-ignored Context: ref still hard-fails
PASS test43: missing, git-ignored Edits: ref still hard-fails (#808's literal repro is deliberately unfixed by this batch)
PASS test44: holistic cost metadata happy path -- reviews[0] carries duration_s/tool_calls/cost_usd and the written file's yaml header carries duration_s:
PASS test45: holistic NEED_CONTEXT retry summation -- reviews[0] carries the sum of both calls, not just the retry's values
PASS test46: holistic None-absorbing summation -- first call's tool_calls/cost_usd survive a retry that reports None for those signals
PASS test47: holistic cost metadata call-failure ERROR -- LLMError.duration_s surfaces on the synthetic ERROR entry with file=None
PASS test48: holistic parse-failure ERROR -- metrics survive into both the ERROR entry and the raw file's injected yaml header
PASS test49: per-batch cost metadata -- the finalize_scope-backed entry carries duration_s/tool_calls/cost_usd
PASS test50: per-batch outer ReviewError path stays file-less -- metrics carried envelope-only, no review file written (regression guard)
PASS test51: per-batch pre-call ReviewError (round_n > max_rounds) -- the three metrics are None rather than raising UnboundLocalError
PASS test52: finalize() parse_verdict failure tags error_kind: reviewer
PASS test53: _review_one_batch bulk-mode prompt is plan-relative
PASS test54: _review_one_batch tool-use prompt is plan-relative
PASS test55: prepare() batch-mode bulk prompt is plan-relative
PASS test56: prepare() batch-mode tool-use prompt is plan-relative
PASS test57: prepare() holistic bulk prompt is plan-relative
PASS test58: prepare() holistic tool-use prompt is plan-relative
PASS test59: run() holistic bulk prompt is plan-relative
PASS test60: run() holistic tool-use prompt is plan-relative
PASS test61: NEED_CONTEXT re-attachment retry_prompt is plan-relative (batch + holistic)
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_review_plan] slug='test-slug' plan_dir=/tmp/tmpg773alo7/container/wts/test-slug/plan batch_max_rounds=3 holistic_max_rounds=3
[_review_plan] found 3 batch file(s)
[_review_plan] batch 02-beta: verdict=APPROVE file=20260904-172626-plan-review-02-beta-r1.md
[_review_plan] batch 01-alpha: verdict=APPROVE file=20260904-172626-plan-review-01-alpha-r1.md
[_review_plan] batch 03-gamma: verdict=APPROVE file=20260904-172626-plan-review-03-gamma-r1.md
[_review_plan] running holistic review
[_review_plan] holistic: verdict=APPROVE file=20260904-172626-plan-review-r1.md
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_review_plan] slug='test-slug' plan_dir=/tmp/tmpg773alo7/container/wts/test-slug/plan batch_max_rounds=3 holistic_max_rounds=3
[_review_plan] found 3 batch file(s)
[_review_plan] skipping 3 already-approved batch(es): ['01-alpha', '02-beta', '03-gamma']
[_review_plan] running holistic review
[_review_plan] holistic: verdict=APPROVE file=20260904-172626-plan-review-r2.md
[safe-rmtree] starting: path=/tmp/tmpg773alo7 allowed_root=/tmp/tmpg773alo7
[safe-rmtree] removed: /tmp/tmpg773alo7
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_review_plan] slug='test-slug' plan_dir=/tmp/tmp6npnh6bn/container/wts/test-slug/plan batch_max_rounds=3 holistic_max_rounds=3
[_review_plan] found 3 batch file(s)
[_review_plan] warn: could not parse verdict in 20260418-000000-plan-review-01-alpha-r1.md; will re-review
[_review_plan] batch 03-gamma: verdict=APPROVE file=20260904-172626-plan-review-03-gamma-r1.md
[_review_plan] batch 02-beta: verdict=APPROVE file=20260904-172626-plan-review-02-beta-r1.md
[_review_plan] batch 01-alpha: verdict=APPROVE file=20260904-172626-plan-review-01-alpha-r2.md
[_review_plan] running holistic review
[_review_plan] holistic: verdict=APPROVE file=20260904-172626-plan-review-r2.md
[safe-rmtree] starting: path=/tmp/tmp6npnh6bn allowed_root=/tmp/tmp6npnh6bn
[safe-rmtree] removed: /tmp/tmp6npnh6bn
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_review_plan] slug='test-slug' plan_dir=/tmp/tmp33_9yyxj/container/wts/test-slug/plan batch_max_rounds=3 holistic_max_rounds=3
[_review_plan] found 3 batch file(s)
[_review_plan] batch 01-alpha: verdict=APPROVE file=20260904-172626-plan-review-01-alpha-r1.md
[_review_plan] batch 02-beta: verdict=APPROVE file=20260904-172626-plan-review-02-beta-r1.md
[_review_plan] batch 03-gamma: verdict=APPROVE file=20260904-172626-plan-review-03-gamma-r1.md
[_review_plan] running holistic review
[_review_plan] holistic: verdict=APPROVE file=20260904-172626-plan-review-r1.md
[safe-rmtree] starting: path=/tmp/tmp33_9yyxj allowed_root=/tmp/tmp33_9yyxj
[safe-rmtree] removed: /tmp/tmp33_9yyxj
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_review_plan] slug='test-slug' plan_dir=/tmp/tmpfh2ii2bn/container/wts/test-slug/plan batch_max_rounds=3 holistic_max_rounds=3
[_review_plan] found 2 batch file(s)
[_review_plan] batch 01-alpha: verdict=APPROVE file=20260904-172626-plan-review-01-alpha-r1.md
[subprocess] spawn argv=['git', '-C', '/tmp/tmpfh2ii2bn/container/wts/test-slug', 'check-ignore', '-q', '/tmp/tmpfh2ii2bn/container/wts/test-slug/nonexistent/path.py'] timeout=None
[subprocess] exit code=1 duration=0.002s
[subprocess] spawn argv=['git', '-C', '/tmp/tmpfh2ii2bn/container/wts/test-slug', 'check-ignore', '-q', '/tmp/tmpfh2ii2bn/container/wts/test-slug/nonexistent/path.py'] timeout=None
[subprocess] exit code=1 duration=0.002s
[safe-rmtree] starting: path=/tmp/tmpfh2ii2bn allowed_root=/tmp/tmpfh2ii2bn
[safe-rmtree] removed: /tmp/tmpfh2ii2bn
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_review_plan] slug='test-slug' plan_dir=/tmp/tmp50e5pbvf/container/wts/test-slug/plan batch_max_rounds=3 holistic_max_rounds=3
[_review_plan] found 3 batch file(s)
[subprocess] spawn argv=['git', '-C', '/tmp/tmp50e5pbvf/container/wts/test-slug', 'check-ignore', '-q', '/tmp/tmp50e5pbvf/container/wts/test-slug/nonexistent/path.py'] timeout=None
[subprocess] exit code=1 duration=0.002s
[_review_plan] batch 01-alpha: verdict=APPROVE file=20260904-172626-plan-review-01-alpha-r1.md
[_review_plan] batch 03-gamma: verdict=APPROVE file=20260904-172626-plan-review-03-gamma-r1.md
[subprocess] spawn argv=['git', '-C', '/tmp/tmp50e5pbvf/container/wts/test-slug', 'check-ignore', '-q', '/tmp/tmp50e5pbvf/container/wts/test-slug/nonexistent/path.py'] timeout=None
[subprocess] exit code=1 duration=0.002s
[_review_plan] running holistic review
[subprocess] spawn argv=['git', '-C', '/tmp/tmp50e5pbvf/container/wts/test-slug', 'check-ignore', '-q', '/tmp/tmp50e5pbvf/container/wts/test-slug/nonexistent/path.py'] timeout=None
[subprocess] exit code=1 duration=0.002s
[subprocess] spawn argv=['git', '-C', '/tmp/tmp50e5pbvf/container/wts/test-slug', 'check-ignore', '-q', '/tmp/tmp50e5pbvf/container/wts/test-slug/nonexistent/path.py'] timeout=None
[subprocess] exit code=1 duration=0.001s
[safe-rmtree] starting: path=/tmp/tmp50e5pbvf allowed_root=/tmp/tmp50e5pbvf
[safe-rmtree] removed: /tmp/tmp50e5pbvf
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_review_plan] slug='test-slug' plan_dir=/tmp/tmpl5_b4vd3/container/wts/test-slug/plan batch_max_rounds=3 holistic_max_rounds=3
[_review_plan] found 1 batch file(s)
[_review_plan] batch 01-alpha NEED_CONTEXT round-1; retrying with resume (1 re-attached file(s)) session=sid-1
[_review_plan] batch 01-alpha: verdict=APPROVE file=20260904-172626-plan-review-01-alpha-r1.md
[_review_plan] running holistic review
[_review_plan] holistic: verdict=APPROVE file=20260904-172626-plan-review-r1.md
[safe-rmtree] starting: path=/tmp/tmpl5_b4vd3 allowed_root=/tmp/tmpl5_b4vd3
[safe-rmtree] removed: /tmp/tmpl5_b4vd3
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_review_plan] slug='test-slug' plan_dir=/tmp/tmpg6r6625m/container/wts/test-slug/plan batch_max_rounds=3 holistic_max_rounds=3
[_review_plan] found 1 batch file(s)
[_review_plan] batch 01-alpha: verdict=APPROVE file=20260904-172626-plan-review-01-alpha-r1.md
[_review_plan] running holistic review
[_review_plan] holistic NEED_CONTEXT round-1; retrying with resume (1 re-attached file(s)) session=sid-2
[_review_common] warning: finding has unknown or missing class -- cleanup note
[_review_plan] holistic: verdict=APPROVE file=20260904-172626-plan-review-r1.md
[safe-rmtree] starting: path=/tmp/tmpg6r6625m allowed_root=/tmp/tmpg6r6625m
[safe-rmtree] removed: /tmp/tmpg6r6625m
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_review_plan] slug='test-slug' plan_dir=/tmp/tmp8qxb5gva/container/wts/test-slug/plan batch_max_rounds=3 holistic_max_rounds=3
[_review_plan] found 1 batch file(s)
[_review_plan] batch 01-alpha: verdict=APPROVE file=20260904-172626-plan-review-01-alpha-r1.md
[_review_plan] running holistic review
[_review_common] warning: finding has unknown or missing class -- pending cleanup
[_review_plan] holistic: verdict=NEED_CONTEXT file=20260904-172626-plan-review-r1.md
[safe-rmtree] starting: path=/tmp/tmp8qxb5gva allowed_root=/tmp/tmp8qxb5gva
[safe-rmtree] removed: /tmp/tmp8qxb5gva
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_review_plan] slug='test-slug' plan_dir=/tmp/tmpiqhku3b_/container/wts/test-slug/plan batch_max_rounds=3 holistic_max_rounds=3
[_review_plan] found 3 batch file(s)
[_review_common] warning: finding has unknown or missing class -- mislabeled issue
[_review_common] warning: finding has unknown or missing class -- cosmetic
[_review_plan] skipping 2 already-approved batch(es): ['01-a', '03-c']
[_review_plan] batch 02-b: verdict=APPROVE file=20260904-172626-plan-review-02-b-r2.md
[_review_plan] running holistic review
[_review_plan] holistic: verdict=APPROVE file=20260904-172626-plan-review-r2.md
[safe-rmtree] starting: path=/tmp/tmpiqhku3b_ allowed_root=/tmp/tmpiqhku3b_
[safe-rmtree] removed: /tmp/tmpiqhku3b_
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_review_plan] slug='test-slug' plan_dir=/tmp/tmpo9kz_rwz/container/wts/test-slug/plan batch_max_rounds=3 holistic_max_rounds=3
[_review_plan] found 3 batch file(s)
[_review_plan] resuming round 1 from 3 on-disk per-batch files; firing holistic only
[_review_plan] running holistic review
[_review_plan] holistic: verdict=APPROVE file=20260904-172627-plan-review-r1.md
[safe-rmtree] starting: path=/tmp/tmpo9kz_rwz allowed_root=/tmp/tmpo9kz_rwz
[safe-rmtree] removed: /tmp/tmpo9kz_rwz
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_review_plan] slug='test-slug' plan_dir=/tmp/tmpm2zolp__/container/wts/test-slug/plan batch_max_rounds=3 holistic_max_rounds=3
[_review_plan] found 3 batch file(s)
[_review_plan] warn: could not parse verdict in 20260429-000001-plan-review-01-a-r1.md; will re-review
[_review_plan] batch 02-b: verdict=APPROVE file=20260904-172627-plan-review-02-b-r1.md
[_review_plan] batch 01-a: verdict=APPROVE file=20260904-172627-plan-review-01-a-r2.md
[_review_plan] batch 03-c: verdict=APPROVE file=20260904-172627-plan-review-03-c-r1.md
[_review_plan] running holistic review
[_review_plan] holistic: verdict=APPROVE file=20260904-172627-plan-review-r2.md
[safe-rmtree] starting: path=/tmp/tmpm2zolp__ allowed_root=/tmp/tmpm2zolp__
[safe-rmtree] removed: /tmp/tmpm2zolp__
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_review_plan] slug='test-slug' plan_dir=/tmp/tmp1scp7b1_/container/wts/test-slug/plan batch_max_rounds=3 holistic_max_rounds=3
[_review_plan] found 2 batch file(s)
[_review_plan] running holistic review
[_review_plan] holistic: verdict=APPROVE file=20260904-172627-plan-review-r1.md
[safe-rmtree] starting: path=/tmp/tmp1scp7b1_ allowed_root=/tmp/tmp1scp7b1_
[safe-rmtree] removed: /tmp/tmp1scp7b1_
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_review_plan] slug='test-slug' plan_dir=/tmp/tmpnlmsfbtw/container/wts/test-slug/plan batch_max_rounds=3 holistic_max_rounds=3
[_review_plan] found 2 batch file(s)
[_review_plan] batch 02-beta: verdict=APPROVE file=20260904-172627-plan-review-02-beta-r1.md
[_review_plan] batch 01-alpha: verdict=APPROVE file=20260904-172627-plan-review-01-alpha-r1.md
[safe-rmtree] starting: path=/tmp/tmpnlmsfbtw allowed_root=/tmp/tmpnlmsfbtw
[safe-rmtree] removed: /tmp/tmpnlmsfbtw
[safe-rmtree] starting: path=/tmp/tmppe6du41h allowed_root=/tmp/tmppe6du41h
[safe-rmtree] removed: /tmp/tmppe6du41h
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_review_plan] slug='test-slug' plan_dir=/tmp/tmpmgqyg4j0/container/wts/test-slug/plan batch_max_rounds=3 holistic_max_rounds=3
[_review_plan] found 2 batch file(s)
[_review_common] warning: finding has unknown or missing class -- issue one
[_review_common] warning: finding has unknown or missing class -- issue two
[_review_common] warning: finding has unknown or missing class -- issue four
[_review_plan] batch 01-alpha: verdict=REQUEST_CHANGES file=20260904-172627-plan-review-01-alpha-r1.md
[_review_common] warning: finding has unknown or missing class -- issue three
[_review_plan] batch 02-beta: verdict=REQUEST_CHANGES file=20260904-172627-plan-review-02-beta-r1.md
[_review_plan] running holistic review
[_review_plan] holistic: verdict=APPROVE file=20260904-172627-plan-review-r1.md
[safe-rmtree] starting: path=/tmp/tmpmgqyg4j0 allowed_root=/tmp/tmpmgqyg4j0
[safe-rmtree] removed: /tmp/tmpmgqyg4j0
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_review_plan] slug='test-slug' plan_dir=/tmp/tmp7ve5m7ne/container/wts/test-slug/plan batch_max_rounds=3 holistic_max_rounds=3
[_review_plan] found 1 batch file(s)
[_review_plan] batch 01-alpha: verdict=APPROVE file=20260904-172627-plan-review-01-alpha-r1.md
[_review_plan] running holistic review
[_review_common] warning: finding has unknown or missing class -- missing edge case
[_review_common] warning: finding has unknown or missing class -- naming nit
[_review_plan] holistic: verdict=REQUEST_CHANGES file=20260904-172627-plan-review-r1.md
[safe-rmtree] starting: path=/tmp/tmp7ve5m7ne allowed_root=/tmp/tmp7ve5m7ne
[safe-rmtree] removed: /tmp/tmp7ve5m7ne
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_review_plan] slug='test-slug' plan_dir=/tmp/tmpi2qxe8lr/container/wts/test-slug/plan batch_max_rounds=3 holistic_max_rounds=3
[_review_plan] found 1 batch file(s)
[_review_plan] skipping 1 already-approved batch(es): ['01-alpha']
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_review_plan] slug='test-slug' plan_dir=/tmp/tmpi2qxe8lr/container/wts/test-slug/plan batch_max_rounds=5 holistic_max_rounds=5
[_review_plan] found 1 batch file(s)
[_review_plan] skipping 1 already-approved batch(es): ['01-alpha']
[_review_plan] running holistic review
[_review_plan] holistic: verdict=APPROVE file=20260904-172627-plan-review-r4.md
[safe-rmtree] starting: path=/tmp/tmpi2qxe8lr allowed_root=/tmp/tmpi2qxe8lr
[safe-rmtree] removed: /tmp/tmpi2qxe8lr
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_review_plan] slug='test-slug' plan_dir=/tmp/tmposwp9gjb/container/wts/test-slug/plan batch_max_rounds=3 holistic_max_rounds=3
[_review_plan] found 1 batch file(s)
[_review_plan] running holistic review
[safe-rmtree] starting: path=/tmp/tmposwp9gjb allowed_root=/tmp/tmposwp9gjb
[safe-rmtree] removed: /tmp/tmposwp9gjb
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_review_plan] slug='test-slug' plan_dir=/tmp/tmps0qs1rwb/container/wts/test-slug/plan batch_max_rounds=3 holistic_max_rounds=3
[_review_plan] found 2 batch file(s)
[_review_plan] resuming round 1 from 2 on-disk per-batch files; firing holistic only
[_review_plan] running holistic review
[_review_plan] holistic: verdict=APPROVE file=20260904-172627-plan-review-r1.md
[safe-rmtree] starting: path=/tmp/tmps0qs1rwb allowed_root=/tmp/tmps0qs1rwb
[safe-rmtree] removed: /tmp/tmps0qs1rwb
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_review_plan] slug='test-slug' plan_dir=/tmp/tmpw1ca8jxj/container/wts/test-slug/plan batch_max_rounds=3 holistic_max_rounds=3
[_review_plan] found 1 batch file(s)
[_review_plan] batch 01-alpha: verdict=APPROVE file=20260904-172627-plan-review-01-alpha-r1.md
[_review_plan] running holistic review
[_review_plan] holistic: verdict=APPROVE file=20260904-172627-plan-review-r1.md
[safe-rmtree] starting: path=/tmp/tmpw1ca8jxj allowed_root=/tmp/tmpw1ca8jxj
[safe-rmtree] removed: /tmp/tmpw1ca8jxj
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_review_plan] slug='test-slug' plan_dir=/tmp/tmp1l6qepqo/container/wts/test-slug/plan batch_max_rounds=3 holistic_max_rounds=3
[_review_plan] found 1 batch file(s)
[_review_plan] batch 01-alpha: verdict=APPROVE file=20260904-172627-plan-review-01-alpha-r1.md
[_review_plan] running holistic review
[_review_plan] holistic: verdict=APPROVE file=20260904-172627-plan-review-r1.md
[safe-rmtree] starting: path=/tmp/tmp1l6qepqo allowed_root=/tmp/tmp1l6qepqo
[safe-rmtree] removed: /tmp/tmp1l6qepqo
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_review_plan] slug='test-slug' plan_dir=/tmp/tmpyrk2xwqu/container/wts/test-slug/plan batch_max_rounds=3 holistic_max_rounds=3
[_review_plan] found 1 batch file(s)
[_review_plan] batch 01-alpha: verdict=APPROVE file=20260904-172627-plan-review-01-alpha-r1.md
[_review_plan] running holistic review
[safe-rmtree] starting: path=/tmp/tmpyrk2xwqu allowed_root=/tmp/tmpyrk2xwqu
[safe-rmtree] removed: /tmp/tmpyrk2xwqu
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_review_plan] slug='test-slug' plan_dir=/tmp/tmptnle4rae/container/wts/test-slug/plan batch_max_rounds=3 holistic_max_rounds=3
[_review_plan] found 1 batch file(s)
[_review_plan] running holistic review
[_review_plan] holistic: verdict=APPROVE file=20260904-172627-plan-review-r1.md
[safe-rmtree] starting: path=/tmp/tmptnle4rae allowed_root=/tmp/tmptnle4rae
[safe-rmtree] removed: /tmp/tmptnle4rae
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_review_plan] slug='test-slug' plan_dir=/tmp/tmpfbmlxecd/container/wts/test-slug/plan batch_max_rounds=3 holistic_max_rounds=3
[_review_plan] found 1 batch file(s)
[safe-rmtree] starting: path=/tmp/tmpfbmlxecd allowed_root=/tmp/tmpfbmlxecd
[safe-rmtree] removed: /tmp/tmpfbmlxecd
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_review_plan] slug='test-slug' plan_dir=/tmp/tmpvvij4vus/container/wts/test-slug/plan batch_max_rounds=3 holistic_max_rounds=3
[_review_plan] found 1 batch file(s)
[_review_plan] running holistic review
[safe-rmtree] starting: path=/tmp/tmpvvij4vus allowed_root=/tmp/tmpvvij4vus
[safe-rmtree] removed: /tmp/tmpvvij4vus
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_review_plan] slug='test-slug' plan_dir=/tmp/tmpvv5dmzww/container/wts/test-slug/plan batch_max_rounds=0 holistic_max_rounds=0
[_review_plan] found 1 batch file(s)
[safe-rmtree] starting: path=/tmp/tmpvv5dmzww allowed_root=/tmp/tmpvv5dmzww
[safe-rmtree] removed: /tmp/tmpvv5dmzww
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_review_plan] slug='test-slug' plan_dir=/tmp/tmp29884wmt/container/wts/test-slug/plan batch_max_rounds=3 holistic_max_rounds=1
[_review_plan] found 1 batch file(s)
[_review_plan] running holistic review
[_review_plan] holistic: verdict=APPROVE file=20260904-172627-plan-review-r1.md
[safe-rmtree] starting: path=/tmp/tmp29884wmt allowed_root=/tmp/tmp29884wmt
[safe-rmtree] removed: /tmp/tmp29884wmt
[safe-rmtree] starting: path=/tmp/tmph_yqacgx allowed_root=/tmp/tmph_yqacgx
[safe-rmtree] removed: /tmp/tmph_yqacgx
[safe-rmtree] starting: path=/tmp/tmpuhtc7m8q allowed_root=/tmp/tmpuhtc7m8q
[safe-rmtree] removed: /tmp/tmpuhtc7m8q
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_review_plan] slug='test-slug' plan_dir=/tmp/tmpqmn63k7q/container/wts/test-slug/plan batch_max_rounds=3 holistic_max_rounds=3
[_review_plan] found 1 batch file(s)
[_review_plan] batch 01-alpha: verdict=APPROVE file=20260904-172627-plan-review-01-alpha-r1.md
[_review_plan] running holistic review
[_review_plan] holistic: verdict=APPROVE file=20260904-172627-plan-review-r1.md
[safe-rmtree] starting: path=/tmp/tmpqmn63k7q allowed_root=/tmp/tmpqmn63k7q
[safe-rmtree] removed: /tmp/tmpqmn63k7q
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_review_plan] slug='test-slug' plan_dir=/tmp/tmpnb9dqqgj/container/wts/test-slug/plan batch_max_rounds=3 holistic_max_rounds=3
[_review_plan] found 2 batch file(s)
[_review_plan] batch 02-beta: verdict=APPROVE file=20260904-172627-plan-review-02-beta-r1.md
[_review_plan] batch 01-alpha: verdict=APPROVE file=20260904-172627-plan-review-01-alpha-r1.md
[_review_plan] running holistic review
[_review_plan] holistic: verdict=APPROVE file=20260904-172627-plan-review-r1.md
[safe-rmtree] starting: path=/tmp/tmpnb9dqqgj allowed_root=/tmp/tmpnb9dqqgj
[safe-rmtree] removed: /tmp/tmpnb9dqqgj
FAIL test28: expected exit code 0 for clean nested-layout plan, got 1; stdout='', stderr='[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree\nTraceback (most recent call last):\n  File "/home/knatte/Code/millhouse/wts/review-manifest-listings-full-path-clutter/plugins/mill/scripts/millpy-review-plan.py", line 364, in <module>\n    sys.exit(main())\n             ~~~~^^\n  File "/home/knatte/Code/millhouse/wts/review-manifest-listings-full-path-clutter/plugins/mill/scripts/millpy-review-plan.py", line 197, in main\n    project_root = _paths.resolve_active_hub(\n        container_path, slug, cfg=cfg, git_root=git_root, skip_slug_validation=True\n    )\n  File "/home/knatte/Code/millhouse/wts/review-manifest-listings-full-path-clutter/plugins/mill/scripts/_paths.py", line 495, in resolve_active_hub\n    wt = resolve_active_worktree(\n        container_path,\n    ...<3 lines>...\n        skip_slug_validation=skip_slug_validation,\n    )\n  File "/home/knatte/Code/millhouse/wts/review-manifest-listings-full-path-clutter/plugins/mill/scripts/_paths.py", line 455, in resolve_active_worktree\n    raise ActiveWorktreeSlugMismatch(\n        f"Worktree at {worktree} has slug {dir_slug!r}, expected {slug!r}"\n    )\n_paths.ActiveWorktreeSlugMismatch: Worktree at /tmp/tmpigrbq0b7/container/wts/test-slug has slug \'hanf/test-slug\', expected \'test-slug\'\n'
[safe-rmtree] starting: path=/tmp/tmpigrbq0b7 allowed_root=/tmp/tmpigrbq0b7
[safe-rmtree] removed: /tmp/tmpigrbq0b7
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_review_plan] slug='test-slug' plan_dir=/tmp/tmppe4zlhrv/container/wts/test-slug/plan batch_max_rounds=3 holistic_max_rounds=3
[_review_plan] found 1 batch file(s)
[_review_common] warning: finding has unknown or missing class -- compile break
[_review_common] warning: finding has unknown or missing class -- minor note
[_review_plan] batch 01-alpha: verdict=REQUEST_CHANGES file=20260904-172628-plan-review-01-alpha-r1.md
[_review_plan] running holistic review
[_review_plan] holistic: verdict=APPROVE file=20260904-172628-plan-review-r1.md
[safe-rmtree] starting: path=/tmp/tmppe4zlhrv allowed_root=/tmp/tmppe4zlhrv
[safe-rmtree] removed: /tmp/tmppe4zlhrv
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_review_plan] slug='test-slug' plan_dir=/tmp/tmpajr8g2dj/container/wts/test-slug/plan batch_max_rounds=3 holistic_max_rounds=3
[_review_plan] found 1 batch file(s)
[_review_plan] batch 01-alpha: verdict=APPROVE file=20260904-172628-plan-review-01-alpha-r1.md
[_review_plan] running holistic review
[_review_common] warning: finding has unknown or missing class -- borderline concern
[_review_plan] holistic: verdict=REQUEST_CHANGES file=20260904-172628-plan-review-r1.md
[safe-rmtree] starting: path=/tmp/tmpajr8g2dj allowed_root=/tmp/tmpajr8g2dj
[safe-rmtree] removed: /tmp/tmpajr8g2dj
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[safe-rmtree] starting: path=/tmp/tmpvg7q_0cw allowed_root=/tmp/tmpvg7q_0cw
[safe-rmtree] removed: /tmp/tmpvg7q_0cw
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[safe-rmtree] starting: path=/tmp/tmpxvxcehgu allowed_root=/tmp/tmpxvxcehgu
[safe-rmtree] removed: /tmp/tmpxvxcehgu
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[safe-rmtree] starting: path=/tmp/tmp8uefd9pk allowed_root=/tmp/tmp8uefd9pk
[safe-rmtree] removed: /tmp/tmp8uefd9pk
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[safe-rmtree] starting: path=/tmp/tmpzmyw8e86 allowed_root=/tmp/tmpzmyw8e86
[safe-rmtree] removed: /tmp/tmpzmyw8e86
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[safe-rmtree] starting: path=/tmp/tmpgo55pp_e allowed_root=/tmp/tmpgo55pp_e
[safe-rmtree] removed: /tmp/tmpgo55pp_e
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_review_plan] slug='test-slug' plan_dir=/tmp/tmpd6_nvcab/container/wts/test-slug/plan batch_max_rounds=3 holistic_max_rounds=3
[_review_plan] found 1 batch file(s)
[_review_plan] running holistic review
[_review_plan] holistic: verdict=APPROVE file=20260904-172628-plan-review-r1.md
[safe-rmtree] starting: path=/tmp/tmpd6_nvcab allowed_root=/tmp/tmpd6_nvcab
[safe-rmtree] removed: /tmp/tmpd6_nvcab
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_review_plan] slug='test-slug' plan_dir=/tmp/tmp6rrxnby9/container/wts/test-slug/plan batch_max_rounds=3 holistic_max_rounds=3
[_review_plan] found 1 batch file(s)
[safe-rmtree] starting: path=/tmp/tmp6rrxnby9 allowed_root=/tmp/tmp6rrxnby9
[safe-rmtree] removed: /tmp/tmp6rrxnby9
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_review_plan] slug='test-slug' plan_dir=/tmp/tmpl487nf3n/container/wts/test-slug/plan batch_max_rounds=3 holistic_max_rounds=3
[_review_plan] found 1 batch file(s)
[_review_plan] running holistic review
[_review_plan] holistic: verdict=APPROVE file=20260904-172628-plan-review-r1.md
[safe-rmtree] starting: path=/tmp/tmpl487nf3n allowed_root=/tmp/tmpl487nf3n
[safe-rmtree] removed: /tmp/tmpl487nf3n
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_review_plan] slug='test-slug' plan_dir=/tmp/tmpffqn_0yg/container/wts/test-slug/plan batch_max_rounds=3 holistic_max_rounds=3
[_review_plan] found 1 batch file(s)
[_review_plan] running holistic review
[_review_plan] holistic: verdict=APPROVE file=20260904-172628-plan-review-r1.md
[safe-rmtree] starting: path=/tmp/tmpffqn_0yg allowed_root=/tmp/tmpffqn_0yg
[safe-rmtree] removed: /tmp/tmpffqn_0yg
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_review_plan] slug='test-slug' plan_dir=/tmp/tmpghgycsgg/container/wts/test-slug/plan batch_max_rounds=1 holistic_max_rounds=1
[_review_plan] found 1 batch file(s)
[_review_plan] running holistic review
[_review_plan] holistic: verdict=APPROVE file=20260904-172628-plan-review-r1.md
[safe-rmtree] starting: path=/tmp/tmpghgycsgg allowed_root=/tmp/tmpghgycsgg
[safe-rmtree] removed: /tmp/tmpghgycsgg
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_review_plan] slug='test-slug' plan_dir=/tmp/tmpzbh7cgcz/container/wts/test-slug/plan batch_max_rounds=3 holistic_max_rounds=3
[_review_plan] found 2 batch file(s)
[_review_common] warning: finding has unknown or missing class -- issue one
[_review_common] warning: finding has unknown or missing class -- issue two
[_review_plan] batch 02-beta: verdict=REQUEST_CHANGES file=20260904-172628-plan-review-02-beta-r1.md
[_review_common] warning: finding has unknown or missing class -- issue three
[_review_plan] batch 01-alpha: verdict=APPROVE file=20260904-172628-plan-review-01-alpha-r1.md
[_review_plan] running holistic review
[_review_plan] holistic: verdict=APPROVE file=20260904-172628-plan-review-r1.md
[safe-rmtree] starting: path=/tmp/tmpzbh7cgcz allowed_root=/tmp/tmpzbh7cgcz
[safe-rmtree] removed: /tmp/tmpzbh7cgcz
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_review_plan] slug='test-slug' plan_dir=/tmp/tmpbc01kn14/container/wts/test-slug/plan batch_max_rounds=3 holistic_max_rounds=3
[_review_plan] found 1 batch file(s)
[_review_plan] batch 01-alpha: verdict=APPROVE file=20260904-172628-plan-review-01-alpha-r1.md
[_review_plan] running holistic review
[_review_plan] holistic: verdict=REQUEST_CHANGES file=20260904-172628-plan-review-r1.md
[safe-rmtree] starting: path=/tmp/tmpbc01kn14 allowed_root=/tmp/tmpbc01kn14
[safe-rmtree] removed: /tmp/tmpbc01kn14
[_review_common] warning: finding has unknown or missing class -- cosmetic
[safe-rmtree] starting: path=/tmp/tmpmywgk2id allowed_root=/tmp/tmpmywgk2id
[safe-rmtree] removed: /tmp/tmpmywgk2id
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_review_plan] slug='test-slug' plan_dir=/tmp/tmpl3ve32fz/container/wts/test-slug/plan batch_max_rounds=3 holistic_max_rounds=3
[_review_plan] found 2 batch file(s)
[_review_common] warning: finding has unknown or missing class -- cosmetic
[_review_plan] skipping 1 already-approved batch(es): ['01-a']
[_review_common] warning: finding has unknown or missing class -- fresh issue
[_review_plan] batch 02-b: verdict=REQUEST_CHANGES file=20260904-172628-plan-review-02-b-r1.md
[_review_plan] running holistic review
[_review_plan] holistic: verdict=APPROVE file=20260904-172628-plan-review-r2.md
[safe-rmtree] starting: path=/tmp/tmpl3ve32fz allowed_root=/tmp/tmpl3ve32fz
[safe-rmtree] removed: /tmp/tmpl3ve32fz
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[safe-rmtree] starting: path=/tmp/tmp7pxzpsnz allowed_root=/tmp/tmp7pxzpsnz
[safe-rmtree] removed: /tmp/tmp7pxzpsnz
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_review_plan] slug='test-slug' plan_dir=/tmp/tmpu4e8cnr3/container/wts/test-slug/plan batch_max_rounds=3 holistic_max_rounds=3
[_review_plan] found 1 batch file(s)
[_review_plan] batch 01-alpha: verdict=APPROVE file=20260904-172628-plan-review-01-alpha-r1.md
[_review_plan] running holistic review
[_review_plan] holistic: verdict=APPROVE file=20260904-172628-plan-review-r1.md
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_review_plan] slug='test-slug' plan_dir=/tmp/tmpu4e8cnr3/container/wts/test-slug/plan batch_max_rounds=3 holistic_max_rounds=3
[_review_plan] found 1 batch file(s)
[_review_plan] warn: could not parse verdict in 20260603-000001-plan-review-01-alpha-r3.md; will re-review
[safe-rmtree] starting: path=/tmp/tmpu4e8cnr3 allowed_root=/tmp/tmpu4e8cnr3
[safe-rmtree] removed: /tmp/tmpu4e8cnr3
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[resolve_ref_paths] warning: skipping git-ignored Context: ref '.scratch/probe.md' (confirmed ignored under /tmp/tmpnlw6cf_p/container/wts/test-slug)
[safe-rmtree] starting: path=/tmp/tmpnlw6cf_p allowed_root=/tmp/tmpnlw6cf_p
[safe-rmtree] removed: /tmp/tmpnlw6cf_p
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[resolve_ref_paths] warning: skipping git-ignored Context: ref '.scratch/probe.md' (confirmed ignored under /tmp/tmpf85rj1yx/container/wts/test-slug)
[safe-rmtree] starting: path=/tmp/tmpf85rj1yx allowed_root=/tmp/tmpf85rj1yx
[safe-rmtree] removed: /tmp/tmpf85rj1yx
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[subprocess] spawn argv=['git', '-C', '/tmp/tmpqhyudi8l/container/wts/test-slug', 'check-ignore', '-q', '/tmp/tmpqhyudi8l/container/wts/test-slug/not_ignored_missing.py'] timeout=None
[subprocess] exit code=1 duration=0.002s
[subprocess] spawn argv=['git', '-C', '/tmp/tmpqhyudi8l/container/wts/test-slug', 'check-ignore', '-q', '/tmp/tmpqhyudi8l/container/wts/test-slug/not_ignored_missing.py'] timeout=None
[subprocess] exit code=1 duration=0.002s
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[subprocess] spawn argv=['git', '-C', '/tmp/tmpqhyudi8l/container/wts/test-slug', 'check-ignore', '-q', '/tmp/tmpqhyudi8l/container/wts/test-slug/not_ignored_missing.py'] timeout=None
[subprocess] exit code=1 duration=0.002s
[subprocess] spawn argv=['git', '-C', '/tmp/tmpqhyudi8l/container/wts/test-slug', 'check-ignore', '-q', '/tmp/tmpqhyudi8l/container/wts/test-slug/not_ignored_missing.py'] timeout=None
[subprocess] exit code=1 duration=0.001s
[safe-rmtree] starting: path=/tmp/tmpqhyudi8l allowed_root=/tmp/tmpqhyudi8l
[safe-rmtree] removed: /tmp/tmpqhyudi8l
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[safe-rmtree] starting: path=/tmp/tmp_13o0dke allowed_root=/tmp/tmp_13o0dke
[safe-rmtree] removed: /tmp/tmp_13o0dke
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_review_plan] slug='test-slug' plan_dir=/tmp/tmp9en8duwo/container/wts/test-slug/plan batch_max_rounds=3 holistic_max_rounds=3
[_review_plan] found 1 batch file(s)
[_review_plan] running holistic review
[_review_plan] holistic: verdict=APPROVE file=20260904-172628-plan-review-r1.md
[safe-rmtree] starting: path=/tmp/tmp9en8duwo allowed_root=/tmp/tmp9en8duwo
[safe-rmtree] removed: /tmp/tmp9en8duwo
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_review_plan] slug='test-slug' plan_dir=/tmp/tmpukak_03y/container/wts/test-slug/plan batch_max_rounds=3 holistic_max_rounds=3
[_review_plan] found 1 batch file(s)
[_review_plan] running holistic review
[_review_plan] holistic NEED_CONTEXT round-1; retrying with resume (1 re-attached file(s)) session=sid-1
[_review_plan] holistic: verdict=APPROVE file=20260904-172628-plan-review-r1.md
[safe-rmtree] starting: path=/tmp/tmpukak_03y allowed_root=/tmp/tmpukak_03y
[safe-rmtree] removed: /tmp/tmpukak_03y
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_review_plan] slug='test-slug' plan_dir=/tmp/tmpq590mfze/container/wts/test-slug/plan batch_max_rounds=3 holistic_max_rounds=3
[_review_plan] found 1 batch file(s)
[_review_plan] running holistic review
[_review_plan] holistic NEED_CONTEXT round-1; retrying with resume (1 re-attached file(s)) session=sid-1
[_review_plan] holistic: verdict=APPROVE file=20260904-172628-plan-review-r1.md
[safe-rmtree] starting: path=/tmp/tmpq590mfze allowed_root=/tmp/tmpq590mfze
[safe-rmtree] removed: /tmp/tmpq590mfze
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_review_plan] slug='test-slug' plan_dir=/tmp/tmp2mn2i8is/container/wts/test-slug/plan batch_max_rounds=3 holistic_max_rounds=3
[_review_plan] found 1 batch file(s)
[_review_plan] running holistic review
[safe-rmtree] starting: path=/tmp/tmp2mn2i8is allowed_root=/tmp/tmp2mn2i8is
[safe-rmtree] removed: /tmp/tmp2mn2i8is
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_review_plan] slug='test-slug' plan_dir=/tmp/tmp2mt8zz8l/container/wts/test-slug/plan batch_max_rounds=3 holistic_max_rounds=3
[_review_plan] found 1 batch file(s)
[_review_plan] running holistic review
[safe-rmtree] starting: path=/tmp/tmp2mt8zz8l allowed_root=/tmp/tmp2mt8zz8l
[safe-rmtree] removed: /tmp/tmp2mt8zz8l
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_review_plan] slug='test-slug' plan_dir=/tmp/tmpvmtc2dgd/container/wts/test-slug/plan batch_max_rounds=3 holistic_max_rounds=3
[_review_plan] found 1 batch file(s)
[_review_plan] batch 01-alpha: verdict=APPROVE file=20260904-172628-plan-review-01-alpha-r1.md
[safe-rmtree] starting: path=/tmp/tmpvmtc2dgd allowed_root=/tmp/tmpvmtc2dgd
[safe-rmtree] removed: /tmp/tmpvmtc2dgd
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_review_plan] slug='test-slug' plan_dir=/tmp/tmphfw8ewut/container/wts/test-slug/plan batch_max_rounds=3 holistic_max_rounds=3
[_review_plan] found 1 batch file(s)
[safe-rmtree] starting: path=/tmp/tmphfw8ewut allowed_root=/tmp/tmphfw8ewut
[safe-rmtree] removed: /tmp/tmphfw8ewut
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_review_plan] slug='test-slug' plan_dir=/tmp/tmpe8qgyky_/container/wts/test-slug/plan batch_max_rounds=3 holistic_max_rounds=3
[_review_plan] found 1 batch file(s)
[safe-rmtree] starting: path=/tmp/tmpe8qgyky_ allowed_root=/tmp/tmpe8qgyky_
[safe-rmtree] removed: /tmp/tmpe8qgyky_
[safe-rmtree] starting: path=/tmp/tmp4vjvoie5 allowed_root=/tmp/tmp4vjvoie5
[safe-rmtree] removed: /tmp/tmp4vjvoie5
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_review_plan] slug='test-slug' plan_dir=/tmp/tmp5lxzyi05/container/wts/test-slug/plan batch_max_rounds=3 holistic_max_rounds=3
[_review_plan] found 1 batch file(s)
[_review_plan] batch 01-alpha: verdict=APPROVE file=20260904-172628-plan-review-01-alpha-r1.md
[safe-rmtree] starting: path=/tmp/tmp5lxzyi05 allowed_root=/tmp/tmp5lxzyi05
[safe-rmtree] removed: /tmp/tmp5lxzyi05
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_review_plan] slug='test-slug' plan_dir=/tmp/tmpdhiwzc0l/container/wts/test-slug/plan batch_max_rounds=3 holistic_max_rounds=3
[_review_plan] found 1 batch file(s)
[_review_plan] batch 01-alpha: verdict=APPROVE file=20260904-172628-plan-review-01-alpha-r1.md
[safe-rmtree] starting: path=/tmp/tmpdhiwzc0l allowed_root=/tmp/tmpdhiwzc0l
[safe-rmtree] removed: /tmp/tmpdhiwzc0l
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[safe-rmtree] starting: path=/tmp/tmpbc2mg4pz allowed_root=/tmp/tmpbc2mg4pz
[safe-rmtree] removed: /tmp/tmpbc2mg4pz
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[safe-rmtree] starting: path=/tmp/tmp8hheyubk allowed_root=/tmp/tmp8hheyubk
[safe-rmtree] removed: /tmp/tmp8hheyubk
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[safe-rmtree] starting: path=/tmp/tmpc8g9nttw allowed_root=/tmp/tmpc8g9nttw
[safe-rmtree] removed: /tmp/tmpc8g9nttw
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[safe-rmtree] starting: path=/tmp/tmpblp1frel allowed_root=/tmp/tmpblp1frel
[safe-rmtree] removed: /tmp/tmpblp1frel
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_review_plan] slug='test-slug' plan_dir=/tmp/tmpg1jdb4oa/container/wts/test-slug/plan batch_max_rounds=3 holistic_max_rounds=3
[_review_plan] found 1 batch file(s)
[_review_plan] running holistic review
[_review_plan] holistic: verdict=APPROVE file=20260904-172629-plan-review-r1.md
[safe-rmtree] starting: path=/tmp/tmpg1jdb4oa allowed_root=/tmp/tmpg1jdb4oa
[safe-rmtree] removed: /tmp/tmpg1jdb4oa
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_review_plan] slug='test-slug' plan_dir=/tmp/tmpzsd5o2sa/container/wts/test-slug/plan batch_max_rounds=3 holistic_max_rounds=3
[_review_plan] found 1 batch file(s)
[_review_plan] running holistic review
[_review_plan] holistic: verdict=APPROVE file=20260904-172629-plan-review-r1.md
[safe-rmtree] starting: path=/tmp/tmpzsd5o2sa allowed_root=/tmp/tmpzsd5o2sa
[safe-rmtree] removed: /tmp/tmpzsd5o2sa
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_config] note: no repo-layer mill-config.yaml found in hub, main worktree, or task worktree
[config] unknown key: paths.wiki (in config.local.yaml)
[_review_plan] slug='test-slug' plan_dir=/tmp/tmp7qxds4yb/container/wts/test-slug/plan batch_max_rounds=3 holistic_max_rounds=3
[_review_plan] found 1 batch file(s)
[_review_plan] batch 01-alpha NEED_CONTEXT round-1; retrying with resume (1 re-attached file(s)) session=sid-1
[_review_plan] batch 01-alpha: verdict=APPROVE file=20260904-172629-plan-review-01-alpha-r1.md
[_review_plan] running holistic review
[_review_plan] holistic NEED_CONTEXT round-1; retrying with resume (1 re-attached file(s)) session=sid-3
[_review_plan] holistic: verdict=APPROVE file=20260904-172629-plan-review-r1.md
[safe-rmtree] starting: path=/tmp/tmp7qxds4yb allowed_root=/tmp/tmp7qxds4yb
[safe-rmtree] removed: /tmp/tmp7qxds4yb

1 test(s) FAILED
Running 1 tests across 12 worker(s).
--- FAIL test-review-plan-flow.py (2.7s) ---

Slowest 10:
     2.7s  test-review-plan-flow.py

FAIL -- 1 of 1 in 2.7s: ['test-review-plan-flow.py']
```

## Merge Diff

```diff
diff --git a/plugins/mill/scripts/_implementer_common.py b/plugins/mill/scripts/_implementer_common.py
index eef34b80..c884c9fa 100644
--- a/plugins/mill/scripts/_implementer_common.py
+++ b/plugins/mill/scripts/_implementer_common.py
@@ -1052,6 +1052,8 @@ def _run_verify_gates(
     start_sha: str | None = None,
     status_path: Path | None = None,
     batch_name: str | None = None,
+    git_name: str | None = None,
+    git_email: str | None = None,
 ) -> dict | None:
     """
     Run the batch-level verify gate and, if it passes, the module-wide verify gate.
@@ -1136,6 +1138,12 @@ def _run_verify_gates(
         batch_name: This batch's name,
             forwarded to _status.set_batch_field alongside status_path.
             Defaults to None, which disables the self-healing persist exactly like status_path=None.
+        git_name: Git commit identity (user.name) used to persist an expanded
+            verify_baseline_failures corroboration result to status.md.
+            Defaults to None, which disables the persist-commit.
+        git_email: Git commit identity (user.email) used to persist an expanded
+            verify_baseline_failures corroboration result to status.md.
+            Defaults to None, which disables the persist-commit.
 
     Returns:
         A stuck dict on the first gate that fails,
@@ -1187,6 +1195,30 @@ def _run_verify_gates(
                                 )
                             except Exception:
                                 pass
+                            else:
+                                # Commit the status.md write immediately so the in-scope dirty-tree
+                                # gate (which runs later in the same finalize_from_output
+                                # invocation) never observes this write as uncommitted dirt (#954).
+                                # Best-effort: a commit failure here must never crash finalize --
+                                # the pre-existing dirty-tree gate is the fallback authority.
+                                if git_name is not None and git_email is not None:
+                                    try:
+                                        _subprocess_util.run(
+                                            [
+                                                "git",
+                                                "add",
+                                                status_path.relative_to(project_root).as_posix(),
+                                            ],
+                                            cwd=project_root,
+                                        )
+                                        _subprocess_util.git_commit(
+                                            project_root,
+                                            f"mill-go: persist corroborated verify baseline for {batch_name}",
+                                            name=git_name,
+                                            email=git_email,
+                                        )
+                                    except Exception:
+                                        pass
                         batch_result = None
         if batch_result is not None:
             return batch_result
@@ -1638,6 +1670,8 @@ def finalize_from_output(
     batch_verify_baseline: list[str] | None = None,
     commit_sha_field_name: str = "commit_sha",
     batch_name: str | None = None,
+    git_name: str | None = None,
+    git_email: str | None = None,
 ) -> int:
     """Read sub-agent output and finalize.
 
@@ -1695,6 +1729,12 @@ def finalize_from_output(
             calls.
             See _run_verify_gates for the self-healing persist this enables.
             Defaults to None (persist disabled, as before this parameter existed).
+        git_name: Git commit identity (user.name) forwarded unchanged to _forward_output's
+            _run_verify_gates calls.
+            Defaults to None (persist-commit disabled).
+        git_email: Git commit identity (user.email) forwarded unchanged to _forward_output's
+            _run_verify_gates calls.
+            Defaults to None (persist-commit disabled).
     """
     # Normalize to Path for safety -- call sites pass this via Path(args.agent_output),
     # but the parameter is documented (not enforced) as Path.
@@ -1734,6 +1774,8 @@ def finalize_from_output(
         batch_verify_baseline=batch_verify_baseline,
         commit_sha_field_name=commit_sha_field_name,
         batch_name=batch_name,
+        git_name=git_name,
+        git_email=git_email,
     )
 
 
@@ -1792,6 +1834,8 @@ def _forward_output(
     batch_verify_baseline: list[str] | None = None,
     commit_sha_field_name: str = "commit_sha",
     batch_name: str | None = None,
+    git_name: str | None = None,
+    git_email: str | None = None,
 ) -> int:
     """Extract the last JSON object containing a 'status' key from output.
 
@@ -1856,6 +1900,10 @@ def _forward_output(
     already-present start_sha and status_path parameters, enabling the self-healing persist
     documented on _run_verify_gates.
     Defaults to None (persist disabled, as before this parameter existed).
+    git_name and git_email are forwarded unchanged to every _run_verify_gates call site below: the
+    git commit identity used to persist an expanded verify_baseline_failures corroboration result to
+    status.md.
+    Both default to None, which disables the persist-commit.
     """
     parsed = _extract_status_json(output)
     if parsed is not None:
@@ -1884,6 +1932,8 @@ def _forward_output(
                 start_sha=start_sha,
                 status_path=status_path,
                 batch_name=batch_name,
+                git_name=git_name,
+                git_email=git_email,
             )
             if gate_result is not None:
                 # Reclassify a verify failure that is really a partial-batch stop (stuck_type:transient) or a no-content stop (stuck_type:logic).
@@ -2112,6 +2162,8 @@ def _forward_output(
                                         start_sha=start_sha,
                                         status_path=status_path,
                                         batch_name=batch_name,
+                                        git_name=git_name,
+                                        git_email=git_email,
                                     )
                                     if gate_result is not None:
                                         # No parsed success JSON on this inference path -- there is nothing to self-report from, so cards_done is always None here (the absent-field fallback always applies).
@@ -2222,6 +2274,8 @@ def _forward_output(
                         start_sha=start_sha,
                         status_path=status_path,
                         batch_name=batch_name,
+                        git_name=git_name,
+                        git_email=git_email,
                     )
                     if gate_result is not None:
                         # No parsed success JSON on this inference path -- cards_done is always None (the absent-field fallback always applies).
@@ -2332,6 +2386,8 @@ def _forward_output(
                         start_sha=start_sha,
                         status_path=status_path,
                         batch_name=batch_name,
+                        git_name=git_name,
+                        git_email=git_email,
                     )
                     if gate_result is not None:
                         # No parsed success JSON on this inference path -- cards_done is always None (the absent-field fallback always applies).
diff --git a/plugins/mill/scripts/_status.py b/plugins/mill/scripts/_status.py
index b2c6ed06..12fdf88e 100644
--- a/plugins/mill/scripts/_status.py
+++ b/plugins/mill/scripts/_status.py
@@ -518,6 +518,7 @@ _BATCH_ALLOWED_KEYS = {
     "review_file",
     "blocked_reason",
     "verify_baseline_failures",
+    "self_resolve_remint_at",
 }
 _BATCH_STATES = {
     "pending",
@@ -593,6 +594,7 @@ def _serialise_batches(batches: list[dict]) -> str:
         "review_file",
         "blocked_reason",
         "verify_baseline_failures",
+        "self_resolve_remint_at",
     ]
     parts = ["batches:"]
     for entry in batches:
diff --git a/plugins/mill/scripts/millpy-bg.py b/plugins/mill/scripts/millpy-bg.py
index d2a7f3bf..d85d531f 100644
--- a/plugins/mill/scripts/millpy-bg.py
+++ b/plugins/mill/scripts/millpy-bg.py
@@ -29,8 +29,15 @@ import sys
 if "--_worker" in sys.argv:
     import os
     import subprocess
+    import threading
     from datetime import datetime, timezone
 
+    # How often the worker appends a "[mill-bg] HEARTBEAT" line to the log while
+    # the inner subprocess runs. Narrows the diagnostic window when the worker
+    # process is hard-killed (SIGKILL/TerminateProcess) before its own
+    # except/finally handlers can run -- see module docstring.
+    _HEARTBEAT_INTERVAL_S = 30
+
     def _worker_main(args: list[str]) -> int:
         try:
             sep = args.index("--")
@@ -60,13 +67,31 @@ if "--_worker" in sys.argv:
                     f"[mill-bg] WORKER PID={os.getpid()} START "
                     f"{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}\n"
                 )
-                result = subprocess.run(
-                    cmd,
-                    stdout=log_f,
-                    stderr=subprocess.STDOUT,
-                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
-                )
-                exit_code = result.returncode
+                _heartbeat_stop = threading.Event()
+
+                def _heartbeat() -> None:
+                    while not _heartbeat_stop.wait(_HEARTBEAT_INTERVAL_S):
+                        try:
+                            log_f.write(
+                                f"[mill-bg] HEARTBEAT "
+                                f"{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}\n"
+                            )
+                        except Exception:
+                            return
+
+                _heartbeat_thread = threading.Thread(target=_heartbeat, daemon=True)
+                _heartbeat_thread.start()
+                try:
+                    result = subprocess.run(
+                        cmd,
+                        stdout=log_f,
+                        stderr=subprocess.STDOUT,
+                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
+                    )
+                    exit_code = result.returncode
+                finally:
+                    _heartbeat_stop.set()
+                    _heartbeat_thread.join()
             return 0
         except Exception as exc:
             try:
diff --git a/plugins/mill/scripts/millpy-fix.py b/plugins/mill/scripts/millpy-fix.py
index c6cd3d37..cf6f0fe7 100644
--- a/plugins/mill/scripts/millpy-fix.py
+++ b/plugins/mill/scripts/millpy-fix.py
@@ -417,10 +417,26 @@ def main(argv=None) -> int:
             print("--agent-output is required when --stage finalize", file=sys.stderr)
             return 1
         fixer_snapshot_path = project_root / "_mill" / ".cleanliness-snapshot-fixer.txt"
+        # Module-wide verify derivation, mirroring millpy-implement.py's main(): read the
+        # overview's own verify field and the already-cached module-scoped baseline so the
+        # fixer's live verify replay can apply the same subset-diff waiver the implementer
+        # dispatch already gets. Without this, forwarding module_verify_baseline alone would
+        # be inert -- _run_verify_gates short-circuits the module-wide gate whenever
+        # module_wide_verify_cmd is None.
+        overview_frontmatter = _plan_dag._read_batch_frontmatter(overview_path)
+        module_wide_verify_cmd, module_wide_cwd_override = _plan_dag.parse_verify_field(
+            overview_frontmatter, project_root, git_root
+        )
+        module_verify_baseline = _status.get_module_verify_baseline(status_path)
+
         # Resolve verify command for batch/holistic fixes.
         # cwd_override is pre-initialized to None here (before branching on args.scope) because the batch-scope read below is nested inside `if batch_entry is not None:` and the holistic-scope read inside `if batch_verifies:` -- either guard can be false, leaving the pre-initialized None value, exactly matching pre-#604 behavior.
         verify_cmd = None
         cwd_override = None
+        # batch_verify_baseline must be defined unconditionally (both scope arms below only
+        # reassign it inside their own guard), since it is read regardless of scope when
+        # building the finalize_from_output call below.
+        batch_verify_baseline = None
         if args.scope == "batch":
             batch_entry = next(
                 (b for b in batches if b["name"] == args.batch_name), None
@@ -431,6 +447,13 @@ def main(argv=None) -> int:
                 verify_cmd, cwd_override = _plan_dag.parse_verify_field(
                     batch_frontmatter, project_root, git_root
                 )
+            batch_status = next(
+                (b for b in _status.read_batches(status_path) if b.get("name") == args.batch_name),
+                None,
+            )
+            batch_verify_baseline = (
+                batch_status.get("verify_baseline_failures") if batch_status is not None else None
+            )
         elif args.scope == "holistic":
             # Derive concatenated verify_cmd from all batch verify commands in DAG order
             batch_verifies = _plan_dag.iter_batch_verifies(
@@ -441,6 +464,16 @@ def main(argv=None) -> int:
             )
             if batch_verifies:
                 verify_cmd, cwd_override = _resolve_holistic_verify(batch_verifies)
+            # Union every contributing batch's cached verify-baseline failure set, so the
+            # holistic waiver covers pre-existing/unrelated failures from any batch this
+            # fix round spans -- not just one arbitrarily-chosen batch's baseline.
+            _all_batches_status = _status.read_batches(status_path)
+            _union_baseline: set[str] = set()
+            for _bv_name, _bv_cmd, _bv_cwd in batch_verifies:
+                _bv_status = next((b for b in _all_batches_status if b.get("name") == _bv_name), None)
+                if _bv_status is not None and _bv_status.get("verify_baseline_failures"):
+                    _union_baseline.update(_bv_status["verify_baseline_failures"])
+            batch_verify_baseline = sorted(_union_baseline) if _union_baseline else None
         nits_scope = args.batch_name if args.scope == "batch" else "holistic"
         return finalize_from_output(
             Path(args.agent_output),
@@ -454,6 +487,13 @@ def main(argv=None) -> int:
             nits_scope=nits_scope,
             git_root=git_root,
             cwd_override=cwd_override,
+            git_name=git_name,
+            git_email=git_email,
+            module_wide_verify_cmd=module_wide_verify_cmd,
+            module_wide_cwd_override=module_wide_cwd_override,
+            module_verify_baseline=module_verify_baseline,
+            batch_verify_baseline=batch_verify_baseline,
+            batch_name=args.batch_name,
         )
 
     # Compute the fixer-brief carve-out clause once, from the already-parsed --nits-only flag.
@@ -711,6 +751,8 @@ def main(argv=None) -> int:
         nits_scope=nits_scope,
         git_root=git_root,
         cwd_override=cwd_override,
+        git_name=git_name,
+        git_email=git_email,
     )
 
 
diff --git a/plugins/mill/scripts/millpy-implement.py b/plugins/mill/scripts/millpy-implement.py
index b5282659..4c42abcd 100644
--- a/plugins/mill/scripts/millpy-implement.py
+++ b/plugins/mill/scripts/millpy-implement.py
@@ -750,6 +750,8 @@ def main(argv=None) -> int:
             git_root=git_root,
             cwd_override=cwd_override,
             module_wide_cwd_override=module_wide_cwd_override,
+            git_name=git_name,
+            git_email=git_email,
         )
 
     # Stages: prepare and full (need pre-commit, render, and setup)
@@ -762,6 +764,10 @@ def main(argv=None) -> int:
     # mill-go resuming after a transient dispatch failure) would overwrite implementer_session in status.md and make a second "mill-go: start batch" commit, both of which corrupt state the agent-mode dispatch loop and finalize's completeness recount rely on (#625, #635, #643).
     # Resolved once, before the resume/fresh-mint branches below, so the three-way branch reads as: resume-after-incomplete, prepare-reuse, fresh-mint.
     _prepare_reuse_entry = None
+    # Set only when the most recent timeline row is a self-resolve marker (see below);
+    # the fresh-mint branch reads this even when the block above never runs (e.g. --stage full),
+    # so it must be initialized at this same top-level scope regardless of args.stage.
+    _self_resolve_remint_ts = None
     if args.stage == "prepare" and not args.resume_incomplete:
         _prepare_batches = _status.read_batches(status_path)
         _prepare_candidate = next(
@@ -772,7 +778,25 @@ def main(argv=None) -> int:
             and _prepare_candidate.get("state") == "running"
             and _prepare_candidate.get("implementer_session")
         ):
-            _prepare_reuse_entry = _prepare_candidate
+            # A self-resolve (mill-go-base/SKILL.md's per-batch self-resolve step) leaves
+            # "state: running" and the original implementer_session untouched -- it only appends a
+            # "self-resolved-verify-logic" timeline row -- so this reuse heuristic cannot tell a
+            # self-resolved re-fire apart from a genuine transient-dispatch-failure re-fire without
+            # also consulting the timeline.
+            # Withhold reuse exactly once per self-resolve marker: the fresh-mint branch below
+            # records self_resolve_remint_at so a *second* prepare call sees _already_reminted and
+            # reuses normally, bounding this to one remint rather than an unbounded chain.
+            _timeline = _status.read_full(status_path)["timeline"]
+            if _timeline:
+                _last_parts = _timeline[-1].split(None, 1)
+                if len(_last_parts) > 1 and _last_parts[0] == "self-resolved-verify-logic":
+                    _self_resolve_remint_ts = _last_parts[1].strip("'\"")
+            _already_reminted = (
+                _self_resolve_remint_ts is not None
+                and _prepare_candidate.get("self_resolve_remint_at") == _self_resolve_remint_ts
+            )
+            if _self_resolve_remint_ts is None or _already_reminted:
+                _prepare_reuse_entry = _prepare_candidate
 
     if args.resume_incomplete:
         # Resume path: read the original start_sha and implementer_session from status.md.
@@ -824,11 +848,18 @@ def main(argv=None) -> int:
 
         session_id = str(uuid.uuid4())
 
-        _status.set_batch_fields(
-            status_path,
-            args.batch_name,
-            {"state": "running", "start_sha": start_sha, "implementer_session": session_id},
-        )
+        _fresh_mint_fields = {
+            "state": "running",
+            "start_sha": start_sha,
+            "implementer_session": session_id,
+        }
+        # Record the remint marker only when this fresh mint was actually triggered by an
+        # unreacted self-resolve, not an ordinary first-pass dispatch -- so a later prepare
+        # call for this same session can detect _already_reminted and reuse it instead of
+        # minting a third session on a following transient retry.
+        if _self_resolve_remint_ts is not None:
+            _fresh_mint_fields["self_resolve_remint_at"] = _self_resolve_remint_ts
+        _status.set_batch_fields(status_path, args.batch_name, _fresh_mint_fields)
 
         # Stage status.md and the cleanliness snapshot unconditionally.
         # On a re-fire the prepare step regenerated implementer_session, so status.md is always dirty;
@@ -1001,6 +1032,8 @@ def main(argv=None) -> int:
         git_root=git_root,
         cwd_override=cwd_override,
         module_wide_cwd_override=module_wide_cwd_override,
+        git_name=git_name,
+        git_email=git_email,
     )
 
 
diff --git a/plugins/mill/skills/code-comments/SKILL.md b/plugins/mill/skills/code-comments/SKILL.md
index 7d2b9954..c8b86edf 100644
--- a/plugins/mill/skills/code-comments/SKILL.md
+++ b/plugins/mill/skills/code-comments/SKILL.md
@@ -65,3 +65,7 @@ See the per-language skill for how that language's tooling renders consecutive c
   If code needs a "what" comment, refactor instead.
 - **No measured-result or design-rationale narrative** — a doc comment must not contain measured numeric deltas, rejected-alternative trails, or reproduction/incident narrative.
   That belongs in an inline why-comment, `_codeguide/` module docs, or a `Doc/` design-decision note.
+- **No enumerated-consumer lists** — don't name every current caller, writer, consumer, or implementer of a shared symbol or resource when the comment's point doesn't depend on which ones currently do
+  (e.g. "the logger, reed, shuttle, and burler all write it").
+  That list goes stale whenever a subsystem is added or removed, turning an unrelated change elsewhere in the codebase into a forced edit here.
+  Write "several of `<component>`'s own subsystems" or similar instead, unless the specific names are themselves load-bearing to the point being made.
diff --git a/plugins/mill/skills/mill-merge-in/SKILL.md b/plugins/mill/skills/mill-merge-in/SKILL.md
index 72b1f567..db5956df 100644
--- a/plugins/mill/skills/mill-merge-in/SKILL.md
+++ b/plugins/mill/skills/mill-merge-in/SKILL.md
@@ -200,7 +200,7 @@ Staging is unconditional on `_mill/briefs` existing, but the commit is gated on
 
 ```bash
 if [ -d <worktree>/_mill/briefs ]; then
-  git -C <worktree> add <worktree>/_mill/briefs/
+  git -C <worktree> add _mill/briefs/
 fi
 if [ -n "$(git -C <worktree> diff --cached --name-only)" ]; then
   git -C <worktree> commit -m "mill-merge-in: commit dispatch briefs"
diff --git a/plugins/mill/skills/mill-start/SKILL.md b/plugins/mill/skills/mill-start/SKILL.md
index 54210df7..4486aef5 100644
--- a/plugins/mill/skills/mill-start/SKILL.md
+++ b/plugins/mill/skills/mill-start/SKILL.md
@@ -403,7 +403,7 @@ If not `converged` and `round >= max_review_rounds`: run the branch's full termi
    NIT fixes fold into the same round's write and commit as the gap resolutions: no separate commit, no separate fixer report,
    and the Q&A log is not used for NITs (gaps are Q&A-logged;
    NITs are not).
-   When the final batch in this round is answered, write `<discussion_path>`, commit on the task branch (`git -C <worktree> add <discussion_path> <reviews_dir>/ _mill/briefs/ && git commit -m "mill-start: discussion-gap-fix round {N} for {slug}"`), push, and start round N+1.
+   When the final batch in this round is answered, write `<discussion_path>`, call `_status.append_phase(status_path, f"discussion-gap-fix-r{N}", _timestamp.now_utc_iso())`, commit on the task branch (`git -C <worktree> add <discussion_path> <reviews_dir>/ _mill/briefs/ <status_path> && git commit -m "mill-start: discussion-gap-fix round {N} for {slug}"`), push, and start round N+1.
    If a gap is genuinely impossible to answer (operator does not know yet), the operator may pick the recommended option and add a follow-up note inline — that is the same fallback as Phase: Discuss.
 
 If unresolved gaps remain after `max_review_rounds`: present them to the user for an explicit override ("ignore gap X for now") or more-info decision.
diff --git a/plugins/mill/skills/orch-review/SKILL.md b/plugins/mill/skills/orch-review/SKILL.md
index e5790b8d..93f3cdfd 100644
--- a/plugins/mill/skills/orch-review/SKILL.md
+++ b/plugins/mill/skills/orch-review/SKILL.md
@@ -6,7 +6,7 @@ argument-hint: "<slug> [<slug>...]"
 
 # orch-review
 
-Companion to `mill-start`'s `--orch` flag. A worker running `/mill-start --orch` pauses before discussion-review round 1's automated reviewer dispatch, waiting for a file named `orch-review.md` to appear next to `discussion.md`. This skill is what **this session** (the orchestrator/driver, not the worker) loads to actually write that file — it is the human-in-the-loop substitute for round 1's automated reviewer.
+Companion to `mill-start`'s `--orch` flag. A worker running `/mill-start --orch` pauses before discussion-review round 1's automated reviewer dispatch, waiting for a file named `orch-review.md` to appear at `.scratch/orch-review.md`. This skill is what **this session** (the orchestrator/driver, not the worker) loads to actually write that file — it is the human-in-the-loop substitute for round 1's automated reviewer.
 
 **The `discussion.md` wait runs in this session, not in a fork.** A fork that arms a `Monitor` wait and then produces no further output is treated as finished and torn down — the monitor trigger has nothing left to wake up, so a fork left waiting on one never resumes. Only this top-level session reliably survives an armed `Monitor` wait and gets woken back up when it fires. So: **this session owns every `Monitor` wait, one per slug; a fork is only launched per slug after that slug's `discussion.md` is already confirmed to exist** — the fork only ever does the (non-blocking) read/review/write work, which is what still needs to stay out of this session's own context.
 
@@ -62,7 +62,7 @@ When a fork's completion notification arrives (a later turn, not this one), rela
 
 ### Step 1 — Read the discussion in full
 
-Read `<worktree>/_mill/discussion.md` in full — do not skim. If `<worktree>/_mill/orch-review.md` already exists, halt and ask whether to overwrite (a stale file from a prior round may still be awaiting pickup).
+Read `<worktree>/_mill/discussion.md` in full — do not skim. If `<worktree>/.scratch/orch-review.md` already exists, halt and ask whether to overwrite (a stale file from a prior round may still be awaiting pickup).
 
 ### Step 2 — Review it
 
@@ -72,7 +72,7 @@ Severity and class vocabulary are closed, per `plugins/mill/templates/review-out
 
 ### Step 3 — Write `orch-review.md`
 
-Write `<worktree>/_mill/orch-review.md` (next to `discussion.md`, never inside `_mill/reviews/` — that directory is reserved for the canonical, timestamped files the worker's `finalize()` call produces) in the exact format `plugins/mill/templates/review-output.schema.md` documents:
+Write `<worktree>/.scratch/orch-review.md` (gitignored ephemeral scratch space per `mill:conversation`'s convention — never inside `_mill/` at all, and specifically never inside `_mill/reviews/`, which is reserved for the canonical, timestamped files the worker's `finalize()` call produces) in the exact format `plugins/mill/templates/review-output.schema.md` documents:
 
 ```markdown
 # Review: <task title>
@@ -104,7 +104,7 @@ Omit `## Findings` entirely (write `(no findings)`) if there are none. `duration
 End with a short final message this fork's own turn — this becomes the text the orchestrator's Step 4 relays as a summary, e.g.:
 
 ```
-Wrote _mill/orch-review.md for <slug>. The waiting worker polls every few seconds and will
+Wrote .scratch/orch-review.md for <slug>. The waiting worker polls every few seconds and will
 pick this up, apply the mill-start review-fix decision tree, and resume mill-start --orch
 on its own — no further action needed here.
 ```
@@ -112,7 +112,7 @@ on its own — no further action needed here.
 ## Rules
 
 - **This session owns every `Monitor` wait — never a fork.** A fork that ends its turn on an armed `Monitor` wait with nothing left to do is torn down as "finished" before the monitor ever fires; only this session survives that. Forking happens only after a slug's `discussion.md` is already confirmed present.
-- **One file, one purpose, per fork.** Each fork's entire footprint is writing its own `_mill/orch-review.md`. No fork reads or writes `status.md`, `_mill/reviews/`, or anything under the wiki. No fork waits on anything.
+- **One file, one purpose, per fork.** Each fork's entire footprint is writing its own `.scratch/orch-review.md`. No fork reads or writes `status.md`, `_mill/reviews/`, or anything under the wiki. No fork waits on anything.
 - **Never used for round 2+.** `mill-start --orch` only waits for this file on discussion-review round 1; any later round in the same task reverts to the normal configured automated reviewer. Re-running this skill against a task past round 1 has no effect (nothing is waiting for the file).
 - **Ground every finding.** Same source-grounding rule the automated reviewer prompt carries: never fabricate file contents or discussion.md sections not actually read.
 - **Don't peek.** The orchestrator never reads a fork's transcript/output_file mid-flight — trust the completion notification per this session's own fork guidance.
diff --git a/plugins/mill/skills/orch-wait/SKILL.md b/plugins/mill/skills/orch-wait/SKILL.md
index a36a2c64..c675de3e 100644
--- a/plugins/mill/skills/orch-wait/SKILL.md
+++ b/plugins/mill/skills/orch-wait/SKILL.md
@@ -12,17 +12,17 @@ This skill assumes `mill-start`'s Entry and Path Setup have already run — `slu
 
 ## Step 1 — Announce the wait
 
-Report to the log/status: `"Waiting for orchestrator review -- write _mill/orch-review.md next to discussion.md to resume."` No operator is present in this worker's own conversation to prompt.
+Report to the log/status: `"Waiting for orchestrator review -- write .scratch/orch-review.md to resume."` No operator is present in this worker's own conversation to prompt.
 
 ## Step 2 — Blocking wait for the file
 
-Same idiom as the entry-gate wait in `mill-go-base/SKILL.md` (`Monitor` tool, persistent bash poll, not a fixed `sleep`): poll every 30 seconds for `<worktree_root>/_mill/orch-review.md` to exist, giving up after the configured `pipeline.entry_wait_timeout_minutes` (read from config the same way `mill-go-base`'s entry-gate wait does, rather than hardcoding).
+Same idiom as the entry-gate wait in `mill-go-base/SKILL.md` (`Monitor` tool, persistent bash poll, not a fixed `sleep`): poll every 30 seconds for `<worktree_root>/.scratch/orch-review.md` to exist, giving up after the configured `pipeline.entry_wait_timeout_minutes` (read from config the same way `mill-go-base`'s entry-gate wait does, rather than hardcoding).
 
 On timeout: `_status.set_blocked(status_path, "auto: awaiting orchestrator review (orch-review.md) timed out after <N>h", timestamp=_timestamp.now_utc_iso())`, then `git -C <worktree> add <status_path> && git -C <worktree> commit -m "mill-start: blocked (auto: orchestrator review timeout) for <slug>" && git -C <worktree> push`, then halt. Do not retry. This halt message must read differently from `--auto`'s own "discussion review gaps unresolved after N rounds" halt, so an operator reading `status.md` later can tell which condition fired.
 
 ## Step 3 — Consume the file
 
-Read `<worktree_root>/_mill/orch-review.md` in full as `raw_text`, then run it through the same backend `finalize()` call the normal Step 2 Agent-mode dispatch would otherwise reach — this reuses the blocking-class ceiling, verdict parsing, and canonical file-naming/writing `_review_discussion.finalize` already implements, so round 1's envelope shape needs no hand-derivation:
+Read `<worktree_root>/.scratch/orch-review.md` in full as `raw_text`, then run it through the same backend `finalize()` call the normal Step 2 Agent-mode dispatch would otherwise reach — this reuses the blocking-class ceiling, verdict parsing, and canonical file-naming/writing `_review_discussion.finalize` already implements, so round 1's envelope shape needs no hand-derivation:
 
 ```bash
 PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "
@@ -35,7 +35,7 @@ worktree_root = _paths.resolve_hub_path()
 cfg = _config.load_config(worktree_root, git_root)
 wiki_path = _paths.resolve_wiki_path(git_root)
 reviews_dir = worktree_root / cfg['paths']['reviews_dir']
-raw_text = open(worktree_root / '_mill/orch-review.md', encoding='utf-8').read()
+raw_text = open(worktree_root / '.scratch/orch-review.md', encoding='utf-8').read()
 
 result = finalize(
     cfg, '<slug>', raw_text,
@@ -51,7 +51,7 @@ print(json.dumps(dataclasses.asdict(result)))
 
 ## Step 4 — Remove the trigger file
 
-`<worktree_root>/_mill/orch-review.md` is ephemeral and never committed — delete it now that `finalize()` produced the canonical copy, so it can't be mistaken for a fresh one on a later task.
+`<worktree_root>/.scratch/orch-review.md` is ephemeral, gitignored, and never committed — delete it now that `finalize()` produced the canonical copy, so it can't be mistaken for a fresh one on a later task.
 
 ## Step 5 — Cost line
 
diff --git a/plugins/mill/unit_tests/test-fix-finalize.py b/plugins/mill/unit_tests/test-fix-finalize.py
index 2d434041..ef612a77 100644
--- a/plugins/mill/unit_tests/test-fix-finalize.py
+++ b/plugins/mill/unit_tests/test-fix-finalize.py
@@ -100,6 +100,12 @@ def main() -> int:
                 return_value={"model": "claude-haiku-4-5-20251001"}
             )
             mock_modules["_plan_dag"].extract_batch_index = unittest.mock.MagicMock(return_value=[])
+            # No batches contribute a verify command in these two tests -- the module-wide
+            # derivation this batch added to the finalize block still runs unconditionally, so
+            # parse_verify_field must be configured to unpack cleanly even here.
+            mock_modules["_plan_dag"].parse_verify_field = unittest.mock.MagicMock(
+                return_value=(None, None)
+            )
 
             def mock_subprocess_run(*args, **kwargs):
                 result = unittest.mock.MagicMock()
@@ -228,6 +234,12 @@ def main() -> int:
                 return_value={"model": "claude-haiku-4-5-20251001"}
             )
             mock_modules["_plan_dag"].extract_batch_index = unittest.mock.MagicMock(return_value=[])
+            # No batches contribute a verify command in these two tests -- the module-wide
+            # derivation this batch added to the finalize block still runs unconditionally, so
+            # parse_verify_field must be configured to unpack cleanly even here.
+            mock_modules["_plan_dag"].parse_verify_field = unittest.mock.MagicMock(
+                return_value=(None, None)
+            )
 
             def mock_subprocess_run(*args, **kwargs):
                 result = unittest.mock.MagicMock()
@@ -509,6 +521,331 @@ def main() -> int:
             print(f"FAIL: test 5 ({exc})", file=sys.stderr)
             errors += 1
 
+    # Test 6: --scope batch forwards batch_verify_baseline from status.md's batch entry,
+    # and forwards module_wide_verify_cmd/module_wide_cwd_override derived from the overview's
+    # own verify frontmatter (#916 -- Card 6/7).
+    with tempfile.TemporaryDirectory() as tmpdir:
+        project_root = Path(tmpdir)
+        (project_root / "_mill").mkdir(parents=True)
+        (project_root / "_mill/plan").mkdir(parents=True)
+        review_file = project_root / "review.json"
+        review_file.write_text("{}", encoding="utf-8")
+        agent_output_file = project_root / "agent_output.txt"
+        agent_output_file.write_text("test output", encoding="utf-8")
+
+        overview_file = project_root / "_mill/plan/00-overview.md"
+        overview_file.write_text("```yaml\nbatches: []\n```", encoding="utf-8")
+
+        # Sentinel resolved cwds distinguishing the module-wide (overview) verify from the
+        # batch-scope verify -- proves the two `_plan_dag.parse_verify_field` calls are kept
+        # separate rather than one accidentally reusing the other's result.
+        module_wide_cwd = project_root / "module-wide-hub"
+        batch_cwd = project_root / "batch-hub"
+        overview_frontmatter = {"verify": "module-wide-verify-cmd"}
+        batch_frontmatter = {"verify": {"cwd": "hub", "command": "exit 0"}}
+
+        try:
+            import importlib.util
+
+            mock_modules = {
+                "_review_common": unittest.mock.MagicMock(),
+                "_marker": unittest.mock.MagicMock(),
+                "_status": unittest.mock.MagicMock(),
+                "_reviewers": unittest.mock.MagicMock(),
+                "_plan_dag": unittest.mock.MagicMock(),
+                "_subprocess_util": unittest.mock.MagicMock(),
+                "_paths": unittest.mock.MagicMock(),
+                "_agent_dispatch": unittest.mock.MagicMock(),
+                "_render": unittest.mock.MagicMock(),
+                "_timestamp": unittest.mock.MagicMock(),
+            }
+
+            mock_modules["_review_common"].load_config = unittest.mock.MagicMock(
+                return_value={
+                    "paths": {"reviews_dir": "_mill/reviews/", "status_md": "_mill/status.md", "plan_dir": "_mill/plan/"},
+                    "roles": {"fixer": {"model": "haiku"}, "implementer": {"self_fix_rounds": 2}},
+                }
+            )
+            mock_modules["_marker"].slug_from_branch = unittest.mock.MagicMock(return_value="test-slug")
+            mock_modules["_status"].read_full = unittest.mock.MagicMock(
+                return_value={"yaml": {"task": "Test", "branch": "test-branch"}, "timeline": []}
+            )
+            mock_modules["_status"].read_branch = unittest.mock.MagicMock(return_value="test-branch")
+            mock_modules["_status"].read_batches = unittest.mock.MagicMock(
+                return_value=[
+                    {"name": "test-batch", "verify_baseline_failures": ["sigA", "sigB"]},
+                ]
+            )
+            mock_modules["_status"].get_module_verify_baseline = unittest.mock.MagicMock(
+                return_value="pre-existing-failures"
+            )
+            mock_modules["_reviewers"].load = unittest.mock.MagicMock(return_value={})
+            mock_modules["_reviewers"].resolve = unittest.mock.MagicMock(
+                return_value={"model": "claude-haiku-4-5-20251001"}
+            )
+            mock_modules["_plan_dag"].extract_batch_index = unittest.mock.MagicMock(
+                return_value=[{"name": "test-batch", "file": "01-test-batch.md", "depends-on": []}]
+            )
+
+            def mock_read_frontmatter(path):
+                if Path(path).name == "00-overview.md":
+                    return overview_frontmatter
+                return batch_frontmatter
+
+            mock_modules["_plan_dag"]._read_batch_frontmatter = unittest.mock.MagicMock(
+                side_effect=mock_read_frontmatter
+            )
+
+            def mock_parse_verify_field(frontmatter, project_root_arg, git_root_arg):
+                if frontmatter is overview_frontmatter:
+                    return ("module-wide-verify-cmd", module_wide_cwd)
+                return ("exit 0", batch_cwd)
+
+            mock_modules["_plan_dag"].parse_verify_field = unittest.mock.MagicMock(
+                side_effect=mock_parse_verify_field
+            )
+
+            def mock_subprocess_run(*args, **kwargs):
+                result = unittest.mock.MagicMock()
+                result.returncode = 0
+                if args and ("user.name" in str(args) or "user.email" in str(args)):
+                    result.stdout = "Test User" if "user.name" in str(args) else "test@example.com"
+                else:
+                    result.stdout = ""
+                result.stderr = ""
+                return result
+
+            def mock_resolve_task_path(project_root_arg, rel_path):
+                return project_root / rel_path.lstrip("/")
+
+            mock_modules["_subprocess_util"].run = unittest.mock.MagicMock(side_effect=mock_subprocess_run)
+            mock_modules["_paths"].status_path = unittest.mock.MagicMock(
+                return_value=project_root / "_mill/status.md"
+            )
+            mock_modules["_paths"].resolve_task_path = unittest.mock.MagicMock(
+                side_effect=mock_resolve_task_path
+            )
+            mock_modules["_paths"].resolve_git_root = unittest.mock.MagicMock(return_value=project_root)
+            mock_modules["_paths"].resolve_wiki_path = unittest.mock.MagicMock(return_value=project_root)
+
+            with unittest.mock.patch.dict(sys.modules, mock_modules):
+                spec = importlib.util.spec_from_file_location(
+                    "millpy_fix_test6",
+                    HUB / "plugins/mill/scripts/millpy-fix.py",
+                )
+                millpy_fix = importlib.util.module_from_spec(spec)
+
+                mock_finalize = unittest.mock.MagicMock(return_value=0)
+
+                sys.modules["millpy_fix_test6"] = millpy_fix
+                with unittest.mock.patch.object(
+                    millpy_fix, "finalize_from_output", mock_finalize, create=True
+                ):
+                    spec.loader.exec_module(millpy_fix)
+                    millpy_fix.finalize_from_output = mock_finalize
+
+                    millpy_fix.main(
+                        [
+                            "--scope",
+                            "batch",
+                            "--batch-name",
+                            "test-batch",
+                            "--review-file",
+                            str(review_file),
+                            "--round",
+                            "1",
+                            "--stage",
+                            "finalize",
+                            "--agent-output",
+                            str(agent_output_file),
+                            "--session-id",
+                            "sid-xyz",
+                        ]
+                    )
+
+                    if mock_finalize.called:
+                        call_args = mock_finalize.call_args
+                        if (
+                            call_args.kwargs.get("batch_verify_baseline") == ["sigA", "sigB"]
+                            and call_args.kwargs.get("module_wide_verify_cmd") == "module-wide-verify-cmd"
+                            and call_args.kwargs.get("module_wide_cwd_override") == module_wide_cwd
+                            and call_args.kwargs.get("module_verify_baseline") == "pre-existing-failures"
+                            and call_args.kwargs.get("batch_name") == "test-batch"
+                            # main()'s already-resolved git_name/git_email locals (from mock_subprocess_run's
+                            # user.name/user.email branch above) must be forwarded into finalize_from_output --
+                            # the #954 corroboration-commit git-identity fix; a future edit that silently drops
+                            # these kwargs must fail this test.
+                            and call_args.kwargs.get("git_name") == "Test User"
+                            and call_args.kwargs.get("git_email") == "test@example.com"
+                        ):
+                            print(
+                                "PASS: --scope batch forwards batch_verify_baseline and module-wide verify derivation"
+                            )
+                        else:
+                            print(
+                                f"FAIL: batch-scope baseline forwarding - call_args={call_args}",
+                                file=sys.stderr,
+                            )
+                            errors += 1
+                    else:
+                        print("FAIL: finalize_from_output not called", file=sys.stderr)
+                        errors += 1
+        except Exception as exc:
+            print(f"FAIL: test 6 ({exc})", file=sys.stderr)
+            errors += 1
+
+    # Test 7: --scope holistic forwards batch_verify_baseline as the sorted union of every
+    # contributing batch's own verify_baseline_failures list (#916 -- Card 6/7).
+    with tempfile.TemporaryDirectory() as tmpdir:
+        project_root = Path(tmpdir)
+        (project_root / "_mill").mkdir(parents=True)
+        (project_root / "_mill/plan").mkdir(parents=True)
+        review_file = project_root / "review.json"
+        review_file.write_text("{}", encoding="utf-8")
+        agent_output_file = project_root / "agent_output.txt"
+        agent_output_file.write_text("test output", encoding="utf-8")
+
+        overview_file = project_root / "_mill/plan/00-overview.md"
+        overview_file.write_text("```yaml\nbatches: []\n```", encoding="utf-8")
+
+        overview_frontmatter = {"verify": "module-wide-verify-cmd"}
+
+        try:
+            import importlib.util
+
+            mock_modules = {
+                "_review_common": unittest.mock.MagicMock(),
+                "_marker": unittest.mock.MagicMock(),
+                "_status": unittest.mock.MagicMock(),
+                "_reviewers": unittest.mock.MagicMock(),
+                "_plan_dag": unittest.mock.MagicMock(),
+                "_subprocess_util": unittest.mock.MagicMock(),
+                "_paths": unittest.mock.MagicMock(),
+                "_agent_dispatch": unittest.mock.MagicMock(),
+                "_render": unittest.mock.MagicMock(),
+                "_timestamp": unittest.mock.MagicMock(),
+            }
+
+            mock_modules["_review_common"].load_config = unittest.mock.MagicMock(
+                return_value={
+                    "paths": {"reviews_dir": "_mill/reviews/", "status_md": "_mill/status.md", "plan_dir": "_mill/plan/"},
+                    "roles": {"fixer": {"model": "haiku"}, "implementer": {"self_fix_rounds": 2}},
+                }
+            )
+            mock_modules["_marker"].slug_from_branch = unittest.mock.MagicMock(return_value="test-slug")
+            mock_modules["_status"].read_full = unittest.mock.MagicMock(
+                return_value={"yaml": {"task": "Test", "branch": "test-branch"}, "timeline": []}
+            )
+            mock_modules["_status"].read_branch = unittest.mock.MagicMock(return_value="test-branch")
+            # Two contributing batches, each with a distinct non-empty verify_baseline_failures
+            # list, with an overlapping signature ("sigShared") to prove the union deduplicates.
+            mock_modules["_status"].read_batches = unittest.mock.MagicMock(
+                return_value=[
+                    {"name": "batch-one", "verify_baseline_failures": ["sigA", "sigShared"]},
+                    {"name": "batch-two", "verify_baseline_failures": ["sigB", "sigShared"]},
+                ]
+            )
+            mock_modules["_status"].get_module_verify_baseline = unittest.mock.MagicMock(return_value=None)
+            mock_modules["_reviewers"].load = unittest.mock.MagicMock(return_value={})
+            mock_modules["_reviewers"].resolve = unittest.mock.MagicMock(
+                return_value={"model": "claude-haiku-4-5-20251001"}
+            )
+            mock_modules["_plan_dag"].extract_batch_index = unittest.mock.MagicMock(return_value=[])
+
+            def mock_read_frontmatter(path):
+                return overview_frontmatter
+
+            mock_modules["_plan_dag"]._read_batch_frontmatter = unittest.mock.MagicMock(
+                side_effect=mock_read_frontmatter
+            )
+            mock_modules["_plan_dag"].parse_verify_field = unittest.mock.MagicMock(
+                return_value=("module-wide-verify-cmd", None)
+            )
+            # Both batches contribute a runnable verify command in DAG order -- the exact shape
+            # `iter_batch_verifies` returns -- so the holistic union loop below has something to
+            # iterate over.
+            mock_modules["_plan_dag"].iter_batch_verifies = unittest.mock.MagicMock(
+                return_value=[
+                    ("batch-one", "exit 0", None),
+                    ("batch-two", "exit 0", None),
+                ]
+            )
+
+            def mock_subprocess_run(*args, **kwargs):
+                result = unittest.mock.MagicMock()
+                result.returncode = 0
+                if args and ("user.name" in str(args) or "user.email" in str(args)):
+                    result.stdout = "Test User" if "user.name" in str(args) else "test@example.com"
+                else:
+                    result.stdout = ""
+                result.stderr = ""
+                return result
+
+            def mock_resolve_task_path(project_root_arg, rel_path):
+                return project_root / rel_path.lstrip("/")
+
+            mock_modules["_subprocess_util"].run = unittest.mock.MagicMock(side_effect=mock_subprocess_run)
+            mock_modules["_paths"].status_path = unittest.mock.MagicMock(
+                return_value=project_root / "_mill/status.md"
+            )
+            mock_modules["_paths"].resolve_task_path = unittest.mock.MagicMock(
+                side_effect=mock_resolve_task_path
+            )
+            mock_modules["_paths"].resolve_git_root = unittest.mock.MagicMock(return_value=project_root)
+            mock_modules["_paths"].resolve_wiki_path = unittest.mock.MagicMock(return_value=project_root)
+
+            with unittest.mock.patch.dict(sys.modules, mock_modules):
+                spec = importlib.util.spec_from_file_location(
+                    "millpy_fix_test7",
+                    HUB / "plugins/mill/scripts/millpy-fix.py",
+                )
+                millpy_fix = importlib.util.module_from_spec(spec)
+
+                mock_finalize = unittest.mock.MagicMock(return_value=0)
+
+                sys.modules["millpy_fix_test7"] = millpy_fix
+                with unittest.mock.patch.object(
+                    millpy_fix, "finalize_from_output", mock_finalize, create=True
+                ):
+                    spec.loader.exec_module(millpy_fix)
+                    millpy_fix.finalize_from_output = mock_finalize
+
+                    millpy_fix.main(
+                        [
+                            "--scope",
+                            "holistic",
+                            "--review-file",
+                            str(review_file),
+                            "--round",
+                            "1",
+                            "--stage",
+                            "finalize",
+                            "--agent-output",
+                            str(agent_output_file),
+                            "--session-id",
+                            "sid-xyz",
+                        ]
+                    )
+
+                    if mock_finalize.called:
+                        call_args = mock_finalize.call_args
+                        if call_args.kwargs.get("batch_verify_baseline") == ["sigA", "sigB", "sigShared"]:
+                            print(
+                                "PASS: --scope holistic forwards sorted union of contributing batches' baselines"
+                            )
+                        else:
+                            print(
+                                f"FAIL: holistic-scope baseline union - call_args={call_args}",
+                                file=sys.stderr,
+                            )
+                            errors += 1
+                    else:
+                        print("FAIL: finalize_from_output not called", file=sys.stderr)
+                        errors += 1
+        except Exception as exc:
+            print(f"FAIL: test 7 ({exc})", file=sys.stderr)
+            errors += 1
+
     if errors:
         print(f"\n{errors} test(s) FAILED", file=sys.stderr)
         return 1
diff --git a/plugins/mill/unit_tests/test-implementer-common.py b/plugins/mill/unit_tests/test-implementer-common.py
index 0bf16dc1..8d656306 100644
--- a/plugins/mill/unit_tests/test-implementer-common.py
+++ b/plugins/mill/unit_tests/test-implementer-common.py
@@ -5455,7 +5455,277 @@ def main() -> int:
             print(f"FAIL: case 77 ({exc}) captured={captured!r}", file=sys.stderr)
             errors += 1
 
-    # Case 78: commit_sha_field_name="pre_merge_head" -> the corrective SHA is attached under
+    # Case 78: #954 regression -- the explicit-JSON-success path, with the corroboration-waiver
+    # firing (a subset-diff mismatch that reproduces against a start_sha checkout), must not
+    # self-trip the in-scope dirty-tree gate on the very status.md write the waiver itself makes.
+    # git_name/git_email supplied -> batch 1's fix commits that write before the dirty-tree gate
+    # runs later in this same _forward_output call, so the batch reaches success cleanly.
+    with tempfile.TemporaryDirectory() as tmpdir:
+        project_root = Path(tmpdir)
+        _setup_fixture(project_root)
+        status_path = project_root / "_mill" / "status.md"
+        status_path.parent.mkdir(parents=True, exist_ok=True)
+        status_path.write_text(
+            _status.render_initial(
+                "Test Task",
+                "test",
+                "2026-01-01T00:00:00Z",
+                "main",
+                "test-slug",
+                "test-branch",
+            ),
+            encoding="utf-8",
+        )
+        _status.init_batches(status_path, ["01-test-batch"])
+        subprocess.run(
+            ["git", "-C", str(project_root), "add", "_mill/status.md"],
+            check=True,
+            capture_output=True,
+        )
+        subprocess.run(
+            ["git", "-C", str(project_root), "commit", "-m", "add status.md"],
+            check=True,
+            capture_output=True,
+        )
+        batch_start_sha = subprocess.run(
+            ["git", "-C", str(project_root), "rev-parse", "HEAD"],
+            check=True,
+            capture_output=True,
+            text=True,
+        ).stdout.strip()
+        # A genuine content commit for this batch, distinct from both start_sha and any
+        # batch-start housekeeping commit, so the no-content-commit gate lets the report
+        # through to the verify/dirty-tree gates this case actually exercises.
+        marker = project_root / "_mill" / "marker.txt"
+        marker.write_text("card-5 content commit", encoding="utf-8")
+        subprocess.run(
+            ["git", "-C", str(project_root), "add", "_mill/marker.txt"],
+            check=True,
+            capture_output=True,
+        )
+        subprocess.run(
+            ["git", "-C", str(project_root), "commit", "-m", "card-5 commit"],
+            check=True,
+            capture_output=True,
+        )
+        verify_cmd = "echo '--- FAIL: TestNew (0.00s)' && exit 1"
+        agent_output = json.dumps(
+            {"status": "success", "session_id": "case78", "cards_done": [5]}
+        )
+        captured = ""
+        try:
+            rc, captured = _capture_stdout(
+                lambda: _forward_output(
+                    agent_output,
+                    project_root,
+                    start_sha=batch_start_sha,
+                    verify_cmd=verify_cmd,
+                    session_id="case78",
+                    task_dir=project_root / "_mill",
+                    parent_branch="main",
+                    batch_verify_baseline=["--- FAIL: TestOld (1.11s)"],
+                    status_path=status_path,
+                    batch_name="01-test-batch",
+                    git_name="Test",
+                    git_email="test@test.com",
+                )
+            )
+            data = json.loads(captured.strip())
+            assert data["status"] == "success", (
+                f"case 78: expected success once the corroboration-waiver fires, got {data}"
+            )
+            print(
+                "PASS: case 78 - #954: explicit-JSON-success path with the corroboration-waiver"
+                " commits its status.md write before the dirty-tree gate, so the batch does not"
+                " self-trip"
+            )
+        except Exception as exc:
+            print(f"FAIL: case 78 ({exc}) captured={captured!r}", file=sys.stderr)
+            errors += 1
+
+    # Case 79: #954 regression -- same corroboration-waiver, driven through one of the three
+    # no-JSON-inference call sites in _forward_output (no parseable status JSON, snapshot_path
+    # omitted, forcing the inferred-success branch). This is the discriminating assertion for
+    # these call sites: none of them reach _in_scope_dirty_stuck, so "success not stuck" alone
+    # would not prove git_name/git_email were actually threaded through -- only the absence of
+    # an uncommitted status.md diff afterward proves the persist-commit actually ran here too.
+    with tempfile.TemporaryDirectory() as tmpdir:
+        project_root = Path(tmpdir)
+        _setup_fixture(project_root)
+        status_path = project_root / "_mill" / "status.md"
+        status_path.parent.mkdir(parents=True, exist_ok=True)
+        status_path.write_text(
+            _status.render_initial(
+                "Test Task",
+                "test",
+                "2026-01-01T00:00:00Z",
+                "main",
+                "test-slug",
+                "test-branch",
+            ),
+            encoding="utf-8",
+        )
+        _status.init_batches(status_path, ["01-test-batch"])
+        subprocess.run(
+            ["git", "-C", str(project_root), "add", "_mill/status.md"],
+            check=True,
+            capture_output=True,
+        )
+        subprocess.run(
+            ["git", "-C", str(project_root), "commit", "-m", "add status.md"],
+            check=True,
+            capture_output=True,
+        )
+        batch_start_sha = subprocess.run(
+            ["git", "-C", str(project_root), "rev-parse", "HEAD"],
+            check=True,
+            capture_output=True,
+            text=True,
+        ).stdout.strip()
+        marker = project_root / "_mill" / "marker.txt"
+        marker.write_text("card-5 content commit", encoding="utf-8")
+        subprocess.run(
+            ["git", "-C", str(project_root), "add", "_mill/marker.txt"],
+            check=True,
+            capture_output=True,
+        )
+        subprocess.run(
+            ["git", "-C", str(project_root), "commit", "-m", "card-5 commit"],
+            check=True,
+            capture_output=True,
+        )
+        verify_cmd = "echo '--- FAIL: TestNew (0.00s)' && exit 1"
+        captured = ""
+        try:
+            # snapshot_path omitted (defaults to None) -> the "elif start_sha is not None and
+            # snapshot_path is None" inference branch, with no parseable status JSON in output.
+            rc, captured = _capture_stdout(
+                lambda: _forward_output(
+                    "no structured status here, just log noise",
+                    project_root,
+                    start_sha=batch_start_sha,
+                    verify_cmd=verify_cmd,
+                    session_id="case79",
+                    batch_verify_baseline=["--- FAIL: TestOld (1.11s)"],
+                    status_path=status_path,
+                    batch_name="01-test-batch",
+                    git_name="Test",
+                    git_email="test@test.com",
+                )
+            )
+            data = json.loads(captured.strip())
+            assert data["status"] == "success", (
+                f"case 79: expected inferred success once corroborated, got {data}"
+            )
+            status_diff = _subprocess_util.run(
+                ["git", "status", "--porcelain", "_mill/status.md"],
+                cwd=project_root,
+            )
+            assert status_diff.stdout.strip() == "", (
+                "case 79: status.md must have no uncommitted diff after the corroboration"
+                f" persist-commit, got {status_diff.stdout!r}"
+            )
+            print(
+                "PASS: case 79 - #954: a no-JSON-inference call site also commits its"
+                " corroboration-waiver status.md write, leaving no uncommitted diff behind"
+            )
+        except Exception as exc:
+            print(f"FAIL: case 79 ({exc}) captured={captured!r}", file=sys.stderr)
+            errors += 1
+
+    # Case 80: git_name/git_email both omitted (None, the default) -- the corroboration-waiver
+    # itself must still succeed (the safe no-op degrades only the persist-commit, matching every
+    # other optional-parameter-absent behavior in this module), but no commit is attempted for
+    # the status.md write, which is left as an uncommitted diff.
+    with tempfile.TemporaryDirectory() as tmpdir:
+        project_root = Path(tmpdir)
+        _setup_fixture(project_root)
+        status_path = project_root / "_mill" / "status.md"
+        status_path.parent.mkdir(parents=True, exist_ok=True)
+        status_path.write_text(
+            _status.render_initial(
+                "Test Task",
+                "test",
+                "2026-01-01T00:00:00Z",
+                "main",
+                "test-slug",
+                "test-branch",
+            ),
+            encoding="utf-8",
+        )
+        _status.init_batches(status_path, ["01-test-batch"])
+        subprocess.run(
+            ["git", "-C", str(project_root), "add", "_mill/status.md"],
+            check=True,
+            capture_output=True,
+        )
+        subprocess.run(
+            ["git", "-C", str(project_root), "commit", "-m", "add status.md"],
+            check=True,
+            capture_output=True,
+        )
+        batch_start_sha = subprocess.run(
+            ["git", "-C", str(project_root), "rev-parse", "HEAD"],
+            check=True,
+            capture_output=True,
+            text=True,
+        ).stdout.strip()
+        marker = project_root / "_mill" / "marker.txt"
+        marker.write_text("card-5 content commit", encoding="utf-8")
+        subprocess.run(
+            ["git", "-C", str(project_root), "add", "_mill/marker.txt"],
+            check=True,
+            capture_output=True,
+        )
+        subprocess.run(
+            ["git", "-C", str(project_root), "commit", "-m", "card-5 commit"],
+            check=True,
+            capture_output=True,
+        )
+        verify_cmd = "echo '--- FAIL: TestNew (0.00s)' && exit 1"
+        agent_output = json.dumps(
+            {"status": "success", "session_id": "case80", "cards_done": [5]}
+        )
+        captured = ""
+        try:
+            # task_dir/parent_branch deliberately omitted here -- the dirty-tree gate this
+            # module's fix guards against is Card 1's own scope (covered by case 78 above);
+            # this case isolates whether the corroboration-waiver itself still fires safely
+            # when the persist-commit's identity parameters are absent.
+            rc, captured = _capture_stdout(
+                lambda: _forward_output(
+                    agent_output,
+                    project_root,
+                    start_sha=batch_start_sha,
+                    verify_cmd=verify_cmd,
+                    session_id="case80",
+                    batch_verify_baseline=["--- FAIL: TestOld (1.11s)"],
+                    status_path=status_path,
+                    batch_name="01-test-batch",
+                )
+            )
+            data = json.loads(captured.strip())
+            assert data["status"] == "success", (
+                f"case 80: expected success once corroborated, even with git identity absent,"
+                f" got {data}"
+            )
+            status_diff = _subprocess_util.run(
+                ["git", "status", "--porcelain", "_mill/status.md"],
+                cwd=project_root,
+            )
+            assert status_diff.stdout.strip() != "", (
+                "case 80: with git_name/git_email omitted, the status.md write must be a safe"
+                " no-op commit-wise -- left uncommitted, not silently attempted"
+            )
+            print(
+                "PASS: case 80 - git_name/git_email omitted: corroboration-waiver still"
+                " succeeds, but the persist-commit safely no-ops rather than raising"
+            )
+        except Exception as exc:
+            print(f"FAIL: case 80 ({exc}) captured={captured!r}", file=sys.stderr)
+            errors += 1
+
+    # Case 81: commit_sha_field_name="pre_merge_head" -> the corrective SHA is attached under
     # the override key, and the default "commit_sha" key must not appear at all (#953).
     with tempfile.TemporaryDirectory() as tmpdir:
         project_root = Path(tmpdir)
@@ -5496,14 +5766,14 @@ def main() -> int:
                 f"expected pre_merge_head={new_head}, got {data}"
             )
             print(
-                "PASS: case 78 - commit_sha_field_name override renames the fallback"
+                "PASS: case 81 - commit_sha_field_name override renames the fallback"
                 " SHA field and drops the stale self-reported commit_sha key"
             )
         except Exception as exc:
-            print(f"FAIL: case 78 ({exc}) captured={captured!r}", file=sys.stderr)
+            print(f"FAIL: case 81 ({exc}) captured={captured!r}", file=sys.stderr)
             errors += 1
 
-    # Case 79 (#932 regression): a truncated self-reported commit_sha (39 chars, one short of
+    # Case 82 (#932 regression): a truncated self-reported commit_sha (39 chars, one short of
     # the real 40-char SHA) on the default field-name path must be discarded and replaced by the
     # real git rev-parse HEAD value, not passed through.
     with tempfile.TemporaryDirectory() as tmpdir:
@@ -5542,11 +5812,11 @@ def main() -> int:
                 f"expected commit_sha={new_head} (full, not truncated), got {data}"
             )
             print(
-                "PASS: case 79 - #932 truncated self-reported commit_sha is discarded and"
+                "PASS: case 82 - #932 truncated self-reported commit_sha is discarded and"
                 " replaced by the real git rev-parse HEAD value"
             )
         except Exception as exc:
-            print(f"FAIL: case 79 ({exc}) captured={captured!r}", file=sys.stderr)
+            print(f"FAIL: case 82 ({exc}) captured={captured!r}", file=sys.stderr)
             errors += 1
 
     if errors:
diff --git a/plugins/mill/unit_tests/test-millpy-bg.py b/plugins/mill/unit_tests/test-millpy-bg.py
index 23ad7641..46c0c220 100644
--- a/plugins/mill/unit_tests/test-millpy-bg.py
+++ b/plugins/mill/unit_tests/test-millpy-bg.py
@@ -432,6 +432,94 @@ def main() -> int:
     except Exception as exc:
         failures.append(f"FAIL (p) worker-KeyboardInterrupt ({type(exc).__name__}): {exc}")
 
+    # (q) heartbeat line appears in log before the EXIT sentinel
+    try:
+        with tempfile.TemporaryDirectory() as tmpdir:
+            log_path = Path(tmpdir) / "test-heartbeat.log"
+            with unittest.mock.patch.object(_worker_mod, "_HEARTBEAT_INTERVAL_S", 0.05):
+                ret = _worker_main([
+                    "--log", str(log_path), "--",
+                    sys.executable, "-c", "import time; time.sleep(0.2)",
+                ])
+            assert ret == 0, f"expected 0, got {ret}"
+            log_text = log_path.read_text(encoding="utf-8")
+            heartbeat_pattern = re.compile(
+                r"^\[mill-bg\] HEARTBEAT \d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z\n?$",
+                re.MULTILINE,
+            )
+            heartbeat_lines = [
+                ln for ln in log_text.splitlines() if heartbeat_pattern.match(ln + "\n")
+            ]
+            assert len(heartbeat_lines) >= 1, (
+                f"no HEARTBEAT line found in log: {log_text!r}"
+            )
+            exit_index = log_text.index("[mill-bg] EXIT 0")
+            heartbeat_index = log_text.index(heartbeat_lines[0])
+            assert heartbeat_index < exit_index, (
+                "HEARTBEAT line did not appear before [mill-bg] EXIT 0"
+            )
+            stripped = log_text.rstrip()
+            assert stripped.endswith("[mill-bg] EXIT 0"), (
+                f"log does not end with '[mill-bg] EXIT 0'; last 60 chars: {stripped[-60:]!r}"
+            )
+        print("PASS (q): heartbeat line present before EXIT sentinel")
+    except AssertionError as exc:
+        failures.append(f"FAIL (q) heartbeat presence: {exc}")
+    except Exception as exc:
+        failures.append(f"FAIL (q) heartbeat presence ({type(exc).__name__}): {exc}")
+
+    # (r) heartbeat writes through the single already-open log handle, never a second handle
+    try:
+        with tempfile.TemporaryDirectory() as tmpdir:
+            log_path = Path(tmpdir) / "test-heartbeat-handle.log"
+            with unittest.mock.patch.object(_worker_mod, "_HEARTBEAT_INTERVAL_S", 0.05), \
+                 unittest.mock.patch("builtins.open", wraps=open) as mock_open:
+                ret = _worker_main([
+                    "--log", str(log_path), "--",
+                    sys.executable, "-c", "import time; time.sleep(0.2)",
+                ])
+            assert ret == 0, f"expected 0, got {ret}"
+            log_path_calls = [
+                call for call in mock_open.call_args_list
+                if call.args and str(call.args[0]) == str(log_path)
+            ]
+            assert len(log_path_calls) == 2, (
+                f"expected exactly 2 opens of log_path (\"w\" + \"a\"), got "
+                f"{len(log_path_calls)}: {log_path_calls}"
+            )
+        print("PASS (r): heartbeat writes through the single open log handle")
+    except AssertionError as exc:
+        failures.append(f"FAIL (r) single log handle: {exc}")
+    except Exception as exc:
+        failures.append(f"FAIL (r) single log handle ({type(exc).__name__}): {exc}")
+
+    # (s) heartbeat thread stop/join is clean -- no exception escapes to threading.excepthook
+    try:
+        import threading
+
+        with tempfile.TemporaryDirectory() as tmpdir:
+            log_path = Path(tmpdir) / "test-heartbeat-join.log"
+            escaped: list = []
+            prior_hook = threading.excepthook
+            threading.excepthook = lambda args: escaped.append(args)
+            try:
+                with unittest.mock.patch.object(_worker_mod, "_HEARTBEAT_INTERVAL_S", 0.05):
+                    ret = _worker_main([
+                        "--log", str(log_path), "--",
+                        sys.executable, "-c", "import time; time.sleep(0.2)",
+                    ])
+            finally:
+                threading.excepthook = prior_hook
+            assert ret == 0, f"expected 0, got {ret}"
+            assert escaped == [], (
+                f"heartbeat thread raised an uncaught exception: {escaped}"
+            )
+        print("PASS (s): heartbeat thread stop/join leaves no escaped exception")
+    except AssertionError as exc:
+        failures.append(f"FAIL (s) clean heartbeat join: {exc}")
+    except Exception as exc:
+        failures.append(f"FAIL (s) clean heartbeat join ({type(exc).__name__}): {exc}")
+
     if failures:
         for msg in failures:
             print(msg, file=sys.stderr)
diff --git a/plugins/mill/unit_tests/test-millpy-implement.py b/plugins/mill/unit_tests/test-millpy-implement.py
index 3c34cc2e..08dde3b6 100644
--- a/plugins/mill/unit_tests/test-millpy-implement.py
+++ b/plugins/mill/unit_tests/test-millpy-implement.py
@@ -776,6 +776,12 @@ class TestMillpyImplement(unittest.TestCase):
         # Finalize must use status.md values, not the CLI --round/--session-id/--start-sha args.
         self.assertEqual(call_kwargs.get("start_sha"), "STATUS_SHA")
         self.assertEqual(call_kwargs.get("session_id"), "STATUS_SESSION")
+        # main()'s already-resolved git_name/git_email locals (from `git config --global --get
+        # user.name`/`user.email`, mocked via mock_subprocess_run's default "abc1234" stdout)
+        # must be forwarded into finalize_from_output -- this is the #954 corroboration-commit
+        # git-identity fix; a future edit that silently drops these kwargs must fail this test.
+        self.assertEqual(call_kwargs.get("git_name"), "abc1234")
+        self.assertEqual(call_kwargs.get("git_email"), "abc1234")
 
     def test_prepare_retry_dirty_staged_commits(self):
         """Re-fire with non-empty staged diff (regenerated session): git_commit IS called.
@@ -2179,6 +2185,143 @@ SESSION_ID equals retained session.
         self.assertEqual(batch_entry["start_sha"], original_start_sha)
         self.assertEqual(batch_entry["implementer_session"], original_session)
 
+    def _write_running_batch_status(self, *, timeline_last_row, batch_extra_yaml=""):
+        """Write a status.md fixture with a "running" test-batch and a custom Timeline tail row.
+
+        Mirrors ``_make_fixture``'s status.md shape but lets each self-resolve test control the
+        most recent timeline row (an ordinary phase vs. a self-resolve marker) and any extra
+        per-batch yaml (e.g. a pre-existing ``self_resolve_remint_at``).
+        """
+        status_path = self.tmp_path / "task" / "status.md"
+        status_path.write_text(
+            "```yaml\n"
+            "phase: implementing\n"
+            "slug: test-slug\n"
+            "task: Test Task\n"
+            "branch: test-branch\n"
+            "parent: main\n"
+            "```\n\n"
+            "## Timeline\n\n"
+            "```text\n"
+            "implementing  2026-01-01T00:00:00Z\n"
+            f"{timeline_last_row}\n"
+            "```\n\n"
+            "## Batches\n\n"
+            "```yaml\n"
+            "batches:\n"
+            "  - name: test-batch\n"
+            "    state: running\n"
+            "    start_sha: reuse_start_sha_123\n"
+            "    implementer_session: reuse-session-uuid-456\n"
+            f"{batch_extra_yaml}"
+            "```\n",
+            encoding="utf-8",
+        )
+        return status_path
+
+    def test_prepare_mints_fresh_session_after_unreacted_self_resolve(self):
+        """Card 10 (#956): a prepare re-fire after an unreacted self-resolve marker mints fresh
+        session_id/start_sha instead of reusing the stale ones from the original stuck attempt,
+        and records self_resolve_remint_at with the self-resolve row's own timestamp.
+        """
+        status_path = self._write_running_batch_status(
+            timeline_last_row="self-resolved-verify-logic  '2026-06-01T09:00:00Z'",
+        )
+
+        with unittest.mock.patch.object(millpy_implement._render, "render", return_value="Brief text"):
+            rc, out = self._run_main(["test-batch", "--stage", "prepare"])
+
+        self.assertEqual(rc, 0)
+        data = json.loads(out.strip())
+        self.assertNotEqual(data["session_id"], "reuse-session-uuid-456")
+        self.assertNotEqual(data["start_sha"], "reuse_start_sha_123")
+
+        batches = millpy_implement._status.read_batches(status_path)
+        batch_entry = next(b for b in batches if b["name"] == "test-batch")
+        self.assertEqual(batch_entry["self_resolve_remint_at"], "2026-06-01T09:00:00Z")
+
+    def test_prepare_reuses_session_when_last_timeline_row_is_not_self_resolve(self):
+        """Regression guard for #625/#635/#643: an ordinary (non-self-resolve) most-recent timeline
+        row must still reuse the recorded session_id/start_sha, exactly as before Card 10's change.
+        """
+        self._write_running_batch_status(
+            timeline_last_row="coding  '2026-03-01T00:00:00Z'",
+        )
+
+        with unittest.mock.patch.object(millpy_implement._render, "render", return_value="Brief text"):
+            with unittest.mock.patch.object(millpy_implement._subprocess_util, "git_commit") as mock_git_commit:
+                rc, out = self._run_main(["test-batch", "--stage", "prepare"])
+
+        self.assertEqual(rc, 0)
+        data = json.loads(out.strip())
+        self.assertEqual(data["session_id"], "reuse-session-uuid-456")
+        self.assertEqual(data["start_sha"], "reuse_start_sha_123")
+        mock_git_commit.assert_not_called()
+
+    def test_prepare_second_call_after_remint_reuses_bounded_to_one_remint(self):
+        """Compounding-retry regression: a second prepare re-fire against the just-fresh-minted
+        session (simulating a transient-retry re-dispatch of that fresh session) must reuse the
+        fresh mint's own session_id/start_sha rather than minting a third distinct pair -- proving
+        the self-resolve marker's remint effect is bounded to exactly one fresh mint.
+        """
+        self._write_running_batch_status(
+            timeline_last_row="self-resolved-verify-logic  '2026-06-01T09:00:00Z'",
+        )
+
+        # Two distinct UUIDs so a buggy second re-mint would be visibly distinguishable from a
+        # correct reuse of the first fresh mint's session_id.
+        self.mock_uuid4.side_effect = [
+            uuid.UUID("00000000-0000-0000-0000-0000000000a1"),
+            uuid.UUID("00000000-0000-0000-0000-0000000000a2"),
+        ]
+        # Two distinct rev-parse HEAD results so a buggy second re-mint would also be visibly
+        # distinguishable from a correct reuse of the first fresh mint's start_sha -- the reuse
+        # path never calls rev-parse HEAD at all, so a correct second call sees no new value.
+        rev_parse_calls = []
+
+        def routing_fn(argv, **kw):
+            if argv[1] == "rev-parse":
+                rev_parse_calls.append(1)
+                sha = f"{'0' * 39}{len(rev_parse_calls)}"
+                return subprocess.CompletedProcess(args=argv, returncode=0, stdout=sha + "\n", stderr="")
+            if argv[1] == "diff":
+                return subprocess.CompletedProcess(args=argv, returncode=1, stdout="", stderr="")
+            return subprocess.CompletedProcess(args=argv, returncode=0, stdout="abc1234\n", stderr="")
+
+        self.mock_subprocess_run.side_effect = routing_fn
+
+        with unittest.mock.patch.object(millpy_implement._render, "render", return_value="Brief text"):
+            rc1, out1 = self._run_main(["test-batch", "--stage", "prepare"])
+            rc2, out2 = self._run_main(["test-batch", "--stage", "prepare"])
+
+        self.assertEqual(rc1, 0)
+        self.assertEqual(rc2, 0)
+        data1 = json.loads(out1.strip())
+        data2 = json.loads(out2.strip())
+        self.assertEqual(data2["session_id"], data1["session_id"])
+        self.assertEqual(data2["start_sha"], data1["start_sha"])
+        # Exactly one rev-parse HEAD call happened -- the first (fresh-mint) call. The second call
+        # took the reuse path and never captured a new HEAD.
+        self.assertEqual(len(rev_parse_calls), 1)
+
+    def test_prepare_fresh_mint_after_self_resolve_does_not_touch_phase_field(self):
+        """Phase-field isolation: the fresh-mint branch's set_batch_fields call must never touch
+        status.md's top-level phase: value -- that field is reserved for
+        mill-go-base/SKILL.md's phase-gate crash-recovery table, distinct from this batch-scoped
+        self_resolve_remint_at marker.
+        """
+        status_path = self._write_running_batch_status(
+            timeline_last_row="self-resolved-verify-logic  '2026-06-01T09:00:00Z'",
+        )
+        phase_before = millpy_implement._status.read_full(status_path)["yaml"]["phase"]
+
+        with unittest.mock.patch.object(millpy_implement._render, "render", return_value="Brief text"):
+            rc, _out = self._run_main(["test-batch", "--stage", "prepare"])
+
+        self.assertEqual(rc, 0)
+        phase_after = millpy_implement._status.read_full(status_path)["yaml"]["phase"]
+        self.assertEqual(phase_after, phase_before)
+
     def test_prepare_stage_push_failure_nonfatal_but_commit_failure_still_fatal(self):
         """Card 3 (#626): a failed git push is non-fatal (warning + envelope still emitted);
     a failed git commit remains fatal (return 1, no envelope).
diff --git a/plugins/mill/unit_tests/test-orch-review-scratch-path.py b/plugins/mill/unit_tests/test-orch-review-scratch-path.py
new file mode 100644
index 00000000..8d13cb07
--- /dev/null
+++ b/plugins/mill/unit_tests/test-orch-review-scratch-path.py
@@ -0,0 +1,90 @@
+"""Unit tests for the orch-review .scratch/ path migration regression lock.
+
+Batch: review-hygiene-fixes
+
+Card 3: Regression-lock the .scratch/ hand-off path
+SKILLs: - orch-review: writes the --orch hand-off file to .scratch/orch-review.md
+- orch-wait: reads the --orch hand-off file from .scratch/orch-review.md
+"""
+from __future__ import annotations
+
+import sys
+from pathlib import Path
+
+HUB = Path(__file__).resolve().parent.parent.parent.parent
+SKILLS = HUB / "plugins" / "mill" / "skills"
+
+
+def test_scratch_path_migration() -> list[str]:
+    """
+    Assert orch-review/SKILL.md and orch-wait/SKILL.md both reference the
+    .scratch/orch-review.md hand-off path and no longer reference the
+    stale _mill/orch-review.md path.
+
+    Returns list of failure messages (empty list = all passed).
+    """
+    failures: list[str] = []
+    paths = [
+        SKILLS / "orch-review" / "SKILL.md",
+        SKILLS / "orch-wait" / "SKILL.md",
+    ]
+
+    for path in paths:
+        try:
+            text = path.read_text(encoding="utf-8")
+        except (UnicodeDecodeError, OSError) as e:
+            failures.append(f"FAIL: could not read {path}: {e}")
+            continue
+
+        if text.count(".scratch/orch-review.md") < 1:
+            failures.append(
+                f"FAIL: {path}: expected '.scratch/orch-review.md' to appear "
+                f"at least once, found 0 occurrences"
+            )
+
+        stale_count = text.count("_mill/orch-review.md")
+        if stale_count != 0:
+            failures.append(
+                f"FAIL: {path}: found {stale_count} occurrence(s) of stale "
+                f"'_mill/orch-review.md', expected 0"
+            )
+
+    return failures
+
+
+def main() -> int:
+    """
+    Run the scratch-path migration regression lock.
+
+    Returns 0 on all passes, 1 on any failure.
+    """
+    try:
+        print("--- Card 3: orch-review .scratch/ path regression lock ---")
+
+        print("Testing orch-review/orch-wait .scratch/orch-review.md path...")
+        failures = test_scratch_path_migration()
+        if failures:
+            for msg in failures:
+                print(msg, file=sys.stderr)
+            print(
+                f"FAIL: {len(failures)} scratch-path migration check(s) failed",
+                file=sys.stderr,
+            )
+            return 1
+        print(
+            "PASS: orch-review/SKILL.md and orch-wait/SKILL.md reference "
+            ".scratch/orch-review.md with no stale _mill/orch-review.md references"
+        )
+
+        print("All test-orch-review-scratch-path checks passed.")
+        return 0
+
+    except Exception as e:
+        print(f"FAIL: unexpected error: {e}", file=sys.stderr)
+        import traceback
+        traceback.print_exc(file=sys.stderr)
+        return 1
+
+
+if __name__ == "__main__":
+    sys.exit(main())
diff --git a/plugins/mill/unit_tests/test-status.py b/plugins/mill/unit_tests/test-status.py
index 661eb7d3..1dcbdd92 100644
--- a/plugins/mill/unit_tests/test-status.py
+++ b/plugins/mill/unit_tests/test-status.py
@@ -696,6 +696,18 @@ def main() -> int:
             assert entry["start_sha"] == "abc", f"start_sha mismatch: {entry['start_sha']!r}"
         print("PASS: set_batch_fields writes multiple fields atomically")
 
+        # self_resolve_remint_at round-trips through set_batch_fields
+        with tempfile.TemporaryDirectory() as tmp:
+            sp = Path(tmp) / "status.md"
+            sp.write_text(_out_sbf, encoding="utf-8")
+            init_batches(sp, ["foundation"])
+            set_batch_fields(sp, "foundation", {"self_resolve_remint_at": "2026-09-04T10:49:08Z"})
+            entry = next(b for b in read_batches(sp) if b["name"] == "foundation")
+            assert entry["self_resolve_remint_at"] == "2026-09-04T10:49:08Z", (
+                f"self_resolve_remint_at mismatch: {entry['self_resolve_remint_at']!r}"
+            )
+        print("PASS: set_batch_fields writes and round-trips self_resolve_remint_at")
+
         # Unknown key raises ValueError
         with tempfile.TemporaryDirectory() as tmp:
             sp = Path(tmp) / "status.md"

```

## Instructions

1. Read the failing tests and the source files they exercise.
2. Fix the root cause of the failures.
   Do not modify tests unless they are genuinely wrong due to the merge (e.g. a test asserted against a value that the merge legitimately changed).
3. Re-run `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-plan-flow.py` after each fix attempt using `git -C /home/knatte/Code/millhouse/wts/review-manifest-listings-full-path-clutter` for git commands.
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
Use `git -C /home/knatte/Code/millhouse/wts/review-manifest-listings-full-path-clutter` for git commands;
do not `cd`.
Worktree cwd is `/home/knatte/Code/millhouse/wts/review-manifest-listings-full-path-clutter`.
