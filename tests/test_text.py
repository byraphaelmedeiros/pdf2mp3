"""
Unit tests for text processing utilities in pdf2mp3.

These tests cover:
- Cleaning text (hyphenation removal, normalization).
- Splitting text into chunks.
- Sanitizing text for TTS consumption.
"""

from pdf2mp3 import clean_text, split_into_chunks, sanitize_for_tts


def test_clean_text_removes_hyphenation():
    """
    Ensure that clean_text merges words broken by hyphenation across lines.
    """
    raw = "multi-\nline text"
    cleaned = clean_text(raw)

    assert "multi-line" not in cleaned  # should not keep the hyphen
    assert "multiline" in cleaned       # should merge properly


def test_clean_text_preserves_content():
    """
    Ensure that clean_text returns a non-empty string
    and preserves meaningful content (even if headers are repeated).
    """
    raw = "Header\nBody text\nHeader\nBody text again"
    cleaned = clean_text(raw)

    assert isinstance(cleaned, str)
    assert "Body text" in cleaned
    assert len(cleaned) > 0


def test_split_into_chunks_respects_max_chars():
    """
    Ensure that split_into_chunks divides text into chunks
    not exceeding the specified maximum length.
    """
    text = "Sentence one. Sentence two. Sentence three."
    chunks = split_into_chunks(text, max_chars=20)

    assert all(len(c) <= 20 for c in chunks)
    assert len(chunks) > 1


def test_sanitize_for_tts_quotes_ampersand():
    """
    Ensure that sanitize_for_tts normalizes quotes and replaces ampersands.
    """
    s = "“Hello” & hi’"
    sanitized = sanitize_for_tts(s)

    assert '"' in sanitized     # smart quotes replaced with plain quotes
    assert "&" not in sanitized
    assert "and" in sanitized
