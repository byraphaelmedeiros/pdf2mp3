# OpenAI narration in 2.0

The optional OpenAI adapter uses the **Realtime API over WebSocket** with
`gpt-realtime-2.1-mini` by default. It preserves the `alloy` voice default and
produces a single MP3 through local FFmpeg processing. Edge remains the default
engine. This adapter is part of the optional `2.0.0` package integration,
not the published 1.0.0 workflow.

## Installation and use

Install the provider extra:

```bash
python -m pip install 'pdf2mp3[openai]==2.0.0'
pdf2mp3 convert --help
pdf2mp3 check --engine openai --json
```

Python 3.10+ and FFmpeg/ffprobe on PATH are required. The extra installs
`openai[realtime]>=3.26.1,<4`, including the SDK's WebSocket dependency.
The base installation does not require OpenAI or WebSockets. The SDK and
transitive dependencies are covered by the same dependency and license gates.

Actual conversion requires an `OPENAI_API_KEY` in the process environment,
an API account with access to the selected model, and Internet access allowing
secure WebSocket connections to OpenAI. Keep credentials out of Git and logs.
An existing API key is not a guarantee of model access, quota or available credit.

With those requirements already configured, examples are:

```bash
pdf2mp3 convert local/inputs/demo.pdf --engine openai --output local/outputs/demo-openai.mp3
python -m pdf2mp3 convert local/inputs/demo-en.pdf --engine openai --lang en --voice coral --output local/outputs/demo-openai-en.mp3 --json
pdf2mp3 convert local/inputs/demo.pdf --engine openai --model gpt-realtime-2.1 --voice alloy --output local/outputs/demo-openai-large.mp3
```

The CLI accepts model names beginning with `gpt-realtime`; their actual
availability is determined by the service. Built-in voices accepted by this
adapter are `alloy`, `ash`, `ballad`, `coral`, `echo`, `sage`, `shimmer`, `verse`,
`marin` and `cedar`. Custom voice objects are not supported by the CLI.
Legacy Speech API models and unsupported voices fail validation before PDF
extraction or service use. `--rate` and `--volume` remain Edge-only.

`check` verifies local executable/module presence, including `websockets`, and
whether a key is configured. It does not import/start the SDK, connect, synthesize
or write files. It cannot validate the key, remote model/voice access or billing.

## Narration contract and limitations

Each prepared text chunk gets an independent, out-of-band Realtime response with
no conversation history or tools. Only text is submitted: the adapter does not
record a microphone or upload the PDF. It requests literal narration in the
original language rather than a response, translation or summary.

The service streams mono signed 16-bit PCM at 24 kHz. The adapter accepts only a
completed response with nonempty, sample-aligned audio and a matching output
transcript. Comparison ignores case, punctuation and whitespace, but preserves
word order and spelling. Missing, added or changed words cause synthesis failure
(exit 5 / `speech_failed`), rather than a successful partial MP3. Verbalized
numbers or abbreviations can therefore cause refusal even when the pronunciation
sounds reasonable. Neither a matching provider transcript nor offline tests
prove that every spoken sample faithfully matches the document; listen before
relying on the narration. This is a generative model, not a deterministic reader.

Connection/request/response work has a 120-second deadline per chunk; transport
cleanup may take additional time. There are no automatic application retries or
SDK reconnect callbacks. Failure or cancellation closes the connection and client
and preserves the input PDF and previous destination. Existing chunk order and
the 120 ms pause after each chunk are retained. MP3 encoding and final export
remain local; the application still assembles audio in memory.

OpenAI receives extracted text and API use may incur charges, including requests
whose output is later rejected or a conversion cancelled after work has started.
Present shared OpenAI narration as AI-generated speech, not a human recording.
Use only synthetic text for development checks and opt-in service tests.

## Migration and evidence

Official documentation checked on **2026-10-08** still describes
`POST /v1/audio/speech`, but the
[deprecation notice](https://developers.openai.com/api/docs/deprecations#2026-10-01-text-to-speech-models)
announces retirement of `tts-1`, `tts-1-hd` and the listed GPT-4o Mini TTS snapshots
on **2027-01-06**, recommending `gpt-realtime-2.1-mini`. The previous
`gpt-4o-mini-tts` default points to the
[2025-12-15 snapshot](https://developers.openai.com/api/docs/models/gpt-4o-mini-tts).
This adapter migrates the protocol as well as the model; changing
only `--model` on the old Speech API call would not implement that migration.

The implementation follows the
[Realtime model reference](https://developers.openai.com/api/docs/models/gpt-realtime-2.1-mini),
[WebSocket guide](https://developers.openai.com/api/docs/guides/voice-websockets?api=realtime)
and [out-of-band response/audio contracts](https://developers.openai.com/api/docs/guides/realtime-conversations).

Normal tests use synthetic events with network sockets blocked. The standard
quality profile also tests the installed SDK's real serialization/parsing and
real FFmpeg encode/decode with a synthetic transport and inert test credential.
This proves local protocol integration, not a successful API handshake, current
account access, provider behavior, voice quality or native Windows execution.
Live validation is separate, opt-in, potentially billable and was not performed
for this migration.
