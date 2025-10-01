"""
CLI tests for the pdf2mp3 package.

These tests verify the command-line interface behavior:
- Help output
- Error handling for missing files
- Retry logic for TTS synthesis (mocked)

All tests follow best practices for readability, consistency,
and international open-source standards.
"""

import subprocess
import sys
import pytest
from unittest.mock import patch


def test_cli_help():
    """
    Ensure that running the CLI with --help prints usage information
    and exits with return code 0.
    """
    result = subprocess.run(
        [sys.executable, "-m", "pdf2mp3", "--help"],
        capture_output=True,
        text=True,
    )

    # argparse --help prints to stdout, not stderr
    assert result.returncode == 0
    assert "usage" in result.stdout.lower()
    assert result.stderr == ""


def test_cli_invalid_pdf():
    """
    Ensure that providing a non-existent PDF path returns a non-zero exit code
    and prints a meaningful error message to stderr.
    """
    result = subprocess.run(
        [sys.executable, "-m", "pdf2mp3", "nonexistent.pdf"],
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    err = result.stderr.lower()

    # The program prints: "[error] PDF not found: <path>"
    assert "[error]" in err or "pdf not found" in err


@pytest.mark.asyncio
async def test_tts_chunk_with_retry_mocked():
    """
    Ensure that tts_chunk_with_retry fails with RuntimeError after
    exhausting retries when the underlying TTS call always fails.

    The tts_chunk function is patched to raise an Exception.
    """
    from pdf2mp3 import tts_chunk_with_retry

    # Patch the symbol where tts_chunk_with_retry resolves it
    with patch("pdf2mp3.pdf2mp3.tts_chunk", side_effect=Exception("fake error")):
        with pytest.raises(RuntimeError):
            await tts_chunk_with_retry(
                "Hello", "en-US-AriaNeural", "+0%", "+0%", retries=2
            )
