"""Human and machine CLI contracts; all synthesis stays behind an offline double."""

import json

import pytest

import pdf2mp3.cli as cli
import pdf2mp3.pdf2mp3 as app


def response(capsys):
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert set(data) == {"schema_version", "command", "ok", "data", "error"}
    assert data["schema_version"] == 1
    return data, captured.err


def test_check_prepares_pdf_without_speech_or_writes(synthetic_pdf, invoke, monkeypatch, capsys):
    before = set(synthetic_pdf.parent.iterdir())
    original = synthetic_pdf.read_bytes()

    async def forbidden(*args, **kwargs):
        pytest.fail("check must not synthesize")

    monkeypatch.setattr(app, "synthesize_chunks", forbidden)
    assert invoke("check", synthetic_pdf, "--json") == 0
    result, _ = response(capsys)
    assert result["command"] == "check" and result["ok"] and result["error"] is None
    assert result["data"]["chunks"] > 0
    assert result["data"]["characters"] > 0
    assert result["data"]["external_processing"] is True
    assert result["data"]["speech_verified"] is False
    assert result["data"]["voice"] == "pt-BR-ThalitaNeural"
    assert all(item["ok"] for item in result["data"]["checks"])
    assert synthetic_pdf.read_bytes() == original
    assert set(synthetic_pdf.parent.iterdir()) == before


@pytest.mark.parametrize("prefix", [True, False])
def test_json_conversion_has_clean_stdout(prefix, synthetic_pdf, synthetic_speech, invoke, capsys):
    args = ["convert", synthetic_pdf]
    args = ["--json", *args] if prefix else [*args, "--json"]
    assert invoke(*args) == 0
    result, diagnostic = response(capsys)
    assert result["ok"] and result["command"] == "convert"
    assert result["data"]["output"] == str(synthetic_pdf.with_suffix(".mp3"))
    assert result["data"]["duration_seconds"] == 0.1
    assert "Synthetic first" not in diagnostic


@pytest.mark.parametrize(
    "args",
    [
        ["convert"],
        ["convert", "--max-chars", "oops"],
        ["wrong-command"],
        ["--json"],
        ["convert", "file.pdf", "--eng", "edge"],
        ["convert", "file.pdf", "--say-voice", "Samantha"],
    ],
)
def test_argument_errors_are_json(args, invoke, capsys):
    assert invoke("--json", *args) == 2
    result, _ = response(capsys)
    assert not result["ok"]
    assert result["error"]["code"] == "invalid_arguments"
    assert result["error"]["exit_code"] == 2


@pytest.mark.parametrize(
    "flags",
    [
        ["--engine", "say", "--rate=+0%"],
        ["--engine", "gtts", "--voice", "anything"],
        ["--engine", "edge", "--model", "anything"],
        ["--rate=oops"],
        ["--volume=1.5%"],
        ["--max-chars", "0"],
        ["--voice", ""],
        ["--lang", "fr"],
    ],
)
def test_invalid_configuration_precedes_extraction(
    flags, synthetic_pdf, invoke, monkeypatch, capsys
):
    def forbidden(*args):
        pytest.fail("invalid options must be rejected before extraction")

    monkeypatch.setattr(app, "extract_text_from_pdf", forbidden)
    assert invoke("convert", synthetic_pdf, "--json", *flags) == 2
    result, _ = response(capsys)
    assert result["error"]["code"] == "invalid_arguments"


def test_negative_percentages_with_spaces(synthetic_pdf, invoke, monkeypatch, capsys):
    from pydub import AudioSegment

    calls = []

    async def speak(chunks, **kwargs):
        calls.append(kwargs)
        return AudioSegment.silent(duration=80)

    monkeypatch.setattr(app, "synthesize_chunks", speak)
    assert invoke("convert", synthetic_pdf, "--rate", "-5%", "--volume", "-10%", "--json") == 0
    assert calls == [{"voice": "pt-BR-ThalitaNeural", "rate": "-5%", "volume": "-10%"}]
    assert response(capsys)[0]["ok"]


