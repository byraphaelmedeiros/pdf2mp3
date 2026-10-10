# PDF2MP3 — Listen to text-based PDFs

[![PyPI version](https://badge.fury.io/py/pdf2mp3.svg)](https://pypi.org/project/pdf2mp3/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://github.com/byraphaelmedeiros/pdf2mp3/blob/v2.0.1/LICENSE)
[![CI](https://github.com/byraphaelmedeiros/pdf2mp3/actions/workflows/ci.yml/badge.svg)](https://github.com/byraphaelmedeiros/pdf2mp3/actions)

PDF2MP3 is a Python command-line tool that turns the readable text in a PDF into
a single MP3 file. It extracts and cleans text locally, splits it into chunks,
requests speech from Microsoft's online voice service through `edge-tts`, and
joins the audio using `pydub` and FFmpeg.

Use it to listen to text-based documents in **English** or **Brazilian Portuguese**.
Reading order and pronunciation depend on the PDF's extracted text and the voice
service; complex layouts may need preparation before conversion.

> **Privacy:** the default voice engine sends extracted text chunks to an external
> Microsoft service for speech synthesis. The PDF itself is read locally by this
> tool, but the default conversion requires external processing. Progress does
> not include document snippets. Only use documents whose contents you are
> permitted and comfortable to send to the selected provider.

Version **2** introduces a redesigned CLI. The conversion and check examples
below require version 2. Version 1.0.0 uses `pdf2mp3 sample.pdf`, without
subcommands or JSON. See the
[CLI contract](https://github.com/byraphaelmedeiros/pdf2mp3/blob/v2.0.1/docs/cli.md) and [quality gates](https://github.com/byraphaelmedeiros/pdf2mp3/blob/v2.0.1/docs/quality-gates.md).

## Requirements

- **Python 3.10+.** The configured test matrix covers 3.10–3.14. Version 2
  includes a conditional audioop compatibility dependency for Python 3.13+.
  See [support details](https://github.com/byraphaelmedeiros/pdf2mp3/blob/v2.0.1/docs/support.md), including version 1.0.0's limits.
- **FFmpeg**, including `ffprobe`, must be available on your `PATH` for audio
  decoding and MP3 export. Installing the Python package does not install FFmpeg.
- **An internet connection** is required for the default Edge voice service.
  Availability of the service and individual voices can change.
- **A PDF containing extractable text.** Image-only scans require OCR beforehand.

## Install

### 1. Install FFmpeg

macOS with Homebrew:

```bash
brew install ffmpeg
```

Debian/Ubuntu:

```bash
sudo apt-get update
sudo apt-get install ffmpeg
```

Windows with winget:

```powershell
winget install --id=Gyan.FFmpeg -e
```

Open a new terminal if the installer updates your `PATH`, then check:

```text
ffmpeg -version
ffprobe -version
```

### 2. Create a Python 3.12 environment

macOS/Linux:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
```

Windows PowerShell:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
```

### 3. Install version 2

With the environment activated:

```bash
python -m pip install --upgrade pip
python -m pip install pdf2mp3==2.0.1
pdf2mp3 --version
pdf2mp3 --help
python -m pdf2mp3 --help
```

Both commands invoke the same CLI. The console command is installed through
`pyproject.toml`; module execution is provided by `pdf2mp3/__main__.py`.
Confirm that `--version` reports `2.0.1` before using these examples. Upgrading
from version 1 requires the new `convert`/`check` syntax. Follow the
[CLI migration contract](https://github.com/byraphaelmedeiros/pdf2mp3/blob/v2.0.1/docs/cli.md) when updating existing scripts.

If `pdf2mp3` is not found, activate the environment where you installed it or use
`python -m pdf2mp3` with that environment's Python interpreter.

## Convert a PDF

Start with a short document containing non-sensitive sample text. In the
activated environment, convert it using the Portuguese defaults:

```bash
pdf2mp3 convert "sample.pdf"
```

On success, this writes `sample.mp3` next to the input, using `pt-BR-ThalitaNeural`.
Choose English explicitly; the tool does not translate the document:

```bash
python -m pdf2mp3 convert "sample.pdf" --lang en
```

Choose an output location:

```bash
pdf2mp3 convert "sample.pdf" --output "audio/sample.mp3"
```

Adjust speaking rate, volume or chunk length:

```bash
pdf2mp3 convert "sample.pdf" --rate=+5% --volume=+0% --max-chars 1200
```

Negative percentages accept either `--rate -5%` or `--rate=-5%`.
An existing destination is refused unless you add `--overwrite`; there are no
interactive prompts. The input PDF and an existing destination are preserved
on failed export. Input/output collisions are always rejected. Choose distinct
output names when trying several examples on the same sample.

### Options for the default Edge workflow

| Argument | Purpose | Default |
| --- | --- | --- |
| `INPUT` after `convert` | Path to a PDF containing readable text | Required |
| `-o`, `--output` | Output MP3 path | Input path with `.mp3` extension |
| `-l`, `--lang` | `en` or `pt-br` | `pt-br` |
| `--voice` | Explicit Edge voice name | `en-US-AriaNeural` for English; `pt-BR-ThalitaNeural` for Portuguese |
| `--rate` | Speaking rate adjustment | `+0%` |
| `--volume` | Speaking volume adjustment | `+0%` |
| `--max-chars` | Chunk size before TTS sanitization; use a positive integer | `1600` |
| `--overwrite` | Explicitly allow destination replacement | Off |
| `--quiet` | Suppress progress, keep result and errors | Off |
| `--json` | One structured result on stdout, also on errors | Off |
| `-h`, `--help` | Display help (`convert --help` for provider options) | — |

Version 2 also provides optional gTTS, OpenAI, pyttsx3 and macOS `say` adapters. See
[provider installation and requirements](https://github.com/byraphaelmedeiros/pdf2mp3/blob/v2.0.1/docs/support.md) before using them.
Remote adapters send text to their respective services; OpenAI requires an API
key and may incur charges. Local adapters depend on installed system voices.
Automated adapter tests use synthetic responses and do not certify live voice availability.
The OpenAI adapter now uses Realtime with `gpt-realtime-2.1-mini`, receives PCM
and encodes MP3 locally. It rejects incomplete responses or changed narration
transcripts. See [OpenAI setup, limitations and migration](https://github.com/byraphaelmedeiros/pdf2mp3/blob/v2.0.1/docs/openai.md);
this integration has offline evidence, not live API validation.
The gTTS extra retains a Click version constraint and a
[historical, now withdrawn security advisory](https://github.com/byraphaelmedeiros/pdf2mp3/blob/v2.0.1/SECURITY.md#known-development-dependency-finding).
Current audits no longer report it; no dependency override or security exemption is used.
Use `convert --help` to inspect provider options. `--voice` selects Edge,
OpenAI or local voices; `--model` applies only to OpenAI. gTTS uses `--lang`.
Irrelevant provider options are rejected before processing. See
[the CLI contract](https://github.com/byraphaelmedeiros/pdf2mp3/blob/v2.0.1/docs/cli.md) for stable exit codes and migration details.

## Check before converting

```bash
pdf2mp3 check
pdf2mp3 check "sample.pdf" --engine edge --json
```

`check` verifies local requirements and optionally extracts/prepares a PDF. It
does not synthesize speech, contact voice services or write files. It reports
configuration, text/chunk counts and whether conversion would send text
externally. Passing this check does not establish remote voice availability or
valid credentials. `--json` works before or after either subcommand; progress
and diagnostics go to stderr. See the [CLI guide](https://github.com/byraphaelmedeiros/pdf2mp3/blob/v2.0.1/docs/cli.md).

## Limits and troubleshooting

- **Scanned PDFs:** PDF2MP3 does not perform OCR. Run a separate OCR tool first
  to add a text layer, then check that the text extracts correctly.
- **Document structure:** columns, tables, headers and footers may produce
  unexpected reading order. Text cleanup is heuristic; it does not reconstruct
  the visual layout or guarantee a faithful audiobook.
- **Remote speech:** the Edge path retries failed speech requests, but network
  problems, unavailable voices or service changes can still stop conversion.
  Local installation/help checks do not verify live speech availability.
- **Long documents:** audio is assembled in memory, so large documents can use
  substantial memory and take time to process. Try a short sample first.
- **Audio errors:** confirm `ffmpeg` and `ffprobe` are on `PATH`. For
  `audioop`/`pyaudioop` import errors, use a fresh Python 3.12 environment.
- **PDF parser security:** version 2.0 requires `pdfminer.six>=20251230`, raising
  the Python minimum to 3.10. Keep dependencies updated; the quality gate audits
  the resolved versions. Parsing a PDF is not a sandbox for untrusted files.

## Install from source

To install the release source, create and activate a separate Python 3.12
environment as above, then:

```bash
git clone --branch v2.0.1 https://github.com/byraphaelmedeiros/pdf2mp3.git
cd pdf2mp3
python -m pip install .
pdf2mp3 --help
python -m pdf2mp3 --help
```

`python -m pip install .` installs the package and its declared base dependencies.
The repository's requirement files now delegate to that same package metadata;
`requirements-dev.txt` also installs the pinned QA tools.
For contributor setup, see [CONTRIBUTING.md](https://github.com/byraphaelmedeiros/pdf2mp3/blob/v2.0.1/CONTRIBUTING.md).

### Try the synthetic demo

After installing the development requirements and activating `.venv-dev` as
described in CONTRIBUTING, generate a small text-based PDF:

```bash
python scripts/create_demo_pdf.py
pdf2mp3 check local/inputs/demo.pdf --json
pdf2mp3 convert local/inputs/demo.pdf --output local/outputs/demo-edge.mp3
```

The first command creates `local/inputs/demo.pdf` with synthetic Brazilian Portuguese text;
it refuses to replace an existing file. The conversion sends only this sample
text to the external Edge service. For an English sample, macOS offline speech
and Windows validation steps, see [the local demo guide](https://github.com/byraphaelmedeiros/pdf2mp3/blob/v2.0.1/docs/local-demo.md).
Generated demo PDFs and MP3s stay local and are ignored by Git.

## Project information

- [Documentation](https://github.com/byraphaelmedeiros/pdf2mp3/blob/v2.0.1/docs/README.md)
- [Python API reference](https://github.com/byraphaelmedeiros/pdf2mp3/blob/v2.0.1/docs/api.md)
- [Changelog](https://github.com/byraphaelmedeiros/pdf2mp3/blob/v2.0.1/CHANGELOG.md)
- [Contributing](https://github.com/byraphaelmedeiros/pdf2mp3/blob/v2.0.1/CONTRIBUTING.md) and [Code of Conduct](https://github.com/byraphaelmedeiros/pdf2mp3/blob/v2.0.1/CODE_OF_CONDUCT.md)
- [Security policy](https://github.com/byraphaelmedeiros/pdf2mp3/blob/v2.0.1/SECURITY.md): report vulnerabilities privately to
  **pdf2mp3@byraphaelmedeiros.com**.
- [MIT license](https://github.com/byraphaelmedeiros/pdf2mp3/blob/v2.0.1/LICENSE)

Maintained by [Raphael Medeiros](https://github.com/byraphaelmedeiros).
