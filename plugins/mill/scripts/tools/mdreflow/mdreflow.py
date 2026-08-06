"""One-shot repo sweep for the mill:markdown skill's semantic-line-break rule.

Reflows markdown prose/list-item paragraphs to one-sentence-per-line, with extra breaks at internal
clause boundaries (semicolon, or comma+coordinating- conjunction+explicit-subject) per
plugins/mill/skills/markdown/SKILL.md's "No fixed-column hard-wrapping" section.
Line breaks only -- never rewords, reorders, or drops content.
Never touches fenced code blocks (nested fences tracked by CommonMark backtick-run-length matching,
not a naive toggle), inline code spans, links/autolinks, YAML frontmatter, headings, tables,
blockquotes, thematic breaks, or link-reference definitions.

Safety invariant enforced on every file before writing: the transformed text, with all runs of
whitespace collapsed to a single space, must be byte-identical to the original collapsed the same
way.
A file that fails this check is left untouched and reported, never partially written.

Usage:
    python mdreflow.py [--dry-run] [--diff] <path-or-glob> [...]

Last run: 2026-08-05, repo-wide sweep of markdown-semantic-linebreaks task.
"""

from __future__ import annotations

import argparse
import difflib
import re
import sys
from pathlib import Path

MASK_DELIM = ""
MASK_RE = re.compile(MASK_DELIM + r"(\d+)" + MASK_DELIM)

ABBREVIATIONS = {
    "e.g", "i.e", "etc", "vs", "cf", "approx", "no", "fig", "eq", "al", "et",
    "a.m", "p.m", "u.s", "u.k", "vol", "ch", "pp", "p", "dr", "mr", "mrs",
    "ms", "prof", "sr", "jr", "st", "ave", "inc", "ltd", "co", "corp",
}

PRONOUNS = {"i", "you", "he", "she", "it", "we", "they",
            "this", "that", "these", "those"}
DETERMINERS = {"a", "an", "the", "this", "that", "these", "those", "my",
                "your", "his", "her", "its", "our", "their", "no", "some",
                "any", "each", "every", "many", "most", "such"}

OPEN_MARKUP = set("*_`\"'[")

PREPOSITIONS = {"to", "of", "in", "on", "at", "for", "with", "from", "by",
                "as", "into", "onto", "about", "over", "under", "between",
                "among", "through", "during", "per", "via", "within",
                "without", "against", "across", "after", "before"}
VERB_AUX = {"is", "are", "was", "were", "be", "been", "being", "has",
            "have", "had", "do", "does", "did", "will", "would", "can",
            "could", "shall", "should", "may", "might", "must", "took",
            "went", "came", "made", "said", "got", "put", "ran", "saw",
            "gave", "found", "told", "knew", "felt", "kept", "held",
            "meant", "began", "showed", "called", "needed", "seems",
            "needs", "means", "brought", "thought", "became"}


def _has_verb_before_preposition(s, pos, max_words=6):
    words = re.findall(r"[A-Za-z]+", s[pos:pos + 60])[:max_words]
    for w in words:
        lw = w.lower()
        if lw in PREPOSITIONS:
            return False
        if lw in VERB_AUX or re.search(r"(s|es|ed|ing)$", lw):
            return True
    return False

LIST_MARKER_RE = re.compile(r"^(?P<indent>[ \t]*)(?P<marker>[-*+]|\d{1,9}[.)])(?P<spaces>\s+)(?P<rest>.*)$")
# Indentation unbounded for the same reason as the fence regexes above: these constructs commonly
# nest inside list-item content columns deeper than CommonMark's top-level 3-space rule.
HEADING_RE = re.compile(r"^\s*#{1,6}(\s|$)")
BLOCKQUOTE_RE = re.compile(r"^\s*>")
HR_RE = re.compile(r"^\s*([-*_])\1{2,}\s*$")
LINKDEF_RE = re.compile(r"^\s*\[[^\]]+\]:\s")
HTML_BLOCK_RE = re.compile(r"^\s*<[a-zA-Z!/]")


