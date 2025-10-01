#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# pdf2mp3.py
#
# MIT License
#
# Copyright (c) 2025 Raphael Medeiros <pdf2mp3@byraphaelmedeiros.com>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the “Software”), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
# -----------------------------------------------------------------------------

"""
PDF → MP3 (female voices) in EN or PT-BR using edge-tts.

This CLI extracts text from a PDF, cleans it, splits it into TTS-friendly
chunks, synthesizes female neural speech via Microsoft Edge TTS, and exports a
single MP3 file. It requires ffmpeg to be installed for `pydub` to export MP3.

Dependencies:
    pip install pdfminer.six edge-tts pydub tqdm

System requirement:
    ffmpeg (required by pydub to export MP3)

Usage (examples):
    pdf2mp3.py input.pdf
    pdf2mp3.py input.pdf -l en -o out.mp3 --rate +5% --volume +0%

Notes:
    * Logic is intentionally unchanged from the original version.
    * Default female neural voices:
        - English (US): en-US-AriaNeural
        - Portuguese (BR): pt-BR-ThalitaNeural
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
from pathlib import Path
from typing import List

from pdfminer.high_level import extract_text
from tqdm import tqdm  # noqa: F401 (kept for parity with original imports)
from pydub import AudioSegment
from io import BytesIO
import edge_tts
import random

__version__ = "1.0.0"

# ---- Recommended female voices (unchanged logic/values) ----
VOICE_BY_LANG = {
    "en": "en-US-AriaNeural",
    "pt-br": "pt-BR-ThalitaNeural",
}

# Smaller default to reduce TTS hiccups on long chunks
DEFAULT_MAX_CHARS = 1600


def normalize_lang(lang: str) -> str:
    """
    Normalize a user-provided language string to the internal keys.

    Args:
        lang: Language string provided by the user.

    Returns:
        One of: "en", "pt-br".

    Raises:
        ValueError: If the language cannot be mapped to supported options.
    """
    l = (lang or "pt-br").lower().strip()
    if l in ("en", "en-us", "english"):
        return "en"
    if l in ("pt", "pt-br", "ptbr", "pt_br", "portuguese", "português", "portugues"):
        return "pt-br"
    raise ValueError("Invalid language. Use 'en' or 'pt-br'.")


def extract_text_from_pdf(pdf_path: Path) -> str:
    """Extract raw text from a PDF using pdfminer.six.

    Args:
        pdf_path: Absolute path to the input PDF.

    Returns:
        Extracted text as a single string (may be empty).
    """
    text = extract_text(str(pdf_path)) or ""
    return text


def clean_text(raw: str) -> str:
    """Normalize and lightly post-process raw PDF text for TTS.

    Operations (heuristic but conservative):
        - Remove carriage returns
        - De-hyphenate line-breaking hyphens (word-\nwrap => wordwrap)
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
        joined: List[str] = []
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
    counter = {}
    for ln in lines:
        key = ln.strip().lower()
        if 1 <= len(key.split()) <= 6:
            counter[key] = counter.get(key, 0) + 1
    common = {k for k, v in counter.items() if v >= 5}

    filtered = [ln for ln in lines if ln.strip().lower() not in common]
    t = "\n".join(filtered).strip()
    return t


def split_into_chunks(text: str, max_chars: int) -> List[str]:
    """Split text into chunks no longer than `max_chars`, preserving paragraphs.

    Strategy:
        - Temporarily mark paragraph breaks to avoid losing them when splitting
          by sentences.
        - Prefer to split by sentence boundaries where possible.
        - If a single sentence exceeds `max_chars`, perform a hard split.

    Args:
        text: Cleaned text to split.
        max_chars: Upper bound for chunk length.

    Returns:
        List of chunk strings.
    """
    marker = "<PARA_BREAK>"
    text2 = text.replace("\n\n", f" {marker} ")
    sentences = re.split(r"(?<=[.!?])\s+", text2)
    sentences = [s.strip() for s in sentences if s.strip()]

    chunks: List[str] = []
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
                    part = s[i:i + max_chars]
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
    s = s.replace("\u00A0", " ").replace("\u200B", "")
    s = s.replace("“", "\"").replace("”", "\"").replace("’", "'")
    s = s.replace("&", " and ")
    return s


def preview(s: str, n: int = 80) -> str:
    """One-line preview helper for logging."""
    s = s.replace("\n", " ")[:n]
    return s + ("…" if len(s) == n else "")


async def tts_chunk(text: str, voice: str, rate: str = "+0%", volume: str = "+0%") -> bytes:
    """Call edge-tts to synthesize one chunk as MP3 bytes."""
    communicate = edge_tts.Communicate(text=text, voice=voice, rate=rate, volume=volume)
    mp3_bytes = BytesIO()
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            mp3_bytes.write(chunk["data"])
    return mp3_bytes.getvalue()


