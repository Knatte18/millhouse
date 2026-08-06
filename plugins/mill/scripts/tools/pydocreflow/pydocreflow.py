#!/usr/bin/env python3
"""
Reflow Python docstrings and multi-line `#`-comment blocks to semantic line breaks (one sentence per
line, plus a break at an internal independent-clause boundary), per the python-comments skill's
"Line-wrap style" section (plugins/python/skills/python-comments/SKILL.md).

Pure mechanical transform: only re-breaks existing text onto different lines, never adds, drops, or
changes a word.
Uses `ast` to locate docstrings precisely (so a `#` inside a string literal can't be mistaken for a
comment) and `tokenize` to locate standalone comment lines (so a comment can't be mistaken for
code).

Left untouched: single-line docstrings/comments, doctest blocks (`>>>`), function-signature-shaped
or assignment-shaped lines (literal code/output quoted inside a docstring), and any
docstring/comment block whose lines sit at more than one indentation level where the shallower line
is itself code-shaped.

Usage:
    python pydocreflow.py [--check] [--max-width N] <file_or_dir> [<file_or_dir> ...]

    --check Print unified diffs instead of writing files (dry run).

    --max-width N Max column width (indentation + `#`/docstring prefix included) before a resulting
    line, after semantic/clause splitting, falls back to a word-boundary wrap as a last resort.
    Only applies when the line has no remaining comma+conjunction or semicolon boundary left to
    split on.
    Default: 100.

Last run: 2026-08-06, longline fallback-wrap repo-wide sweep (pydocreflow-longline-fallback-wrap
task).
"""

import ast
import difflib
import io
import re
import sys
import tokenize
from pathlib import Path

# ---------------------------------------------------------------------------
# Sentence / clause splitting
# ---------------------------------------------------------------------------

_ABBREVIATIONS = {
    "e.g", "i.e", "etc", "vs", "cf", "approx", "no", "fig", "eq", "pp",
    "dr", "mr", "mrs", "ms", "st", "inc", "ltd", "u.s", "u.k", "vol", "ch",
}

_SENTENCE_END_RE = re.compile(r'([.!?])(["\')\]]*)(\s+)(?=[A-Za-z0-9])')
_CLAUSE_RE = re.compile(r',\s+(and|but|or|nor)\s+')
_SEMICOLON_RE = re.compile(r';\s+')

_CODE_SIGNATURE_RE = re.compile(r'^[\w\.\[\]]+\(.*\)(\s*->\s*.*)?:?$')
_CODE_ASSIGNMENT_RE = re.compile(r'^[\w\.\[\]]+\s*=\s*\S')
_HEADER_LINE_RE = re.compile(r'^[\w][\w \(\),/:\-]*:$')
# Python keywords that double as common English words (for, with, if, from, return, ...)
# can't be trusted as bare startswith() prefixes -- "for consistent logging" is prose, not a for-loop.
# Block keywords (if/for/...)
# are only code-shaped when the line is a real compound statement ending in ':'.
# Simple keywords (return/import/...)
# are only code-shaped on a short, unpunctuated line -- a real prose sentence fragment is longer.
_CODE_BLOCK_STARTER_RE = re.compile(r'^(?:def|class|if|elif|else|for|while|with|try|except)\b')
_CODE_SIMPLE_STARTER_RE = re.compile(r'^(?:return|import|from|raise|yield|pass)\b')


def _looks_like_code_starter(line):
    if line.startswith("@"):
        return True
    if _CODE_BLOCK_STARTER_RE.match(line):
        return line.rstrip().endswith(":")
    if _CODE_SIMPLE_STARTER_RE.match(line):
        if line.rstrip().endswith((".", "!", "?", ",")):
            return False
        return len(line.split()) <= 6
    return False


def _in_backtick_span(text, pos):
    """True if `pos` falls inside a single- or double-backtick code span."""
    before = text[:pos]
    # Double-backtick spans first (Sphinx ``code``), then single.
    for marker in ("``", "`"):
        if before.count(marker) % 2 == 1:
            return True
    return False


