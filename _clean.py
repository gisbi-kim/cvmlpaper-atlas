"""Shared cleanup predicates.

OpenAlex (and occasionally DBLP) indexes conference front-matter — volume
titles, workshop overviews, preface entries — as "works". These pollute
counts and inflate co-author networks.
"""
from __future__ import annotations
import re

FRONT_MATTER_EXACT = {
    'table of contents', 'front cover', 'back cover', 'blank page',
    'editorial', 'frontispiece', 'index', 'contents', 'toc',
    'publication information', 'information for authors',
    'masthead', 'colophon', 'title page', 'preface', 'foreword',
}

_FRONT_MATTER_PREFIX = re.compile(
    r'^(?:'
    r'table of contents\b|'
    r'front cover\b|'
    r'back cover\b|'
    r'blank page\b|'
    r'publication information\b|'
    r'information for authors\b|'
    r'proceedings of\b|'
    r'\d{4}\s+index\b|'
    r'volume\s+\d+\s+index\b'
    r')',
    re.I,
)


def is_front_matter(title: str | None) -> bool:
    t = (title or '').strip().rstrip('.').lower()
    if not t:
        return True
    if t in FRONT_MATTER_EXACT:
        return True
    return bool(_FRONT_MATTER_PREFIX.match(t))


_TRANSLATED_TITLE = re.compile(
    r'[぀-ヿ一-鿿가-힯]'
    r'|【\s*Powered\s+by\s+NICT\s*】',
    re.I,
)


def is_translated_dup(title: str | None) -> bool:
    if not title:
        return False
    return bool(_TRANSLATED_TITLE.search(title))