def test_existing_output_requires_overwrite(synthetic_pdf, synthetic_speech, invoke, capsys):
    output = synthetic_pdf.with_suffix(".mp3")
    output.write_bytes(b"previous audio")
    assert invoke("convert", synthetic_pdf, "--json") == 2
    assert response(capsys)[0]["error"]["code"] == "output_exists"
    assert output.read_bytes() == b"previous audio"
    assert invoke("convert", synthetic_pdf, "--overwrite", "--json") == 0
    assert response(capsys)[0]["ok"]
    assert output.read_bytes() != b"previous audio"


def test_destination_created_during_synthesis_is_preserved(
    synthetic_pdf, invoke, monkeypatch, capsys
):
    from pydub import AudioSegment

    output = synthetic_pdf.with_suffix(".mp3")

    async def speak(*args, **kwargs):
        output.write_bytes(b"another process output")
        return AudioSegment.silent(duration=80)

    monkeypatch.setattr(app, "synthesize_chunks", speak)
    before = set(synthetic_pdf.parent.iterdir())
    assert invoke("convert", synthetic_pdf, "--json") == 2
    assert response(capsys)[0]["error"]["code"] == "output_exists"
    assert output.read_bytes() == b"another process output"
    assert set(synthetic_pdf.parent.iterdir()) == before | {output}


def test_debug_does_not_expose_exception_values(synthetic_pdf, invoke, monkeypatch, capsys):
    def fail(*args):
        raise OSError("SECRET_SYNTHETIC_TOKEN private document text")

    monkeypatch.setattr(app, "extract_text_from_pdf", fail)
    assert invoke("convert", synthetic_pdf, "--json", "--debug") == 6
    result, diagnostic = response(capsys)
    assert result["error"]["code"] == "pdf_failed"
    assert "OSError" in diagnostic
    assert "SECRET_SYNTHETIC_TOKEN" not in diagnostic
    assert "private document text" not in diagnostic


@pytest.mark.parametrize(
    "args", [[], ["--help"], ["--version"], ["convert", "--help"], ["check", "--help"]]
)
def test_informational_commands(args, invoke, capsys):
    assert invoke(*args) == 0
    captured = capsys.readouterr()
    assert captured.out.startswith("pdf2mp3 2.0.1" if args == ["--version"] else "usage: pdf2mp3")
    assert not captured.err


def test_check_without_input_and_quiet_conversion(synthetic_pdf, synthetic_speech, invoke, capsys):
    assert invoke("check", "--json") == 0
    data = response(capsys)[0]["data"]
    assert data["input"] is None and data["output"] is None
    assert data["chunks"] == data["characters"] == 0
    assert invoke("--quiet", "convert", synthetic_pdf) == 0
    captured = capsys.readouterr()
    assert captured.out.startswith("Saved ") and not captured.err
    assert invoke("check", "--overwrite") == 2
    assert "require an INPUT" in capsys.readouterr().err


@pytest.mark.parametrize(
    "stage,code,error",
    [
        ("extract", 6, "pdf_failed"),
        ("speech", 5, "speech_failed"),
        ("export", 7, "output_failed"),
    ],
)
@pytest.mark.parametrize("interrupt", [False, True])
def test_json_failure_stages(
    stage, code, error, interrupt, synthetic_pdf, synthetic_speech, invoke, monkeypatch, capsys
):
    from pydub import AudioSegment

    def fail(*args, **kwargs):
        print("provider diagnostics")
        raise KeyboardInterrupt() if interrupt else OSError("private synthetic detail")

    async def speech(*args, **kwargs):
        fail()

    if stage == "extract":
        monkeypatch.setattr(app, "extract_text_from_pdf", fail)
    elif stage == "speech":
        monkeypatch.setattr(app, "synthesize_chunks", speech)
    else:
        monkeypatch.setattr(AudioSegment, "export", fail)
    assert invoke("convert", synthetic_pdf, "--json", "--debug") == (130 if interrupt else code)
    result, diagnostic = response(capsys)
    assert result["error"]["code"] == ("interrupted" if interrupt else error)
    assert "provider diagnostics" in diagnostic
    assert "private synthetic detail" not in diagnostic
    assert not synthetic_pdf.with_suffix(".mp3").exists()