def _in_paren_span(text, pos):
    """True if `pos` falls inside an unclosed '(' ... ')' span."""
    depth = 0
    for ch in text[:pos]:
        if ch == "(":
            depth += 1
        elif ch == ")" and depth > 0:
            depth -= 1
    return depth > 0


def _preceding_word(text, pos):
    m = re.search(r'([A-Za-z]+)$', text[:pos])
    return m.group(1) if m else ""


def _looks_like_url(text, pos):
    start = max(text.rfind(" ", 0, pos), text.rfind("\n", 0, pos)) + 1
    token = text[start:pos]
    return "://" in token or token.startswith("www.")


_LIST_MARKER_RE = re.compile(r'(?:^|[\s(])(\d{1,3})$')


def _looks_like_list_marker(text, pos):
    """True if the period at `pos` closes a numbered-list marker like "1."
at the start of an item, not a decimal/sentence-ending period.
"""
    return bool(_LIST_MARKER_RE.search(text[:pos]))


def split_sentences(text):
    """Split a prose string into a list of sentences (no trailing whitespace)."""
    sentences = []
    last = 0
    for m in _SENTENCE_END_RE.finditer(text):
        pos = m.start(1)
        word = _preceding_word(text, pos)
        if word.lower() in _ABBREVIATIONS:
            continue
        if _looks_like_url(text, pos):
            continue
        if _in_backtick_span(text, pos):
            continue
        if _looks_like_list_marker(text, pos):
            continue
        end = m.end(1) + len(m.group(2))
        sentences.append(text[last:end].strip())
        last = m.end()
    tail = text[last:].strip()
    if tail:
        sentences.append(tail)
    return sentences or ([text.strip()] if text.strip() else [])


def split_clauses(sentence):
    """Split one sentence at semicolons and at independent-clause commas."""
    pieces = []
    for chunk in _semicolon_split(sentence):
        pieces.extend(_conjunction_split(chunk))
    return [p.strip() for p in pieces if p.strip()]


_BARE_PARTICIPLE_RE = re.compile(r"^[A-Za-z]+(?:ed|ing)\b")


def _semicolon_split(text):
    parts = []
    last = 0
    for m in _SEMICOLON_RE.finditer(text):
        if _in_backtick_span(text, m.start()) or _in_paren_span(text, m.start()):
            continue
        tail = text[m.end():].lstrip()
        # A tail opening with a bare past-participle/gerund ("serialised to X", "used by Y") is a continuation phrase describing the previous clause's subject, not a new independent clause of its own.
        if _BARE_PARTICIPLE_RE.match(tail):
            continue
        parts.append(text[last:m.start() + 1])
        last = m.end()
    parts.append(text[last:])
    return parts


_CLAUSE_TAIL_RE = re.compile(r'^[^.,;]*')


def _has_subject_and_verb(clause_tail):
    """Cheap proxy for "has its own subject and verb": an independent clause needs at least two real
    words.
    A bare one-word tail ("or ``None``.")
    is a compound object/alternative, not a new clause.
    """
    words = re.findall(r"[A-Za-z0-9_']+", clause_tail)
    return len(words) >= 2


def _conjunction_split(text):
    """Split at ", and/but/or/nor " when it looks like an independent-clause join rather than a list
    item or compound predicate.

    Heuristic: only the FIRST comma in the sentence is eligible -- a comma that already has an
    earlier sibling comma in the same sentence signals an enumerated list (Oxford comma), not a
    two-clause join -- and the clause after the conjunction must itself contain at least two words
    (a proxy for "has its own subject and verb").
    """
    parts = []
    last = 0
    search_from = 0
    while True:
        m = _CLAUSE_RE.search(text, search_from)
        if not m:
            break
        comma_pos = m.start()
        if _in_backtick_span(text, comma_pos) or _in_paren_span(text, comma_pos):
            search_from = m.end()
            continue
        # Is there another comma earlier in this sentence (before this one)?
        # If so, this looks like an Oxford-comma list item, not a clause join.
        if text.find(",", last, comma_pos) != -1:
            search_from = m.end()
            continue
        tail = _CLAUSE_TAIL_RE.match(text[m.end():]).group(0)
        if not _has_subject_and_verb(tail):
            search_from = m.end()
            continue
        parts.append(text[last:comma_pos + 1])
        last = m.start(1)  # keep "and"/"but"/"or"/"nor" with the new clause
        search_from = m.end(1)
    parts.append(text[last:])
    return parts


