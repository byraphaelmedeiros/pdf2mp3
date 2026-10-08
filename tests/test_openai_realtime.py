"""Offline OpenAI Realtime protocol, narration and real MP3 contracts."""

import asyncio
import base64
import json
import sys
from contextlib import asynccontextmanager
from io import BytesIO
from types import SimpleNamespace

import pytest
from pydub import AudioSegment
from pydub.generators import Sine

import pdf2mp3.cli as cli
import pdf2mp3.pdf2mp3 as app


@pytest.fixture
def realtime(monkeypatch):
    state = {"sent": [], "closed": [], "events": []}

    class Connection:
        def __init__(self):
            self.response = SimpleNamespace(create=self.create)

        async def create(self, **kwargs):
            state["sent"].append(kwargs)

        def __aiter__(self):
            return self.events()

        async def events(self):
            for event in state["events"]:
                if isinstance(event, BaseException):
                    raise event
                yield event
            if state.get("stall"):
                await asyncio.sleep(60)

    class Client:
        def __init__(self, **kwargs):
            state["client"] = kwargs
            self.realtime = self

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            state["closed"].append("client")

        @asynccontextmanager
        async def connect(self, **kwargs):
            state["connect"] = kwargs
            try:
                yield Connection()
            finally:
                state["closed"].append("connection")

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(AsyncOpenAI=Client))
    pcm = Sine(440, sample_rate=24000).to_audio_segment(duration=100).raw_data
    state["pcm"] = pcm
    state["events"] = [
        SimpleNamespace(type="session.created"),
        SimpleNamespace(
            type="response.output_audio.delta", delta=base64.b64encode(pcm[:301]).decode()
        ),
        SimpleNamespace(
            type="response.output_audio.delta", delta=base64.b64encode(pcm[301:]).decode()
        ),
        SimpleNamespace(
            type="response.output_audio_transcript.done", transcript="Synthetic narration."
        ),
        SimpleNamespace(type="response.done", response=SimpleNamespace(status="completed")),
    ]
    return state


def test_realtime_request_produces_real_mp3_and_closes_resources(realtime):
    data = app.tts_chunk_openai("Synthetic narration.", "gpt-realtime-2.1-mini", "alloy")
    audio = AudioSegment.from_mp3(BytesIO(data))
    assert 95 <= len(audio) <= 105 and audio.rms > 0
    assert audio.channels == 1 and audio.frame_rate == 24000
    assert realtime["connect"] == {"model": "gpt-realtime-2.1-mini"}
    request = realtime["sent"][0]["response"]
    assert request["conversation"] == "none"
    assert request["output_modalities"] == ["audio"]
    assert request["audio"] == {
        "output": {"voice": "alloy", "format": {"type": "audio/pcm", "rate": 24000}}
    }
    assert request["input"] == [
        {
            "type": "message",
            "role": "user",
            "content": [{"type": "input_text", "text": "Synthetic narration."}],
        }
    ]
    assert request["tools"] == [] and request["tool_choice"] == "none"
    assert "verbatim" in request["instructions"]
    assert realtime["client"]["max_retries"] == 0
    assert realtime["closed"] == ["connection", "client"]


@pytest.mark.parametrize("status", ["failed", "cancelled", "incomplete"])
def test_partial_response_is_not_exported(status, realtime):
    realtime["events"][-1].response.status = status
    with pytest.raises(RuntimeError, match="complete"):
        app.tts_chunk_openai("Synthetic narration.", "gpt-realtime-2.1-mini", "alloy")
    assert realtime["closed"] == ["connection", "client"]


@pytest.mark.parametrize(
    "problem",
    [
        "error",
        "disconnect",
        "invalid_base64",
        "empty",
        "odd_pcm",
        "missing_transcript",
        "changed_words",
    ],
)
def test_invalid_response_cannot_be_reported_as_speech(problem, realtime):
    events = realtime["events"]
    if problem == "error":
        events.insert(0, SimpleNamespace(type="error", error="synthetic private content"))
    elif problem == "disconnect":
        events.pop()
    elif problem == "invalid_base64":
        events[1].delta = "!!!"
    elif problem == "empty":
        events[:] = events[3:]
    elif problem == "odd_pcm":
        events[2].delta = base64.b64encode(realtime["pcm"][301:-1]).decode()
    elif problem == "missing_transcript":
        events.pop(3)
    else:
        events[3].transcript = "Invented narration."
    with pytest.raises((RuntimeError, ValueError)):
        app.tts_chunk_openai("Synthetic narration.", "gpt-realtime-2.1-mini", "alloy")
    assert realtime["closed"] == ["connection", "client"]


