"""Offline request, codec and cleanup contracts for optional voice engines."""

import builtins
import sys
from importlib.machinery import ModuleSpec
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydub import AudioSegment

import pdf2mp3.pdf2mp3 as app
from pdf2mp3 import cli


@pytest.mark.parametrize("provider", ["gtts", "openai", "pyttsx3"])
def test_missing_optional_package_has_install_hint(monkeypatch, provider):
    original = builtins.__import__

    def importing(name, *args, **kwargs):
        if name == provider:
            raise ImportError("synthetic missing package")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", importing)
    with pytest.raises(RuntimeError, match="not installed"):
        if provider == "gtts":
            app.tts_chunk_gtts("text", "en")
        elif provider == "openai":
            app.tts_chunk_openai("text", "gpt-realtime-2.1-mini", "alloy")
        else:
            app.synthesize_chunks_pyttsx3(["text"], None)


def test_gtts_request_and_bytes(monkeypatch):
    class Google:
        def __init__(self, *, text, lang):
            assert (text, lang) == ("synthetic", "pt-br")

        def write_to_fp(self, stream):
            stream.write(b"speech bytes")

    monkeypatch.setitem(sys.modules, "gtts", SimpleNamespace(gTTS=Google))
    assert app.tts_chunk_gtts("synthetic", "pt-br") == b"speech bytes"


def test_synchronous_audio_join():
    calls = []
    data = AudioSegment.silent(duration=100).export(format="mp3").read()

    def speech(text):
        calls.append(text)
        return data

    assert len(app.synthesize_chunks_sync(["one", "two"], speech)) == 440
    assert calls == ["one", "two"]
    assert len(app.synthesize_chunks_sync([], speech)) == 0


@pytest.mark.parametrize(
    ("platform", "voice", "objc_state"),
    [
        ("linux", None, "absent"),
        ("linux", "Synthetic", "absent"),
        ("linux", "voice-id", "absent"),
        ("linux", "unknown", "absent"),
        ("darwin", None, "absent"),
        ("darwin", None, "existing"),
        ("darwin", None, "missing-package"),
    ],
)
def test_local_engine_voice_selection_audio_and_cleanup(monkeypatch, platform, voice, objc_state):
    paths = []
    settings = []
    original_objc = object()
    monkeypatch.setattr(app.sys, "platform", platform)
    monkeypatch.delattr(builtins, "objc", raising=False)
    if objc_state == "existing":
        monkeypatch.setattr(builtins, "objc", original_objc, raising=False)
    monkeypatch.setitem(
        sys.modules, "objc", None if objc_state == "missing-package" else SimpleNamespace()
    )

    class Local:
        def getProperty(self, name):
            assert name == "voices"
            return [
                SimpleNamespace(name=None, id=None),
                SimpleNamespace(name="Synthetic", id="voice-id"),
            ]

        def setProperty(self, name, value):
            settings.append((name, value))

        def save_to_file(self, text, path):
            assert text == "synthetic"
            paths.append(Path(path))
            AudioSegment.silent(duration=100).export(path, format="wav").close()

        def runAndWait(self):
            pass

    monkeypatch.setitem(sys.modules, "pyttsx3", SimpleNamespace(init=Local))
    if voice == "unknown":
        with pytest.raises(RuntimeError, match="voice is not installed"):
            app.synthesize_chunks_pyttsx3(["synthetic"], voice)
        assert not paths and not settings
        return
    assert len(app.synthesize_chunks_pyttsx3(["synthetic"], voice)) == 220
    assert settings == ([("voice", "voice-id")] if voice in ("Synthetic", "voice-id") else [])
    assert all(not path.exists() for path in paths)
    if objc_state == "existing":
        assert builtins.objc is original_objc
    else:
        assert not hasattr(builtins, "objc")


@pytest.mark.parametrize("message", ["objc unavailable", "other failure"])
def test_local_engine_failure_cleans_file(monkeypatch, message):
    paths = []

    def save(text, path):
        paths.append(Path(path))
        raise NameError(message)

    monkeypatch.setattr(app.sys, "platform", "linux")
    monkeypatch.setitem(
        sys.modules, "pyttsx3", SimpleNamespace(init=lambda: SimpleNamespace(save_to_file=save))
    )
    with pytest.raises(RuntimeError if "objc" in message else NameError):
        app.synthesize_chunks_pyttsx3(["synthetic"], None)
    assert paths and not paths[0].exists()