def reflow_text(text):
    """Collapse existing hard-wraps in `text` and re-split into semantic lines (list of strings, no
    indentation, no trailing whitespace).
    """
    joined = " ".join(text.split())
    lines = []
    for sentence in split_sentences(joined):
        lines.extend(split_clauses(sentence))
    return lines


def _should_collapse_boundary(line_a, line_b):
    """True if `line_b` looks like a hard-wrap continuation of `line_a` (safe to join with a single
    space).

    Narrow, deliberately conservative check: a line ending in a closing paren immediately followed
    by a capitalized word is a strong signal of two separate remarks (a parenthetical aside just
    closed, and a new capitalized word starts) that merely lack terminal punctuation -- joining them
    with a plain space would fuse two thoughts into one unreadable run-on with no separator.
    Everything else collapses, since this codebase capitalizes plenty of mid-sentence field names
    (``Edits:``, ``Moves:``, ...)
    that are NOT new-sentence signals.
    """
    a = line_a.rstrip()
    b = line_b.lstrip()
    if not a or not b:
        return True
    if a[-1] == ")" and b[0].isupper():
        return False
    return True


def reflow_lines(lines):
    """Reflow a list of raw (stripped) text lines belonging to one item, preserving any existing
    boundary that does not look like a hard-wrap continuation (see `_should_collapse_boundary`).
    """
    groups = []
    current = []
    prev = None
    for line in lines:
        if prev is not None and not _should_collapse_boundary(prev, line):
            groups.append(current)
            current = []
        current.append(line)
        prev = line
    if current:
        groups.append(current)

    out = []
    for group in groups:
        out.extend(reflow_text(" ".join(group)))
    return out


# ---------------------------------------------------------------------------
# Last-resort word-boundary wrap fallback
# ---------------------------------------------------------------------------

_DEFAULT_MAX_WIDTH = 100
_max_width = _DEFAULT_MAX_WIDTH
_fallback_wrap_count = 0

_INDENT_PREFIX_RE = re.compile(r'^(\s*)')
_COMMENT_PREFIX_RE = re.compile(r'^(\s*#[ ]?)')


def _has_usable_clause_boundary(text):
    """True if `text` still has a comma+conjunction or semicolon boundary the splitter could act on.

    Delegates to `split_clauses` itself rather than re-matching `_CLAUSE_RE`/`_SEMICOLON_RE` by
    hand, so this check stays exactly consistent with what the real splitter already tried --
    Oxford-comma list items, bare-participle tails, and backtick/paren spans are all excluded the
    same way a plain regex re-scan would wrongly flag as "boundary present".
    """
    return len(split_clauses(text)) > 1


_DOCTEST_MARKER_RE = re.compile(r'^(?:>>>|\.\.\.)')


