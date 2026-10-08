#!/usr/bin/env python3
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
PDF → MP3 with selectable TTS engines (edge-tts default).

This CLI extracts text from a PDF, cleans it, splits it into TTS-friendly
chunks, synthesizes speech, and exports a single MP3 file. It requires ffmpeg
to be installed for `pydub` to export MP3.

Dependencies (base):
    pip install pdfminer.six edge-tts pydub tqdm

Optional engines:
    gTTS:  pip install gTTS
    OpenAI: pip install 'pdf2mp3[openai]' (and set OPENAI_API_KEY)
    Local: pip install pyttsx3
    macOS: built-in 'say' (no extra deps)

System requirement:
    ffmpeg (required by pydub to export MP3)

Usage (examples):
    pdf2mp3 convert input.pdf
    pdf2mp3 convert input.pdf --engine edge -l en -o out.mp3 --rate +5% --volume +0%

Notes:
    * Default female neural voices for edge-tts:
        - English (US): en-US-AriaNeural
        - Portuguese (BR): pt-BR-ThalitaNeural
"""

from __future__ import annotations

import asyncio
import logging
import random
import subprocess  # nosec B404 - only the fixed macOS say executable; no shell
import sys
import tempfile
from collections.abc import Callable
from io import BytesIO
from pathlib import Path

import edge_tts
from pdfminer.high_level import extract_text
from pydub import AudioSegment
from tqdm import tqdm  # noqa: F401 (kept for parity with original imports)

from . import openai_tts
from .text import clean_text as clean_text
from .text import normalize_lang as normalize_lang
from .text import preview as preview
from .text import sanitize_for_tts as sanitize_for_tts
from .text import split_into_chunks as split_into_chunks

__version__ = "2.0.0"

# ---- Recommended female voices (unchanged logic/values) ----
VOICE_BY_LANG = {
    "en": "en-US-AriaNeural",
    "pt-br": "pt-BR-ThalitaNeural",
}

ENGINE_CHOICES = ("edge", "gtts", "openai", "pyttsx3", "say")
DEFAULT_ENGINE = "edge"
DEFAULT_OPENAI_MODEL = openai_tts.DEFAULT_MODEL
DEFAULT_OPENAI_VOICE = "alloy"

# Smaller default to reduce TTS hiccups on long chunks
DEFAULT_MAX_CHARS = 1600


def extract_text_from_pdf(pdf_path: Path) -> str:
    """Extract raw text from a PDF using pdfminer.six.

    Args:
        pdf_path: Path to the input PDF, absolute or relative to the working directory.

    Returns:
        Extracted text as a single string (may be empty).

    File and PDF parser errors propagate; this helper does not perform OCR.
    """
    text = extract_text(str(pdf_path)) or ""
    return text


async def tts_chunk(text: str, voice: str, rate: str = "+0%", volume: str = "+0%") -> bytes:
    """Call edge-tts to synthesize one chunk as MP3 bytes."""
    communicate = edge_tts.Communicate(text=text, voice=voice, rate=rate, volume=volume)
    mp3_bytes = BytesIO()
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            mp3_bytes.write(chunk["data"])
    return mp3_bytes.getvalue()


async def tts_chunk_with_retry(
    text: str,
    voice: str,
    rate: str,
    volume: str,
    *,
    timeout_s: float = 120,
    retries: int = 4,
    base_backoff: float = 1.6,
) -> bytes:
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

    Each attempt sends text to the external Edge service. Empty bytes and ordinary
    provider errors are retried; cancellation propagates. Backoff uses jitter,
    with no sleep after the last failure. Caller code controls logging of errors.
    """
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            data = await asyncio.wait_for(
                tts_chunk(text, voice=voice, rate=rate, volume=volume), timeout=timeout_s
            )
            if not data:
                raise RuntimeError("TTS returned empty audio")
            return data
        except Exception as e:
            last_err = e
            if attempt == retries:
                break
            wait = base_backoff**attempt + random.uniform(0, 0.5)  # nosec B311 - retry jitter
            logging.getLogger("pdf2mp3").warning(
                "TTS attempt %d/%d failed (%s); retrying in %.1fs",
                attempt,
                retries,
                type(e).__name__,
                wait,
            )
            await asyncio.sleep(wait)
    raise RuntimeError(f"TTS failed after {retries} attempts: {last_err}")


async def synthesize_chunks(
    chunks: list[str], voice: str, rate: str = "+0%", volume: str = "+0%"
) -> AudioSegment:
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
        logging.getLogger("pdf2mp3").info(
            "TTS chunk %d/%d (%d characters)", idx, len(chunks), len(ch)
        )
        data = await tts_chunk_with_retry(ch, voice=voice, rate=rate, volume=volume)
        seg = AudioSegment.from_file(BytesIO(data), format="mp3")
        full_audio += seg
        full_audio += AudioSegment.silent(duration=120)  # Short pause between chunks
    return full_audio


def tts_chunk_gtts(text: str, lang: str) -> bytes:
    """Synthesize one chunk using gTTS (Google Translate TTS) and return MP3 bytes."""
    try:
        from gtts import gTTS
    except ImportError as exc:
        raise RuntimeError("gTTS is not installed. Run: pip install gTTS") from exc
    mp3_bytes = BytesIO()
    gTTS(text=text, lang=lang).write_to_fp(mp3_bytes)
    return mp3_bytes.getvalue()