def test_pyttsx3_empty_audio_fails_and_preserves_input_and_output(
    monkeypatch, synthetic_pdf, invoke, tmp_path, capsys
):
    paths = []

    def save(text, path):
        paths.append(Path(path))
        AudioSegment.silent(duration=0).export(path, format="wav").close()

    engine = SimpleNamespace(save_to_file=save, runAndWait=lambda: None)
    monkeypatch.setattr(
        cli, "_dependencies", lambda args: [{"name": "synthetic local engine", "ok": True}]
    )
    monkeypatch.setitem(
        sys.modules,
        "pyttsx3",
        SimpleNamespace(init=lambda: engine, __spec__=ModuleSpec("pyttsx3", loader=None)),
    )
    output = tmp_path / "previous.mp3"
    output.write_bytes(b"previous synthetic audio")
    original = synthetic_pdf.read_bytes()
    assert invoke("convert", synthetic_pdf, "--engine", "pyttsx3", "-o", output, "--overwrite") == 5
    assert "speech_failed" in capsys.readouterr().err
    assert output.read_bytes() == b"previous synthetic audio"
    assert synthetic_pdf.read_bytes() == original
    assert paths and all(not path.exists() for path in paths)


def test_say_rejects_other_platforms(monkeypatch):
    monkeypatch.setattr(app.sys, "platform", "linux")
    with pytest.raises(RuntimeError, match="macOS"):
        app.synthesize_chunks_say(["text"], None)


@pytest.mark.parametrize("voice", [None, "Synthetic"])
@pytest.mark.parametrize("returncode", [0, 1])
@pytest.mark.parametrize(
    "text",
    ["synthetic", "--input-file=/synthetic/private.txt", "--output-file=/synthetic/previous.aiff"],
)
def test_say_arguments_audio_and_cleanup(monkeypatch, voice, returncode, text):
    monkeypatch.setattr(app.sys, "platform", "darwin")
    paths = []

    def run(args, **kwargs):
        assert args[0:2] == ["say", "-o"]
        assert args[3:] == (["-v", "Synthetic"] if voice else [])
        assert kwargs == dict(check=False, capture_output=True, text=True, input=text)
        path = Path(args[2])
        paths.append(path)
        AudioSegment.silent(duration=100).export(path, format="aiff").close()
        return SimpleNamespace(returncode=returncode, stderr="synthetic failure", stdout="")

    monkeypatch.setattr(app.subprocess, "run", run)
    if returncode:
        with pytest.raises(RuntimeError, match="synthetic failure"):
            app.synthesize_chunks_say([text], voice)
    else:
        assert len(app.synthesize_chunks_say([text], voice)) == 220
    assert paths and not paths[0].exists()


def test_say_empty_audio_is_a_synthesis_failure(
    monkeypatch, synthetic_pdf, invoke, tmp_path, capsys
):
    """macOS can return success with a header-only AIFF when speech access is blocked."""
    monkeypatch.setattr(app.sys, "platform", "darwin")
    monkeypatch.setattr(
        cli, "_dependencies", lambda args: [{"name": "synthetic local engine", "ok": True}]
    )
    paths = []

    def run(args, **kwargs):
        path = Path(args[2])
        paths.append(path)
        AudioSegment.silent(duration=0).export(path, format="aiff").close()
        return SimpleNamespace(returncode=0, stderr="", stdout="")

    monkeypatch.setattr(app.subprocess, "run", run)
    output = tmp_path / "previous.mp3"
    output.write_bytes(b"previous audio")
    original = synthetic_pdf.read_bytes()
    assert (
        invoke("convert", synthetic_pdf, "--engine", "say", "--output", output, "--overwrite") == 5
    )
    assert "speech_failed" in capsys.readouterr().err
    assert output.read_bytes() == b"previous audio"
    assert synthetic_pdf.read_bytes() == original
    assert paths and all(not path.exists() for path in paths)