def _apply_fallback_wrap(line, cont_indent_extra=0, is_comment=False):
    """Last-resort fallback for one already fully-prefixed physical line: if it still exceeds
    `_max_width` and has no remaining clause boundary to split on, wrap it at the nearest word
    boundary at or before that column, repeating the line's leading indentation/`#`-prefix on
    every continuation (plus `cont_indent_extra` extra columns of hang).

    `is_comment` picks which prefix regex applies: comment physical lines are always built as indent
    + literal `#`, so matching it is unambiguous;
    a docstring line's own prose can start with a literal `#` too (e.g.
    a `#582` issue reference), so treating that as a marker to repeat would inject a spurious,
    ever-growing `#` on every re-pass -- docstring lines match indentation only, never `#`.

    `cont_indent_extra` matters for idempotency on docstring body lines: `group_items` treats any
    line at or above a section's base indent as the start of a *new* item, so a wrapped continuation
    reusing its origin line's exact indent can be misread as a new item on the next pass.
    Bumping it deeper (matching the codebase's own continuation-indent convention) avoids that;
    comment blocks pass 0 since their grouping is column-exact-match based, not indent-threshold
    based, so no ambiguity exists there.

    A continuation is also never allowed to start on a word matching `_DOCTEST_MARKER_RE`
    (`>>>`/`...`) -- prose that happens to contain a literal ellipsis or repl-prompt-shaped token
    could otherwise land at column 0 of a wrapped line and get misread as a doctest block by
    `_is_code_like` on the next pass, freezing that item out of reflow entirely.

    Only that one outlier line is affected -- a line that already fits,
    or still has a clause boundary left, is returned unchanged.
    """
    global _fallback_wrap_count
    if len(line) <= _max_width:
        return [line]
    prefix_re = _COMMENT_PREFIX_RE if is_comment else _INDENT_PREFIX_RE
    lead_prefix = prefix_re.match(line).group(1)
    text = line[len(lead_prefix):]
    if _has_usable_clause_boundary(text):
        return [line]
    cont_prefix = lead_prefix + (" " * cont_indent_extra)

    out_lines = []
    line_prefix = lead_prefix
    current = line_prefix
    at_line_start = True
    for word in text.split(" "):
        if not word:
            continue
        if at_line_start:
            current = line_prefix + word
        else:
            candidate = current + " " + word
            overflows = len(candidate) > _max_width
            if overflows and not _DOCTEST_MARKER_RE.match(word):
                out_lines.append(current)
                line_prefix = cont_prefix
                current = line_prefix + word
            else:
                current = candidate
        at_line_start = False
    out_lines.append(current)
    _fallback_wrap_count += 1
    return out_lines


def _wrap_docstring_lead(prefix_width, cont_prefix, text):
    """Fallback-wrap a docstring's lead line: `text` sits glued directly onto the source line that
    already carries the opening triple-quote (plus any enclosing indentation), so its true
    rendered column width is `prefix_width + len(text)` even though `prefix_width` is never part
    of `text` itself.

    Returns `[text]` unchanged if it fits,
    or still has a clause boundary.
    Otherwise returns the wrapped lines: the first with no literal prefix (the caller glues it back
    onto the existing `\"\"\"`), later ones prefixed with `cont_prefix` (the docstring's normal
    continuation indentation).
    """
    wrapped = _apply_fallback_wrap((" " * prefix_width) + text)
    if len(wrapped) == 1:
        return [text]
    out = [wrapped[0][prefix_width:]]
    out.extend(cont_prefix + line[prefix_width:] for line in wrapped[1:])
    return out


# ---------------------------------------------------------------------------
# Skip-detection
# ---------------------------------------------------------------------------

def _is_code_like(joined_lines):
    """True if this item's lines look like quoted code/output, not prose."""
    if not joined_lines:
        return False
    first = joined_lines[0].strip()
    if _CODE_SIGNATURE_RE.match(first) or _CODE_ASSIGNMENT_RE.match(first):
        return True
    for line in joined_lines:
        stripped = line.strip()
        if stripped.startswith(">>>") or stripped.startswith("..."):
            return True
        if _looks_like_code_starter(stripped):
            return True
    return False


def _is_header_line(line, next_lines_deeper_indent):
    stripped = line.strip()
    return bool(_HEADER_LINE_RE.match(stripped)) and next_lines_deeper_indent


# ---------------------------------------------------------------------------
# Indentation-based item grouping
# ---------------------------------------------------------------------------

def _leading_ws(line):
    return len(line) - len(line.lstrip(" "))


