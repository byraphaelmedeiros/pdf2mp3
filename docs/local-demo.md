# Synthetic local demo

This guide applies to a `2.0.1` source checkout with development dependencies.
Use only the generated synthetic samples. Existing personal PDFs in a checkout
are not test fixtures. The commands below create local samples and run checks.

## Prepare the environment

Install Python 3.12, FFmpeg and ffprobe. On macOS with Homebrew:

```bash
brew install python@3.12 ffmpeg
python3.12 -m venv .venv-dev
source .venv-dev/bin/activate
python -m pip install --upgrade 'pip>=26.2'
python -m pip install -r requirements-dev.txt
python -m pip check
pdf2mp3 --help
pdf2mp3 --version
pdf2mp3 convert --help
python -m pdf2mp3 --help
ffmpeg -version
ffprobe -version
```

Run these commands from the repository root. `.venv-dev` is an isolated,
editable development installation; it does not replace an older `.venv`.
The QA tools, including ReportLab for sample creation, are development
dependencies. They are not needed to convert an existing PDF with the base
package. The development setup does not install the optional voice extras.

## Create the samples

```bash
python scripts/create_demo_pdf.py
python scripts/create_demo_pdf.py --lang en --output local/inputs/demo-en.pdf
```

`local/inputs/demo.pdf` contains Brazilian Portuguese; `local/inputs/demo-en.pdf`
contains English. Both are one-page PDFs with extractable synthetic text,
including Portuguese accents.
They use the same ReportLab approach as the existing temporary test fixtures.
The generator is also used for the wheel/sdist installation checks.

Creation refuses to overwrite an existing file. If a sample already exists,
reuse it or select a new `--output` path. Only the generator and tests are source files.

The generator creates parent directories and defaults to `local/inputs/demo.pdf`.
Keep manual PDFs in `local/inputs/` and audio or other results in `local/outputs/`.
The entire `local/` directory is ignored by Git and excluded from wheel/sdist,
including text, WAV and AIFF files. It is storage, not an automated-test fixture
directory. Tests use temporary synthetic files; QA evidence remains in `.quality/`.
Never substitute private documents for the generated samples in test commands.
Conversion still defaults to an MP3 beside its input; the examples use explicit
`--output` paths to keep results separate.

## Run the offline suite

```bash
python -m pytest -q tests/test_demo.py
python scripts/quality.py fast --base v1.0.0
python scripts/quality.py standard --base v1.0.0
```

The demo tests extract the actual PDF, verify language/voice arguments, produce
and decode MP3 through FFmpeg, and check that input bytes are unchanged. Speech
is replaced only at the provider boundary, using a synthetic tone. All ordinary
tests block unexpected network access. These tests do not produce spoken audio
or prove that an external voice service is available.