async def tts_chunk_with_retry(
    text,
    voice,
    rate,
    volume,
    *,
    timeout_s=120,
    retries=4,
    base_backoff=1.6,
):
    """Retry wrapper around `tts_chunk` with exponential backoff.

    Args:
        text: Text to synthesize.
        voice: edge-tts voice name.
        rate: Speaking rate (e.g., "+5%").
        volume: Speaking volume (e.g., "+0%").
        timeout_s: Per-attempt timeout in seconds.
        retries: Maximum attempts.
        base_backoff: Exponential base for wait calculation.

    Returns:
        Raw MP3 bytes on success.

    Raises:
        RuntimeError: After exhausting retries.
    """
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            return await asyncio.wait_for(
                tts_chunk(text, voice=voice, rate=rate, volume=volume),
                timeout=timeout_s
            )
        except Exception as e:
            last_err = e
            wait = base_backoff ** attempt + random.uniform(0, 0.5)
            print(f"[warn] TTS failed {attempt}/{retries}: {e} | retrying in {wait:.1f}s")
            await asyncio.sleep(wait)
    raise RuntimeError(f"TTS failed after {retries} attempts: {last_err}")


async def synthesize_chunks(chunks: List[str], voice: str, rate: str = "+0%", volume: str = "+0%") -> AudioSegment:
    """Synthesize a sequence of chunks and concatenate them with short silences.

    Args:
        chunks: List of text chunks to synthesize.
        voice: edge-tts voice.
        rate: Speaking rate (string with percent).
        volume: Speaking volume (string with percent).

    Returns:
        A `pydub.AudioSegment` containing the full audio.
    """
    full_audio = AudioSegment.empty()
    for idx, ch in enumerate(chunks, start=1):
        print(f"[TTS] Chunk {idx}/{len(chunks)} | {len(ch)} chars | {preview(ch)}")
        data = await tts_chunk_with_retry(ch, voice=voice, rate=rate, volume=volume)
        seg = AudioSegment.from_file(BytesIO(data), format="mp3")
        full_audio += seg
        full_audio += AudioSegment.silent(duration=120)  # Short pause between chunks
    return full_audio


def main():
    """
    CLI entry point for pdf2mp3.

    Parses arguments, validates inputs, extracts and processes text,
    runs TTS synthesis, and writes the final MP3 file.

    Example:
        python pdf2mp3.py input.pdf -l en -o output.mp3
    """
    parser = argparse.ArgumentParser(
        description="Generate an MP3 (female voice) from a PDF. Languages: en, pt-br."
    )
    # Positional: input PDF
    parser.add_argument("input", help="Path to the input PDF file")

    # Optional args
    parser.add_argument("-o", "--output", help="Path to the output MP3 (default: <PDF>.mp3)")
    parser.add_argument(
        "-l",
        "--lang",
        default="pt-br",
        help="Audio language: 'en' or 'pt-br' (default: pt-br)",
    )
    parser.add_argument(
        "--voice",
        help="edge-tts voice (defaults: en-US-AriaNeural / pt-BR-ThalitaNeural)",
    )
    parser.add_argument(
        "--rate",
        default="+0%",
        help="Speaking rate (e.g., +5%%, -5%%). Default: +0%%",
    )
    parser.add_argument(
        "--volume",
        default="+0%",
        help="Speaking volume (e.g., +0%%, +5%%). Default: +0%%",
    )
    parser.add_argument(
        "--max-chars",
        type=int,
        default=DEFAULT_MAX_CHARS,
        help=f"Maximum characters per chunk (default: {DEFAULT_MAX_CHARS})",
    )

    args = parser.parse_args()

    pdf_path = Path(args.input).expanduser().resolve()
    if not pdf_path.exists():
        print(f"[error] PDF not found: {pdf_path}", file=sys.stderr)
        sys.exit(1)

    # Output default = same name as PDF with .mp3
    if args.output:
        out_path = Path(args.output).expanduser().resolve()
    else:
        out_path = pdf_path.with_suffix(".mp3")

    try:
        lang = normalize_lang(args.lang)
    except ValueError as e:
        print(f"[error] {e}", file=sys.stderr)
        sys.exit(2)

    voice = args.voice or VOICE_BY_LANG[lang]

    print(">> Extracting text from PDF…")
    raw = extract_text_from_pdf(pdf_path)
    if not raw.strip():
        print("[error] No readable text was extracted (possibly a scanned PDF).", file=sys.stderr)
        print("       Tip: run OCR first (e.g., ocrmypdf --force-ocr in.pdf out.pdf).", file=sys.stderr)
        sys.exit(3)

    print(">> Cleaning and preparing text…")
    cleaned = clean_text(raw)
    chunks = [sanitize_for_tts(c) for c in split_into_chunks(cleaned, max_chars=args.max_chars)]
    if not chunks:
        print("[error] No content after cleaning.", file=sys.stderr)
        sys.exit(4)

    print(f">> Total TTS chunks: {len(chunks)} | Voice: {voice} | Language: {lang}")

    try:
        audio: AudioSegment = asyncio.run(
            synthesize_chunks(chunks, voice=voice, rate=args.rate, volume=args.volume)
        )
    except KeyboardInterrupt:
        print("\n[interrupted] Operation cancelled by user.", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f"[error] Failure during TTS: {e}", file=sys.stderr)
        sys.exit(5)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    print(f">> Exporting MP3 to: {out_path}")
    audio.export(out_path, format="mp3")
    print("Done!")


if __name__ == "__main__":
    main()