def tts_chunk_openai(text: str, model: str, voice: str) -> bytes:
    """Narrate one chunk through OpenAI Realtime and return MP3 bytes."""
    return openai_tts.synthesize_mp3(text, model, voice)


def synthesize_chunks_sync(
    chunks: list[str], tts_fn: Callable[[str], bytes], *, pause_ms: int = 120
) -> AudioSegment:
    """Synthesize chunks using a sync TTS function that returns MP3 bytes."""
    full_audio = AudioSegment.empty()
    for idx, ch in enumerate(chunks, start=1):
        logging.getLogger("pdf2mp3").info(
            "TTS chunk %d/%d (%d characters)", idx, len(chunks), len(ch)
        )
        data = tts_fn(ch)
        seg = AudioSegment.from_file(BytesIO(data), format="mp3")
        full_audio += seg
        full_audio += AudioSegment.silent(duration=pause_ms)
    return full_audio


def synthesize_chunks_pyttsx3(
    chunks: list[str], voice: str | None, *, pause_ms: int = 120
) -> AudioSegment:
    """Synthesize chunks using pyttsx3 and return a combined AudioSegment."""
    try:
        import pyttsx3
    except ImportError as exc:
        raise RuntimeError("pyttsx3 is not installed. Run: pip install pyttsx3") from exc

    builtins_objc = None
    if sys.platform == "darwin":
        try:
            import builtins

            import objc

            builtins_objc = getattr(builtins, "objc", None)
            builtins.objc = objc  # type: ignore[attr-defined]  # pyttsx3 macOS workaround
        except Exception:  # nosec B110 - optional legacy bridge; pyttsx3.init reports failure
            pass

    try:
        engine = pyttsx3.init()
    finally:
        if sys.platform == "darwin" and "builtins" in locals():
            if builtins_objc is None:
                try:
                    delattr(builtins, "objc")
                except Exception:  # nosec B110 - restore optional bridge if present
                    pass
            else:
                builtins.objc = builtins_objc  # type: ignore[attr-defined]
    if voice:
        for v in engine.getProperty("voices"):
            if voice.lower() in {(v.name or "").lower(), (v.id or "").lower()}:
                engine.setProperty("voice", v.id)
                break
        else:
            raise RuntimeError("Requested pyttsx3 voice is not installed.")

    full_audio = AudioSegment.empty()
    for idx, ch in enumerate(chunks, start=1):
        logging.getLogger("pdf2mp3").info(
            "TTS chunk %d/%d (%d characters)", idx, len(chunks), len(ch)
        )
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            engine.save_to_file(ch, tmp_path)
            engine.runAndWait()
            seg = AudioSegment.from_file(tmp_path, format="wav")
            if not seg.raw_data:
                raise RuntimeError("pyttsx3 returned empty audio; check the system voice engine")
        except NameError as exc:
            msg = str(exc)
            if "objc" in msg.lower():
                raise RuntimeError(
                    "pyttsx3 on macOS requires pyobjc. Run: pip install pyobjc"
                ) from exc
            raise
        finally:
            try:
                Path(tmp_path).unlink(missing_ok=True)
            except Exception:  # nosec B110 - preserve the provider error during best-effort cleanup
                pass
        full_audio += seg
        full_audio += AudioSegment.silent(duration=pause_ms)
    return full_audio


def synthesize_chunks_say(
    chunks: list[str], voice: str | None, *, pause_ms: int = 120
) -> AudioSegment:
    """Synthesize chunks through macOS 'say' stdin and combine the local audio."""
    if sys.platform != "darwin":
        raise RuntimeError("The 'say' engine is only available on macOS.")

    full_audio = AudioSegment.empty()
    for idx, ch in enumerate(chunks, start=1):
        logging.getLogger("pdf2mp3").info(
            "TTS chunk %d/%d (%d characters)", idx, len(chunks), len(ch)
        )
        with tempfile.NamedTemporaryFile(suffix=".aiff", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            cmd = ["say", "-o", tmp_path]
            if voice:
                cmd += ["-v", voice]
            # Keep document text out of argv so leading hyphens cannot become options.
            result = subprocess.run(cmd, input=ch, check=False, capture_output=True, text=True)  # nosec B603 - no shell, fixed executable
            if result.returncode != 0:
                err = (result.stderr or result.stdout or "").strip()
                raise RuntimeError(f"say failed: {err or 'unknown error'}")
            seg = AudioSegment.from_file(tmp_path, format="aiff")
            if not seg.raw_data:
                raise RuntimeError(
                    "say returned empty audio; check the voice and macOS speech access"
                )
        finally:
            try:
                Path(tmp_path).unlink(missing_ok=True)
            except Exception:  # nosec B110 - preserve the provider error during best-effort cleanup
                pass
        full_audio += seg
        full_audio += AudioSegment.silent(duration=pause_ms)
    return full_audio


def main() -> None:
    """Run the v2 CLI using sys.argv, returning None after a successful command.

    No arguments prints help and returns None; explicit help/version may raise
    SystemExit(0) through argparse. Failures raise SystemExit with their exit code.
    Conversion may send text externally and write audio; check only inspects/prepares input.
    Use the console/module CLI for subprocess integration and structured JSON.
    """
    from .cli import main as cli_main

    exit_code = cli_main()
    if exit_code:
        sys.exit(exit_code)


if __name__ == "__main__":
    main()