@pytest.mark.parametrize(
    "kind,code,error",
    [("corrupt", 6, "pdf_failed"), ("scan", 3, "no_text"), ("cleaned", 4, "empty_text")],
)
def test_json_pdf_failures(kind, code, error, synthetic_pdf, invoke, monkeypatch, capsys):
    from reportlab.pdfgen import canvas

    if kind == "corrupt":
        synthetic_pdf.write_text("Synthetic corrupt PDF")
    elif kind == "scan":
        document = canvas.Canvas(str(synthetic_pdf))
        document.showPage()
        document.save()
    else:
        monkeypatch.setattr(app, "clean_text", lambda raw: "")
    original = synthetic_pdf.read_bytes()
    assert invoke("check", synthetic_pdf, "--json") == code
    assert response(capsys)[0]["error"]["code"] == error
    assert synthetic_pdf.read_bytes() == original


@pytest.mark.parametrize(
    "engine,platform,missing",
    [
        ("edge", "linux", "ffprobe"),
        ("gtts", "linux", "gtts"),
        ("openai", "linux", "OPENAI_API_KEY"),
        ("pyttsx3", "darwin", "objc"),
        ("pyttsx3", "linux", "espeak"),
        ("say", "win32", "macOS say"),
    ],
)
def test_dependency_checks_do_not_initialize_providers(
    engine, platform, missing, invoke, monkeypatch, capsys
):
    monkeypatch.setattr(cli.sys, "platform", platform)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(
        cli.importlib.util, "find_spec", lambda name: None if name == missing else object()
    )
    monkeypatch.setattr(
        cli.shutil,
        "which",
        lambda name: None if name in {missing, "espeak-ng"} else "/synthetic/bin",
    )
    assert invoke("check", "--engine", engine, "--json") == 2
    result, _ = response(capsys)
    assert result["error"]["code"] == "dependency_missing"
    assert {item["name"] for item in result["data"]["checks"] if not item["ok"]} == {missing}


@pytest.mark.parametrize(
    "engine,platform",
    [
        ("openai", "linux"),
        ("pyttsx3", "linux"),
        ("pyttsx3", "win32"),
        ("pyttsx3", "darwin"),
        ("say", "darwin"),
    ],
)
def test_ready_optional_provider_check(engine, platform, invoke, monkeypatch, capsys):
    monkeypatch.setattr(cli.sys, "platform", platform)
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-key")
    monkeypatch.setattr(cli.importlib.util, "find_spec", lambda name: object())
    monkeypatch.setattr(cli.shutil, "which", lambda name: "/synthetic/bin")
    assert invoke("check", "--engine", engine, "--json") == 0
    data = response(capsys)[0]["data"]
    assert data["external_processing"] == (engine == "openai")
    assert not data["speech_verified"]


@pytest.mark.parametrize("voice,exit_code", [("Samantha", 0), ("Synthetic missing voice", 2)])
def test_say_voice_inventory_no_speech(voice, exit_code, invoke, monkeypatch, capsys):
    from types import SimpleNamespace

    monkeypatch.setattr(cli.sys, "platform", "darwin")
    monkeypatch.setattr(cli.shutil, "which", lambda name: "/synthetic/bin")

    def inventory(args, **kwargs):
        assert args == ["say", "-v", "?"]
        assert kwargs == dict(capture_output=True, text=True, check=True, timeout=5)
        return SimpleNamespace(
            stdout="Samantha    en_US # Synthetic\nLuciana (Portuguese (Brazil)) pt_BR # Synthetic"
        )

    monkeypatch.setattr(cli.subprocess, "run", inventory)
    assert invoke("check", "--engine", "say", "--voice", voice, "--json") == exit_code
    assert response(capsys)[0]["ok"] == (exit_code == 0)


