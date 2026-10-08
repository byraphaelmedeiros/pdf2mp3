"""Regressions for destructive output and unhandled CLI boundary failures."""

import os
import shutil

import pytest
from pydub import AudioSegment
from reportlab.pdfgen import canvas

import pdf2mp3.cli as cli
import pdf2mp3.pdf2mp3 as app


@pytest.mark.parametrize("kind", ["same", "symlink", "hardlink"])
def test_output_cannot_replace_input(kind, synthetic_pdf, synthetic_speech, invoke):
    original = synthetic_pdf.read_bytes()
    output = synthetic_pdf
    if kind != "same":
        output = synthetic_pdf.with_name("alias.mp3")
        if kind == "symlink":
            output.symlink_to(synthetic_pdf)
        else:
            os.link(synthetic_pdf, output)
    assert invoke("convert", synthetic_pdf, "-o", output) == 2
    assert synthetic_pdf.read_bytes() == original


@pytest.mark.parametrize("size", [0, -1])
def test_nonpositive_chunk_size_is_argument_error(size, synthetic_pdf, invoke):
    assert invoke("convert", synthetic_pdf, "--max-chars", size) == 2
    assert not synthetic_pdf.with_suffix(".mp3").exists()


def test_corrupt_pdf_has_controlled_error(tmp_path, invoke, capsys):
    path = tmp_path / "invalid.pdf"
    path.write_text("Synthetic invalid PDF")
    assert invoke("convert", path) == 6
    assert "extract" in capsys.readouterr().err.lower()


def test_directory_is_not_a_pdf(tmp_path, invoke):
    assert invoke("convert", tmp_path) == 1


def test_missing_ffmpeg_does_not_start_speech(synthetic_pdf, synthetic_speech, invoke, monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda name: None)
    assert invoke("convert", synthetic_pdf) == 2


@pytest.mark.parametrize("exception", [OSError("synthetic write error"), KeyboardInterrupt()])
def test_failed_export_preserves_destination_and_cleans_temp(
    exception, synthetic_pdf, synthetic_speech, invoke, monkeypatch
):
    output = synthetic_pdf.with_suffix(".mp3")
    output.write_bytes(b"previous audio")
    before = set(output.parent.iterdir())

    def broken_export(self, destination, **kwargs):
        with open(destination, "wb") as stream:
            stream.write(b"incomplete audio")
        raise exception

    monkeypatch.setattr(AudioSegment, "export", broken_export)
    assert invoke("convert", synthetic_pdf, "--overwrite") == (
        130 if isinstance(exception, KeyboardInterrupt) else 7
    )
    assert output.read_bytes() == b"previous audio"
    assert set(output.parent.iterdir()) == before


def test_encrypted_pdf_has_controlled_error(tmp_path, invoke):
    path = tmp_path / "encrypted.pdf"
    document = canvas.Canvas(str(path), encrypt="synthetic-password")
    document.drawString(60, 750, "Synthetic private text")
    document.save()
    assert invoke("convert", path) == 6


def test_default_conversion_preserves_input(synthetic_pdf, synthetic_speech, invoke):
    before = synthetic_pdf.read_bytes()
    assert invoke("convert", synthetic_pdf) == 0
    assert len(AudioSegment.from_mp3(synthetic_pdf.with_suffix(".mp3"))) == 100
    assert synthetic_pdf.read_bytes() == before


def test_existing_error_codes_and_empty_pdf(tmp_path, synthetic_pdf, invoke, monkeypatch):
    assert invoke("convert", tmp_path / "missing.pdf") == 1
    assert invoke("convert", synthetic_pdf, "--lang", "fr") == 2
    monkeypatch.setattr(app, "extract_text_from_pdf", lambda path: "")
    assert invoke("convert", synthetic_pdf) == 3
    monkeypatch.setattr(app, "extract_text_from_pdf", lambda path: "synthetic")
    monkeypatch.setattr(app, "clean_text", lambda text: "")
    assert invoke("convert", synthetic_pdf) == 4


