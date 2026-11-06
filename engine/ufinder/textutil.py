"""Shared text handling for the keyword index."""
from __future__ import annotations

import re

CJK = re.compile(r"([぀-ヿ㐀-䶿一-鿿가-힯])")
WORD = re.compile(r"[\w]+", re.UNICODE)
STOP = {
    "a", "an", "and", "are", "at", "be", "by", "can", "did", "do", "find", "for", "from", "get", "give", "had", "has",
    "have", "i", "in", "is", "it", "its", "me", "my", "of", "on", "or", "our", "show", "that", "the", "their", "there",
    "this", "to", "was", "we", "were", "what", "when", "where", "which", "who", "with", "you", "your", "file", "files",
    "photo", "photos", "picture", "pictures", "image", "images", "document", "documents", "look", "looking", "need",
}


def fts_text(text: str) -> str:
    """Space out CJK characters so the unicode tokenizer indexes each one."""
    return CJK.sub(r" \1 ", text)


def query_terms(text: str) -> list[str]:
    spaced = fts_text(text.lower())
    return [t for t in WORD.findall(spaced) if t not in STOP and (len(t) > 1 or CJK.match(t))]


def match_expr(text: str) -> str:
    terms = query_terms(text)
    return " OR ".join(f'"{t}"' for t in terms)
