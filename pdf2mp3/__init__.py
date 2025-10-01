"""
pdf2mp3 package initializer.

This module exposes the main public API of pdf2mp3 so that users can
import functions directly from the package without navigating internal modules.

Example:
    from pdf2mp3 import clean_text, split_into_chunks
"""

from .pdf2mp3 import (
    normalize_lang,
    extract_text_from_pdf,
    clean_text,
    split_into_chunks,
    sanitize_for_tts,
    tts_chunk_with_retry,
    main,
)

__all__ = [
    "normalize_lang",
    "extract_text_from_pdf",
    "clean_text",
    "split_into_chunks",
    "sanitize_for_tts",
    "tts_chunk_with_retry",
    "main",
]
