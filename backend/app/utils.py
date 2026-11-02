"""Markdown-stripping utility for generating snippets and search text."""
import re


# Patterns to strip from Markdown to produce plain text.
_MD_PATTERNS = [
    (re.compile(r"```[\s\S]*?```"), ""),          # fenced code blocks
    (re.compile(r"`([^`]+)`"), r"\1"),             # inline code
    (re.compile(r"!\[([^\]]*)\]\([^)]+\)"), ""),   # images
    (re.compile(r"\[([^\]]+)\]\([^)]+\)"), r"\1"), # links → keep text
    (re.compile(r"^#{1,6}\s+", re.M), ""),         # headings
    (re.compile(r"^[>\s]*>\s?", re.M), ""),        # blockquotes
    (re.compile(r"^[-*+]\s+", re.M), ""),          # unordered list markers
    (re.compile(r"^\d+\.\s+", re.M), ""),          # ordered list markers
    (re.compile(r"^-{3,}$", re.M), ""),            # horizontal rules
    (re.compile(r"\*{1,3}([^*]+)\*{1,3}"), r"\1"), # bold / italic
    (re.compile(r"_{1,3}([^_]+)_{1,3}"), r"\1"),   # bold / italic underscore
    (re.compile(r"~~([^~]+)~~"), r"\1"),            # strikethrough
    (re.compile(r"<[^>]+>"), ""),                  # HTML tags
    (re.compile(r"^\||\|$", re.M), ""),            # table borders
    (re.compile(r"\|"), " "),                      # table cells
    (re.compile(r":?-{3,}:?"), ""),                # table header dividers
]


def strip_markdown(text: str) -> str:
    """Return *text* with Markdown syntax removed, suitable for search."""
    for pattern, replacement in _MD_PATTERNS:
        text = pattern.sub(replacement, text)
    # Collapse whitespace.
    text = re.sub(r"\n{2,}", "\n", text).strip()
    return text


def make_snippet(body: str, max_len: int = 200) -> str:
    """Return the first *max_len* characters of the plain-text body."""
    plain = strip_markdown(body)
    if len(plain) <= max_len:
        return plain
    return plain[:max_len]