_ITEM_MARKER_RE = re.compile(r'^\S.{0,60}?—\s')
_ITEM_LEADER_RE = re.compile(r'^(?:\(\d{1,3}\)|\d{1,3}[.)])\s|^[-*]\s')


def _is_item_start_line(text):
    return bool(_ITEM_MARKER_RE.match(text) or _ITEM_LEADER_RE.match(text))


def _regroup_by_marker(indexed_lines):
    """Same-indent lines can still be a list of items with no indentation cue at all, e.g. "0 —
    description" / "1 — description" or "(1) ..." / "(2) ..."
    lines.
    Two or more lines matching an item-marker pattern signal that shape;
    split there instead of treating the whole run as one flat paragraph.
    """
    marker_count = sum(1 for _, t in indexed_lines if _is_item_start_line(t))
    if marker_count < 2:
        return [list(indexed_lines)]
    items = []
    current = None
    for indent, text in indexed_lines:
        if current is None or _is_item_start_line(text):
            current = [(indent, text)]
            items.append(current)
        else:
            current.append((indent, text))
    return items


def group_items(indexed_lines):
    """Group (indent, text) lines into items: a line at the block's minimum indent starts a new
    item;
    deeper-indented lines continue the previous item.
    All-same-indent input collapses to a single item (a plain wrapped paragraph) unless
        `_regroup_by_marker` detects a same-indent item list.
    """
    if not indexed_lines:
        return []
    indents = sorted({i for i, _ in indexed_lines})
    if len(indents) <= 1:
        return _regroup_by_marker(indexed_lines)
    base = indents[0]
    items = []
    current = None
    for indent, text in indexed_lines:
        if indent <= base or current is None:
            current = [(indent, text)]
            items.append(current)
        else:
            current.append((indent, text))
    return items


def split_into_sections(body_lines):
    """Split docstring body lines (already stripped of leading/trailing blank framing lines) into
    sections separated by blank lines.
    Returns list of list[str] (raw lines, indentation intact).
    """
    sections = []
    current = []
    for line in body_lines:
        if line.strip() == "":
            if current:
                sections.append(current)
                current = []
        else:
            current.append(line)
    if current:
        sections.append(current)
    return sections


def _emit_item(item_texts, item_indent, is_flat_section, continuation_indent_step,
                skip_first_line_fallback=False):
    if _is_code_like(item_texts):
        return [(" " * item_indent) + t for t in item_texts]
    out = []
    for i, rline in enumerate(reflow_lines(item_texts)):
        indent = item_indent if (is_flat_section or i == 0) else item_indent + continuation_indent_step
        raw_line = (" " * indent) + rline
        if skip_first_line_fallback and i == 0:
            # This is the docstring's lead line, still glued to the opening `"""` at this point --
            # its true rendered width isn't knowable here (see `_wrap_docstring_lead` in
            # `reflow_source`, the only place that has the real column offset).
            out.append(raw_line)
        else:
            # A flat section already has "no hanging indent" as its established convention (see the
            # comment on `is_flat_section` below) -- a fallback continuation matches that, not the
            # definition-list hang, to stay visually consistent with its sibling lines.
            extra = 0 if is_flat_section else continuation_indent_step
            out.extend(_apply_fallback_wrap(raw_line, cont_indent_extra=extra))
    return out