def _fence_open_match(line):
    # Indentation is unbounded (not CommonMark's top-level <=3-space rule): this repo nests fenced
    # examples inside list items, where the fence's effective indent is relative to the item's
    # content column, not to column 0. Treating any indent as fence-eligible avoids corrupting those
    # indented fences into single-line prose paragraphs.
    m = re.match(r"^\s*(`{3,}|~{3,})", line)
    if not m:
        return None
    run = m.group(1)
    return run[0], len(run)


def _fence_close_match(line, char, count):
    m = re.match(r"^\s*(" + re.escape(char) + r"{3,})\s*$", line)
    if not m:
        return False
    return len(m.group(1)) >= count


def _is_table_line(line):
    stripped = line.strip()
    if not stripped:
        return False
    if "|" not in stripped:
        return False
    # header/separator row: |---|---| or ---|---
    if re.match(r"^:?-+:?(\s*\|\s*:?-+:?)+$", stripped.replace(" ", "")):
        return True
    return "|" in stripped


def _mask(text):
    spans = []

    def _save(m):
        spans.append(m.group(0))
        return f"{MASK_DELIM}{len(spans) - 1}{MASK_DELIM}"

    text = re.sub(r"(`+)(.+?)(?<!`)\1(?!`)", _save, text)
    text = re.sub(r"<(?:https?|ftp)://[^>\s]+>", _save, text)
    text = re.sub(r"\[([^\]\n]*)\]\(([^)\n]*)\)", _save, text)
    text = re.sub(r"\[([^\]\n]*)\]\[[^\]\n]*\]", _save, text)
    text = re.sub(r"https?://\S+", _save, text)
    return text, spans


def _unmask(text, spans):
    return MASK_RE.sub(lambda m: spans[int(m.group(1))], text)


def _next_sentence_start_ok(s, pos):
    j = pos
    n = len(s)
    while j < n and s[j] in OPEN_MARKUP:
        j += 1
    if j >= n:
        return False
    c = s[j]
    return "A" <= c <= "Z"


def _preceding_word(s, pos):
    j = pos
    while j > 0 and (s[j - 1].isalpha() or s[j - 1] == "."):
        j -= 1
    return s[j:pos]


BOUNDARY_RE = re.compile(
    r"(?P<term>[.!?])(?P<closers>[\"'\)\]\*_`]*)(?P<sp1>\s+)"
    r"|(?P<semi>;)(?P<sp2>\s+)"
    r"|,(?P<sp3>\s+)\b(?P<conj>and|but|or)\b(?P<sp4>\s+)(?P<subj>[A-Za-z]+)"
)


def _find_cuts(s):
    cuts = []
    for m in BOUNDARY_RE.finditer(s):
        if m.group("term") is not None:
            word = _preceding_word(s, m.start("term")).lower()
            if word in ABBREVIATIONS:
                continue
            if len(word) == 1:
                continue
            right_start = m.end("sp1")
            if not _next_sentence_start_ok(s, right_start):
                continue
            left_end = m.start("sp1")
            cuts.append((left_end, right_start))
        elif m.group("semi") is not None:
            left_end = m.start("sp2")
            right_start = m.end("sp2")
            cuts.append((left_end, right_start))
        elif m.group("conj") is not None:
            subj = m.group("subj").lower()
            if subj not in PRONOUNS and subj not in DETERMINERS:
                continue
            lookahead = s[m.end("subj"):m.end("subj") + 25]
            if "—" in lookahead or "–" in lookahead:
                continue
            if not _has_verb_before_preposition(s, m.end("subj")):
                continue
            comma_pos = m.start(0)
            left_end = comma_pos + 1
            right_start = m.start("conj")
            cuts.append((left_end, right_start))
    return cuts


def _split_semantic(content):
    masked, spans = _mask(content)
    cuts = _find_cuts(masked)
    chunks = []
    last = 0
    for left_end, right_start in cuts:
        chunks.append(masked[last:left_end].strip())
        last = right_start
    chunks.append(masked[last:].strip())
    chunks = [c for c in chunks if c]
    if not chunks:
        chunks = [masked.strip()]
    return [_unmask(c, spans) for c in chunks]