def test_dependency_probe_failure_is_safe(invoke, monkeypatch, capsys):
    def fail(*args):
        raise OSError("synthetic sensitive detail")

    monkeypatch.setattr(cli.shutil, "which", fail)
    assert invoke("check", "--json") == 2
    result, _ = response(capsys)
    assert result["error"]["code"] == "dependency_missing"
    assert "sensitive" not in result["error"]["message"]


@pytest.mark.parametrize("options", [["--voice", "Custom"], ["--model", ""], ["--voice", "a\nb"]])
def test_reject_invalid_names(options, synthetic_pdf, invoke, capsys):
    assert invoke("convert", synthetic_pdf, "--json", *options) == 2
    assert response(capsys)[0]["error"]["code"] == "invalid_arguments"


@pytest.mark.parametrize("replace_reservation", [False, True])
def test_failed_final_commit_cleans_only_owned_reservation(
    replace_reservation, synthetic_pdf, synthetic_speech, invoke, monkeypatch, capsys
):
    from pathlib import Path

    output = synthetic_pdf.with_suffix(".mp3")
    original = synthetic_pdf.read_bytes()
    before = set(output.parent.iterdir())

    def fail(path, destination):
        if replace_reservation:
            # Keep the old inode allocated without open handles (also works on Windows).
            output.rename(output.with_suffix(".reservation"))
            output.write_bytes(b"another process output")
        raise OSError("synthetic rename failure")

    monkeypatch.setattr(Path, "replace", fail)
    assert invoke("convert", synthetic_pdf, "--json") == 7
    assert response(capsys)[0]["error"]["code"] == "output_failed"
    if replace_reservation:
        assert output.read_bytes() == b"another process output"
        output.with_suffix(".reservation").unlink()
    assert set(output.parent.iterdir()) == before | ({output} if replace_reservation else set())
    assert synthetic_pdf.read_bytes() == original


def test_missing_input_json_and_path_validation(synthetic_pdf, invoke, monkeypatch, capsys):
    from pathlib import Path

    assert invoke("convert", synthetic_pdf.with_name("missing.pdf"), "--json") == 1
    assert response(capsys)[0]["error"]["code"] == "input_missing"

    def fail(*args):
        raise OSError("synthetic path error")

    monkeypatch.setattr(Path, "resolve", fail)
    assert invoke("check", synthetic_pdf, "--json") == 2
    assert response(capsys)[0]["error"]["code"] == "invalid_arguments"


def test_sentinel_keeps_argument_contents(invoke, capsys):
    assert invoke("convert", "--", "--json") == 1
    captured = capsys.readouterr()
    assert not captured.out and "input_missing" in captured.err


def test_no_document_preview_in_progress(synthetic_pdf, invoke, monkeypatch, capsys):
    from pydub.generators import Sine

    data = Sine(440).to_audio_segment(duration=80).export(format="mp3").read()

    async def speech(*args, **kwargs):
        return data

    monkeypatch.setattr(app, "tts_chunk", speech)
    assert invoke("convert", synthetic_pdf, "--json") == 0
    result, diagnostic = response(capsys)
    assert result["ok"] and "TTS chunk 1/1" in diagnostic
    assert "Synthetic first" not in diagnostic


def test_human_check_reports_configuration(invoke, capsys):
    assert invoke("check") == 0
    captured = capsys.readouterr()
    assert "Local checks passed for edge" in captured.out
    assert "External text processing: yes" in captured.out


def test_exported_main_keeps_success_return_contract(monkeypatch, capsys):
    import sys

    monkeypatch.setattr(sys, "argv", ["pdf2mp3", "check"])
    assert app.main() is None
    assert "Local checks passed" in capsys.readouterr().out


def test_empty_output_is_invalid_before_extraction(synthetic_pdf, invoke, monkeypatch, capsys):
    def forbidden(*args):
        pytest.fail("empty destination must be rejected before extraction")

    monkeypatch.setattr(app, "extract_text_from_pdf", forbidden)
    assert invoke("convert", synthetic_pdf, "--output", "", "--json") == 2
    assert response(capsys)[0]["error"]["code"] == "invalid_arguments"
