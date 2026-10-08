#!/usr/bin/env python3
"""Exercise the installed OpenAI SDK with a synthetic transport and blocked network."""

import base64
import importlib.metadata
import json
import os
from io import BytesIO

from network_guard import block_network


def main():
    block_network()
    # This is an inert test value, never a provisioned or user credential.
    inert_value = "synthetic-offline-key"
    os.environ["OPENAI_API_KEY"] = inert_value
    os.environ.pop("OPENAI_BASE_URL", None)
    os.environ.pop("OPENAI_LOG", None)
    from openai.lib import _websocket
    from pydub import AudioSegment
    from pydub.generators import Sine

    import pdf2mp3.pdf2mp3 as app

    transports = []
    pcm = Sine(440, sample_rate=24000).to_audio_segment(duration=100).raw_data

    class Transport:
        def __init__(self):
            self.closed = False
            self.events = iter([])

        async def send(self, data):
            event = json.loads(data)
            assert event["type"] == "response.create"
            request = event["response"]
            assert request["conversation"] == "none" and request["output_modalities"] == ["audio"]
            assert request["audio"]["output"]["format"] == {"type": "audio/pcm", "rate": 24000}
            assert request["tools"] == [] and request["tool_choice"] == "none"
            text = request["input"][0]["content"][0]["text"]
            identifiers = {
                "response_id": "resp_synthetic",
                "item_id": "item_synthetic",
                "output_index": 0,
                "content_index": 0,
            }
            self.events = iter(
                [
                    {
                        "type": "response.output_audio.delta",
                        "event_id": "event_audio",
                        **identifiers,
                        "delta": base64.b64encode(pcm).decode(),
                    },
                    {
                        "type": "response.output_audio_transcript.done",
                        "event_id": "event_transcript",
                        **identifiers,
                        "transcript": text,
                    },
                    {
                        "type": "response.done",
                        "event_id": "event_done",
                        "response": {
                            "id": "resp_synthetic",
                            "object": "realtime.response",
                            "status": "completed",
                            "status_details": None,
                            "output": [
                                {
                                    "id": "item_synthetic",
                                    "object": "realtime.item",
                                    "type": "message",
                                    "role": "assistant",
                                    "status": "completed",
                                    "content": [{"type": "audio", "transcript": text}],
                                }
                            ],
                            "conversation_id": None,
                            "output_modalities": ["audio"],
                            "audio": request["audio"],
                            "usage": None,
                        },
                    },
                ]
            )

        async def recv(self, **kwargs):
            return json.dumps(next(self.events)).encode()

        async def close(self, **kwargs):
            self.closed = True

    async def connect(url, **kwargs):
        assert url == "wss://api.openai.com/v1/realtime?model=gpt-realtime-2.1-mini"
        assert kwargs["additional_headers"]["Authorization"] == "Bearer synthetic-offline-key"
        transport = Transport()
        transports.append(transport)
        return transport

    # Replace only the external transport; SDK serialization/parsing remains real.
    _websocket._WebSocketConnect = connect
    for text in ("Synthetic English narration.", "Narração sintética em português. 42."):
        data = app.tts_chunk_openai(text, "gpt-realtime-2.1-mini", "alloy")
        audio = AudioSegment.from_mp3(BytesIO(data))
        assert 95 <= len(audio) <= 105 and audio.rms > 0
        assert audio.frame_rate == 24000 and audio.channels == 1
    assert len(transports) == 2 and all(transport.closed for transport in transports)
    print(
        json.dumps(
            {
                "ok": True,
                "sdk_version": importlib.metadata.version("openai"),
                "network": "blocked",
                "cases": 2,
                "live_api_verified": False,
            }
        )
    )


if __name__ == "__main__":
    main()
