"""
Autonomous bug-fix pipeline helpers.

Public API:
    slug_from_title(title, existing_slugs, issue_number) -> str
        Derive a URL-safe slug from an issue title. Guaranteed to be unique
        within existing_slugs by appending the issue number on collision.
"""
from __future__ import annotations

import re


def slug_from_title(title: str, existing_slugs: set[str], issue_number: int) -> str:
    """Return a unique, URL-safe slug derived from ``title``.

    Algorithm:
    1. Lowercase.
    2. Replace every character not in [a-z0-9] with ``-``.
    3. Collapse consecutive ``-`` runs to a single ``-``.
    4. Strip leading and trailing ``-``.
    5. Truncate to 30 characters at the last ``-`` boundary within the prefix;
       hard-cut at 30 if no boundary exists.
    6. If the result is already in ``existing_slugs``, append ``-<issue_number>``.
    """
    slug = title.lower()
    slug = re.sub(r"[^a-z0-9]", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    slug = slug.strip("-")
    if len(slug) > 30:
        idx = slug[:30].rfind("-")
        if idx != -1:
            slug = slug[:idx]
        else:
            slug = slug[:30]
    if slug in existing_slugs:
        slug = f"{slug}-{issue_number}"
    return slug
