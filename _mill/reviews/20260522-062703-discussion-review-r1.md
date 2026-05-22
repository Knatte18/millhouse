Review: Set MILL_PYTHON via mill-setup, use in all skill invocations

verdict: APPROVE
reviewer_model:sonnetmax_tool
  reviewed_file: _mill/discussion.md
  date: 2026-05-22

  Findings

  [NOTE] mill-setup intro text "Step 0 alias" claim is stale and will remain wrong

  Section: Technical context → Phase 4.8 logic / mill-setup SKILL.md "How to invoke helpers"
  Issue: mill-setup/SKILL.md line 69 currently reads "mill-go uses an equivalent form with $MILL_PYTHON, an alias defined in its Step 0 block" — but mill-go has 33 full-path occurrences and zero uses
  of MILL_PYTHON today; after the task it will use $MILL_PYTHON as a CC env var, not a Step 0 alias. The scope says only "add Phase 4.8 and update Phase 8 verification," so a plan writer could miss
  this.
  Fix: Add an explicit bullet to the mill-setup scope item: also update the "How to invoke helpers" parenthetical to remove "an alias defined in its Step 0 block" and replace it with "a CC env var
  written by mill-setup."

  Verdict

  APPROVE
  All counts and file lists verified; decisions well-reasoned; one stale parenthetical worth cleaning.