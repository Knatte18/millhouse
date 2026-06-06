Review: subprocess-to-agents

  verdict: GAPS_FOUND
reviewer_model: sonnetmax_tool
reviewed_file:_mill/discussion.md
  date: 2026-06-06

  Findings

  [GAP] via_psmux migration policy is unresolved

  Section: Testing (_config dispatch enum bullet)
  Issue: "the old via_psmux key is handled per the chosen migration (rejected or mapped)" lists two options without choosing one; the plan writer cannot implement _config validation without this
  decision.
  Fix: Decide explicitly: (a) treat via_psmux as an unknown key (existing warn_unknown_keys path, silent continue) with a deprecation note in the template, or (b) raise ConfigError if via_psmux: true
  appears without dispatch: psmux. Reject-vs-map affects every existing hub config that currently has via_psmux: true.

  [NOTE] Brief <identifier> naming scheme left open

  Section: brief-file-lifecycle Decision
  Issue: _mill/briefs/<role>-<identifier>.md gives no definition of <identifier>; implementer (batch name) and reviewer (round number?) conventions could diverge across CLIs.
  Fix: Name the pattern — e.g., <role>-<batch_name>.md for the implementer and <role>-round<N>.md for reviewers — so all six dispatch sites use a consistent scheme.

  [NOTE] Agent-mode timeout fate not stated

  Section: model-and-effort Decision
  Issue: Effort is explicitly dropped in agent mode; timeout (implementer_timeout, holistic_timeout, tool_use_timeout) is not mentioned. The Agent tool has no timeout parameter.
  Fix: Add one sentence: configured timeout values are not forwarded in agent mode (no equivalent parameter); they remain in config but are ignored for this dispatch path.

  [NOTE] Git worktree commit context deferred without guidance

  Section: Technical context (Gotchas)
  Issue: "the plan should confirm the implementer sub-agent commits to the correct worktree/branch" is raised but not guided; the concern is real because the Agent tool sub-agent inherits orchestrator
  cwd rather than receiving an explicit cwd= like _llm_claude.run_implementer().
  Fix: State the expected mechanism — e.g., the brief includes PROJECT_ROOT (already in the template render dict in millpy-implement.py:167) and instructs the sub-agent to run git commands via -C
  <PROJECT_ROOT> — so the plan writer knows what invariant to preserve.

  Verdict

  GAPS_FOUND
  One undecided item (via_psmux migration policy) blocks plan writing; three NOTEs flag details the plan should pin.