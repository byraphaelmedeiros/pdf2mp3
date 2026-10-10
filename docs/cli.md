# CLI v2 contract

This interface belongs to version `2.0.1`. Install it with
`python -m pip install pdf2mp3==2.0.1`, or install a source checkout with
`python -m pip install .`. Version 1.0.0 uses the previous flat CLI.
Both `pdf2mp3` and `python -m pdf2mp3` identify themselves as `pdf2mp3` and expose
identical help. No arguments prints help and exits 0. `--version` prints the
version. Help and version remain text even when `--json` is present.

```bash
pdf2mp3 convert local/inputs/demo.pdf --output local/outputs/demo-edge.mp3
python -m pdf2mp3 convert local/inputs/demo.pdf --rate -5% --volume=-10% --output local/outputs/demo-adjusted.mp3
pdf2mp3 convert local/inputs/demo.pdf --output local/outputs/demo-edge.mp3 --overwrite --quiet
pdf2mp3 check
pdf2mp3 check local/inputs/demo.pdf --engine edge --json
pdf2mp3 --json convert local/inputs/demo.pdf --output local/outputs/demo-json.mp3
```

## Preparation and provider options

`convert INPUT` extracts selectable text, cleans and chunks it, synthesizes
speech, and saves MP3. `check [INPUT]` inspects local requirements and optionally
performs the same text preparation and destination validation. It does not
synthesize, contact a service, create output directories or write files.

| Option | Scope | Default / meaning |
| --- | --- | --- |
| `--engine` | Both commands | `edge`; alternatives: `gtts`, `openai`, `pyttsx3`, `say` |
| `-l`, `--lang` | Both | `pt-br` or `en`; documented language aliases are normalized; no translation |
| `--max-chars` | Both | Positive integer, `1600`; applied before final TTS sanitation |
| `--voice` | Edge, OpenAI, local engines | Edge: `pt-BR-ThalitaNeural` or `en-US-AriaNeural`; OpenAI: `alloy`; local: system default |
| `--model` | OpenAI Realtime only | `gpt-realtime-2.1-mini` |
| `--rate`, `--volume` | Edge only | Signed integer percentages, both `+0%`; `--rate -5%` and `--rate=-5%` work |
| `-o`, `--output` | With INPUT | Input suffix changed to `.mp3` |
| `--overwrite` | With INPUT | Explicitly permit replacing an existing file; no interactive prompts |
| `--json` | Before or after command | One JSON object on stdout; see below |
| `--quiet` | Before or after command | Suppress progress, preserve result/errors and retry warnings |
| `--debug` | Before or after command | Safe exception types and stack locations on stderr; same exit/result contract |

Incompatible options fail before extraction or remote processing, even if the
supplied value equals a default. Long options cannot be abbreviated. The old
flat conversion syntax and `--say-voice`, `--gtts-lang`, `--openai-model` and
`--openai-voice` are removed; use subcommands and the unified options above.
gTTS maps Portuguese to its service language `pt` and English to `en`.

`check` verifies executable/module presence and OpenAI key presence; it never
returns credentials. For `say`, it can inspect the local voice inventory without
speech. It cannot verify remote voices, connectivity, credentials' validity,
service quotas, installed drivers' usability or speech quality. pyttsx3 voice
selection is verified during synthesis; exact installed names or IDs are
required. An explicitly missing local voice fails instead of silently falling
back. OpenAI accepts Realtime model names and the built-in voices listed in
[OpenAI narration](openai.md); current remote availability still needs service
validation. Legacy Speech API settings fail locally. Edge voice IDs must have
the expected neural voice format.

## Output and failure safety

Successful conversion prints a result on stdout. Progress and diagnostics use
stderr and omit document snippets. `--quiet` keeps the final result. JSON mode
keeps stdout exclusively for its result, including parsing errors.

An existing destination is refused with exit 2 unless `--overwrite` is provided.
Aliases of the input PDF are always rejected. Audio is fully exported to a
sibling temporary file before committing it. Without `--overwrite`, final
commit reserves the destination exclusively: a file created since validation
is preserved and conversion returns exit 2. Reservation handles are closed
before replacement for Windows; failed commits clean their owned reservation
and temporary file. Authorized replacement leaves the previous file intact
until successful export. These protections do not make arbitrary filesystem
changes by an adversary safe. The input PDF is never modified.

## JSON schema version 1

Every `convert`/`check` JSON response has exactly these top-level keys:

```json
{
  "schema_version": 1,
  "command": "check",
  "ok": true,
  "data": {
    "input": "/absolute/demo.pdf",
    "output": "/absolute/demo.mp3",
    "engine": "edge",
    "language": "pt-br",
    "voice": "pt-BR-ThalitaNeural",
    "model": null,
    "rate": "+0%",
    "volume": "+0%",
    "max_chars": 1600,
    "external_processing": true,
    "chunks": 1,
    "characters": 80,
    "checks": [{"name": "ffmpeg", "ok": true}, {"name": "ffprobe", "ok": true}],
    "speech_verified": false
  },
  "error": null
}
```

Counts above are illustrative. Paths are absolute. Without INPUT, paths are
null and counts are zero. Conversion uses the same configuration/preparation
fields, plus `duration_seconds` (assembled audio duration before MP3 encoding),
and omits `checks`/`speech_verified`. `external_processing` states whether the
selected engine would transmit text during conversion, not whether `check`
transmitted anything. Local engine voice is null when using the system default.

Failures set `ok` false and `error` to `code`, safe `message` and `exit_code`.
`data` is normally null; missing dependencies may return partial configuration
and checks. `command` can be null when no valid command could be parsed.
Consumers must use stable codes and exit status rather than matching messages;
tolerate additional data fields in future schema-compatible changes.

| Exit | Error code | Meaning |
| --- | --- | --- |
| 0 | — | Success, help or version |
| 1 | `input_missing` | Missing input or nonregular file |
| 2 | `invalid_arguments`, `output_exists`, `dependency_missing` | Parsing/configuration/path error, overwrite refusal or local prerequisite missing |
| 3 | `no_text` | No selectable text; perform OCR separately |
| 4 | `empty_text` | Text preparation leaves no content |
| 5 | `speech_failed` | Speech/provider failure, including missing local voice or empty local audio |
| 6 | `pdf_failed` | Invalid, encrypted or unreadable PDF |
| 7 | `output_failed` | Export/filesystem failure |
| 130 | `interrupted` | Cancellation before completion |

## Automation example

Use subprocess argument arrays, inspect both JSON and exit status, and select an
explicit destination. Run `check` before authorizing external text processing.

```python
import json
import subprocess

result = subprocess.run(
    ["pdf2mp3", "check", "local/inputs/demo.pdf", "--engine", "edge", "--json"],
    capture_output=True,
    text=True,
    timeout=30,
)
report = json.loads(result.stdout)
if result.returncode != 0 or not report["ok"]:
    raise RuntimeError(report["error"]["code"])
# external_processing=True requires a deliberate decision about the text.
```

Runtime requirements and provider costs are in [support](support.md). Scanned
PDFs require separate OCR; cleanup does not reconstruct complex layouts.
Remote providers need Internet access and send extracted text externally.
Use synthetic content for tests; never include private text in logs or bug reports.
See the [security policy](../SECURITY.md) for the gTTS dependency constraint and
historical advisory status.