@pytest.mark.parametrize("engine", ["edge", "gtts", "openai", "pyttsx3", "say"])
@pytest.mark.parametrize("custom", [False, True])
def test_engine_dispatch(engine, custom, synthetic_pdf, invoke, monkeypatch, tmp_path):
    calls = []
    segment = AudioSegment.silent(duration=80)

    async def edge(chunks, **kwargs):
        calls.append((chunks, kwargs))
        return segment

    def sync(chunks, fn):
        for chunk in chunks:
            fn(chunk)
        return segment

    def local(chunks, **kwargs):
        calls.append((chunks, kwargs))
        return segment

    monkeypatch.setattr(app, "synthesize_chunks", edge)
    monkeypatch.setattr(app, "synthesize_chunks_sync", sync)
    monkeypatch.setattr(app, "tts_chunk_gtts", lambda text, **kw: calls.append((text, kw)))
    monkeypatch.setattr(app, "tts_chunk_openai", lambda text, **kw: calls.append((text, kw)))
    monkeypatch.setattr(app, "synthesize_chunks_pyttsx3", local)
    monkeypatch.setattr(app, "synthesize_chunks_say", local)
    output = tmp_path / "nested" / "custom.mp3"
    monkeypatch.setattr(cli, "_dependencies", lambda args: [{"name": "synthetic", "ok": True}])
    args = ["convert", synthetic_pdf, "--engine", engine, "-o", output]
    if custom:
        args += ["--lang", "en"]
        if engine != "gtts":
            args += [
                "--voice",
                "en-US-AriaNeural"
                if engine == "edge"
                else "coral"
                if engine == "openai"
                else "Custom",
            ]
        if engine == "edge":
            args += ["--rate", "+5%", "--volume", "+3%"]
        elif engine == "openai":
            args += ["--model", "gpt-realtime-2.1"]
    assert invoke(*args) == 0
    assert len(AudioSegment.from_mp3(output)) == 80
    assert len(calls) == 1
    content, kwargs = calls[0]
    assert "Synthetic first sentence." in (content if isinstance(content, str) else content[0])
    if engine == "edge":
        assert kwargs == {
            "voice": "en-US-AriaNeural" if custom else "pt-BR-ThalitaNeural",
            "rate": "+5%" if custom else "+0%",
            "volume": "+3%" if custom else "+0%",
        }
    elif engine == "gtts":
        assert kwargs == {"lang": "en" if custom else "pt"}
    elif engine == "openai":
        assert kwargs == {
            "model": "gpt-realtime-2.1" if custom else app.DEFAULT_OPENAI_MODEL,
            "voice": "coral" if custom else app.DEFAULT_OPENAI_VOICE,
        }
    else:
        assert kwargs == {"voice": "Custom" if custom else None}


@pytest.mark.parametrize("stage,code", [("extract", 6), ("speech", 5), ("export", 7)])
@pytest.mark.parametrize("debug", [False, True])
def test_error_boundaries(stage, code, debug, synthetic_pdf, synthetic_speech, invoke, monkeypatch):
    def fail(*args, **kwargs):
        raise OSError("synthetic failure")

    async def speech(*args, **kwargs):
        fail()

    if stage == "extract":
        monkeypatch.setattr(app, "extract_text_from_pdf", fail)
    elif stage == "speech":
        monkeypatch.setattr(app, "synthesize_chunks", speech)
    else:
        monkeypatch.setattr(AudioSegment, "export", fail)
    assert invoke("convert", synthetic_pdf, *(["--debug"] if debug else [])) == code
    assert not synthetic_pdf.with_suffix(".mp3").exists()


@pytest.mark.parametrize("stage", ["extract", "speech"])
def test_interrupt_boundaries(stage, synthetic_pdf, invoke, monkeypatch):
    def fail(*args, **kwargs):
        raise KeyboardInterrupt()

    async def speech(*args, **kwargs):
        fail()

    monkeypatch.setattr(
        app,
        "extract_text_from_pdf" if stage == "extract" else "synthesize_chunks",
        fail if stage == "extract" else speech,
    )
    assert invoke("convert", synthetic_pdf) == 130


def test_output_parent_failure(synthetic_pdf, synthetic_speech, invoke, tmp_path):
    parent = tmp_path / "file-not-directory"
    parent.write_text("keep")
    assert invoke("convert", synthetic_pdf, "-o", parent / "out.mp3") == 7
    assert parent.read_text() == "keep"


def test_public_exports_and_module_import():
    import importlib

    import pdf2mp3

    module = importlib.import_module("pdf2mp3.__main__")
    assert module.main is pdf2mp3.main
    assert set(pdf2mp3.__all__) == {
        "normalize_lang",
        "extract_text_from_pdf",
        "clean_text",
        "split_into_chunks",
        "sanitize_for_tts",
        "tts_chunk_with_retry",
        "main",
    }
    for name in pdf2mp3.__all__:
        assert getattr(pdf2mp3, name) is getattr(app, name)