def reflow_section(section_lines, continuation_indent_step=4, skip_first_line_fallback=False):
    """Reflow one blank-line-delimited section.
    Returns list of output lines (raw text, no trailing newline).

    Handles the "header (one line, or a whole flat intro paragraph) ending in ':', followed by a
    more deeply indented sub-list" shape (Args:, Returns:, "...accordingly:" + bullets, etc.) by
    peeling the header run off first and recursing into the sub-list.

    `skip_first_line_fallback` propagates to the very first emitted line only (the candidate for a
    docstring's lead line) -- everything after that gets normal fallback-wrap treatment.
    """
    out = []
    lines = section_lines
    if not lines:
        return out

    base = _leading_ws(lines[0])
    run_end = 1
    while run_end < len(lines) and _leading_ws(lines[run_end]) == base:
        run_end += 1
    deeper_follows = run_end < len(lines) and _leading_ws(lines[run_end]) > base
    run_texts = [l.strip() for l in lines[:run_end]]
    run_has_marker = any(_is_item_start_line(t) for t in run_texts)

    if deeper_follows and not run_has_marker and _is_header_line(lines[run_end - 1], True):
        out.extend(_emit_item(run_texts, base, True, continuation_indent_step,
                               skip_first_line_fallback=skip_first_line_fallback))
        out.extend(reflow_section(lines[run_end:], continuation_indent_step))
        return out

    indexed = [(_leading_ws(l), l.strip()) for l in lines]
    # A section with only one indentation level is a flat wrapped paragraph: every resulting sentence line stays at that same indent, no hanging indent.
    # A section with 2+ indentation levels is a definition-list-like block (Args:-style items with wrapped continuations);
    # only there does a continuation sentence get pushed to item_indent + step.
    is_flat_section = len({i for i, _ in indexed}) <= 1
    for idx, item in enumerate(group_items(indexed)):
        item_indent = item[0][0]
        item_texts = [t for _, t in item]
        out.extend(_emit_item(item_texts, item_indent, is_flat_section, continuation_indent_step,
                               skip_first_line_fallback=(skip_first_line_fallback and idx == 0)))
    return out


def reflow_docstring_body(raw_lines):
    """raw_lines: the docstring's inner text split on '\\n', with raw_lines[0] possibly holding
    same-line-as-opening-quote text (or '' if the opening quotes stand alone), and raw_lines[-1]
    possibly holding same-line-as- closing-quote text (or whitespace-only if the closer stands
    alone).

    Returns the new list of lines in the same shape.
    """
    lead = raw_lines[0]
    tail = raw_lines[-1]
    body = raw_lines[1:-1]

    lead_is_text = lead.strip() != ""
    tail_is_text = tail.strip() != ""

    working = list(body)
    if lead_is_text:
        working = [lead] + working
    if tail_is_text:
        working = working + [tail]

    sections = split_into_sections(working)
    out_lines = []
    for i, section in enumerate(sections):
        if i > 0:
            out_lines.append("")
        # Only section 0's very first emitted line can be the lead line glued to the opening `"""`
        # -- its width isn't knowable here (see `_wrap_docstring_lead` in `reflow_source`).
        out_lines.extend(reflow_section(section, skip_first_line_fallback=(lead_is_text and i == 0)))

    if lead_is_text:
        new_lead = out_lines[0].lstrip(" ") if out_lines else ""
        rest = out_lines[1:]
    else:
        new_lead = ""
        rest = out_lines

    if tail_is_text and rest:
        new_tail = rest[-1]
        rest = rest[:-1]
    else:
        new_tail = tail if not tail_is_text else ""

    return [new_lead] + rest + [new_tail]


# ---------------------------------------------------------------------------
# AST-driven docstring rewriting
# ---------------------------------------------------------------------------

_TRIPLE_RE = re.compile(r'^([a-zA-Z]*)("""|\'\'\')')


def _docstring_nodes(tree):
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.body:
                continue
            first = node.body[0]
            if (isinstance(first, ast.Expr)
                    and isinstance(first.value, ast.Constant)
                    and isinstance(first.value.value, str)):
                yield first.value