The standard profile additionally builds and installs wheel/sdist artifacts
outside the checkout and audits dependencies. It downloads packages and queries
advisory services, but does not call speech services. The
[gTTS/Click security note](../SECURITY.md#known-development-dependency-finding)
preserves the earlier finding and explains its upstream withdrawal. Current
audits no longer report it; no dependency override or security waiver is used.

## Opt-in real speech on macOS

The following commands actually synthesize speech. Edge sends the extracted
sample text to Microsoft and needs an internet connection. Do not substitute a
private PDF. No OpenAI key or paid provider is used by these examples.

```bash
pdf2mp3 check local/inputs/demo.pdf --json
pdf2mp3 convert local/inputs/demo.pdf --output local/outputs/demo-edge.mp3
python -m pdf2mp3 convert local/inputs/demo-en.pdf --lang en --output local/outputs/demo-edge-en.mp3
```

For speech using macOS system voices, inspect the available names first:

```bash
say -v '?'
pdf2mp3 convert local/inputs/demo.pdf --engine say --voice 'Luciana (Portuguese (Brazil))' --output local/outputs/demo-say.mp3
python -m pdf2mp3 convert local/inputs/demo-en.pdf --lang en --engine say --voice 'Samantha (English (US))' --output local/outputs/demo-say-en.mp3
```

Use the exact voice names present on your Mac. Install missing voices through
macOS settings before trying them. Once the voice is installed, `say` uses the
local speech engine; this adapter does not submit text to a remote TTS service.
`--lang` does not choose or download a `say` voice: select it with `--voice`.
The `say` adapter does not implement the Edge `--rate`/`--volume` adjustments.
Restricted execution environments can prevent access to the macOS speech
service even when `say` returns success. The adapter rejects an empty AIFF
instead of producing a silent MP3; run these checks in a normal local terminal
with speech access.

Inspect the output and listen:

```bash
ffprobe -v error -show_entries format=duration:stream=codec_name,sample_rate,channels -of json local/outputs/demo-edge.mp3
ffmpeg -v error -i local/outputs/demo-edge.mp3 -f null -
afplay local/outputs/demo-edge.mp3
afplay local/outputs/demo-say.mp3
```

Expect MP3 audio with positive duration, successful full decoding and audible
narration. Repeat inspection for other generated MP3s. File validity and signal
checks do not establish pronunciation quality; listen to both language samples.
External service availability and waveforms can change, so do not compare
remote MP3 bytes to a permanent snapshot. Existing output files require explicit `--overwrite` to be replaced. Repeat
conversions with that flag only when replacement is intended; otherwise choose
a distinct output name. JSON conversion works with `--json`, and `check` does
not prove speech availability or write any output.

## Windows validation to run separately

A macOS run cannot certify Windows speech or installation. On a Windows
checkout of the same source, install Python 3.12 and FFmpeg/ffprobe on `PATH`.
In PowerShell:

```powershell
py -3.12 -m venv .venv-dev
.venv-dev\Scripts\Activate.ps1
python -m pip install --upgrade 'pip>=26.2'
python -m pip install -r requirements-dev.txt
python -m pip check
ffmpeg -version
ffprobe -version
pdf2mp3 --help
pdf2mp3 --version
pdf2mp3 convert --help
python -m pdf2mp3 --help
python -m pytest -q
python scripts/quality.py standard --base v1.0.0
python scripts/create_demo_pdf.py
python scripts/create_demo_pdf.py --lang en --output local/inputs/demo-en.pdf
$before = (Get-FileHash local/inputs/demo.pdf -Algorithm SHA256).Hash
pdf2mp3 check local/inputs/demo.pdf --json
pdf2mp3 convert local/inputs/demo.pdf --output local/outputs/demo-edge.mp3
python -m pdf2mp3 convert local/inputs/demo-en.pdf --lang en --output local/outputs/demo-edge-en.mp3
if ($before -ne (Get-FileHash local/inputs/demo.pdf -Algorithm SHA256).Hash) { throw 'Input PDF changed' }
ffprobe -v error -show_entries format=duration:stream=codec_name,sample_rate,channels -of json local/outputs/demo-edge.mp3
ffmpeg -v error -i local/outputs/demo-edge.mp3 -f null -
Start-Process local/outputs/demo-edge.mp3
```

Reuse already-generated samples if present. Also verify `--json` success/failure,
`--rate -5%`, overwrite refusal (exit 2), authorized replacement and interruption
cleanup on Windows; run `python scripts/package_check.py .quality/windows-package`
to check fresh wheel/sdist installs and both entry points outside the checkout. Run decoding/playback for the English
output as well. Record each command's exit code, Python/FFmpeg versions and the
test result. Expect conversion exit code 0, positive MP3 duration and unchanged
input hash. Help and offline tests do not substitute for the two real speech
checks. Do not run the macOS-only `say` commands on Windows. Optional Windows
speech engines need their own installation and validation.

The CI matrix remains separate evidence; local checks do not prove that GitHub
Actions ran or that any version was published.
