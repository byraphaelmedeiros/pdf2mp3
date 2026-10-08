"""The reusable demo is synthetic, extractable and works through the real codec path."""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from pydub import AudioSegment
from pydub.generators import Sine

import pdf2mp3.pdf2mp3 as app


@pytest.mark.parametrize(
    ("lang", "expected", "voice"),
    [
        ("pt-br", "Olá! Este documento contém apenas texto sintético.", "pt-BR-ThalitaNeural"),
        ("en", "Hello! This document contains only synthetic text.", "en-US-AriaNeural"),
    ],
)
def test_demo_extracts_and_converts(lang, expected, voice, tmp_path, monkeypatch, invoke):
    from scripts.create_demo_pdf import create_demo_pdf

    pdf = tmp_path / "demo.pdf"
    create_demo_pdf(pdf, lang)
    original = pdf.read_bytes()
    assert expected in app.extract_text_from_pdf(pdf)
    calls = []
    tone = Sine(440).to_audio_segment(duration=200).export(format="mp3").read()

    async def speech(text, **kwargs):
        calls.append((text, kwargs))
        return tone

    monkeypatch.setattr(app, "tts_chunk", speech)
    output = tmp_path / "audio" / "demo.mp3"
    assert invoke("convert", pdf, "--lang", lang, "--output", output) == 0
    assert calls and expected in calls[0][0]
    assert all(kwargs["voice"] == voice for _, kwargs in calls)
    audio = AudioSegment.from_mp3(output)
    assert 300 <= len(audio) <= 400
    assert audio.rms > 0
    assert pdf.read_bytes() == original


def test_demo_generator_preserves_existing_file(tmp_path):
    from scripts.create_demo_pdf import create_demo_pdf

    pdf = tmp_path / "demo.pdf"
    pdf.write_bytes(b"existing document")
    with pytest.raises(FileExistsError):
        create_demo_pdf(pdf, "pt-br")
    assert pdf.read_bytes() == b"existing document"


def run_generator(work, *arguments):
    """Run the actual generator with all external network access blocked."""
    root = Path(__file__).resolve().parents[1]
    return subprocess.run(
        [
            sys.executable,
            "-c",
            "from scripts.network_guard import block_network; block_network(); "
            "import runpy, sys; script = sys.argv[1]; sys.argv = sys.argv[1:]; "
            "runpy.run_path(script, run_name='__main__')",
            str(root / "scripts/create_demo_pdf.py"),
            *map(str, arguments),
        ],
        cwd=work,
        env={**os.environ, "PYTHONPATH": str(root)},
        capture_output=True,
        text=True,
        timeout=15,
    )


def test_generator_default_creates_local_input_directory(tmp_path):
    result = run_generator(tmp_path)
    assert result.returncode == 0, result.stderr
    pdf = tmp_path / "local/inputs/demo.pdf"
    assert pdf.is_file() and not (tmp_path / "demo.pdf").exists()
    assert "texto sintético" in app.extract_text_from_pdf(pdf)


def test_generator_custom_nested_destination_creates_parents(tmp_path):
    pdf = tmp_path / "custom/inputs/english.pdf"
    result = run_generator(tmp_path, "--lang", "en", "--output", pdf)
    assert result.returncode == 0, result.stderr
    assert "synthetic text" in app.extract_text_from_pdf(pdf)
    assert not (tmp_path / "local").exists()


def test_generator_default_refuses_overwrite(tmp_path):
    pdf = tmp_path / "local/inputs/demo.pdf"
    pdf.parent.mkdir(parents=True)
    pdf.write_bytes(b"existing synthetic sample")
    result = run_generator(tmp_path)
    assert result.returncode == 2
    assert pdf.read_bytes() == b"existing synthetic sample"