def reflow_source(src):
    tree = ast.parse(src)
    lines = src.splitlines(keepends=True)

    edits = []  # (start_line_idx, start_col, end_line_idx, end_col, new_text)
    for const in _docstring_nodes(tree):
        if const.end_lineno == const.lineno:
            continue  # single-line docstring -- leave alone

        start_line_idx = const.lineno - 1
        end_line_idx = const.end_lineno - 1
        first_src_line = lines[start_line_idx]
        m = _TRIPLE_RE.match(first_src_line[const.col_offset:])
        if not m:
            continue  # not a triple-quoted string -- leave alone
        prefix, quote = m.group(1), m.group(2)
        if quote not in ('"""', "'''"):
            continue

        # Reconstruct the raw text spanning from just after the opening delimiter to just before the closing delimiter.
        raw_chunks = []
        for li in range(start_line_idx, end_line_idx + 1):
            line = lines[li]
            if li == start_line_idx:
                col_start = const.col_offset + len(prefix) + 3
            else:
                col_start = 0
            if li == end_line_idx:
                col_end = const.end_col_offset - 3
            else:
                col_end = len(line)
                if line.endswith("\n"):
                    col_end -= 1
            raw_chunks.append(line[col_start:col_end])
        raw_text = "\n".join(raw_chunks)
        raw_lines = raw_text.split("\n")

        if any(raw_lines[0:1] and '"""' in raw_lines[0] for _ in [0]):
            pass  # (defensive no-op; escaped delimiters inside are not expected)

        new_lines = reflow_docstring_body(raw_lines)
        if raw_lines[0].strip() != "" and new_lines[0]:
            lead_prefix_width = const.col_offset + len(prefix) + 3
            cont_prefix = " " * const.col_offset
            new_lines = _wrap_docstring_lead(lead_prefix_width, cont_prefix, new_lines[0]) + new_lines[1:]
        new_text = "\n".join(new_lines)
        if new_text == raw_text:
            continue

        edits.append((
            start_line_idx, const.col_offset + len(prefix) + 3,
            end_line_idx, const.end_col_offset - 3,
            new_text,
        ))

    if edits:
        src = _apply_edits(src, edits)

    src = _reflow_comment_blocks(src)
    return src


def _apply_edits(src, edits):
    """Apply (start_line, start_col, end_line, end_col, text) edits, given as 0-indexed line numbers
    into src.splitlines(keepends=True), in terms of absolute character offsets.
    Edits are applied last-to-first so earlier offsets stay valid.
    """
    lines = src.splitlines(keepends=True)
    line_starts = [0]
    for line in lines:
        line_starts.append(line_starts[-1] + len(line))

    def offset(line_idx, col):
        return line_starts[line_idx] + col

    edits_abs = [
        (offset(sl, sc), offset(el, ec), text)
        for sl, sc, el, ec, text in edits
    ]
    edits_abs.sort(key=lambda e: e[0], reverse=True)
    for start, end, text in edits_abs:
        src = src[:start] + text + src[end:]
    return src


# ---------------------------------------------------------------------------
# tokenize-driven comment-block rewriting
# ---------------------------------------------------------------------------

def _standalone_comment_tokens(src):
    """Yield COMMENT tokens whose physical line is otherwise blank before them (i.e.
a comment on its own line, not trailing code).
"""
    lines = src.splitlines()
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(src).readline))
    except tokenize.TokenizeError:
        return
    for tok in tokens:
        if tok.type != tokenize.COMMENT:
            continue
        row, col = tok.start
        line = lines[row - 1]
        if line[:col].strip() == "":
            yield tok


_FLANKED_DIVIDER_RE = re.compile(r'^[-=*_#~]{2,}.*[-=*_#~]{2,}$')


def _is_divider_comment(comment_string):
    """True for a '# ---...---'-style section-divider line, either bare (just repeated punctuation)
    or flanking a title ("# --- Title ---").
"""
    stripped = comment_string.lstrip("#").strip()
    if len(stripped) < 3:
        return False
    if len(set(stripped)) == 1 and stripped[0] in "-=*_#~":
        return True
    return bool(_FLANKED_DIVIDER_RE.match(stripped))


