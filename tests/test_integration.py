"""
Integration tests for pdf2mp3.

These tests validate partial integration flows without relying on
external services (e.g., network TTS).
"""

from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from pdf2mp3 import extract_text_from_pdf, split_into_chunks, sanitize_for_tts


def create_sample_pdf(path: Path, text: str = "Hello from pdf2mp3 test!"):
    """
    Create a simple one-page PDF with the given text using reportlab.
    """
    c = canvas.Canvas(str(path), pagesize=letter)
    c.drawString(100, 750, text)
    c.save()


def test_extract_text_from_pdf_returns_string(tmp_path):
    """
    Ensure that extract_text_from_pdf successfully extracts text
    from a valid PDF file generated during the test.
    """
    pdf_file = tmp_path / "test.pdf"
    create_sample_pdf(pdf_file, "Integration test PDF content")

    text = extract_text_from_pdf(pdf_file)
    assert isinstance(text, str)
    assert "Integration test PDF content" in text


def test_pipeline_chunking():
    """
    Ensure that splitting and sanitizing text produces valid chunks.
    """
    text = "This is sentence one. This is sentence two. This is sentence three."
    chunks = [sanitize_for_tts(c) for c in split_into_chunks(text, max_chars=25)]
    assert len(chunks) >= 2
    assert all(isinstance(c, str) for c in chunks)
