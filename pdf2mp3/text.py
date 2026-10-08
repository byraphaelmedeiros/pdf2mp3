"""Deterministic text preparation; public helpers are re-exported by pdf2mp3."""

from __future__ import annotations

import re


def normalize_lang(lang: str | None) -> str:
    """
    Normalize a user-provided language string to the internal keys.

    Args:
        lang: Language string; None or an empty string selects pt-br.
            Surrounding whitespace is stripped before matching aliases.

    Returns:
        One of: "en", "pt-br".

    Raises:
        ValueError: If the language cannot be mapped to supported options.
    """
    normalized = (lang or "pt-br").lower().strip()
    if normalized in ("en", "en-us", "english"):
        return "en"
    if normalized in ("pt", "pt-br", "ptbr", "pt_br", "portuguese", "português", "portugues"):
        return "pt-br"
    raise ValueError("Invalid language. Use 'en' or 'pt-br'.")


def clean_text(raw: str) -> str:
    """Normalize and lightly post-process raw PDF text for TTS.

    Operations (heuristic but conservative):
        - Remove carriage returns
        - De-hyphenate line-breaking hyphens (word-\\nwrap => wordwrap)
        - Normalize paragraph breaks to double newlines
        - Join wrapped lines within the same paragraph unless a sentence-ending
          punctuation is detected
        - Collapse excessive spaces/newlines
        - Heuristically remove common repeated headers/footers (short lines
          seen many times)

    Args:
        raw: The raw extracted text.

    Returns:
        Cleaned text suitable for chunking.
    """
    if not raw:
        return ""

    t = raw.replace("\r", "")

    # Fix end-of-line hyphenation
    t = re.sub(r"(\w)-\n(\w)", r"\1\2", t)

    # Normalize paragraphs
    t = re.sub(r"\n{2,}", "\n\n", t)

    def _join_lines(paragraph: str) -> str:
        lines = [ln.strip() for ln in paragraph.split("\n") if ln.strip()]
        joined: list[str] = []
        for ln in lines:
            if not joined:
                joined.append(ln)
            else:
                # If previous line ends a sentence, start a new one;
                # otherwise, join with a space.
                if re.search(r"[.!?…:;)]$|”$", joined[-1]):
                    joined.append(ln)
                else:
                    joined[-1] = (joined[-1] + " " + ln).strip()
        return "\n".join(joined)

    paragraphs = t.split("\n\n")
    t = "\n\n".join(_join_lines(p) for p in paragraphs)

    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t).strip()

    # Remove repeated headers/footers (simple frequency heuristic)
    lines = t.splitlines()
    counter: dict[str, int] = {}
    for ln in lines:
        key = ln.strip().lower()
        if 1 <= len(key.split()) <= 6:
            counter[key] = counter.get(key, 0) + 1
    common = {k for k, v in counter.items() if v >= 5}

    filtered = [ln for ln in lines if ln.strip().lower() not in common]
    t = "\n".join(filtered).strip()
    return t


def split_into_chunks(text: str, max_chars: int) -> list[str]:
    """Split text into chunks no longer than a positive `max_chars` string length.

    Strategy:
        - Temporarily mark paragraph breaks during sentence splitting; separators
          may be normalized to spaces when the final chunks are assembled.
        - Prefer to split by sentence boundaries where possible.
        - If a single sentence exceeds `max_chars`, perform a hard split.

    Args:
        text: Cleaned text to split.
        max_chars: Positive upper bound for chunk length, measured by len().

    Returns:
        List of chunk strings.

    Raises:
        ValueError: If max_chars is zero or negative.
    """
    if max_chars <= 0:
        raise ValueError("max_chars must be positive")
    marker = "<PARA_BREAK>"
    while marker in text:
        marker = "_" + marker
    text2 = text.replace("\n\n", f" {marker} ")
    sentences = re.split(r"(?<=[.!?])\s+", text2)
    sentences = [s.strip() for s in sentences if s.strip()]

    chunks: list[str] = []
    buf = ""
    for s in sentences:
        s = s.replace(marker, "\n\n").strip()
        add_len = len(s) + (1 if buf else 0)
        if len(buf) + add_len <= max_chars:
            buf = f"{buf} {s}".strip() if buf else s
        else:
            if buf:
                chunks.append(buf)
            if len(s) > max_chars:
                for i in range(0, len(s), max_chars):
                    part = s[i : i + max_chars]
                    if part.strip():
                        chunks.append(part.strip())
                buf = ""
            else:
                buf = s
    if buf:
        chunks.append(buf)
    return chunks


def sanitize_for_tts(s: str) -> str:
    """Apply minimal sanitation to reduce SSML parsing issues in edge-tts.

    Replacements:
        - Non-breaking spaces and zero-width chars
        - Smart quotes to ASCII quotes
        - Ampersand to the word "and" (avoid SSML conflicts)

    Args:
        s: Input string.

    Returns:
        Sanitized string.
    """
    s = s.replace("\u00a0", " ").replace("\u200b", "")
    s = s.replace("“", '"').replace("”", '"').replace("’", "'")
    s = s.replace("&", " and ")
    return s


def preview(s: str, n: int = 80) -> str:
    """Return a caller-requested text preview; the CLI does not log document previews."""
    s = s.replace("\n", " ")[:n]
    return s + ("…" if len(s) == n else "")