def _flush_paragraph(buf, out):
    if not buf:
        return
    first = buf[0]
    m = LIST_MARKER_RE.match(first)
    if m:
        prefix_first = m.group("indent") + m.group("marker") + m.group("spaces")
        first_content = m.group("rest").strip()
    else:
        prefix_first = re.match(r"^\s*", first).group(0)
        first_content = first.strip()
    prefix_cont = " " * len(prefix_first)
    parts = [first_content] + [line.strip() for line in buf[1:]]
    content = " ".join(p for p in parts if p)
    if not content:
        buf.clear()
        return
    chunks = _split_semantic(content)
    out.append(prefix_first + chunks[0])
    for c in chunks[1:]:
        out.append(prefix_cont + c)
    buf.clear()


def _classify_special(line):
    if line.strip() == "":
        return "blank"
    if HEADING_RE.match(line):
        return "heading"
    if BLOCKQUOTE_RE.match(line):
        return "blockquote"
    if HR_RE.match(line):
        return "hr"
    if LINKDEF_RE.match(line):
        return "linkdef"
    if HTML_BLOCK_RE.match(line):
        return "html"
    if _is_table_line(line):
        return "table"
    return None


def reflow_text(text):
    lines = text.split("\n")
    trailing_newline = text.endswith("\n")
    out = []
    buf = []

    i = 0
    n = len(lines)

    # YAML frontmatter: only at the very start of the file.
    if n > 0 and lines[0].strip() == "---":
        j = 1
        while j < n and lines[j].strip() != "---":
            j += 1
        if j < n:
            out.extend(lines[0:j + 1])
            i = j + 1

    fence_char = None
    fence_count = None

    while i < n:
        line = lines[i]

        if fence_char is not None:
            out.append(line)
            if _fence_close_match(line, fence_char, fence_count):
                fence_char = None
                fence_count = None
            i += 1
            continue

        opened = _fence_open_match(line)
        if opened is not None:
            _flush_paragraph(buf, out)
            out.append(line)
            fence_char, fence_count = opened
            i += 1
            continue

        kind = _classify_special(line)
        if kind is not None:
            _flush_paragraph(buf, out)
            out.append(line)
            i += 1
            continue

        if LIST_MARKER_RE.match(line):
            _flush_paragraph(buf, out)
            buf.append(line)
            i += 1
            continue

        buf.append(line)
        i += 1

    _flush_paragraph(buf, out)

    result = "\n".join(out)
    if trailing_newline and not result.endswith("\n"):
        result += "\n"
    return result


def collapsed(text):
    return re.sub(r"\s+", " ", text).strip()


def process_file(path, dry_run, show_diff):
    original = path.read_text(encoding="utf-8")
    transformed = reflow_text(original)

    if collapsed(transformed) != collapsed(original):
        return "mismatch", None

    if transformed == original:
        return "unchanged", None

    if show_diff:
        diff = "".join(difflib.unified_diff(
            original.splitlines(keepends=True),
            transformed.splitlines(keepends=True),
            fromfile=str(path), tofile=str(path) + " (reflowed)",
        ))
    else:
        diff = None

    if not dry_run:
        path.write_text(transformed, encoding="utf-8")

    return "changed", diff


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--diff", action="store_true")
    args = ap.parse_args(argv)

    changed = 0
    unchanged = 0
    mismatches = []

    for p in args.paths:
        path = Path(p)
        status, diff = process_file(path, args.dry_run, args.diff)
        if status == "mismatch":
            mismatches.append(str(path))
            print(f"MISMATCH (left untouched): {path}")
        elif status == "changed":
            changed += 1
            print(f"{'would change' if args.dry_run else 'changed'}: {path}")
            if diff:
                print(diff)
        else:
            unchanged += 1

    print(f"\n{changed} changed, {unchanged} unchanged, {len(mismatches)} mismatches")
    if mismatches:
        print("Files with content mismatches (NOT written):")
        for m in mismatches:
            print(f"  {m}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
