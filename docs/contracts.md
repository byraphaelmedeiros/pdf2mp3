# Architecture and compatibility contracts

`pdf2mp3/__init__.py` exports seven callable helpers. `pdf2mp3` and
`python -m pdf2mp3` both call `pdf2mp3.pdf2mp3.main`. The exported entry point delegates to `pdf2mp3/cli.py` for parsing, validation
and presentation. PDF extraction, provider adapters and audio assembly stay in
`pdf2mp3/pdf2mp3.py`; deterministic text
processing lives in `pdf2mp3/text.py` and remains re-exported at the old paths.
The [Python API reference](api.md) documents signatures, exceptions and effects.

The default pipeline is local PDF extraction → heuristic text cleanup → chunks
→ minimal TTS sanitation → remote Edge speech → local MP3 decode/assembly/export.
The PDF is read locally; extracted text is transmitted to the selected remote
provider. Progress omits document text. Tests use synthetic content only.

## Preserved behavior

- Default language `pt-br`, default engine `edge`, maximum chunk size 1600.
- Default voices `pt-BR-ThalitaNeural` and `en-US-AriaNeural`; rate/volume `+0%`.
- Existing language aliases, cleanup rules and public function names; retries
  remain asynchronous. Text tests use literal expected results and generated
  invariants rather than remote waveform snapshots.
- Audio chunks keep input order and a 120 ms silence after each chunk, including
  the last. Cleanup can discard repeated short lines; it is heuristic, not OCR.
- The default output replaces the input suffix with `.mp3`. Explicit output
  directories are created. Existing MP3 output requires explicit `--overwrite`.

## Intentional 2.0 changes

Python 3.9 is no longer supported. The minimum is 3.10 so the package can require
`pdfminer.six>=20251230`. Python 3.13+ receives `audioop-lts` for pydub compatibility.

The CLI rejects output paths resolving to the input, including existing symlinks
and hardlinks, and rejects nonpositive chunk sizes. Extraction/export failures
have defined errors. Final output is written to a sibling temporary file and
replaced only after successful export and, unless overwrite is authorized,
exclusive destination reservation; an existing destination survives failed
export or interruption. This is not a defense against an adversary changing
filesystem links concurrently.

Retry exhaustion no longer sleeps after the final failure. Empty speech bytes
are retryable failures. Literal `<PARA_BREAK>` text is preserved. Public chunking
raises `ValueError` for nonpositive sizes instead of depending on an incidental
range error or producing invalid chunks.

The macOS `say` adapter rejects a decoded AIFF with no audio samples, even if
the system command returned success. This can happen when system speech access
is blocked. It exits at the speech stage (code 5), cleans the temporary AIFF and
preserves the input and existing destination rather than exporting only a pause.

| Exit | Meaning |
| --- | --- |
| 0 | Completed or help displayed |
| 1 | Input file missing or not a regular file |
| 2 | Invalid CLI arguments/language, input-output collision, or overwrite refusal, or missing local prerequisites |
| 3 | No extractable text; an image-only PDF needs separate OCR |
| 4 | No content after cleanup |
| 5 | Speech synthesis failed |
| 6 | PDF extraction failed, including corrupt/encrypted input |
| 7 | Output creation/export failed |
| 130 | User interrupted extraction, synthesis or export |

`--debug` preserves structured errors and adds safe exception types and stack
locations on stderr, without exception values or document content. Cancellation
returns 130. See [CLI v2](cli.md) for JSON schema, stable identifiers, no-write
preflight and intentional syntax changes; old flat CLI aliases are removed.

## Optional providers

The base package imports without provider extras. `gtts`, `openai` and `pyttsx3`
extras declare their dependencies; the PyObjC dependency is macOS-only. `say`
uses the macOS executable. Edge/gTTS/OpenAI require network access; OpenAI also
requires credentials and may incur charges. pyttsx3 and say depend on installed
system voices. Their request parameters, adapter errors and cleanup are tested
offline; that does not certify actual provider/system voice availability.

`--rate` and `--volume` apply only to Edge. `--voice` selects Edge, OpenAI or
local voices; `--model` is OpenAI-only. gTTS uses `--lang` (Portuguese maps to
`pt`). Explicitly unavailable local voices fail instead of silently falling back. `--lang` does not
translate text. Edge and OpenAI Realtime use asynchronous network IO internally;
their CLI paths still complete one chunk at a time. The project does not promise
parallel conversion, streaming output or bounded memory for books.

OpenAI now uses `gpt-realtime-2.1-mini` with independent Realtime responses,
24 kHz mono PCM and local MP3 encoding. It requires completed audio and a matching
output transcript, has a 120-second request deadline and does not automatically
retry. See [OpenAI narration](openai.md) for accepted options, fidelity limits,
privacy, potential charges and the official deprecation that prompted migration.
