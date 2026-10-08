"""Speech boundary contracts, retry timing and real codec assembly."""

import asyncio
from io import BytesIO

import pytest
from pydub import AudioSegment
from pydub.generators import Sine

import pdf2mp3.pdf2mp3 as app


@pytest.mark.asyncio
async def test_stream_collects_audio_and_ignores_metadata(monkeypatch):
    class Communicate:
        def __init__(self, **kwargs):
            assert kwargs == dict(text="Synthetic", voice="voice", rate="+5%", volume="+0%")

        async def stream(self):
            yield {"type": "WordBoundary", "offset": 0, "duration": 1, "text": "Synthetic"}
            yield {"type": "audio", "data": b"first"}
            yield {"type": "audio", "data": b"second"}

    monkeypatch.setattr(app.edge_tts, "Communicate", Communicate)
    assert await app.tts_chunk("Synthetic", "voice", "+5%", "+0%") == b"firstsecond"


@pytest.mark.asyncio
async def test_retry_recovers_preserving_arguments_and_backoff(monkeypatch):
    attempts = []
    delays = []

    async def request(text, **kwargs):
        attempts.append((text, kwargs))
        if len(attempts) < 3:
            raise TimeoutError("synthetic transient failure")
        return b"audio"

    async def sleep(delay):
        delays.append(delay)

    monkeypatch.setattr(app, "tts_chunk", request)
    monkeypatch.setattr(app.asyncio, "sleep", sleep)
    monkeypatch.setattr(app.random, "uniform", lambda a, b: 0.25)
    assert await app.tts_chunk_with_retry("sample", "v", "+1%", "+2%", base_backoff=2) == b"audio"
    assert delays == [2.25, 4.25]
    assert attempts == [("sample", dict(voice="v", rate="+1%", volume="+2%"))] * 3


@pytest.mark.asyncio
async def test_retry_exhaustion_stops_without_final_sleep(monkeypatch):
    attempts = []
    delays = []

    async def request(*args, **kwargs):
        attempts.append(1)
        raise OSError("synthetic failure")

    async def sleep(delay):
        delays.append(delay)

    monkeypatch.setattr(app, "tts_chunk", request)
    monkeypatch.setattr(app.asyncio, "sleep", sleep)
    monkeypatch.setattr(app.random, "uniform", lambda a, b: 0)
    with pytest.raises(RuntimeError, match="after 2 attempts"):
        await app.tts_chunk_with_retry("t", "v", "+0%", "+0%", retries=2, base_backoff=2)
    assert len(attempts) == 2
    assert delays == [2]


@pytest.mark.asyncio
async def test_timeout_retries_and_cancel_propagates(monkeypatch):
    real_wait_for = asyncio.wait_for
    deadlines = []

    async def checked_wait_for(awaitable, *, timeout):
        deadlines.append(timeout)
        if timeout != 0.001:
            awaitable.close()
            raise AssertionError("per-attempt deadline must be forwarded")
        return await real_wait_for(awaitable, timeout=timeout)

    async def hanging(*args, **kwargs):
        await asyncio.Event().wait()

    monkeypatch.setattr(app, "tts_chunk", hanging)
    monkeypatch.setattr(app.asyncio, "wait_for", checked_wait_for)
    with pytest.raises(RuntimeError, match="after 1 attempts"):
        await app.tts_chunk_with_retry("t", "v", "+0%", "+0%", retries=1, timeout_s=0.001)
    assert deadlines == [0.001]

    async def cancelled(*args, **kwargs):
        raise asyncio.CancelledError()

    monkeypatch.setattr(app.asyncio, "wait_for", real_wait_for)
    monkeypatch.setattr(app, "tts_chunk", cancelled)
    with pytest.raises(asyncio.CancelledError):
        await app.tts_chunk_with_retry("t", "v", "+0%", "+0%")


@pytest.mark.asyncio
async def test_empty_speech_is_a_retryable_failure(monkeypatch):
    async def empty(*args, **kwargs):
        return b""

    monkeypatch.setattr(app, "tts_chunk", empty)
    with pytest.raises(RuntimeError, match="empty"):
        await app.tts_chunk_with_retry("t", "v", "+0%", "+0%", retries=1)


@pytest.mark.asyncio
async def test_real_audio_join_preserves_chunk_order_and_pauses(monkeypatch):
    clips = [Sine(440).to_audio_segment(duration=100), Sine(880).to_audio_segment(duration=200)]
    encoded = [clip.export(format="mp3").read() for clip in clips]
    texts = []

    async def request(text, **kwargs):
        texts.append(text)
        return encoded[len(texts) - 1]

    monkeypatch.setattr(app, "tts_chunk", request)
    audio = await app.synthesize_chunks(["first", "second"], "v")
    assert texts == ["first", "second"]
    assert len(audio) == 540
    assert audio[110:210].rms == 0
    assert audio[230:410].rms > 0
    assert audio[430:530].rms == 0
    assert len(AudioSegment.from_mp3(BytesIO(audio.export(format="mp3").read()))) == 540
    assert len(await app.synthesize_chunks([], "v")) == 0


@pytest.mark.asyncio
async def test_default_retry_budget_and_exponential_deadlines(monkeypatch):
    calls = []
    deadlines = []
    delays = []
    jitter_bounds = []

    async def fail(*args, **kwargs):
        calls.append(1)
        raise OSError("synthetic")

    async def wait_for(awaitable, *, timeout):
        deadlines.append(timeout)
        return await awaitable

    async def sleep(seconds):
        delays.append(seconds)

    def jitter(low, high):
        jitter_bounds.append((low, high))
        return 0

    monkeypatch.setattr(app, "tts_chunk", fail)
    monkeypatch.setattr(app.asyncio, "wait_for", wait_for)
    monkeypatch.setattr(app.asyncio, "sleep", sleep)
    monkeypatch.setattr(app.random, "uniform", jitter)
    with pytest.raises(RuntimeError, match="after 4 attempts"):
        await app.tts_chunk_with_retry("synthetic", "voice", "+0%", "+0%")
    assert len(calls) == 4
    assert deadlines == [120] * 4
    assert delays == pytest.approx([1.6, 2.56, 4.096])
    assert jitter_bounds == [(0, 0.5)] * 3