def _reflow_comment_blocks(src):
    lines = src.splitlines(keepends=True)
    comment_toks = list(_standalone_comment_tokens(src))

    # Group consecutive standalone comments (adjacent rows, same indent) into blocks.
    # A divider line (e.g. "# ---...---") always stands alone, never merging into a reflow-eligible block with its neighbors.
    blocks = []
    current = []
    prev_row = None
    prev_col = None
    for tok in comment_toks:
        row, col = tok.start
        if _is_divider_comment(tok.string):
            if current:
                blocks.append(current)
                current = []
            blocks.append([tok])
            prev_row, prev_col = row, col
            continue
        if prev_row is not None and row == prev_row + 1 and col == prev_col:
            current.append(tok)
        else:
            if current:
                blocks.append(current)
            current = [tok]
        prev_row, prev_col = row, col

    if current:
        blocks.append(current)

    edits = []
    for block in blocks:
        if len(block) < 2:
            continue  # single-line comment -- leave alone
        indent = block[0].start[1]
        texts = []
        for tok in block:
            t = tok.string[1:]  # strip leading '#'
            if t.startswith(" "):
                t = t[1:]
            texts.append(t)

        if _is_code_like(texts):
            continue

        reflowed = reflow_lines(texts)
        raw_new_lines = ["#" + ((" " + l) if l else "") for l in reflowed]
        if raw_new_lines == [("#" + ((" " + t) if t else "")) for t in texts]:
            continue

        start_row = block[0].start[0]
        end_row = block[-1].start[0]
        new_lines = []
        for nl in raw_new_lines:
            new_lines.extend(_apply_fallback_wrap((" " * indent) + nl, is_comment=True))
        new_block_text = "\n".join(new_lines)
        edits.append((start_row, end_row, new_block_text))

    if not edits:
        return src

    out = []
    edits_by_start = {e[0]: e for e in edits}
    skip_until = 0
    for i, line in enumerate(lines, start=1):
        if i in edits_by_start:
            start_row, end_row, new_block_text = edits_by_start[i]
            out.append(new_block_text + "\n")
            skip_until = end_row
            continue
        if i <= skip_until:
            continue
        out.append(line)
    return "".join(out)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _iter_py_files(paths):
    for p in paths:
        path = Path(p)
        if path.is_dir():
            yield from sorted(path.rglob("*.py"))
        else:
            yield path


def _parse_max_width(args):
    """Pull `--max-width N` / `--max-width=N` out of `args`, returning (max_width, remaining_args)."""
    max_width = _DEFAULT_MAX_WIDTH
    remaining = []
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--max-width":
            if i + 1 >= len(args):
                print("error: --max-width requires a value", file=sys.stderr)
                raise SystemExit(2)
            max_width = int(args[i + 1])
            i += 2
            continue
        if a.startswith("--max-width="):
            max_width = int(a.split("=", 1)[1])
            i += 1
            continue
        remaining.append(a)
        i += 1
    return max_width, remaining


def main(argv):
    check = "--check" in argv
    args = [a for a in argv if a != "--check"]
    max_width, args = _parse_max_width(args)
    if not args:
        print("usage: pydocreflow.py [--check] [--max-width N] <file_or_dir> ...", file=sys.stderr)
        return 2

    global _max_width, _fallback_wrap_count
    _max_width = max_width
    _fallback_wrap_count = 0

    changed = 0
    for fp in _iter_py_files(args):
        src = fp.read_text(encoding="utf-8")
        try:
            new_src = reflow_source(src)
        except SyntaxError as e:
            print(f"SKIP (parse error) {fp}: {e}", file=sys.stderr)
            continue
        if new_src == src:
            continue
        changed += 1
        if check:
            diff = difflib.unified_diff(
                src.splitlines(keepends=True),
                new_src.splitlines(keepends=True),
                fromfile=str(fp), tofile=str(fp),
            )
            sys.stdout.writelines(diff)
        else:
            fp.write_text(new_src, encoding="utf-8")
            print(f"reflowed {fp}")
    print(f"{changed} file(s) {'would change' if check else 'changed'}", file=sys.stderr)
    print(f"{_fallback_wrap_count} line(s) needed the word-boundary fallback wrap", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