def test_narration_comparison_ignores_case_punctuation_and_spacing(realtime):
    realtime["events"][3].transcript = "  SYNTHETIC\n narration! "
    assert app.tts_chunk_openai("Synthetic narration.", "gpt-realtime-2.1-mini", "coral")


def test_cli_realtime_conversion_keeps_json_and_audio_contract(
    realtime, synthetic_pdf, invoke, monkeypatch, capsys
):
    original = synthetic_pdf.read_bytes()
    realtime["events"][3].transcript = "Synthetic first sentence. Synthetic second sentence."
    monkeypatch.setattr(cli, "_dependencies", lambda args: [{"name": "synthetic", "ok": True}])
    assert invoke("convert", synthetic_pdf, "--engine", "openai", "--json") == 0
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert result["ok"] and result["data"]["model"] == "gpt-realtime-2.1-mini"
    audio = AudioSegment.from_mp3(synthetic_pdf.with_suffix(".mp3"))
    assert 215 <= len(audio) <= 225 and audio.rms > 0
    assert synthetic_pdf.read_bytes() == original
    assert "Synthetic first" not in captured.out + captured.err


def test_check_requires_websocket_extra_without_importing_sdk(invoke, monkeypatch, capsys):
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-key")
    monkeypatch.setattr(
        cli.importlib.util, "find_spec", lambda name: None if name == "websockets" else object()
    )
    assert invoke("check", "--engine", "openai", "--json") == 2
    result = json.loads(capsys.readouterr().out)
    assert result["error"]["code"] == "dependency_missing"
    assert {item["name"] for item in result["data"]["checks"] if not item["ok"]} == {"websockets"}


def test_realtime_timeout_closes_resources(realtime, monkeypatch):
    import pdf2mp3.openai_tts as provider

    monkeypatch.setattr(provider, "TIMEOUT_SECONDS", 0.01)
    realtime["events"] = []
    realtime["stall"] = True
    with pytest.raises(TimeoutError):
        app.tts_chunk_openai("Synthetic narration.", "gpt-realtime-2.1-mini", "alloy")
    assert realtime["closed"] == ["connection", "client"]


@pytest.mark.parametrize("interrupt", [False, True])
def test_cli_realtime_failure_preserves_files_and_private_text(
    realtime, synthetic_pdf, invoke, monkeypatch, capsys, interrupt
):
    output = synthetic_pdf.with_suffix(".mp3")
    output.write_bytes(b"previous synthetic audio")
    original = synthetic_pdf.read_bytes()
    realtime["events"] = (
        [KeyboardInterrupt()]
        if interrupt
        else [SimpleNamespace(type="error", error="synthetic private text")]
    )
    monkeypatch.setattr(cli, "_dependencies", lambda args: [{"name": "synthetic", "ok": True}])
    assert invoke(
        "convert", synthetic_pdf, "--engine", "openai", "--overwrite", "--json", "--debug"
    ) == (130 if interrupt else 5)
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert result["error"]["code"] == ("interrupted" if interrupt else "speech_failed")
    assert "synthetic private text" not in captured.out + captured.err
    assert output.read_bytes() == b"previous synthetic audio"
    assert synthetic_pdf.read_bytes() == original
    assert realtime["closed"] == ["connection", "client"]


@pytest.mark.parametrize(
    "options", [["--model", "tts-1"], ["--model", "gpt-4o-mini-tts"], ["--voice", "nova"]]
)
def test_cli_rejects_speech_api_options_before_extraction(
    options, synthetic_pdf, invoke, monkeypatch, capsys
):
    def forbidden(*args):
        pytest.fail("invalid Realtime settings must fail before extraction")

    monkeypatch.setattr(app, "extract_text_from_pdf", forbidden)
    assert invoke("convert", synthetic_pdf, "--engine", "openai", *options, "--json") == 2
    result = json.loads(capsys.readouterr().out)
    assert result["error"]["code"] == "invalid_arguments"
